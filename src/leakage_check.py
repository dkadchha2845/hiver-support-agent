"""Eval-integrity checks. Two ways this evaluation could be quietly cheating.

1. Temporal bleed: the history/pool split is by thread *start* time, but threads have
   duration, so some history turns are timestamped after the earliest pool turn.
2. Near-duplicate retrieval: retrieval excludes a unit's own conversation, but the
   same question asked by a different customer is fair game - and if the nearest
   neighbour is a near-verbatim twin, "grounding" is closer to lookup than to
   generalisation.
"""
from __future__ import annotations

import json

from config import BRAND, GOLDEN, PROCESSED, RESULTS
from retrieval import HistoryIndex


def main() -> None:
    history = [json.loads(l) for l in (PROCESSED / f"{BRAND}_units_history.jsonl").open()]
    pool = [json.loads(l) for l in (PROCESSED / f"{BRAND}_units_pool.jsonl").open()]
    golden = [json.loads(l) for l in (GOLDEN / "golden_set.jsonl").open()]

    pool_min_ts = min(u["ts"] or "9" for u in pool)
    bleed = [u for u in history if (u["ts"] or "") > pool_min_ts]

    index = HistoryIndex(history)
    sims = []
    for g in golden:
        nb = index.search(
            g["customer_message"], k=1, exclude_conversation=g["conversation_id"]
        )
        sims.append(nb[0].similarity if nb else 0.0)
    sims_sorted = sorted(sims)

    out = {
        "temporal_bleed": {
            "pool_earliest_ts": pool_min_ts,
            "history_units_after_that": len(bleed),
            "share_of_history": round(len(bleed) / len(history), 4),
            "note": (
                "The split is thread-level and time-ordered by thread start, so no "
                "conversation spans both sides. These units are later turns of "
                "long-running history threads. Retrieval additionally excludes a "
                "unit's own conversation, so this cannot leak a unit's own answer."
            ),
        },
        "nearest_neighbour_similarity_on_golden": {
            "min": round(sims_sorted[0], 4),
            "p25": round(sims_sorted[len(sims) // 4], 4),
            "median": round(sims_sorted[len(sims) // 2], 4),
            "p75": round(sims_sorted[3 * len(sims) // 4], 4),
            "max": round(sims_sorted[-1], 4),
            "share_above_090_near_duplicate": round(
                sum(s > 0.90 for s in sims) / len(sims), 4
            ),
            "share_above_060": round(sum(s > 0.60 for s in sims) / len(sims), 4),
            "share_below_015_no_precedent": round(
                sum(s < 0.15 for s in sims) / len(sims), 4
            ),
        },
    }
    (RESULTS / "leakage_check.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
