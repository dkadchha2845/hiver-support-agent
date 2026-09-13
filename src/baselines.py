"""Baselines. Two of them, as required, plus the brand's own reply as a reference.

B0 "trivial"   - majority-class intent, one fixed canned reply, and a single fixed
                 routing decision (reported both ways: always-auto and always-escalate).
B1 "simple"    - TF-IDF + logistic regression for intent, a hand-written keyword
                 lexicon for routing, and verbatim nearest-neighbour retrieval for the
                 reply. No LLM anywhere.
HUMAN          - the reply @SpotifyCares actually sent, scored by the same judge.

Note the deliberate handicap: B0 and B1 are fitted with 5-fold cross-validation ON
the golden labels, so they see gold data the LLM systems never see. That makes them
harder to beat, not easier.
"""
from __future__ import annotations

import json
import re
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline

from config import GOLDEN, PROCESSED, RESULTS, SEED
from retrieval import HistoryIndex

CANNED = (
    "Hey there, help's here! Could you DM us your account's email address? "
    "We'll take a look backstage for you"
)

# B1 routing lexicon, written by hand from the codebook's hard signals.
ESCALATE_LEXICON = re.compile(
    r"\b(refund|charg\w*|billed?|billing|invoice|payment|paid|debit|credit card|"
    r"hack\w*|compromis\w*|breach|leak\w*|stolen|phish\w*|password|log ?in|login|"
    r"locked out|lawyer|sue|fraud|gdpr|ombudsman|cancel\w*|unsubscrib\w*|"
    r"human|manager|real person|agent|dm)\b",
    re.I,
)
NON_ASCII = re.compile(r"[^\x00-\x7F]")


def load_golden() -> list[dict]:
    return [json.loads(l) for l in (GOLDEN / "golden_set.jsonl").open()]


def _non_english_ish(text: str) -> bool:
    """Crude language heuristic: high share of non-ASCII word characters, or a hit
    on a small stop-word list. Deliberately crude - it is a baseline."""
    stops = (
        " saya ", " tidak ", " yang ", " kalo ", " mau ", " por favor", " gracias",
        " bonjour", " merci", " ich ", " nicht ", " que ", " con ", " pulsa ",
        " kan ", " ada ", " hvis ", " man ", " jeg ", " og ", " denne ",
    )
    low = f" {text.lower()} "
    if any(s in low for s in stops):
        return True
    letters = re.findall(r"\w", text)
    if not letters:
        return False
    return sum(bool(NON_ASCII.match(c)) for c in letters) / len(letters) > 0.25


def trivial_intent_cv(golden: list[dict]) -> list[str]:
    """Majority class, determined per fold from training folds only."""
    y = np.array([g["gold_intent"] for g in golden])
    preds = np.empty(len(y), dtype=object)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    for train, test in skf.split(np.zeros(len(y)), y):
        majority = Counter(y[train]).most_common(1)[0][0]
        preds[test] = majority
    return preds.tolist()


def logreg_intent_cv(golden: list[dict]) -> list[str]:
    texts = np.array(
        [
            " ".join(t["text"] for t in g["context"][-2:]) + " || " + g["customer_message"]
            for g in golden
        ]
    )
    y = np.array([g["gold_intent"] for g in golden])
    preds = np.empty(len(y), dtype=object)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    for train, test in skf.split(texts, y):
        clf = make_pipeline(
            TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2), min_df=1),
            LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced"),
        )
        clf.fit(texts[train], y[train])
        preds[test] = clf.predict(texts[test])
    return preds.tolist()


def lexicon_route(golden: list[dict]) -> list[str]:
    out = []
    for g in golden:
        text = " ".join(t["text"] for t in g["context"]) + " " + g["customer_message"]
        escalate = bool(ESCALATE_LEXICON.search(text)) or _non_english_ish(
            g["customer_message"]
        )
        out.append("escalate" if escalate else "auto")
    return out


def main() -> None:
    golden = load_golden()
    history = [
        json.loads(l)
        for l in (PROCESSED / "SpotifyCares_units_history.jsonl").open()
    ]
    index = HistoryIndex(history)

    triv_intent = trivial_intent_cv(golden)
    lr_intent = logreg_intent_cv(golden)
    lex_route = lexicon_route(golden)

    rows_b0, rows_b1, rows_nn, rows_human = [], [], [], []
    for g, ti, li, lr in zip(golden, triv_intent, lr_intent, lex_route):
        nb = index.search(
            g["customer_message"], k=1, exclude_conversation=g["conversation_id"]
        )
        nn_reply = nb[0].brand_reply if nb else CANNED
        nn_sim = nb[0].similarity if nb else 0.0
        base = {"unit_id": g["unit_id"]}
        rows_b0.append(
            {
                **base,
                "intent": ti,
                "route": "escalate",
                "route_reason": "trivial baseline: escalate everything",
                "reply": CANNED,
                "commitments": [],
            }
        )
        rows_b1.append(
            {
                **base,
                "intent": li,
                "route": lr,
                "route_reason": "keyword lexicon",
                "reply": nn_reply,
                "commitments": [],
                "nn_similarity": nn_sim,
            }
        )
        rows_nn.append({**base, "reply": nn_reply, "nn_similarity": nn_sim})
        rows_human.append({**base, "reply": g["brand_reply"]})

    # B0 with the opposite trivial routing choice, so the bracket is visible.
    rows_b0_auto = [dict(r, route="auto", route_reason="trivial baseline: auto-handle everything") for r in rows_b0]

    for name, rows in [
        ("B0_trivial_escalate_all", rows_b0),
        ("B0_trivial_auto_all", rows_b0_auto),
        ("B1_simple", rows_b1),
        ("HUMAN_brand_reply", rows_human),
    ]:
        path = RESULTS / f"preds_{name}.jsonl"
        with path.open("w") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"wrote {len(rows):>4} -> {path.name}")


if __name__ == "__main__":
    main()
