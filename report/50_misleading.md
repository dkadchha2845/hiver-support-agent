## 5. What is misleading about my headline number

The section I care most about. Ten reasons, roughly by how much they should worry you.

**5.1 The headline metric picks the wrong winner, and I left that in.** TAR says the
copy-paste baseline ({{P:systems.B1_simple.TAR.rate}}) beats the agent
({{P:systems.S3_agent.TAR.rate}}). I designed TAR so no trivial system could win it, and a
trivial system won it. The reason is that TAR inherits the judge's send-ready rate, and §3.3
shows the judge is wrong about B1 in a specific, mechanical way. Two honest readings coexist:
*as computed*, my system loses; *on every judge-independent axis* — escalation recall, unsafe
auto-handle rate, intent macro-F1, unsupported-claim rate — it wins clearly. A composite metric
does not launder a broken component, it propagates it.

**5.2 The judge is an 8B model whose per-item decisions are barely better than noise.** On
{{F:judge_agreement_primary.json:n}} blind-scored replies it calls
{{FP:judge_agreement_primary.json:send_ready.judge_rate}} send-ready where I called
{{FP:judge_agreement_primary.json:send_ready.human_rate}}; raw agreement
{{FP:judge_agreement_primary.json:send_ready.agreement}}, kappa
{{F:judge_agreement_primary.json:send_ready.kappa}}. Quadratic-weighted kappa per dimension is
weak everywhere and near zero on tone
({{F:judge_agreement_primary.json:per_dimension.tone.qwk}}, with a bias of
{{F:judge_agreement_primary.json:per_dimension.tone.bias_judge_minus_human}} points). The
false-pass rate is {{FP:judge_agreement_primary.json:send_ready.false_pass_rate}}: it waved
through {{F:judge_agreement_primary.json:send_ready.judge_waved_through_human_would_block}}
replies I would have blocked. And it is unstable — rerunning the *same* judge at temperature
0.7 flips the send-ready verdict on
{{FP:judge_sensitivity.json:stability.S3_agent.send_ready_flip_rate}} of replies. Read every
send-ready figure as "according to an 8B judge that would disagree with itself two times in
five".

**5.3 The judge ranks the systems in the wrong order, and not subtly.** By mean rubric score it
ranks **B1 (copy-paste) > agent > Spotify's own replies**; on the same replies, hand-scored
blind, I rank **agent ≥ Spotify's replies > B1**. It puts the plagiariser first and the
professionals last. Any rubric with a groundedness axis should be run against a copy-paste
control as a canary; mine would have failed that check before I quoted a number. Related: if a
7B model out-scores the humans it imitates, the rubric is rewarding *legible helpfulness* while
Spotify's agents optimise for throughput and for moving to DM — which my `resolution` anchors
punish as "acknowledges and redirects". **And self-preference is real and measurable**: swapping
in a judge from the agent's own family widens the agent-over-human gap from
{{F:judge_sensitivity.json:agent_minus_human_gap.primary}} to
{{F:judge_sensitivity.json:agent_minus_human_gap.selfjudge}}.

**5.4 Two of my own results did not survive auditing my own work.** §4 F1: five deductions I
made against Spotify's real replies were unjustified — I penalised them for greeting customers
by names the dataset had hidden from me — and removing them collapses my hand-scored
agent-over-human margin from
+{{F:name_audit.json:human_score_variants.agent_minus_human_mean_overall.as_scored_blind}} to
{{F:name_audit.json:human_score_variants.agent_minus_human_mean_overall.name_adjusted}}. §4 F2:
the escalation of non-English messages that looked like policy turned out to be a coincidence
of intent classification. Both were found by writing code to interrogate my own artefacts, and
both were flattering before I looked. I have no reason to think they were the last two.

