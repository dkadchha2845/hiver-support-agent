"""The evaluation harness. Reads predictions + judge scores, writes results/metrics.json.

Headline metric: Trustworthy Automation Rate (TAR).
    TAR = share of ALL golden units where the agent (a) chose to auto-handle,
          (b) gold agrees it was safe to auto-handle, and (c) the judge rated the
          drafted reply send-ready on every rubric dimension.
No trivial baseline can win TAR: escalate-everything scores 0, auto-everything is
punished by (b), and a canned reply is punished by (c).
"""
from __future__ import annotations

import json
from collections import defaultdict

import re

from config import GOLDEN, RESULTS, SEND_READY_THRESHOLD

# Does an escalate-routed draft actually hand off, or does it quietly try to fix the
# problem itself? This is a prompt-compliance bug I found in the failure analysis, and
# it costs nothing to measure in code.
HANDOFF_RE = re.compile(
    r"\b(dm|direct message|human|teammate|team|colleague|specialist|advisor|"
    r"backstage|look into|our friends|pass(ing)? (this|you) on|get back to you)\b",
    re.I,
)
from metrics import (
    distribution,
    intent_metrics,
    routing_metrics,
    weighted_rate,
    wilson,
)

DIMS = ("groundedness", "resolution", "tone", "safety")


def load_golden() -> list[dict]:
    return [json.loads(l) for l in (GOLDEN / "golden_set.jsonl").open()]


def load_preds(system: str) -> dict[str, dict]:
    path = RESULTS / f"preds_{system}.jsonl"
    if not path.exists():
        return {}
    return {json.loads(l)["unit_id"]: json.loads(l) for l in path.open()}


def load_judge(tag: str) -> dict[tuple[str, str], dict]:
    path = RESULTS / f"judge_{tag}.jsonl"
    if not path.exists():
        return {}
    out = {}
    for line in path.open():
        r = json.loads(line)
        out[(r["system"], r["unit_id"])] = r
    return out


def judge_summary(
    golden: list[dict], scores: dict[tuple[str, str], dict], system: str
) -> dict | None:
    rows = [(g, scores[(system, g["unit_id"])]) for g in golden if (system, g["unit_id"]) in scores]
    if not rows:
        return None
    n = len(rows)
    means = {d: round(sum(s[d] for _, s in rows) / n, 3) for d in DIMS}
    ready = [bool(s["send_ready"]) for _, s in rows]
    as_is = [bool(s["send_as_is"]) for _, s in rows]
    weights = [g["weight"] for g, _ in rows]
    return {
        "n_scored": n,
        "mean_scores": means,
        "mean_overall": round(sum(means.values()) / len(DIMS), 3),
        "send_ready_rate": round(sum(ready) / n, 4),
        "send_ready_ci95": wilson(sum(ready), n),
        "send_ready_rate_weighted": round(weighted_rate(ready, weights), 4),
        "judge_send_as_is_rate": round(sum(as_is) / n, 4),
        "pct_with_unsupported_claims": round(
            sum(bool(s["unsupported_claims"]) for _, s in rows) / n, 4
        ),
        "mean_reply_chars": None,
    }


def evaluate_system(
    golden: list[dict],
    system: str,
    judge_tag: str = "primary",
) -> dict | None:
    preds = load_preds(system)
    if not preds:
        return None
    scores = load_judge(judge_tag)
    covered = [g for g in golden if g["unit_id"] in preds]
    out: dict = {"system": system, "n": len(covered)}

    if "intent" in next(iter(preds.values())):
        out["intent"] = intent_metrics(
            [g["gold_intent"] for g in covered],
            [preds[g["unit_id"]]["intent"] for g in covered],
            [g["gold_intent_alt"] for g in covered],
        )
    if "route" in next(iter(preds.values())):
        out["routing"] = routing_metrics(
            [g["gold_route"] for g in covered],
            [preds[g["unit_id"]]["route"] for g in covered],
            [g["weight"] for g in covered],
        )
    if "route" in next(iter(preds.values())):
        esc = [g for g in covered if preds[g["unit_id"]]["route"] == "escalate"]
        if esc:
            complied = sum(
                bool(HANDOFF_RE.search(preds[g["unit_id"]].get("reply", ""))) for g in esc
            )
            out["handoff_compliance"] = {
                "n_escalate_routed": len(esc),
                "mentions_handoff": complied,
                "rate": round(complied / len(esc), 4),
            }

    js = judge_summary(covered, scores, system)
    if js:
        js["mean_reply_chars"] = round(
            sum(len(preds[g["unit_id"]].get("reply", "")) for g in covered) / len(covered), 1
        )
        out["reply_quality"] = js

    # ---- headline composite
    if "route" in next(iter(preds.values())) and js:
        good = []
        for g in covered:
            p = preds[g["unit_id"]]
            s = scores.get((system, g["unit_id"]))
            ok = (
                p["route"] == "auto"
                and g["gold_route"] == "auto"
                and s is not None
                and bool(s["send_ready"])
            )
            good.append(ok)
        out["TAR"] = {
            "rate": round(sum(good) / len(good), 4),
            "ci95": wilson(sum(good), len(good)),
            "rate_weighted": round(
                weighted_rate(good, [g["weight"] for g in covered]), 4
            ),
            "n": len(good),
        }
    return out


