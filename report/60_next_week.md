## 6. What I would do with one more week

Ordered by expected value per day, not by how interesting it is.

**Day 1 — fix the name bug and the handoff bug, then re-measure.** Both are quantified in
§4 and both get *guardrails*, not better prompts, because a guardrail is unit testable. Name
bug: reject any first name in a draft that does not appear in the current thread — a
five-line post-filter that removes the whole class. Handoff bug: if `route == escalate` and
the draft contains no handoff language, fall back to a fixed holding template.

**Day 2 — a second annotator on 80 units.** The biggest hole in this evaluation. Write the
codebook into a labelling guide, hand over 80 stratified units including all
{{F:metrics.json:golden_set.n_flagged_hard}} `hard` ones, compute real inter-annotator
kappa, adjudicate into a v2 golden set. Every number here is conditional on labels only I
have seen, and I cannot fix that alone.

**Day 3 — calibrate the abstention rule that currently does nothing.** Carve a 300-unit dev
slice out of the pool (never the golden set), label it coarsely, and fit both the retrieval
threshold (§5.5) and the confidence band — which currently trusts the model's self-reported
`low`/`medium`/`high` with no evidence those words mean anything. Target a selective
prediction curve so a support lead picks the operating point rather than accepting mine.

**Day 4 — add the `clarify` tier.** The biggest coverage win available. `other_unclear` and
low-confidence cases currently go to a human, but §4 F5 shows many need only "what's
happening exactly, and on which device?". A third routing action makes no commitments, so it
adds almost no risk. Gate it hard: no clarify if any money/security/legal signal fires, and
one clarify then escalate.

**Day 5 — fix the judge, which is now the weakest component.** §3.3 showed the rubric ranks a
copy-paste baseline first, so: add a `relevance` dimension ("does this answer *this* question")
and make `groundedness` conditional on it; keep the copy-paste baseline permanently in the
comparison as a canary and fail the rubric if it ever wins again; run the whole thing past a
genuinely stronger judge and report how far the ranking moves; bootstrap CIs over strata
instead of Wilson, which understates uncertainty on the reweighted numbers; and add a
prompt-injection slice — the golden set contains none, and a public inbox is exactly where
those arrive.

**If a sixth day existed — measure something real.** A shadow-mode harness: run the agent
behind a live queue, send nothing, and have the human who answered the ticket mark whether
they would have sent the draft. Two weeks of that beats everything in this repo, because the
label comes from the person whose name goes on the reply.

## 7. Reproducing this

`make setup && make repro` regenerates every number above from committed artefacts in well
under 15 minutes and without generating a token — every LLM call is cached by content hash,
and this report is *built* from `results/metrics.json` by `scripts/build_report.py`, so no
figure here can drift from the artefact that produced it. `make all` re-runs generation from
the raw 516 MB dump. `make test` runs 16 unit tests covering thread reconstruction, PII
masking, retrieval exclusion, the stratified weights, the escalation policy's invariants
(no always-escalate intent can ever be auto-routed; every hard signal forces escalation)
and the metric definitions.

Design reasoning: [DECISIONS.md](DECISIONS.md). Sampling and labelling protocol:
[data/golden/LABELLING.md](data/golden/LABELLING.md). Full tables including confidence
intervals, per-intent breakdowns, handoff compliance and the matched ablation comparison:
`results/tables.md`.
