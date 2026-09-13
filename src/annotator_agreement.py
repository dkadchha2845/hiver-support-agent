"""Intra-annotator consistency: pass-1 vs pass-2 labels on a 40-unit subset.

Caveat recorded in the report: this is the SAME annotator relabelling, so it is an
optimistic upper bound on what a second independent annotator would agree on.
"""
from __future__ import annotations

import json
import random

from sklearn.metrics import cohen_kappa_score

from config import GOLDEN, RESULTS


def main() -> None:
    rows = [json.loads(l) for l in (GOLDEN / "golden_set.jsonl").open()]
    order = list(rows)
    random.Random(4242).shuffle(order)
    subset = order[:40]

    pass2 = {}
    for line in (GOLDEN / "labels_pass2.tsv").open():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        idx, intent, route = [p.strip() for p in line.split("|")]
        pass2[int(idx)] = (intent, route)

    a_int, b_int, a_rt, b_rt = [], [], [], []
    disagreements = []
    for i, r in enumerate(subset):
        if i not in pass2:
            continue
        p2i, p2r = pass2[i]
        a_int.append(r["gold_intent"])
        b_int.append(p2i)
        a_rt.append(r["gold_route"])
        b_rt.append(p2r)
        if r["gold_intent"] != p2i or r["gold_route"] != p2r:
            disagreements.append(
                {
                    "unit_id": r["unit_id"],
                    "pass1": [r["gold_intent"], r["gold_route"]],
                    "pass2": [p2i, p2r],
                    "message": r["customer_message"][:160],
                }
            )

    out = {
        "n": len(a_int),
        "intent_agreement": round(sum(x == y for x, y in zip(a_int, b_int)) / len(a_int), 4),
        "intent_kappa": round(float(cohen_kappa_score(a_int, b_int)), 4),
        "route_agreement": round(sum(x == y for x, y in zip(a_rt, b_rt)) / len(a_rt), 4),
        "route_kappa": round(float(cohen_kappa_score(a_rt, b_rt)), 4),
        "disagreements": disagreements,
    }
    (RESULTS / "annotator_agreement.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "disagreements"}, indent=2))
    for d in disagreements:
        print(f"  {d['unit_id']}: {d['pass1']} -> {d['pass2']} | {d['message'][:90]}")


if __name__ == "__main__":
    main()
