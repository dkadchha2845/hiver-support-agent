## 6. What I would do with one more week

Ordered by expected value per day, not by how interesting it is.

**Day 1 — fix the name and handoff bugs, then re-measure.** Both are quantified in §4 and both
get *guardrails* rather than better prompts, because a guardrail is unit testable: reject any
first name in a draft that does not appear in the current thread, and fall back to a fixed
holding template when an escalate-routed draft contains no handoff language.

**Day 2 — a second annotator on 80 units.** The biggest hole here. Hand over 80 stratified
units including all {{F:metrics.json:golden_set.n_flagged_hard}} `hard` ones, compute real
inter-annotator kappa, adjudicate into a v2 golden set. Every number in this report is
conditional on labels only I have seen, and I cannot fix that alone.

**Day 3 — calibrate the abstention rule that currently does nothing.** Carve a 300-unit dev
slice out of the pool (never the golden set), label it coarsely, and fit both the retrieval
threshold (§5.7) and the confidence band, which currently trusts the model's self-reported
`low`/`medium`/`high` with no evidence those words mean anything. Target a selective prediction
curve so a support lead picks the operating point rather than accepting mine.

**Day 4 — add the `clarify` tier.** The biggest coverage win available: `other_unclear` and
low-confidence cases go to a human today, but §4 F5 shows many need only "what's happening
exactly, and on which device?". A clarifying question makes no commitments, so it adds almost no
risk. Gate it hard — no clarify if any money/security/legal signal fires, and one clarify then
escalate.

**Day 5 — fix the judge, now the weakest component.** §3.3 showed the rubric ranks a copy-paste
baseline first, so: add a `relevance` dimension and make `groundedness` conditional on it; keep
the copy-paste baseline in the comparison permanently as a canary; run it all past a stronger
judge; bootstrap CIs over strata instead of Wilson; and add a prompt-injection slice — the
golden set has none, and a public inbox is exactly where those arrive.

**If a sixth day existed — measure something real.** A shadow-mode harness: run the agent
behind a live queue, send nothing, and have the human who answered each ticket mark whether
they would have sent the draft. Two weeks of that beats everything in this repo, because the
label comes from the person whose name goes on the reply.