**5.5 The sample is enriched, so the on-sample number is not the inbox number.** Security is
{{FP:data_profile.json:eval_pool_stratum_share.security}} of the real pool and 8% of my sample;
`safety_legal` {{FP:data_profile.json:eval_pool_stratum_share.safety_legal}} of the pool and 5%
of my sample. Gold escalation rate is {{P:golden_set.gold_escalate_rate_on_sample}} on-sample,
{{P:golden_set.gold_escalate_rate_weighted}} reweighted. **Quote the reweighted column** — and
note its flaw: `general` carries weight 74 and `vague_short` 108, so a handful of units drive
the population estimate, whose true variance is wider than the Wilson interval beside it. A
stratum bootstrap would widen it further; I did not implement one.

**5.6 Routing measures agreement with my policy, not with reality.** Gold routes apply a risk
appetite I chose, and the agent routes from signals defined in the same codebook I labelled
from — so escalation recall partly measures whether the model and I read one document the same
way. The external check (did Spotify actually DM?) I kept out of the labels deliberately.

**5.7 One of my four routing conditions never fires.** The policy escalates when best retrieval
similarity is below 0.18; the minimum on the golden set is
{{F:leakage_check.json:nearest_neighbour_similarity_on_golden.min}}. A quarter of my "defence in
depth" is decoration. The fix is calibrating on a held-out dev slice — not, as I was tempted,
tuning on the golden set until the numbers improved.

**5.8 n=200 means ±7pp across ~24 reported numbers, with no multiplicity correction.** Treat
any gap narrower than ~10pp as not demonstrated. The one comparison I would defend at this n is
the router ablation, where the gap is 6.7×.

**5.9 One annotator, and the consistency check is worthless.** I re-labelled 40 units in a
second pass and got 100% agreement (Table 7, `results/tables.md`). That is evidence of *memory* — same person, same
day, items recognised. **Ignore that number.** Label uncertainty is unmeasured; the closest
bound is the 23% `hard` rate, and the slice breakdown shows the agent's unsafe auto-handle rate is
{{P:slices_S3_agent.by_annotator_difficulty.flagged_hard.unsafe_auto_rate}} on those units
against {{P:slices_S3_agent.by_annotator_difficulty.clear.unsafe_auto_rate}} on the clear ones —
a 5× difference driven entirely by how hard *I* found the label.

**5.10 Nothing here measures whether a customer was helped.** No deflection, CSAT, re-contact
or time-to-resolution — `resolution` is a model's guess about a reply whose consequences it
never saw. `non_english` being a hard escalation signal conveniently removes the hardest
generation cases from the quality metric (and §4 F2 shows that exclusion barely works anyway).
The data is 2017, one brand, one channel, one language.

### What I would actually put on a slide

> On 200 held-out, deliberately risk-enriched messages from Spotify's public support inbox, the
> agent produced a send-ready, correctly-auto-routed draft for
> **{{P:systems.S3_agent.TAR.rate}}** of them —
> **{{P:systems.S3_agent.TAR.rate_weighted}}** reweighted to real inbox volume — which is
> **worse than a copy-paste baseline** on the same metric, for reasons I believe are a flaw in
> my judge rather than a virtue of the baseline. The numbers I would actually deploy against are
> judge-free: unsafe auto-handle rate **{{P:systems.S3_agent.routing.unsafe_auto_rate}}** (95% CI
> {{N:systems.S3_agent.routing.unsafe_auto_rate_ci95.0}}–{{N:systems.S3_agent.routing.unsafe_auto_rate_ci95.1}}),
> escalation recall **{{P:systems.S3_agent.routing.escalation_recall}}**, at
> **{{P:systems.S3_agent.routing.auto_coverage}}** auto coverage. Before trusting any of it: one
> annotator, one brand, one language, a 2017 snapshot, and a judge with a
> {{FP:judge_agreement_primary.json:send_ready.false_pass_rate}} false-pass rate that disagrees
> with itself on {{FP:judge_sensitivity.json:stability.S3_agent.send_ready_flip_rate}} of replies.
