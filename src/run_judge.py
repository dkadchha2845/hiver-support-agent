"""Score every system's replies with the LLM judge.

Blind: candidates from all systems are pooled and shuffled before scoring, and the
judge prompt never names the system.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor

from config import BRAND, GOLDEN, JUDGE_MODEL, JUDGE_PROVIDER, PROCESSED, RESULTS, SEED
from judge import Judge
from retrieval import HistoryIndex


def evidence_for(unit: dict, index: HistoryIndex, k: int = 4) -> str:
    nbs = index.search(
        unit["customer_message"], k=k, exclude_conversation=unit["conversation_id"]
    )
    if not nbs:
        return "(no similar past message found)"
    return "\n".join(
        f"[{n.unit_id}] past customer: {n.customer_message}\n  brand replied: {n.brand_reply}"
        for n in nbs
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="+", required=True)
    ap.add_argument("--tag", default="primary")
    ap.add_argument("--provider", default=JUDGE_PROVIDER)
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--show-reference", action="store_true")
    ap.add_argument("--cache-salt", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    golden = {
        json.loads(l)["unit_id"]: json.loads(l)
        for l in (GOLDEN / "golden_set.jsonl").open()
    }
    order = [json.loads(l)["unit_id"] for l in (GOLDEN / "golden_set.jsonl").open()]
    if args.limit:
        order = order[: args.limit]
    history = [
        json.loads(l) for l in (PROCESSED / f"{BRAND}_units_history.jsonl").open()
    ]
    index = HistoryIndex(history)
    ev_cache: dict[str, str] = {}

    tasks = []
    for system in args.systems:
        path = RESULTS / f"preds_{system}.jsonl"
        preds = {json.loads(l)["unit_id"]: json.loads(l) for l in path.open()}
        for uid in order:
            if uid in preds:
                tasks.append((system, uid, preds[uid].get("reply", "")))
    random.Random(SEED).shuffle(tasks)

    judge = Judge(
        BRAND,
        provider=args.provider,
        model=args.model,
        temperature=args.temperature,
        show_reference=args.show_reference,
        cache_salt=args.cache_salt,
    )
    # evidence is deterministic per unit and reused across systems: precompute serially
    for uid in {t[1] for t in tasks}:
        ev_cache[uid] = evidence_for(golden[uid], index)

    out_path = RESULTS / f"judge_{args.tag}.jsonl"
    t0 = time.time()
    done = [0]

    def work(task):
        system, uid, reply = task
        score = judge.score(golden[uid], reply, system, ev_cache[uid])
        done[0] += 1
        i = done[0]
        if i % 25 == 0 or i == len(tasks):
            rate = (time.time() - t0) / i
            print(
                f"  {i}/{len(tasks)}  {rate:.2f}s/call  "
                f"eta {(len(tasks)-i)*rate/60:.1f}min",
                flush=True,
            )
        return score.to_json()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(work, tasks))
    with out_path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    meta = {
        "tag": args.tag,
        "provider": args.provider,
        "model": args.model,
        "temperature": args.temperature,
        "show_reference": args.show_reference,
        "systems": args.systems,
        "n_scores": len(tasks),
        "workers": args.workers,
        "wall_seconds": round(time.time() - t0, 1),
        "llm_stats": judge.llm.stats.as_dict(),
    }
    (RESULTS / f"judgemeta_{args.tag}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
