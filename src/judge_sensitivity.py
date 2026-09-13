"""How much of the headline is the judge rather than the agent?

Compares the primary judge pass against three alternatives on the same replies:
  stability     - same judge, temperature 0.7 (does one sample move the number?)
  selfjudge     - judge from the SAME family as the agent (self-preference)
  withreference - judge also shown the reply the customer really received
"""
from __future__ import annotations

import json

from config import GOLDEN, RESULTS, SEND_READY_THRESHOLD

DIMS = ("groundedness", "resolution", "tone", "safety")


def load(tag: str) -> dict[tuple[str, str], dict]:
    path = RESULTS / f"judge_{tag}.jsonl"
    if not path.exists():
        return {}
    out = {}
    for line in path.open():
        r = json.loads(line)
        out[(r["system"], r["unit_id"])] = r
    return out


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {}
    ready = [min(r[d] for d in DIMS) >= SEND_READY_THRESHOLD for r in rows]
    return {
        "n": n,
        "mean_overall": round(sum(sum(r[d] for d in DIMS) / 4 for r in rows) / n, 3),
        "send_ready_rate": round(sum(ready) / n, 4),
        **{f"mean_{d}": round(sum(r[d] for r in rows) / n, 3) for d in DIMS},
    }


def main() -> None:
    primary = load("primary")
    out: dict = {}
    for tag in ("stability", "selfjudge", "withreference"):
        alt = load(tag)
        if not alt:
            continue
        block = {}
        for system in sorted({s for s, _ in alt}):
            keys = [k for k in alt if k[0] == system and k in primary]
            if not keys:
                continue
            block[system] = {
                "primary": summarise([primary[k] for k in keys]),
                tag: summarise([alt[k] for k in keys]),
            }
            p, a = block[system]["primary"], block[system][tag]
            block[system]["delta_send_ready"] = round(
                a["send_ready_rate"] - p["send_ready_rate"], 4
            )
            block[system]["delta_mean_overall"] = round(
                a["mean_overall"] - p["mean_overall"], 3
            )
            flips = sum(
                (min(primary[k][d] for d in DIMS) >= SEND_READY_THRESHOLD)
                != (min(alt[k][d] for d in DIMS) >= SEND_READY_THRESHOLD)
                for k in keys
            )
            block[system]["send_ready_decision_flips"] = flips
            block[system]["send_ready_flip_rate"] = round(flips / len(keys), 4)
        out[tag] = block

    # Does the same-family judge close the gap to the human reference?
    sj = out.get("selfjudge", {})
    if {"S3_agent", "HUMAN_brand_reply"} <= set(sj):
        for which in ("primary", "selfjudge"):
            gap = (
                sj["S3_agent"][which]["mean_overall"]
                - sj["HUMAN_brand_reply"][which]["mean_overall"]
            )
            out.setdefault("agent_minus_human_gap", {})[which] = round(gap, 3)

    (RESULTS / "judge_sensitivity.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
