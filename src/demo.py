"""Run the agent on one message you type. Useful for poking at it by hand.

    PYTHONPATH=src ./.venv/bin/python src/demo.py "I was charged twice this month"
"""
from __future__ import annotations

import json
import sys

from agent import SupportAgent
from config import BRAND, PROCESSED
from retrieval import HistoryIndex


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('usage: demo.py "the customer message" [--no-retrieval]')
    message = sys.argv[1]
    history = [
        json.loads(l) for l in (PROCESSED / f"{BRAND}_units_history.jsonl").open()
    ]
    agent = SupportAgent(
        HistoryIndex(history), BRAND, use_retrieval="--no-retrieval" not in sys.argv
    )
    unit = {
        "unit_id": "demo",
        "conversation_id": -1,
        "position": 0,
        "context": [],
        "customer_message": message,
    }
    out = agent.run(unit)
    print(f"\ncustomer   : {message}")
    print(f"intent     : {out.intent} (confidence {out.confidence})")
    fired = [k for k, v in out.signals.items() if v]
    print(f"signals    : {fired or 'none'}")
    print(f"route      : {out.route.upper()}  <- {out.route_reason}")
    print(f"reply      : {out.reply}")
    if out.commitments:
        print(f"commitments: {out.commitments}")
    print("\nevidence used for grounding:")
    for n in out.retrieval:
        print(f"  [{n['similarity']}] {n['customer_message'][:90]}")
        print(f"          -> {n['brand_reply'][:110]}")


if __name__ == "__main__":
    main()
