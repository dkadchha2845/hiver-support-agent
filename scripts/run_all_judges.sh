#!/usr/bin/env bash
# Four judge passes. The first is the headline; the other three exist to measure how
# much the headline depends on the judge rather than on the agent.
#
# n per pass is a compute budget, not a methodological choice: this all runs on a
# laptop. The headline systems get the full 200; ablations and sensitivity passes get
# a seeded random subset, and every table reports its own n.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="./.venv/bin/python"
export PYTHONPATH=src
W=${WORKERS:-2}

# 1a. primary, full golden set: the three systems the headline comparison rests on.
$PY src/run_judge.py --tag primary_main --workers "$W" \
    --systems S3_agent B1_simple HUMAN_brand_reply

# 1b. primary, 100-unit subset: trivial baseline (its reply is a constant) + ablations.
$PY src/run_judge.py --tag primary_aux --workers "$W" --limit 100 \
    --systems B0_trivial_escalate_all S2_agent_noretrieval S4_agent_llmrouter

# 2. stability: same judge, temperature 0.7 - how far does one sample move it?
$PY src/run_judge.py --tag stability --workers "$W" --systems S3_agent \
    --temperature 0.7 --cache-salt stability --limit 60

# 3. self-preference: judge from the SAME family as the agent. If the agent's score
#    jumps relative to the human reply, the headline is partly family affinity.
$PY src/run_judge.py --tag selfjudge --workers "$W" --provider ollama \
    --model qwen2.5:7b-instruct --systems S3_agent HUMAN_brand_reply --limit 60

# 4. reference-shown: judge also sees the reply the customer really received.
$PY src/run_judge.py --tag withreference --workers "$W" --systems S3_agent \
    --show-reference --cache-salt ref --limit 60

# merge 1a + 1b into the single `primary` file the harness reads
cat results/judge_primary_main.jsonl results/judge_primary_aux.jsonl > results/judge_primary.jsonl
echo "ALL JUDGE PASSES DONE"
