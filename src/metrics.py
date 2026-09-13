"""Metric definitions, kept separate so the report can cite exact formulas."""
from __future__ import annotations

import math
from collections import Counter

import numpy as np
from sklearn.metrics import classification_report, cohen_kappa_score, f1_score


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval - honest CIs at n=200, unlike the normal approximation."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def weighted_rate(flags: list[bool], weights: list[float]) -> float:
    """Population estimate from a stratified sample (Horvitz-Thompson)."""
    w = np.asarray(weights, dtype=float)
    f = np.asarray(flags, dtype=float)
    return float((w * f).sum() / w.sum()) if w.sum() else 0.0


def intent_metrics(gold: list[str], pred: list[str], alt: list[str | None]) -> dict:
    labels = sorted(set(gold) | set(pred))
    n_strict = sum(g == p for g, p in zip(gold, pred))
    n_lenient = sum(
        p == g or (a is not None and p == a) for g, p, a in zip(gold, pred, alt)
    )
    return {
        "n": len(gold),
        "accuracy_strict": round(n_strict / len(gold), 4),
        "accuracy_strict_ci95": wilson(n_strict, len(gold)),
        "accuracy_lenient": round(n_lenient / len(gold), 4),
        "macro_f1": round(float(f1_score(gold, pred, average="macro", labels=labels, zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(gold, pred, average="weighted", labels=labels, zero_division=0)), 4),
        "per_class": {
            k: {
                "precision": round(v["precision"], 3),
                "recall": round(v["recall"], 3),
                "f1": round(v["f1-score"], 3),
                "support": int(v["support"]),
            }
            for k, v in classification_report(
                gold, pred, labels=labels, output_dict=True, zero_division=0
            ).items()
            if k in labels
        },
    }


def routing_metrics(
    gold: list[str], pred: list[str], weights: list[float]
) -> dict:
    """`escalate` is the positive class: missing one is the expensive error."""
    tp = sum(g == "escalate" and p == "escalate" for g, p in zip(gold, pred))
    fn = sum(g == "escalate" and p == "auto" for g, p in zip(gold, pred))
    fp = sum(g == "auto" and p == "escalate" for g, p in zip(gold, pred))
    tn = sum(g == "auto" and p == "auto" for g, p in zip(gold, pred))
    n = len(gold)
    auto_n = tp_auto = 0
    for g, p in zip(gold, pred):
        if p == "auto":
            auto_n += 1
            tp_auto += int(g == "auto")
    unsafe = [g == "escalate" and p == "auto" for g, p in zip(gold, pred)]
    return {
        "n": n,
        "confusion": {"tp_escalate": tp, "fn_missed_escalation": fn, "fp_over_escalate": fp, "tn_auto": tn},
        "escalation_recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "escalation_recall_ci95": wilson(tp, tp + fn),
        "escalation_precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "auto_coverage": round(auto_n / n, 4),
        "auto_precision": round(tp_auto / auto_n, 4) if auto_n else None,
        "unsafe_auto_rate": round(sum(unsafe) / n, 4),
        "unsafe_auto_rate_ci95": wilson(sum(unsafe), n),
        "unsafe_auto_rate_weighted": round(weighted_rate(unsafe, weights), 4),
        "route_agreement": round(sum(g == p for g, p in zip(gold, pred)) / n, 4),
        "route_kappa": round(float(cohen_kappa_score(gold, pred)), 4) if len(set(pred)) > 1 else 0.0,
    }


def quadratic_weighted_kappa(a: list[int], b: list[int], k: int = 5) -> float:
    a = [int(x) for x in a]
    b = [int(x) for x in b]
    obs = np.zeros((k, k))
    for x, y in zip(a, b):
        obs[x - 1, y - 1] += 1
    ha = np.bincount(np.array(a) - 1, minlength=k)
    hb = np.bincount(np.array(b) - 1, minlength=k)
    exp = np.outer(ha, hb) / len(a)
    w = np.array([[(i - j) ** 2 for j in range(k)] for i in range(k)]) / (k - 1) ** 2
    denom = (w * exp).sum()
    return float(1 - (w * obs).sum() / denom) if denom else 0.0


def spearman(a: list[float], b: list[float]) -> float:
    def rank(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for t in range(i, j + 1):
                r[order[t]] = avg
            i = j + 1
        return r

    ra, rb = rank(list(a)), rank(list(b))
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return round(num / den, 4) if den else 0.0


def distribution(xs: list) -> dict:
    c = Counter(xs)
    return {k: c[k] for k in sorted(c, key=lambda x: (-c[x], str(x)))}
