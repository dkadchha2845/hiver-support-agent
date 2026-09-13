"""Convert index-keyed annotation lines into data/golden/labels.jsonl.

Annotation line format (pipe separated):
    idx | intent | alt_intent | route | driver | hard | note
`alt_intent` may be empty, `driver` must be `none` for auto rows, `hard` is 0/1.
Indexes refer to positions in data/golden/frame.jsonl (stable, seeded order).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"

frame = [json.loads(l) for l in (GOLDEN / "frame.jsonl").open()]
rows: dict[int, dict] = {}
existing = GOLDEN / "labels.jsonl"
by_id: dict[str, dict] = {}
if existing.exists():
    for line in existing.open():
        r = json.loads(line)
        by_id[r["unit_id"]] = r

added = 0
for raw in sys.stdin:
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        continue
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 6:
        sys.exit(f"malformed line: {raw}")
    idx = int(parts[0])
    unit = frame[idx]
    rec = {
        "unit_id": unit["unit_id"],
        "frame_index": idx,
        "gold_intent": parts[1],
        "gold_intent_alt": parts[2] or None,
        "gold_route": parts[3],
        "gold_driver": parts[4] or "none",
        "hard": parts[5] in {"1", "true", "True"},
        "note": parts[6] if len(parts) > 6 else "",
    }
    by_id[rec["unit_id"]] = rec
    added += 1

with (GOLDEN / "labels.jsonl").open("w") as fh:
    for rec in sorted(by_id.values(), key=lambda r: r["frame_index"]):
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
print(f"applied {added} lines; labels file now has {len(by_id)} rows")
