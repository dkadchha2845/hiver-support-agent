"""Loader + helpers for the intent taxonomy (the codebook)."""
from __future__ import annotations

from functools import lru_cache

import yaml

from config import DATA

TAXONOMY_PATH = DATA / "taxonomy.yaml"


@lru_cache(maxsize=1)
def load() -> dict:
    return yaml.safe_load(TAXONOMY_PATH.read_text())


def intent_names() -> list[str]:
    return [i["name"] for i in load()["intents"]]


def escalate_always() -> set[str]:
    return {i["name"] for i in load()["intents"] if i.get("policy") == "always_escalate"}


def auto_eligible() -> set[str]:
    return {i["name"] for i in load()["intents"] if i.get("policy") == "auto_eligible"}


def codebook_block() -> str:
    """Compact rendering of the taxonomy for prompt injection."""
    lines = []
    for i in load()["intents"]:
        lines.append(
            f"- {i['name']}: {i['definition']} "
            f"(e.g. \"{i['examples'][0]}\")"
        )
    return "\n".join(lines)


def risk_signals() -> list[dict]:
    return load()["risk_signals"]
