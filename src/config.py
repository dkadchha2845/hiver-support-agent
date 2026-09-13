"""Central configuration. Everything tunable lives here or in .env."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
GOLDEN = DATA / "golden"
RESULTS = ROOT / "results"
PROMPTS = ROOT / "prompts"
CACHE = RESULTS / "llm_cache"

for _d in (RAW, PROCESSED, GOLDEN, RESULTS, CACHE):
    _d.mkdir(parents=True, exist_ok=True)


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


# ---------------------------------------------------------------- dataset
TWCS_CSV = RAW / "twcs.csv"
# Canonical source is Kaggle (thoughtvector/customer-support-on-twitter).
# HF mirror of the identical file, used when no Kaggle credentials are present.
TWCS_MIRROR_URL = (
    "https://huggingface.co/datasets/SunidhiSriram/twcs/resolve/main/twcs.csv"
)
BRAND = _env("BRAND", "SpotifyCares")

# ---------------------------------------------------------------- splits
SEED = 20250913
# Time-ordered split: history (what the agent may retrieve from) vs eval pool.
# Prevents the agent from retrieving the very thread it is being asked about.
HISTORY_FRACTION = 0.70

# ---------------------------------------------------------------- retrieval
RETRIEVAL_K = 4
RETRIEVAL_MIN_SIM = 0.05

# ---------------------------------------------------------------- llm
AGENT_PROVIDER = _env("AGENT_PROVIDER", "ollama")
AGENT_MODEL = _env("AGENT_MODEL", "qwen2.5:7b-instruct")
JUDGE_PROVIDER = _env("JUDGE_PROVIDER", "ollama")
JUDGE_MODEL = _env("JUDGE_MODEL", "llama3.1:8b-instruct-q4_K_M")
OLLAMA_HOST = _env("OLLAMA_HOST", "http://localhost:11434")
LLM_TIMEOUT = int(_env("LLM_TIMEOUT", "240"))
LLM_MAX_RETRIES = int(_env("LLM_MAX_RETRIES", "3"))
AGENT_TEMPERATURE = float(_env("AGENT_TEMPERATURE", "0.0"))
JUDGE_TEMPERATURE = float(_env("JUDGE_TEMPERATURE", "0.0"))

# ---------------------------------------------------------------- eval
GOLDEN_TARGET_N = 200
JUDGE_HUMAN_SUBSET_N = 60
SEND_READY_THRESHOLD = 4  # min score on every rubric dimension to count as send-ready
