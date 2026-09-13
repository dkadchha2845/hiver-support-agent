"""Turn the raw twcs.csv dump into brand-scoped conversation threads and eval units.

Usage:
    python src/data_prep.py stats            # brand volume table, to pick a brand
    python src/data_prep.py build            # threads + units for config.BRAND
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from config import BRAND, HISTORY_FRACTION, PROCESSED, TWCS_CSV

USECOLS = [
    "tweet_id",
    "author_id",
    "inbound",
    "created_at",
    "text",
    "in_response_to_tweet_id",
]

URL_RE = re.compile(r"https?://\S+|www\.\S+")
MENTION_RE = re.compile(r"@(\w+)")
WS_RE = re.compile(r"\s+")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
LONGNUM_RE = re.compile(r"\b\d{7,}\b")
DM_RE = re.compile(
    r"\b(dm|direct message|private message|send us a message|pm us|"
    r"follow.{0,10}dm|inbox)\b",
    re.I,
)
PHONE_RE = re.compile(r"\b(?:\+?\d[\d\-\s().]{7,}\d)\b")


def load_raw() -> pd.DataFrame:
    if not TWCS_CSV.exists():
        sys.exit(
            f"missing {TWCS_CSV}. Run `make data-download` (or `bash scripts/"
            "download_data.sh`) first."
        )
    df = pd.read_csv(
        TWCS_CSV,
        usecols=USECOLS,
        dtype={
            "tweet_id": "int64",
            "author_id": "str",
            "text": "str",
            "in_response_to_tweet_id": "float64",
        },
    )
    df["inbound"] = df["inbound"].astype(str).str.lower().eq("true")
    return df


# --------------------------------------------------------------------- threads
def assign_conversation_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Union-find over reply edges -> one conversation id per connected component."""
    ids = df["tweet_id"].to_numpy()
    index = {int(t): i for i, t in enumerate(ids)}
    parent = np.arange(len(ids), dtype=np.int64)

    def find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:  # path compression
            parent[x], x = root, parent[x]
        return root

    parents = df["in_response_to_tweet_id"].to_numpy()
    for i, p in enumerate(parents):
        if np.isnan(p):
            continue
        j = index.get(int(p))
        if j is None:
            continue
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    df = df.copy()
    df["conversation_id"] = [int(ids[find(i)]) for i in range(len(ids))]
    return df


def clean_text(text: str, brand: str) -> str:
    if not isinstance(text, str):
        return ""
    text = URL_RE.sub("<url>", text)
    text = EMAIL_RE.sub("<email>", text)
    text = PHONE_RE.sub("<number>", text)
    text = LONGNUM_RE.sub("<number>", text)

    def _m(match: re.Match) -> str:
        handle = match.group(1)
        if handle.lower() == brand.lower():
            return f"@{brand}"
        return "@customer" if handle.isdigit() else f"@{handle}"

    text = MENTION_RE.sub(_m, text)
    return WS_RE.sub(" ", text).strip()


def build_threads(df: pd.DataFrame, brand: str) -> list[dict]:
    brand_tweets = df.index[df["author_id"].str.lower() == brand.lower()]
    convo_ids = set(df.loc[brand_tweets, "conversation_id"].unique().tolist())
    sub = df[df["conversation_id"].isin(convo_ids)].copy()
    sub["ts"] = pd.to_datetime(sub["created_at"], format="%a %b %d %H:%M:%S %z %Y", errors="coerce")
    sub = sub.sort_values(["conversation_id", "ts", "tweet_id"])

    threads: list[dict] = []
    for cid, g in sub.groupby("conversation_id", sort=False):
        turns = []
        for row in g.itertuples():
            author = str(row.author_id)
            is_brand = author.lower() == brand.lower()
            # A third-party brand replying inside the thread is treated as noise.
            if not row.inbound and not is_brand:
                continue
            turns.append(
                {
                    "tweet_id": int(row.tweet_id),
                    "role": "customer" if row.inbound else "agent",
                    "ts": None if pd.isna(row.ts) else row.ts.isoformat(),
                    "text": clean_text(row.text, brand),
                }
            )
        turns = [t for t in turns if t["text"]]
        if len(turns) < 2 or not any(t["role"] == "agent" for t in turns):
            continue
        threads.append(
            {
                "conversation_id": int(cid),
                "brand": brand,
                "n_turns": len(turns),
                "first_ts": turns[0]["ts"],
                "turns": turns,
            }
        )
    threads.sort(key=lambda t: (t["first_ts"] or "", t["conversation_id"]))
    return threads


