"""Run a configured agent over the golden set and dump predictions."""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

from agent import SupportAgent
from config import AGENT_MODEL, AGENT_PROVIDER, BRAND, GOLDEN, PROCESSED, RESULTS
from retrieval import HistoryIndex


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="system name, used in the filename")
    ap.add_argument("--router", default="policy", choices=["policy", "llm"])
    ap.add_argument("--no-retrieval", action="store_true")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--provider", default=AGENT_PROVIDER)
    ap.add_argument("--model", default=AGENT_MODEL)
    ap.add_argument(
        "--workers",
        type=int,
        default=3,
        help="concurrent requests; ollama batches these, ~2x throughput on an M-series",
    )
    args = ap.parse_args()

    golden = [json.loads(l) for l in (GOLDEN / "golden_set.jsonl").open()]
    if args.limit:
        golden = golden[: args.limit]
    history = [
        json.loads(l) for l in (PROCESSED / f"{BRAND}_units_history.jsonl").open()
    ]
    index = HistoryIndex(history)
    agent = SupportAgent(
        index,
        BRAND,
        provider=args.provider,
        model=args.model,
        router=args.router,
        use_retrieval=not args.no_retrieval,
        k=args.k,
    )

    out_path = RESULTS / f"preds_{args.name}.jsonl"
    t0 = time.time()
    done = [0]

    def work(unit: dict) -> dict:
        res = agent.run(unit).to_json()
        done[0] += 1
        i = done[0]
        if i % 10 == 0 or i == len(golden):
            rate = (time.time() - t0) / i
            print(
                f"  {i}/{len(golden)}  {rate:.2f}s/unit  "
                f"eta {(len(golden)-i)*rate/60:.1f}min",
                flush=True,
            )
        return res

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        # map preserves input order, so the output file is deterministic
        rows = list(pool.map(work, golden))
    with out_path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    meta = {
        "system": args.name,
        "provider": args.provider,
        "model": args.model,
        "router": args.router,
        "retrieval": not args.no_retrieval,
        "k": args.k,
        "n": len(golden),
        "workers": args.workers,
        "wall_seconds": round(time.time() - t0, 1),
        "llm_stats": agent.llm.stats.as_dict(),
    }
    (RESULTS / f"runmeta_{args.name}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
