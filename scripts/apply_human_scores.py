"""Turn the hand-scored worksheet into data/golden/human_judge_scores.jsonl.

Line format: blind_id | groundedness | resolution | tone | safety | note
Scores were assigned by reading the customer message, the two most similar historical
Spotify replies (as evidence), and the candidate reply - blind to which system wrote it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "golden" / "human_judge_scores.jsonl"

rows = []
for raw in sys.stdin:
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        continue
    p = [x.strip() for x in raw.split("|")]
    rows.append(
        {
            "blind_id": int(p[0]),
            "groundedness": int(p[1]),
            "resolution": int(p[2]),
            "tone": int(p[3]),
            "safety": int(p[4]),
            "note": p[5] if len(p) > 5 else "",
        }
    )
rows.sort(key=lambda r: r["blind_id"])
with OUT.open("w") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"wrote {len(rows)} human scores -> {OUT}")