def slices(golden: list[dict], system: str, judge_tag: str = "primary") -> dict:
    """Where the headline hides things: openers vs follow-ups, stratum, hard cases."""
    preds = load_preds(system)
    scores = load_judge(judge_tag)
    if not preds:
        return {}

    def block(subset: list[dict]) -> dict:
        subset = [g for g in subset if g["unit_id"] in preds]
        if not subset:
            return {}
        res: dict = {"n": len(subset)}
        if "intent" in next(iter(preds.values())):
            res["intent_strict_acc"] = round(
                sum(preds[g["unit_id"]]["intent"] == g["gold_intent"] for g in subset)
                / len(subset),
                4,
            )
        if "route" in next(iter(preds.values())):
            res["unsafe_auto_rate"] = round(
                sum(
                    g["gold_route"] == "escalate"
                    and preds[g["unit_id"]]["route"] == "auto"
                    for g in subset
                )
                / len(subset),
                4,
            )
        ready = [
            bool(scores[(system, g["unit_id"])]["send_ready"])
            for g in subset
            if (system, g["unit_id"]) in scores
        ]
        if ready:
            res["send_ready_rate"] = round(sum(ready) / len(ready), 4)
        return res

    out = {
        "by_position": {
            "opener": block([g for g in golden if g["position"] == 0]),
            "follow_up": block([g for g in golden if g["position"] > 0]),
        },
        "by_stratum": {
            s: block([g for g in golden if g["stratum"] == s])
            for s in sorted({g["stratum"] for g in golden})
        },
        "by_annotator_difficulty": {
            "clear": block([g for g in golden if not g["hard"]]),
            "flagged_hard": block([g for g in golden if g["hard"]]),
        },
        "by_gold_intent": {
            i: block([g for g in golden if g["gold_intent"] == i])
            for i in sorted({g["gold_intent"] for g in golden})
        },
    }
    return out


def main() -> None:
    golden = load_golden()
    systems = [
        "B0_trivial_escalate_all",
        "B0_trivial_auto_all",
        "B1_simple",
        "S2_agent_noretrieval",
        "S4_agent_llmrouter",
        "S3_agent",
        "HUMAN_brand_reply",
    ]
    results = {}
    for s in systems:
        r = evaluate_system(golden, s)
        if r:
            results[s] = r

    # B0's two routing variants share one reply, so reuse the judged quality.
    if "B0_trivial_escalate_all" in results and "B0_trivial_auto_all" in results:
        src = results["B0_trivial_escalate_all"].get("reply_quality")
        if src and "reply_quality" not in results["B0_trivial_auto_all"]:
            results["B0_trivial_auto_all"]["reply_quality"] = src

    out = {
        "golden_set": {
            "n": len(golden),
            "intent_distribution": distribution([g["gold_intent"] for g in golden]),
            "route_distribution": distribution([g["gold_route"] for g in golden]),
            "escalation_driver_distribution": distribution(
                [g["gold_driver"] for g in golden]
            ),
            "stratum_distribution": distribution([g["stratum"] for g in golden]),
            "position_distribution": distribution(
                ["opener" if g["position"] == 0 else "follow_up" for g in golden]
            ),
            "n_flagged_hard": sum(g["hard"] for g in golden),
            "gold_escalate_rate_on_sample": round(
                sum(g["gold_route"] == "escalate" for g in golden) / len(golden), 4
            ),
            "gold_escalate_rate_weighted": round(
                weighted_rate(
                    [g["gold_route"] == "escalate" for g in golden],
                    [g["weight"] for g in golden],
                ),
                4,
            ),
        },
        "send_ready_definition": (
            f"min(groundedness, resolution, tone, safety) >= {SEND_READY_THRESHOLD}"
        ),
        "systems": results,
        "slices_S3_agent": slices(golden, "S3_agent"),
        "slices_B1_simple": slices(golden, "B1_simple"),
    }
    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out["golden_set"], indent=2))
    for name, r in results.items():
        line = [name]
        if "intent" in r:
            line.append(f"macroF1={r['intent']['macro_f1']}")
        if "routing" in r:
            line.append(f"esc_recall={r['routing']['escalation_recall']}")
            line.append(f"unsafe_auto={r['routing']['unsafe_auto_rate']}")
        if "reply_quality" in r:
            line.append(f"send_ready={r['reply_quality']['send_ready_rate']}")
        if "TAR" in r:
            line.append(f"TAR={r['TAR']['rate']}")
        print("  " + "  ".join(line))


if __name__ == "__main__":
    main()
