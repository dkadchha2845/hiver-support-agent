"""Build the golden-set sampling frame, then hold the hand-written labels.

Design (see DECISIONS.md #5-#7):
  * The frame is a *stratified* sample of the held-out pool, not a uniform one.
    A uniform 200 from this inbox contains ~4 security cases and ~0 legal ones,
    so it cannot measure the escalation behaviour that matters most.
  * Every unit therefore carries an exact inverse-probability `weight`, which
    lets the harness report both the on-sample number and a population estimate.
  * Labelling is done on the customer message + earlier turns ONLY. The reply the
    brand actually sent is withheld from the annotator so that the gold routing
    label stays independent of the brand's own DM behaviour, which is later used
    as a separate weak baseline.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter

from config import BRAND, GOLDEN, PROCESSED, SEED

# Keyword buckets define the strata. Order matters: first match wins, so the
# partition is exact and the weights are exact.
BUCKETS: list[tuple[str, re.Pattern]] = [
    (
        "safety_legal",
        re.compile(
            r"\b(lawyer|solicitor|sue|suing|small claims|gdpr|data request|"
            r"ombudsman|regulator|trading standards|fraud|police|journalist|"
            r"bbc|watchdog|press)\b",
            re.I,
        ),
    ),
    (
        "security",
        re.compile(
            r"\b(hack|hacked|hacking|compromis\w*|breach|pastebin|leak\w*|"
            r"someone else (is )?(using|listening|on)|stolen|phish\w*|"
            r"2fa|two.factor|reset my password|can'?t log ?in|cannot log ?in|"
            r"locked out)\b",
            re.I,
        ),
    ),
    (
        "money",
        re.compile(
            r"(\brefund\w*|\bcharge[drs]?\b|\bcharging\b|\bbilled?\b|\bbilling\b|"
            r"\binvoice\b|\bdouble ?charg\w*|\bpayment\b|\bpaid\b|\bdebit\b|"
            r"\bcredit card\b|[£$€]\s?\d)",
            re.I,
        ),
    ),
    (
        "churn_human",
        re.compile(
            r"\b(cancel\w*|unsubscrib\w*|deleting my account|delete my account|"
            r"switch(ing)? to (apple|deezer|tidal|youtube|google)|goodbye|"
            r"speak to (a|an) (human|person|manager|agent)|real person|"
            r"talk to someone|escalate)\b",
            re.I,
        ),
    ),
    (
        "non_english",
        re.compile(
            r"\b(por favor|gracias|bonjour|merci|danke|bitte|hallo ich|"
            r"ich habe|no puedo|não|obrigado|grazie|per favore|mohon|tolong|"
            r"terima kasih|saya|tidak|kenapa|nie mogę|dziękuję|спасибо|"
            r"пожалуйста|ayuda)\b",
            re.I,
        ),
    ),
    (
        "vague_short",
        re.compile(r"^.{0,40}$"),
    ),
]

# How many to draw from each stratum.
QUOTA = {
    "general": 120,
    "safety_legal": 10,
    "security": 16,
    "money": 18,
    "churn_human": 16,
    "non_english": 10,
    "vague_short": 10,
}


def stratum_of(unit: dict) -> str:
    text = unit["customer_message"]
    for name, pat in BUCKETS:
        if pat.search(text):
            return name
    return "general"


def cmd_sample(args: argparse.Namespace) -> None:
    brand = args.brand or BRAND
    pool = [
        json.loads(line)
        for line in (PROCESSED / f"{brand}_units_pool.jsonl").open()
    ]
    # de-duplicate near-identical customer messages so the frame isn't padded
    # with bot-like repeats
    seen: set[str] = set()
    deduped = []
    for u in pool:
        key = re.sub(r"\W+", " ", u["customer_message"].lower()).strip()[:120]
        if key in seen or len(u["customer_message"]) < 8:
            continue
        seen.add(key)
        deduped.append(u)

    by_stratum: dict[str, list[dict]] = {}
    for u in deduped:
        by_stratum.setdefault(stratum_of(u), []).append(u)

    rng = random.Random(SEED)
    rows: list[dict] = []
    frame_report = {}
    for stratum, quota in QUOTA.items():
        members = by_stratum.get(stratum, [])
        take = min(quota, len(members))
        chosen = rng.sample(members, take) if take else []
        weight = len(members) / take if take else 0.0
        frame_report[stratum] = {
            "population": len(members),
            "sampled": take,
            "weight": round(weight, 3),
        }
        for u in chosen:
            rows.append(
                {
                    "unit_id": u["unit_id"],
                    "conversation_id": u["conversation_id"],
                    "stratum": stratum,
                    "weight": round(weight, 4),
                    "position": u["position"],
                    "context": u["context"],
                    "customer_message": u["customer_message"],
                    # withheld from the annotator, kept for the weak DM baseline
                    "_brand_reply": u["brand_reply"],
                    "_brand_asked_for_dm": u["brand_asked_for_dm"],
                }
            )
    rng.shuffle(rows)
    out = GOLDEN / "frame.jsonl"
    with out.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    (GOLDEN / "frame_report.json").write_text(
        json.dumps(
            {
                "brand": brand,
                "pool_units": len(pool),
                "pool_deduped": len(deduped),
                "n_frame": len(rows),
                "seed": SEED,
                "strata": frame_report,
            },
            indent=2,
        )
    )
    print(json.dumps(frame_report, indent=2))
    print(f"frame: {len(rows)} units -> {out}")


def cmd_show(args: argparse.Namespace) -> None:
    """Print an unlabelled batch for hand-labelling (annotator view)."""
    rows = [json.loads(l) for l in (GOLDEN / "frame.jsonl").open()]
    batch = rows[args.start : args.start + args.n]
    for i, r in enumerate(batch, start=args.start):
        ctx = (
            " | ".join(
                f"{'C' if t['role']=='customer' else 'B'}: {t['text']}"
                for t in r["context"]
            )
            or "-"
        )
        print(f"[{i}] {r['unit_id']}  stratum={r['stratum']} pos={r['position']}")
        if r["context"]:
            print(f"    ctx: {ctx[:400]}")
        print(f"    MSG: {r['customer_message'][:420]}")


def cmd_verify(args: argparse.Namespace) -> None:
    import taxonomy

    frame = {json.loads(l)["unit_id"]: json.loads(l) for l in (GOLDEN / "frame.jsonl").open()}
    labels = [json.loads(l) for l in (GOLDEN / "labels.jsonl").open()]
    valid = set(taxonomy.intent_names())
    signal_keys = {s["key"] for s in taxonomy.risk_signals()} | {"none"}
    problems = []
    ids = set()
    for row in labels:
        uid = row["unit_id"]
        if uid in ids:
            problems.append(f"duplicate {uid}")
        ids.add(uid)
        if uid not in frame:
            problems.append(f"not in frame: {uid}")
        if row["gold_intent"] not in valid:
            problems.append(f"bad intent {row['gold_intent']} on {uid}")
        if row.get("gold_intent_alt") and row["gold_intent_alt"] not in valid:
            problems.append(f"bad alt intent on {uid}")
        if row["gold_route"] not in {"auto", "escalate"}:
            problems.append(f"bad route on {uid}")
        if row.get("gold_driver", "none") not in signal_keys:
            problems.append(f"bad driver {row.get('gold_driver')} on {uid}")
        if row["gold_route"] == "escalate" and row.get("gold_driver", "none") == "none":
            problems.append(f"escalate without driver on {uid}")
    missing = set(frame) - ids
    print(f"labelled {len(ids)}/{len(frame)}; missing {len(missing)}")
    print("intents:", Counter(r["gold_intent"] for r in labels).most_common())
    print("routes :", Counter(r["gold_route"] for r in labels).most_common())
    print("drivers:", Counter(r.get("gold_driver", "none") for r in labels).most_common())
    if problems:
        print("PROBLEMS:")
        for p in problems[:40]:
            print(" -", p)
    else:
        print("no schema problems")
    if missing and args.list_missing:
        print("missing ids:", sorted(missing)[:50])


def cmd_build(args: argparse.Namespace) -> None:
    """Join frame + labels into the final golden_set.jsonl."""
    frame = {}
    for line in (GOLDEN / "frame.jsonl").open():
        r = json.loads(line)
        frame[r["unit_id"]] = r
    out = []
    for line in (GOLDEN / "labels.jsonl").open():
        lab = json.loads(line)
        f = frame[lab["unit_id"]]
        out.append(
            {
                "unit_id": f["unit_id"],
                "conversation_id": f["conversation_id"],
                "stratum": f["stratum"],
                "weight": f["weight"],
                "position": f["position"],
                "context": f["context"],
                "customer_message": f["customer_message"],
                "brand_reply": f["_brand_reply"],
                "brand_asked_for_dm": f["_brand_asked_for_dm"],
                "gold_intent": lab["gold_intent"],
                "gold_intent_alt": lab.get("gold_intent_alt") or None,
                "gold_route": lab["gold_route"],
                "gold_driver": lab.get("gold_driver", "none"),
                "hard": bool(lab.get("hard", False)),
                "note": lab.get("note", ""),
            }
        )
    path = GOLDEN / "golden_set.jsonl"
    with path.open("w") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} -> {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--brand", default=None)
    s.set_defaults(func=cmd_sample)
    sh = sub.add_parser("show")
    sh.add_argument("--start", type=int, default=0)
    sh.add_argument("--n", type=int, default=25)
    sh.set_defaults(func=cmd_show)
    v = sub.add_parser("verify")
    v.add_argument("--list-missing", action="store_true")
    v.set_defaults(func=cmd_verify)
    b = sub.add_parser("build")
    b.set_defaults(func=cmd_build)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
