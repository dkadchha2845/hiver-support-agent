"""Print the 40-unit re-label subset (message only) for the second annotation pass."""
import json, random, sys
rows = [json.loads(l) for l in open("data/golden/golden_set.jsonl")]
random.Random(4242).shuffle(rows)
for i, r in enumerate(rows[:40]):
    ctx = " | ".join(f"{'C' if t['role']=='customer' else 'B'}: {t['text']}" for t in r["context"])
    print(f"<{i}> {r['unit_id']}")
    if ctx:
        print(f"   ctx: {ctx[:260]}")
    print(f"   MSG: {r['customer_message'][:300]}")