# ----------------------------------------------------------------------- units
def build_units(threads: list[dict]) -> list[dict]:
    """One eval unit per customer turn that the brand actually answered.

    `position` 0 means the opening message of the thread; >0 means a follow-up,
    which is the harder, mid-conversation case.
    """
    units: list[dict] = []
    for th in threads:
        turns = th["turns"]
        customer_seen = 0
        for i, turn in enumerate(turns):
            if turn["role"] != "customer":
                continue
            reply_parts = []
            for nxt in turns[i + 1 :]:
                if nxt["role"] != "agent":
                    break
                reply_parts.append(nxt["text"])
            if not reply_parts:
                customer_seen += 1
                continue
            brand_reply = " ".join(reply_parts)
            units.append(
                {
                    "unit_id": f"{th['conversation_id']}-{turn['tweet_id']}",
                    "conversation_id": th["conversation_id"],
                    "brand": th["brand"],
                    "position": customer_seen,
                    "ts": turn["ts"],
                    "context": [
                        {"role": t["role"], "text": t["text"]} for t in turns[:i]
                    ][-4:],
                    "customer_message": turn["text"],
                    "brand_reply": brand_reply,
                    "thread_n_turns": th["n_turns"],
                    "brand_asked_for_dm": bool(DM_RE.search(brand_reply)),
                    "thread_asked_for_dm": bool(
                        DM_RE.search(
                            " ".join(t["text"] for t in turns if t["role"] == "agent")
                        )
                    ),
                }
            )
            customer_seen += 1
    return units


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows):>7,} -> {path.relative_to(PROCESSED.parents[1])}")


def read_jsonl(path: Path) -> list[dict]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def cmd_stats(args: argparse.Namespace) -> None:
    df = load_raw()
    out = (
        df[~df["inbound"]]
        .groupby("author_id")
        .size()
        .sort_values(ascending=False)
        .head(args.top)
    )
    print(f"{'brand':<22}{'outbound tweets':>16}")
    for brand, n in out.items():
        print(f"{brand:<22}{n:>16,}")


def cmd_build(args: argparse.Namespace) -> None:
    brand = args.brand or BRAND
    df = load_raw()
    print(f"raw rows: {len(df):,}")
    df = assign_conversation_ids(df)
    threads = build_threads(df, brand)
    print(f"threads for {brand}: {len(threads):,}")
    units = build_units(threads)
    print(f"answered customer turns: {len(units):,}")

    cut = int(len(threads) * HISTORY_FRACTION)
    history_ids = {t["conversation_id"] for t in threads[:cut]}
    history = [u for u in units if u["conversation_id"] in history_ids]
    pool = [u for u in units if u["conversation_id"] not in history_ids]

    write_jsonl(PROCESSED / f"{brand}_threads.jsonl", threads)
    write_jsonl(PROCESSED / f"{brand}_units_history.jsonl", history)
    write_jsonl(PROCESSED / f"{brand}_units_pool.jsonl", pool)
    meta = {
        "brand": brand,
        "n_threads": len(threads),
        "n_units": len(units),
        "n_history_units": len(history),
        "n_pool_units": len(pool),
        "history_fraction": HISTORY_FRACTION,
        "history_ts_max": max((u["ts"] or "") for u in history) if history else None,
        "pool_ts_min": min((u["ts"] or "") for u in pool) if pool else None,
        "opener_share_pool": round(
            sum(u["position"] == 0 for u in pool) / max(len(pool), 1), 4
        ),
    }
    (PROCESSED / f"{brand}_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stats")
    s.add_argument("--top", type=int, default=30)
    s.set_defaults(func=cmd_stats)
    b = sub.add_parser("build")
    b.add_argument("--brand", default=None)
    b.set_defaults(func=cmd_build)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
