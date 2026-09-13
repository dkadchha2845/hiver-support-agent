## 2. The system and the harness

### 2.1 The agent: LLM for perception, code for policy

**① Perception (LLM).** One call returns the intent (10 codes, `data/taxonomy.yaml`), a
confidence band, and 10 boolean risk signals (`account_specific`, `money_involved`,
`security_or_privacy`, `legal_or_regulatory`, `human_requested`, `churn_threat`,
`safety_or_wellbeing`, `non_english`, `abusive_or_public_escalation`, `vague_no_detail`).
The prompt carries the same codebook the annotator used.

**② Policy (~25 lines of Python).** `auto` requires all of: intent auto-eligible, no hard risk
signal, confidence not `low`. Otherwise escalate, with the failing condition returned as the
reason ("risk signal `money_involved`"). Auditable, unit tested, and the risk appetite is a
YAML edit. It also makes failure attribution possible — §4 F2 exists only because of it.
Ablation S4 measures what happens when the LLM decides instead.

**③ Generation (LLM).** A second call drafts the reply given the four most similar past
messages Spotify actually answered, real replies attached, under the rule that every
commitment must appear in that evidence.

**Grounding store.** TF-IDF over word 1–2-grams plus `char_wb` 3–5-grams, fitted only on
the 70% time-ordered history split; a unit can never retrieve its own conversation. Median
best-neighbour similarity on the golden set is
{{F:leakage_check.json:nearest_neighbour_similarity_on_golden.median}} and only
{{FP:leakage_check.json:nearest_neighbour_similarity_on_golden.share_above_090_near_duplicate}}
of units have a near-verbatim twin, so this is analogy, not lookup.

### 2.2 The golden set (200 hand-labelled units)

Held-out pool de-duplicated to {{F:data_profile.json:eval_pool_deduped}} answered turns,
partitioned into 7 keyword strata (first match wins, so partition and weights are exact),
with quotas per stratum: 120 `general`, 18 `money`, 16 `security`, 16 `churn_human`, 10 each
`safety_legal`/`non_english`/`vague_short`. Every unit carries
`weight = stratum population / sampled`, which is what makes the reweighted column possible.
Frame: `data/golden/frame_report.json`; protocol: `data/golden/LABELLING.md`.

One annotator (me), seeing only the customer message and up to four earlier turns.
**Spotify's actual reply was withheld by the tooling** — otherwise my "should this
escalate?" label would have collapsed into "did Spotify ask for a DM?", and I would be
evaluating the agent against a proxy for itself. Per unit: gold intent, an acceptable
alternative intent, gold route, the single escalation driver, a `hard` flag, a note.

Two signal definitions were tightened after ~100 units showed they were too loose
(`money_involved` no longer fires on general price questions; `churn_threat` no longer
fires on routine cancellation admin or jokes), and the affected units were re-labelled.
Documented with indices in `LABELLING.md`.

**{{F:metrics.json:golden_set.n_flagged_hard}} of 200 units are flagged `hard`** — 23%.
That is the most honest statistic here: a quarter of real support messages have no obvious
right answer, so a model scoring 100% would mean my labels were wrong.

### 2.3 The judge

Pointwise, blind, four dimensions on 1–5 against written anchors (`prompts/judge.txt`):
**groundedness**, **resolution**, **tone**, **safety**, plus extraction of the phrases it
considers unsupported (which is what makes §4 F4 possible). Candidates from all systems are
pooled and shuffled; the prompt never names the system, including for Spotify's own replies.

`send_ready` is **not** the judge's boolean. It is `min(all four) >= 4`, computed in code —
a policy knob I can defend rather than a mood. The judge's own `send_as_is` is reported
alongside and is systematically looser.

The judge is `llama3.1:8b`, a different family from the `qwen2.5:7b` agent, plus three
further passes (temperature, same-family, reference-shown) whose only purpose is to measure
how much of the headline is the judge rather than the agent.

### 2.4 Baselines

| | intent | routing | reply |
|---|---|---|---|
| **B0 trivial** | majority class | one fixed decision, reported both ways | one canned "DM us" line |
| **B1 simple** | TF-IDF + logistic regression | keyword lexicon | verbatim nearest-neighbour Spotify reply |
| **S2 ablation** | LLM | same policy | LLM with **no** evidence |
| **S4 ablation** | LLM | **LLM** decides | LLM with evidence |
| **S3 agent** | LLM | policy | LLM with evidence |
| **HUMAN** | – | – | the reply Spotify actually sent |

B0 and B1 are fitted with 5-fold cross-validation *on the golden labels*; the LLM systems
are zero-shot and never see one. The baselines are deliberately allowed to cheat.
