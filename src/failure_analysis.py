"""Dig out concrete failures so the report can quote real examples, not vibes.

Writes results/failures.json and prints a readable digest.
"""
from __future__ import annotations

import json
import re
from collections import Counter

from config import GOLDEN, RESULTS

HANDOFF_RE = re.compile(
    r"\b(dm|direct message|human|teammate|team|colleague|specialist|advisor|"
    r"backstage|look into|our friends|pass(ing)? (this|you) on|get back to you)\b",
    re.I,
)

DIMS = ("groundedness", "resolution", "tone", "safety")


def main(system: str = "S3_agent", judge_tag: str = "primary") -> None:
    golden = {json.loads(l)["unit_id"]: json.loads(l) for l in (GOLDEN / "golden_set.jsonl").open()}
    preds = {json.loads(l)["unit_id"]: json.loads(l) for l in (RESULTS / f"preds_{system}.jsonl").open()}
    judge = {}
    judge_path = RESULTS / f"judge_{judge_tag}.jsonl"
    if judge_path.exists():
        for line in judge_path.open():
            r = json.loads(line)
            judge[(r["system"], r["unit_id"])] = r

    def row(uid: str) -> dict:
        g, p = golden[uid], preds[uid]
        j = judge.get((system, uid), {})
        best_sim = max((n["similarity"] for n in p.get("retrieval", [])), default=0.0)
        return {
            "unit_id": uid,
            "stratum": g["stratum"],
            "position": g["position"],
            "hard": g["hard"],
            "customer_message": g["customer_message"][:300],
            "gold_intent": g["gold_intent"],
            "gold_intent_alt": g["gold_intent_alt"],
            "pred_intent": p.get("intent"),
            "confidence": p.get("confidence"),
            "gold_route": g["gold_route"],
            "gold_driver": g["gold_driver"],
            "pred_route": p.get("route"),
            "route_reason": p.get("route_reason"),
            "signals_fired": [k for k, v in (p.get("signals") or {}).items() if v],
            "reply": p.get("reply", "")[:300],
            "brand_reply": g["brand_reply"][:250],
            "best_retrieval_similarity": best_sim,
            "judge": {d: j.get(d) for d in DIMS} if j else None,
            "judge_send_ready": j.get("send_ready") if j else None,
            "judge_reason": j.get("one_line_reason") if j else None,
            "unsupported_claims": j.get("unsupported_claims") if j else None,
            "note": g["note"],
        }

    uids = [u for u in golden if u in preds]
    missed = [row(u) for u in uids if golden[u]["gold_route"] == "escalate" and preds[u].get("route") == "auto"]
    over = [row(u) for u in uids if golden[u]["gold_route"] == "auto" and preds[u].get("route") == "escalate"]
    wrong_intent = [row(u) for u in uids if preds[u].get("intent") != golden[u]["gold_intent"]]
    wrong_intent_strict = [
        r for r in wrong_intent if r["pred_intent"] != r["gold_intent_alt"]
    ]
    confusions = Counter(
        (r["gold_intent"], r["pred_intent"]) for r in wrong_intent_strict
    ).most_common(12)

    judged = [row(u) for u in uids if (system, u) in judge]
    worst = sorted(
        judged, key=lambda r: (min(r["judge"].values()), sum(r["judge"].values()))
    )[:15] if judged else []
    unsupported = [r for r in judged if r["unsupported_claims"]][:15]
    grounded_but_blocked = [
        r for r in judged
        if r["best_retrieval_similarity"] >= 0.3 and not r["judge_send_ready"]
    ][:12]
    no_precedent = [r for r in judged if r["best_retrieval_similarity"] < 0.15][:12]

    # Which hard risk signals does the model actually detect? For every unit whose
    # gold escalation driver is signal X, did the model fire X?
    signal_recall: dict[str, dict] = {}
    for u in uids:
        drv = golden[u]["gold_driver"]
        if drv == "none":
            continue
        blk = signal_recall.setdefault(drv, {"gold_n": 0, "model_fired": 0, "escalated_anyway": 0})
        blk["gold_n"] += 1
        blk["model_fired"] += int(bool((preds[u].get("signals") or {}).get(drv)))
        blk["escalated_anyway"] += int(preds[u].get("route") == "escalate")
    for drv, blk in signal_recall.items():
        blk["signal_recall"] = round(blk["model_fired"] / blk["gold_n"], 3)
        blk["route_recall"] = round(blk["escalated_anyway"] / blk["gold_n"], 3)

    # How harmful were the missed escalations really? A draft that still says
    # "DM us" has not exposed the customer to much, even though routing was wrong.
    missed_but_safe = [r for r in missed if HANDOFF_RE.search(r["reply"] or "")]

    out = {
        "system": system,
        "risk_signal_detection": dict(
            sorted(signal_recall.items(), key=lambda kv: -kv[1]["gold_n"])
        ),
        "missed_escalation_severity": {
            "n_missed": len(missed),
            "draft_still_handed_off": len(missed_but_safe),
            "draft_attempted_to_resolve": len(missed) - len(missed_but_safe),
            "note": (
                "A missed escalation whose draft still routes the customer to DM is a "
                "routing-label error with little real exposure. The rows that matter "
                "are the ones where the draft tried to solve it in public."
            ),
        },
        "counts": {
            "missed_escalations": len(missed),
            "over_escalations": len(over),
            "intent_wrong_strict": len(wrong_intent_strict),
            "intent_wrong_but_matched_alt": len(wrong_intent) - len(wrong_intent_strict),
            "replies_with_unsupported_claims": sum(bool(r["unsupported_claims"]) for r in judged),
        },
        "top_intent_confusions": [
            {"gold": g, "pred": p, "n": n} for (g, p), n in confusions
        ],
        "missed_escalations": missed,
        "over_escalations": over[:20],
        "worst_judged_replies": worst,
        "unsupported_claim_examples": unsupported,
        "high_precedent_still_blocked": grounded_but_blocked,
        "no_precedent_cases": no_precedent,
    }
    (RESULTS / "failures.json").write_text(json.dumps(out, indent=2))

    print(json.dumps(out["counts"], indent=2))
    print("\nTop intent confusions (gold -> pred):")
    for c in out["top_intent_confusions"]:
        print(f"  {c['gold']:>22} -> {c['pred']:<22} x{c['n']}")
    print(f"\nMissed escalations ({len(missed)}):")
    for r in missed:
        print(f"  [{r['unit_id']}] gold_driver={r['gold_driver']} pred={r['pred_intent']} "
              f"signals={r['signals_fired']} hard={r['hard']}")
        print(f"      MSG: {r['customer_message'][:150]}")
        print(f"      GOT: {r['reply'][:150]}")


if __name__ == "__main__":
    main()
