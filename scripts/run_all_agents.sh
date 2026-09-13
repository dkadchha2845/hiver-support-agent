#!/usr/bin/env bash
# S3 is the headline system and runs on all 200 golden units.
# The two ablations run on the first 100 (the golden file order is seeded and
# shuffled, so that is a random half). Reported as n=100 in the tables.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="./.venv/bin/python"
export PYTHONPATH=src
W=${WORKERS:-2}
$PY src/run_agent.py --name S3_agent                 --workers "$W"
$PY src/run_agent.py --name S2_agent_noretrieval     --workers "$W" --no-retrieval --limit 100
$PY src/run_agent.py --name S4_agent_llmrouter       --workers "$W" --router llm    --limit 100
echo "ALL AGENT RUNS DONE"
