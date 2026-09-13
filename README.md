# A support agent for @SpotifyCares — and an honest account of how good it is

Built for the Hiver SDE intern take-home. The system classifies an incoming customer
tweet, drafts a reply grounded in how Spotify has actually handled similar messages,
and decides whether to auto-send or hand it to a human with a stated reason.

The system took a day. Most of this repo is the part that took longer: proving whether
it works, and then attacking my own headline number.

**Everything runs on free, local, open-weights models (`qwen2.5:7b-instruct` for the
agent, `llama3.1:8b` for the judge, both via Ollama). No API key, no account, no
spend.** Hosted free tiers (Groq / Gemini / OpenRouter) are supported by setting two
env vars — see `.env.example`.

<!-- HEADLINE -->

---

## Reproduce the headline numbers in under 15 minutes

Every LLM call made in this project is cached on disk by a content hash, and the cache
and all model outputs are committed. So the default path regenerates every number in
the report **without generating a single new token**.

```bash
make setup      # venv + 6 pinned deps, ~60s
make repro      # recompute every metric and table from committed artefacts, ~30s
make test       # 11 unit tests on the parts that fail silently, ~2s
```

`make repro` writes `results/metrics.json`, `results/tables.md`,
`results/judge_agreement_primary.json` and `results/failures.json`. The tables in
[REPORT.md](REPORT.md) are those files; nothing in the report is typed by hand.

### Re-running generation from scratch (optional, hours not minutes)

```bash
make data-download   # twcs.csv, ~516MB, Kaggle CLI if you have creds else the HF mirror
make data            # 2.8M tweets -> 28,280 SpotifyCares threads -> 41,383 eval units
make golden          # rebuild the stratified frame and join the hand labels
make baselines       # B0 trivial, B1 simple, and Spotify's own replies
make agents          # 3 agent variants x 200 units      (~8 min each with 4 workers)
make judge           # 4 judge passes, 1,700 scored replies
make eval            # metrics, tables, failure analysis
```

You need `ollama serve` running with the two models pulled:

```bash
ollama pull qwen2.5:7b-instruct && ollama pull llama3.1:8b-instruct-q4_K_M
```

---

## What is in here

| path | what it is |
|---|---|
| [REPORT.md](REPORT.md) | the report: framing, results, failure analysis, **what is misleading about my headline number**, next steps |
| [DECISIONS.md](DECISIONS.md) | 15 non-obvious decisions and why |
| `data/taxonomy.yaml` | the intent codebook + risk-signal definitions, induced from the data |
| `data/golden/golden_set.jsonl` | **200 hand-labelled units** with stratum, sampling weight, gold intent, gold route, escalation driver, difficulty flag and annotator note |
| `data/golden/frame_report.json` | the sampling frame: stratum populations, quotas, exact weights |
| `data/golden/human_judge_scores.jsonl` | 60 replies scored by hand, blind to which system wrote them |
| `src/agent.py` | triage → deterministic routing policy → grounded draft |
| `src/retrieval.py` | TF-IDF word+char index over Spotify's historical answered messages |
| `src/judge.py`, `prompts/judge.txt` | the LLM-as-judge rubric with per-score anchors |
| `src/judge_agreement.py` | judge vs human: QWK, bias, false-pass rate, system-ranking agreement |
| `src/metrics.py` | every metric, including Wilson intervals and stratum reweighting |
| `src/failure_analysis.py` | pulls the concrete failures the report quotes |
| `results/` | all model outputs, judge scores, metrics and the LLM cache |

## Pipeline

```
twcs.csv (2.8M tweets)
  └─ data_prep.py      union-find over reply edges → 28,280 threads → 41,383 answered
                       customer turns; PII masked; thread-level time-ordered split
                       70% history (retrievable) / 30% eval pool
      ├─ retrieval.py  TF-IDF index over history only; a unit can never retrieve
      │                its own conversation
      ├─ golden.py     stratified sample of the pool → 200 units → hand labels
      └─ agent.py      ① LLM: intent + 10 risk signals
                       ② code: deterministic escalation policy
                       ③ LLM: draft constrained to retrieved evidence
          └─ judge.py  blind LLM-as-judge, 4 dimensions × 1-5 + unsupported-claim extraction
              └─ evaluate.py / judge_agreement.py / failure_analysis.py
```

## Borrowed, and cited

- **Dataset**: *Customer Support on Twitter*, Stuart Axelbrooke, Kaggle
  (`thoughtvector/customer-support-on-twitter`), CC BY-NC-SA 4.0. `scripts/download_data.sh`
  pulls it via the Kaggle CLI when credentials exist, otherwise from a byte-identical
  Hugging Face mirror so a grader with no Kaggle account can still run it.
- **Models**: `Qwen2.5-7B-Instruct` (Alibaba, Apache-2.0) and `Llama-3.1-8B-Instruct`
  (Meta, Llama 3.1 Community License), served locally by [Ollama](https://ollama.com).
- **Libraries**: `scikit-learn` (TF-IDF, logistic regression, `StratifiedKFold`,
  `cohen_kappa_score`, `classification_report`), `pandas`, `numpy`, `PyYAML`,
  `requests`, `pytest`.
- **Methods taken from the literature rather than invented here**: Wilson score
  interval for binomial CIs; Horvitz–Thompson inverse-probability weighting for the
  stratified estimate; quadratic-weighted Cohen's kappa for ordinal rater agreement
  (implemented in `src/metrics.py` from the definition, ~10 lines); the
  self-preference-bias and position-bias concerns in LLM-as-judge evaluation, from the
  *Judging LLM-as-a-Judge / MT-Bench* line of work (Zheng et al., 2023) — that paper is
  why the judge here is a different model family from the agent and why I measured the
  same-family delta instead of assuming it away.
- **AI coding assistance** was used throughout, as the brief permits. Every design
  decision in `DECISIONS.md` is one I can defend and change live; the labels in
  `data/golden/` were written by hand, not generated.

## Known rough edges

- 200 golden units means ±7pp confidence intervals on every rate. Real differences
  smaller than that are not visible here, and I do not claim them.
- One annotator (me). The second-pass agreement number in Table 7 is contaminated by
  memory and should be read as worthless — see report §5.
- Single brand, single language for the auto-handled path, 2017 data.
