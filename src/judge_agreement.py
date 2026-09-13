"""How much should you trust the judge?

Three questions, three answers:
  1. Does it agree with a human per-reply?      -> QWK / Spearman / bias per dimension
  2. Does it agree on the decision that matters -> send-ready kappa, plus the
     asymmetry (does it wave through replies a human would block?)
  3. Does it rank the SYSTEMS the same way?     -> per-system mean, human vs judge

Sub-command `sample` builds a blinded worksheet; `score` compares it to the judge.
"""
from __future__ import annotations

import argparse
import json
import random

from sklearn.metrics import cohen_kappa_score

from config import GOLDEN, JUDGE_HUMAN_SUBSET_N, RESULTS, SEED, SEND_READY_THRESHOLD
from metrics import quadratic_weighted_kappa, spearman, wilson

DIMS = ("groundedness", "resolution", "tone", "safety")
HUMAN_PATH = GOLDEN / "human_judge_scores.jsonl"
BLIND_PATH = GOLDEN / "judge_blind_worksheet.jsonl"


def cmd_sample(args: argparse.Namespace) -> None:
    """Pick (system, unit) pairs across systems, strip the system name, shuffle."""
    from config import BRAND, PROCESSED
    from retrieval import HistoryIndex

    golden = {json.loads(l)["unit_id"]: json.loads(l) for l in (GOLDEN / "golden_set.jsonl").open()}
    history = [json.loads(l) for l in (PROCESSED / f"{BRAND}_units_history.jsonl").open()]
    index = HistoryIndex(history)
    per_system = args.n // len(args.systems)
    rng = random.Random(SEED + 1)
    tasks = []
    for system in args.systems:
        preds = [json.loads(l) for l in (RESULTS / f"preds_{system}.jsonl").open()]
        preds = [p for p in preds if p.get("reply")]
        for p in rng.sample(preds, min(per_system, len(preds))):
            tasks.append({"system": system, "unit_id": p["unit_id"], "reply": p["reply"]})
    rng.shuffle(tasks)
    with BLIND_PATH.open("w") as fh:
        for i, t in enumerate(tasks):
            fh.write(json.dumps({"blind_id": i, **t}, ensure_ascii=False) + "\n")
    print(f"wrote {len(tasks)} blinded items -> {BLIND_PATH}")
    for i, t in enumerate(tasks):
        g = golden[t["unit_id"]]
        ctx = " | ".join(
            f"{'C' if x['role']=='customer' else 'B'}: {x['text']}" for x in g["context"]
        )
        nbs = index.search(
            g["customer_message"], k=2, exclude_conversation=g["conversation_id"]
        )
        print(f"\n<{i}>")
        if ctx:
            print(f"  ctx: {ctx[:220]}")
        print(f"  CUSTOMER: {g['customer_message'][:260]}")
        for n in nbs:
            print(f"  EVID({n.similarity}): {n.brand_reply[:170]}")
        print(f"  REPLY:    {t['reply'][:400]}")


def cmd_score(args: argparse.Namespace) -> None:
    blind = {json.loads(l)["blind_id"]: json.loads(l) for l in BLIND_PATH.open()}
    human = {json.loads(l)["blind_id"]: json.loads(l) for l in HUMAN_PATH.open()}
    judge = {}
    for line in (RESULTS / f"judge_{args.tag}.jsonl").open():
        r = json.loads(line)
        judge[(r["system"], r["unit_id"])] = r

    pairs = []
    for bid, h in human.items():
        b = blind[bid]
        j = judge.get((b["system"], b["unit_id"]))
        if j:
            pairs.append((b, h, j))
    if not pairs:
        raise SystemExit("no overlapping judge scores; run run_judge.py first")

    out: dict = {"n": len(pairs), "judge_tag": args.tag, "per_dimension": {}}
    for d in DIMS:
        hv = [p[1][d] for p in pairs]
        jv = [p[2][d] for p in pairs]
        out["per_dimension"][d] = {
            "human_mean": round(sum(hv) / len(hv), 3),
            "judge_mean": round(sum(jv) / len(jv), 3),
            "bias_judge_minus_human": round(sum(jv) / len(jv) - sum(hv) / len(hv), 3),
            "exact_agreement": round(sum(a == b for a, b in zip(hv, jv)) / len(hv), 3),
            "within_1": round(sum(abs(a - b) <= 1 for a, b in zip(hv, jv)) / len(hv), 3),
            "qwk": round(quadratic_weighted_kappa(hv, jv), 3),
            "spearman": spearman(hv, jv),
        }

    h_ready = [min(p[1][d] for d in DIMS) >= SEND_READY_THRESHOLD for p in pairs]
    j_ready = [min(p[2][d] for d in DIMS) >= SEND_READY_THRESHOLD for p in pairs]
    tp = sum(h and j for h, j in zip(h_ready, j_ready))
    fp = sum((not h) and j for h, j in zip(h_ready, j_ready))
    fn = sum(h and (not j) for h, j in zip(h_ready, j_ready))
    out["send_ready"] = {
        "human_rate": round(sum(h_ready) / len(h_ready), 4),
        "judge_rate": round(sum(j_ready) / len(j_ready), 4),
        "agreement": round(sum(h == j for h, j in zip(h_ready, j_ready)) / len(h_ready), 4),
        "kappa": round(float(cohen_kappa_score(h_ready, j_ready)), 4)
        if len(set(h_ready)) > 1 and len(set(j_ready)) > 1
        else None,
        "judge_waved_through_human_would_block": fp,
        "judge_blocked_human_would_send": fn,
        "false_pass_rate": round(fp / len(pairs), 4),
        "false_pass_rate_ci95": wilson(fp, len(pairs)),
    }

    by_sys: dict[str, dict] = {}
    for b, h, j in pairs:
        s = by_sys.setdefault(b["system"], {"n": 0, "human": 0.0, "judge": 0.0})
        s["n"] += 1
        s["human"] += sum(h[d] for d in DIMS) / len(DIMS)
        s["judge"] += sum(j[d] for d in DIMS) / len(DIMS)
    for s, v in by_sys.items():
        v["human_mean"] = round(v.pop("human") / v["n"], 3)
        v["judge_mean"] = round(v.pop("judge") / v["n"], 3)
    out["by_system"] = by_sys
    h_rank = [s for s, _ in sorted(by_sys.items(), key=lambda kv: -kv[1]["human_mean"])]
    j_rank = [s for s, _ in sorted(by_sys.items(), key=lambda kv: -kv[1]["judge_mean"])]
    out["system_ranking"] = {
        "human": h_rank,
        "judge": j_rank,
        "ranking_identical": h_rank == j_rank,
    }

    path = RESULTS / f"judge_agreement_{args.tag}.json"
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--systems", nargs="+", required=True)
    s.add_argument("--n", type=int, default=JUDGE_HUMAN_SUBSET_N)
    s.set_defaults(func=cmd_sample)
    c = sub.add_parser("score")
    c.add_argument("--tag", default="primary")
    c.set_defaults(func=cmd_score)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
