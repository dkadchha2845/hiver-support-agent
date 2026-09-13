# A support agent for @SpotifyCares — and an honest account of how good it is

Built for the Hiver SDE intern take-home. The system classifies an incoming customer
tweet, drafts a reply grounded in how Spotify has actually handled similar messages,
and decides whether to auto-send or hand it to a human with a stated reason.

The agent is the small part of this repo. Most of it is the harder part: proving whether the
agent works, and then attacking my own headline number — including one place where auditing
my own labels erased the result I was most pleased with (REPORT §4 F1).

**Everything runs on free, local, open-weights models (`qwen2.5:7b-instruct` for the
agent, `llama3.1:8b` for the judge, both via Ollama). No API key, no account, no
spend.** Hosted free tiers (Groq / Gemini / OpenRouter) are supported by setting two
env vars — see `.env.example`.

<!-- HEADLINE -->
### Headline

| | agent (S3) | copy-paste baseline (B1) | trivial (B0) |
|---|---|---|---|
| **Trustworthy Automation Rate** — send-ready *and* correctly auto-routed | **10.5%** (14.8% reweighted) | **21.0%** (27.5%) | 0.0% |
| **Unsafe auto-handle rate** — judge-independent, gates deployment | **6.5%** [3.8%, 10.8%] | 14.0% | 0.0% |
| Escalation recall | **86.7%** | 71.4% | 100% (escalates everything) |
| Intent macro-F1 / strict acc / lenient acc | **0.67** / 71.0% / 83.0% | 0.295 / 41.0% / - | 0.031 |
| Judge send-ready rate | 25.0% | 50.5% | 10.0% |

Spotify's own replies, scored blind by the same judge: **19.0%** send-ready.

**The agent loses to the copy-paste baseline on my own headline metric, and wins on every
axis the judge does not touch.** That is the central finding, not a footnote — see
[REPORT.md](REPORT.md) §3.3 and §5.1-5.3 for why I believe the judge is wrong about B1 and
why that is a flaw in a rubric I wrote. The judge's false-pass rate against my own blind
hand-scoring is **20.8%**, and it disagrees with itself on **41.7%** of replies when
resampled.
<!-- /HEADLINE -->

---

## Reproduce the headline numbers in under 15 minutes

All model outputs are committed (`results/preds_*.jsonl`, `results/judge_*.jsonl`), so the
default path regenerates every number in the report **without generating a single token**.
The 1,810-file LLM response cache is committed too — it is not needed for `make repro`, but it
means `make agents` and `make judge` replay the exact same generations for free if you want to
verify them. A clone is about 9 MB.

```bash
git clone https://github.com/dkadchha2845/hiver-support-agent.git
cd hiver-support-agent
make setup      # venv + 7 pinned deps
make repro      # recompute every metric, table, and the report itself
make test       # 16 unit tests on the parts that fail silently
```

Measured on a fresh clone (Apple M5, Python 3.9): clone 2s, `setup` 14s, `repro` 32s,
`test` 1s — **49 seconds total**. `git status` is clean afterwards, i.e. every regenerated
artefact (`results/metrics.json`, `results/tables.md`, `REPORT.md`, and the README headline
block) comes back **byte-identical** to what is committed. That is the actual reproducibility
claim: not "it runs", but "it produces the same numbers".

`make repro` regenerates `results/metrics.json`, `tables.md`, `failures.json`,
`judge_agreement_primary.json`, `judge_sensitivity.json`, `name_audit.json`,
`leakage_check.json` and `data_profile.json` — then **rebuilds `REPORT.md` from them** via
`scripts/build_report.py`. Every figure in the report is a placeholder resolved against those
artefacts, so no number in the prose can drift from the run that produced it; the build fails
loudly if a placeholder cannot be resolved.

### Re-running generation from scratch (optional, hours not minutes)

```bash
make data-download   # twcs.csv, ~516MB, Kaggle CLI if you have creds else the HF mirror
make data            # 2.8M tweets -> 28,280 SpotifyCares threads -> 41,383 eval units
make golden          # rebuild the stratified frame and join the hand labels
make baselines       # B0 trivial, B1 simple, and Spotify's own replies
make agents          # S3 on 200 units + 2 ablations on 100  (~50 min, 2 workers, M-series)
make judge           # 4 judge passes, ~1,140 scored replies  (~2 h)
make eval            # metrics, tables, failure analysis
```

