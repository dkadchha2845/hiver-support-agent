"""TF-IDF retrieval over the brand's own historical answered messages.

This is the "grounding" store: given a new customer message, find the most
similar past messages *that the brand actually answered* and surface the brand's
real replies as evidence. Deliberately not an embedding model -- see DECISIONS.md.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion

from config import RETRIEVAL_K, RETRIEVAL_MIN_SIM


def _vectorizer(n_docs: int) -> FeatureUnion:
    # min_df must stay below the corpus size or sklearn refuses to fit; this only
    # matters for the tiny corpora used in tests.
    word_min = 2 if n_docs > 20 else 1
    char_min = 3 if n_docs > 20 else 1
    return FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    sublinear_tf=True,
                    ngram_range=(1, 2),
                    min_df=word_min,
                    max_features=120_000,
                    strip_accents="unicode",
                    lowercase=True,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    sublinear_tf=True,
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=char_min,
                    max_features=150_000,
                    lowercase=True,
                ),
            ),
        ]
    )


@dataclass
class Neighbour:
    unit_id: str
    conversation_id: int
    similarity: float
    customer_message: str
    brand_reply: str
    position: int
    brand_asked_for_dm: bool


class HistoryIndex:
    def __init__(self, units: list[dict]):
        self.units = units
        self.vec = _vectorizer(len(units))
        self.matrix = self.vec.fit_transform(
            [u["customer_message"] for u in units]
        )
        # rows are L2-normalised by TfidfVectorizer per sub-vectoriser; renormalise
        # the concatenated space so dot product == cosine.
        norms = np.sqrt(self.matrix.multiply(self.matrix).sum(axis=1)).A.ravel()
        norms[norms == 0] = 1.0
        self._norms = norms

    def search(
        self,
        text: str,
        k: int = RETRIEVAL_K,
        exclude_conversation: int | None = None,
        min_sim: float = RETRIEVAL_MIN_SIM,
    ) -> list[Neighbour]:
        q = self.vec.transform([text])
        qn = float(np.sqrt(q.multiply(q).sum())) or 1.0
        sims = (self.matrix @ q.T).toarray().ravel() / (self._norms * qn)
        order = np.argsort(-sims)[: k * 6 + 12]
        out: list[Neighbour] = []
        seen_convs: set[int] = set()
        for i in order:
            u = self.units[int(i)]
            if exclude_conversation is not None and u["conversation_id"] == exclude_conversation:
                continue
            if u["conversation_id"] in seen_convs:
                continue
            if sims[i] < min_sim:
                break
            seen_convs.add(u["conversation_id"])
            out.append(
                Neighbour(
                    unit_id=u["unit_id"],
                    conversation_id=u["conversation_id"],
                    similarity=round(float(sims[i]), 4),
                    customer_message=u["customer_message"],
                    brand_reply=u["brand_reply"],
                    position=u["position"],
                    brand_asked_for_dm=u["brand_asked_for_dm"],
                )
            )
            if len(out) >= k:
                break
        return out
