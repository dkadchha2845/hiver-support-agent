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
