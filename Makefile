PY := ./.venv/bin/python
export PYTHONPATH := src

.PHONY: help setup data-download data golden baselines agents judge eval agreement all repro test clean

help:
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | column -t -s "$$(printf '\t')"

setup:            ## create the venv and install pinned deps
	python3 -m venv .venv && $(PY) -m pip install -q -r requirements.txt

data-download:    ## fetch twcs.csv (~516MB, Kaggle or HF mirror)
	bash scripts/download_data.sh

data:             ## rebuild brand threads + eval units from twcs.csv
	$(PY) src/data_prep.py build

golden:           ## rebuild the stratified frame and join the hand labels
	$(PY) src/golden.py sample
	$(PY) src/golden.py verify
	$(PY) src/golden.py build

baselines:        ## B0 trivial, B1 simple, and the brand's own replies
	$(PY) src/baselines.py

agents:           ## run the LLM agent + both ablations (~75 min on an M-series Mac)
	bash scripts/run_all_agents.sh

judge:            ## score every system's replies with the LLM judge
	bash scripts/run_all_judges.sh

eval:             ## recompute every metric from committed predictions + judge scores
	$(PY) src/evaluate.py
	$(PY) src/data_profile.py
	$(PY) src/leakage_check.py
	$(PY) src/annotator_agreement.py
	$(PY) src/judge_agreement.py score --tag primary
	$(PY) src/judge_sensitivity.py
	$(PY) src/failure_analysis.py
	$(PY) src/report_tables.py

repro:            ## THE 15-MINUTE PATH: metrics + report tables from committed artefacts
	$(MAKE) eval

all:              ## everything from scratch, including generation (several hours)
	$(MAKE) data golden baselines agents judge eval

test:             ## unit tests for the pieces that are easy to get silently wrong
	$(PY) -m pytest tests -q

clean:
	rm -rf results/*.json results/*.jsonl

demo:             ## run the agent on one message: make demo M="I was charged twice"
	$(PY) src/demo.py "$(M)"

profile:          ## descriptive stats about the brand's inbox (cited in the report)
	$(PY) src/data_profile.py
	$(PY) src/leakage_check.py

failures:         ## dump concrete failure examples the report quotes
	$(PY) src/failure_analysis.py
