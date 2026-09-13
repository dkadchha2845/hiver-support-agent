"""Descriptive statistics the report quotes, so no framing claim is unverified."""
from __future__ import annotations

import json
import re
from collections import Counter

from config import BRAND, GOLDEN, PROCESSED, RESULTS

PATTERNS = {
    "asks_for_dm": r"\b(dm|direct message|private message|inbox)\b",
    "asks_device_os_version": r"\b(device|operating system|os|version|browser)\b",
    "links_somewhere": r"<url>",
    "points_to_community_ideas": r"\b(community|vote|idea)\b",
    "mentions_licensing": r"\b(licens\w+|rights holder|artist'?s request)\b",
    "has_agent_signature": r"/[A-Z]{1,2}\s*$",
    "uses_emoji": r"[\U0001F300-\U0001FAFF☀-➿]",
}


def main() -> None:
    threads = [json.loads(l) for l in (PROCESSED / f"{BRAND}_threads.jsonl").open()]
    history = [json.loads(l) for l in (PROCESSED / f"{BRAND}_units_history.jsonl").open()]
    pool = [json.loads(l) for l in (PROCESSED / f"{BRAND}_units_pool.jsonl").open()]
    units = history + pool
    frame = json.loads((GOLDEN / "frame_report.json").read_text())

    replies = [u["brand_reply"] for u in units]
    pat_share = {
        name: round(sum(bool(re.search(p, r, re.I)) for r in replies) / len(replies), 4)
        for name, p in PATTERNS.items()
    }

    out = {
        "brand": BRAND,
        "n_threads": len(threads),
        "n_answered_customer_turns": len(units),
        "median_thread_turns": sorted(t["n_turns"] for t in threads)[len(threads) // 2],
        "turn_position_share": {
            "opener": round(sum(u["position"] == 0 for u in units) / len(units), 4),
            "follow_up": round(sum(u["position"] > 0 for u in units) / len(units), 4),
        },
        "share_of_threads_with_a_dm_request": round(
            sum(u["thread_asked_for_dm"] for u in units) / len(units), 4
        ),
        "mean_brand_reply_chars": round(sum(len(r) for r in replies) / len(replies), 1),
        "mean_customer_message_chars": round(
            sum(len(u["customer_message"]) for u in units) / len(units), 1
        ),
        "brand_reply_action_patterns": pat_share,
        "eval_pool_stratum_share": {
            k: round(v["population"] / frame["pool_deduped"], 4)
            for k, v in frame["strata"].items()
        },
        "eval_pool_deduped": frame["pool_deduped"],
        "golden_weights": {k: v["weight"] for k, v in frame["strata"].items()},
    }
    (RESULTS / "data_profile.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