You need `ollama serve` running with the two models pulled:

```bash
ollama pull qwen2.5:7b-instruct && ollama pull llama3.1:8b-instruct-q4_K_M
```

---

## Try it on one message

```bash
make demo M="I was charged 9.99 twice this month and I never signed up for premium"
```

```
customer   : I was charged 9.99 twice this month and I never signed up for premium
intent     : billing_charge (confidence high)
signals    : ['account_specific', 'money_involved']
route      : ESCALATE  <- risk signal `account_specific`; risk signal `money_involved`;
                          intent `billing_charge` is never auto-handled
reply      : Hey! Can you DM us your account's email address? We'll check what happened.

evidence used for grounding:
  [0.449] @customer i've been charged twice this month for premium???
          -> Hey! Can you DM us your account's email address? We'll see what we can suggest /CB
  [0.449] yo @SpotifyCares you charged me for premium when i never signed up wtf
          -> Hi! Help's here. Just to check, do you have an account? If so, could you DM us...
```

The routing reason is generated by the policy layer, not the model, so it is always a true
statement about why the decision was made.

---

## What is in here

| path | what it is |
|---|---|
| [REPORT.md](REPORT.md) / [REPORT.pdf](REPORT.pdf) | the report (6 pages): framing, results, failure analysis, **what is misleading about my headline number**, next steps. `make pdf` regenerates the PDF |
| [DECISIONS.md](DECISIONS.md) | 15 non-obvious decisions and why |
| `data/taxonomy.yaml` | the intent codebook + risk-signal definitions, induced from the data |
| `data/golden/golden_set.jsonl` | **200 hand-labelled units** with stratum, sampling weight, gold intent, gold route, escalation driver, difficulty flag and annotator note |
| `data/golden/frame_report.json` | the sampling frame: stratum populations, quotas, exact weights |
| `data/golden/LABELLING.md` | how the golden set was sampled and labelled, including what went wrong |
| `data/golden/human_judge_scores.jsonl` | 60 replies scored by hand, blind to which system wrote them |
| `data/golden/human_judge_scores_name_adjusted.jsonl` | the same, with 7 annotation errors that `src/name_audit.py` caught in my own scoring |
| `src/name_audit.py` | the script that found the error in my own labels — see REPORT §4 F1 |
| `src/leakage_check.py` | temporal-bleed and near-duplicate-retrieval integrity checks |
| `src/judge_sensitivity.py` | how far the headline moves under three alternative judges |
| `src/agent.py` | triage → deterministic routing policy → grounded draft |
| `src/retrieval.py` | TF-IDF word+char index over Spotify's historical answered messages |
| `src/judge.py`, `prompts/judge.txt` | the LLM-as-judge rubric with per-score anchors |
| `src/judge_agreement.py` | judge vs human: QWK, bias, false-pass rate, system-ranking agreement |
| `src/metrics.py` | every metric, including Wilson intervals and stratum reweighting |
| `src/failure_analysis.py` | pulls the concrete failures the report quotes |
| `results/` | all model outputs, judge scores, metrics and the LLM response cache |
| `tests/` | 16 unit tests on the parts that fail silently, two of which assert the escalation policy's invariants |

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
  (`thoughtvector/customer-support-on-twitter`), CC BY-NC-SA 4.0 — see
  [DATA_LICENSE.md](DATA_LICENSE.md) for what this repo redistributes and how PII is masked. `scripts/download_data.sh`
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

- 200 golden units means ±7pp confidence intervals on every rate. Real differences smaller
  than that are not visible here, and I do not claim them.
- The two ablations (S2 no-retrieval, S4 LLM-router) ran on 100 of the 200 units to fit a
  laptop compute budget. `results/metrics.json` → `matched_ablation_comparison` compares them
  against the headline system on exactly those units; never read them against the n=200 rows.
- One annotator (me). The second-pass agreement number in Table 7 is contaminated by
  memory and should be read as worthless — see report §5.
- Single brand, single language for the auto-handled path, 2017 data.
