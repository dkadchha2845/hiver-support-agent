#!/usr/bin/env bash
# Fetch the raw Kaggle dataset (thoughtvector/customer-support-on-twitter).
# Prefers the Kaggle CLI when credentials exist; otherwise pulls the byte-identical
# mirror of twcs.csv hosted on the Hugging Face Hub (no account needed).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw
TARGET=data/raw/twcs.csv
EXPECTED_BYTES=516508641

if [ -f "$TARGET" ] && [ "$(wc -c < "$TARGET" | tr -d ' ')" = "$EXPECTED_BYTES" ]; then
  echo "twcs.csv already present and complete."; exit 0
fi

if command -v kaggle >/dev/null 2>&1 && [ -f "${KAGGLE_CONFIG_DIR:-$HOME/.kaggle}/kaggle.json" ]; then
  echo "Downloading via Kaggle CLI..."
  kaggle datasets download -d thoughtvector/customer-support-on-twitter -p data/raw --unzip
else
  echo "No Kaggle credentials found; using the Hugging Face mirror (~516 MB)..."
  curl -L --retry 5 --retry-delay 3 -C - -o "$TARGET" \
    "https://huggingface.co/datasets/SunidhiSriram/twcs/resolve/main/twcs.csv"
fi
ls -l "$TARGET"
