"""Tests for the parts that fail silently: threading, weights, metrics, parsing."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import data_prep  # noqa: E402
import metrics  # noqa: E402
import taxonomy  # noqa: E402
from llm import _parse_json_loose  # noqa: E402
from retrieval import HistoryIndex  # noqa: E402


def _frame(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "tweet_id",
            "author_id",
            "inbound",
            "created_at",
            "text",
            "in_response_to_tweet_id",
        ],
    )


def test_conversation_ids_join_reply_chains():
    df = _frame(
        [
            [1, "115", True, "Tue Oct 31 22:10:47 +0000 2017", "help", float("nan")],
            [2, "BrandX", False, "Tue Oct 31 22:11:47 +0000 2017", "hi", 1.0],
            [3, "115", True, "Tue Oct 31 22:12:47 +0000 2017", "thanks", 2.0],
            [9, "999", True, "Tue Oct 31 22:13:47 +0000 2017", "unrelated", float("nan")],
        ]
    )
    out = data_prep.assign_conversation_ids(df)
    assert out.loc[0, "conversation_id"] == out.loc[2, "conversation_id"]
    assert out.loc[3, "conversation_id"] != out.loc[0, "conversation_id"]


def test_units_only_count_answered_turns_and_track_position():
    df = _frame(
        [
            [1, "115", True, "Tue Oct 31 22:10:47 +0000 2017", "@BrandX help me", float("nan")],
            [2, "BrandX", False, "Tue Oct 31 22:11:47 +0000 2017", "@115 sure, DM us", 1.0],
            [3, "115", True, "Tue Oct 31 22:12:47 +0000 2017", "@BrandX still broken", 2.0],
        ]
    )
    threads = data_prep.build_threads(data_prep.assign_conversation_ids(df), "BrandX")
    units = data_prep.build_units(threads)
    assert len(units) == 1, "the unanswered final customer turn must not become a unit"
    assert units[0]["position"] == 0
    assert units[0]["brand_asked_for_dm"] is True


def test_clean_text_masks_pii_but_keeps_the_brand_handle():
    out = data_prep.clean_text(
        "@115712 ping me at a@b.com or 07700900123 http://x.co @BrandX", "BrandX"
    )
    assert "@customer" in out and "@BrandX" in out
    assert "a@b.com" not in out and "07700900123" not in out and "http" not in out


def test_retrieval_excludes_the_source_conversation():
    units = [
        {"unit_id": "1-1", "conversation_id": 1, "customer_message": "my app keeps crashing on android", "brand_reply": "which version?", "position": 0, "brand_asked_for_dm": False},
        {"unit_id": "2-2", "conversation_id": 2, "customer_message": "app crashing on android phone", "brand_reply": "try a reinstall", "position": 0, "brand_asked_for_dm": False},
    ]
    idx = HistoryIndex(units)
    hits = idx.search("app keeps crashing on android", k=2, exclude_conversation=1)
    assert [h.conversation_id for h in hits] == [2]


def test_wilson_interval_brackets_the_point_estimate():
    lo, hi = metrics.wilson(78, 200)
    assert lo < 0.39 < hi and hi - lo > 0.05


def test_weighted_rate_respects_stratum_weights():
    # one rare-stratum hit with weight 1 must not outweigh 9 common misses at weight 10
    assert metrics.weighted_rate([True] + [False] * 9, [1.0] + [10.0] * 9) == pytest.approx(1 / 91)


def test_unsafe_auto_rate_counts_only_missed_escalations():
    gold = ["escalate", "escalate", "auto", "auto"]
    pred = ["auto", "escalate", "auto", "escalate"]
    m = metrics.routing_metrics(gold, pred, [1.0] * 4)
    assert m["unsafe_auto_rate"] == 0.25
    assert m["escalation_recall"] == 0.5
    assert m["confusion"]["fp_over_escalate"] == 1


def test_lenient_accuracy_accepts_the_second_label():
    m = metrics.intent_metrics(["how_to"], ["feature_request"], ["feature_request"])
    assert m["accuracy_strict"] == 0.0 and m["accuracy_lenient"] == 1.0


def test_json_parser_survives_fenced_and_trailing_prose():
    assert _parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json_loose('sure! {"a": {"b": 2}} hope that helps') == {"a": {"b": 2}}
    assert _parse_json_loose("not json at all") is None


def test_every_taxonomy_intent_has_a_policy_and_examples():
    for intent in taxonomy.load()["intents"]:
        assert intent["policy"] in {"auto_eligible", "always_escalate"}
        assert intent["examples"] and intent["definition"]
    assert taxonomy.auto_eligible() & taxonomy.escalate_always() == set()


def test_golden_set_is_complete_and_schema_clean():
    path = ROOT / "data" / "golden" / "golden_set.jsonl"
    rows = [json.loads(l) for l in path.open()]
    assert 150 <= len(rows) <= 250
    assert len({r["unit_id"] for r in rows}) == len(rows)
    valid = set(taxonomy.intent_names())
    for r in rows:
        assert r["gold_intent"] in valid
        assert r["gold_route"] in {"auto", "escalate"}
        assert r["weight"] > 0
        if r["gold_route"] == "escalate":
            assert r["gold_driver"] != "none"


def test_signature_detector_catches_real_spotify_sign_offs_only_at_the_end():
    import evaluate

    assert evaluate.SIGNATURE_RE.search("Hey! Try a reinstall /JX")
    assert evaluate.SIGNATURE_RE.search("We'll take a look backstage /NQ <url>")
    assert not evaluate.SIGNATURE_RE.search("Head to https://x.co/A and tap Update")
    assert not evaluate.SIGNATURE_RE.search("No sign off here at all")


def test_handoff_detector_distinguishes_a_handoff_from_a_fix_attempt():
    import evaluate

    assert evaluate.HANDOFF_RE.search("Can you DM us your account's email address?")
    assert evaluate.HANDOFF_RE.search("A human teammate will pick this up")
    assert not evaluate.HANDOFF_RE.search(
        "Try restarting your device and clearing the cache"
    )


def test_golden_weights_reproduce_the_stratum_populations():
    """weight * sampled should recover the stratum population from frame_report.json."""
    frame = json.loads((ROOT / "data" / "golden" / "frame_report.json").read_text())
    rows = [json.loads(l) for l in (ROOT / "data" / "golden" / "golden_set.jsonl").open()]
    counts: dict[str, int] = {}
    weights: dict[str, float] = {}
    for r in rows:
        counts[r["stratum"]] = counts.get(r["stratum"], 0) + 1
        weights[r["stratum"]] = r["weight"]
    for stratum, meta in frame["strata"].items():
        assert counts[stratum] == meta["sampled"]
        assert weights[stratum] * counts[stratum] == pytest.approx(
            meta["population"], rel=1e-3
        )


def test_escalate_always_intents_cannot_be_auto_routed_by_the_policy():
    """The policy must never return `auto` for an intent marked always_escalate."""
    from agent import SupportAgent

    agent = SupportAgent(None, "BrandX", use_retrieval=False)
    for intent in sorted(taxonomy.escalate_always()):
        triage = {
            "intent": intent,
            "confidence": "high",
            "signals": {s["key"]: False for s in taxonomy.risk_signals()},
        }
        route, reason = agent.decide_route(triage, [])
        assert route == "escalate", f"{intent} was auto-routed: {reason}"


def test_any_hard_risk_signal_forces_escalation_even_for_a_safe_intent():
    from agent import SupportAgent

    agent = SupportAgent(None, "BrandX", use_retrieval=False)
    hard = [s["key"] for s in taxonomy.risk_signals() if s.get("hard_escalate")]
    safe_intent = sorted(taxonomy.auto_eligible())[0]
    for key in hard:
        signals = {s["key"]: False for s in taxonomy.risk_signals()}
        signals[key] = True
        route, reason = agent.decide_route(
            {"intent": safe_intent, "confidence": "high", "signals": signals}, []
        )
        assert route == "escalate", f"{key} did not force escalation"
        assert key in reason
