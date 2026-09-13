# Decision log

The 15 choices that were not obvious, and why I made them. Where a decision is
probably wrong, I say so.

---

**1. Brand: `SpotifyCares`, not `AmazonHelp` or `AppleSupport` (the two biggest).**
The task says "draft a reply grounded in how that brand has historically resolved
similar issues". That is only a real task if the brand actually resolves things in
public. I sampled threads from the top brands: Amazon and Apple almost immediately
push customers to DM, so their public corpus is mostly "sorry, DM us" and a grounded
reply generator would learn one behaviour. Spotify has ~28k threads and visibly
different public actions per topic — ask for device/OS/version, link the Community
idea board, explain a licensing removal, redirect to DM. That variety is what makes
grounding measurable. Volume (43k outbound tweets) is still large enough for
retrieval and small enough to process on a laptop.

**2. The intent taxonomy is grouped by what the brand *did next*, not by topic.**
"Songs cut off on my Echo" and "app crashes on Windows" are one code
(`playback_bug`) because Spotify answers both with the same diagnostic question.
"I was charged £14.99" and "how do I join Premium for Family" are separate codes
because one always goes to DM and the other is often answered in public with a link.
Topic-shaped taxonomies produce codes that no downstream action depends on. This
gave 10 codes; see `data/taxonomy.yaml` for the codebook the annotator and the model
both work from.

**3. The unit of work is *every customer turn the brand answered*, not just thread
openers.** Real inboxes are mostly mid-conversation. I record `position` on every
unit and keep ~30% follow-ups in the golden set, which turned out to matter: the
opener and follow-up slices behave differently (Table 4). Evaluating only on openers
would have flattered the agent.

**4. The LLM does perception; deterministic code does policy.**
The model extracts intent + 10 risk signals. A hand-written policy then decides
auto vs escalate from those signals. Three reasons: the policy is auditable and unit
tested, a support lead can change the risk appetite without touching a prompt, and
the failure mode becomes legible ("the model missed `money_involved`" vs "the model
decided something"). I kept a pure-LLM router as ablation S4 so the value of the
policy layer is measured rather than asserted.

**5. The golden set is a *stratified* sample with exact inverse-probability
weights, not a uniform sample.** A uniform 200 from this inbox contains roughly 4
security cases and 0 legal ones — it cannot measure the escalation behaviour that
matters most. So I partitioned the held-out pool into 7 strata by keyword, sampled
quotas from each, and stored `weight = stratum_population / stratum_sampled` on every
unit. Every headline number is therefore reported twice: on-sample, and reweighted to
the real inbox mix. The two differ a lot, and the reweighted one is the honest one.

**6. The annotator never saw the brand's real reply while labelling.**
`golden.py` withholds it (`_brand_reply` is stripped from the annotator view). If I
had labelled with Spotify's reply visible, my "should this escalate?" label would
have collapsed into "did Spotify ask for a DM?", and I would then have been
evaluating an agent against a proxy for itself. Spotify's DM behaviour is kept as a
separate weak signal instead.

**7. Gold escalation is defined by a written policy, not by Spotify's observed
behaviour.** Spotify DMs for reasons that have nothing to do with risk (staffing,
public-thread length, which agent picked it up). Gold routing is what *should*
happen under a stated risk appetite. This means routing accuracy measures agreement
with my policy, not with reality — stated plainly in the report's misleading section.

**8. `other_unclear` always escalates, even though asking a clarifying question is
cheap and safe.** Rationale: a vague message can conceal a billing or security issue
the classifier cannot see, and there is nothing to ground a reply in. This is the
decision I am least happy with — it costs real coverage, and a "clarify-then-auto"
tier is the first thing I would add (see report §6).

**9. Retrieval is TF-IDF (word 1-2 grams + char_wb 3-5 grams), not embeddings.**
Tweets are short and typo-dense, where character n-grams do real work
("prieumn", "acessing"). It needs no model download, is deterministic so the eval
replays exactly, and it sets a floor that an embedding upgrade has to beat. Standard
`scikit-learn` components; the `FeatureUnion` + renormalisation trick so that dot
product equals cosine across the concatenated space is the only non-boilerplate part.

**10. The judge is a different model family from the agent.**
`llama-3.1-8b` judges `qwen-2.5-7b`. Then I ran the *same* judge prompt with
`qwen-2.5-7b` as judge on a 100-unit subset, specifically to measure self-preference.
An LLM-as-judge number from a same-family judge is not evidence, and I wanted the
size of that effect rather than a hand-wave.

**11. The headline metric is a composite (TAR), not the judge's send-ready rate.**
Trustworthy Automation Rate = share of all units where the agent chose auto, gold
agrees auto was safe, *and* the judge rated the draft send-ready on every dimension.
It exists because every single-axis metric here has a trivial winner:
escalate-everything gets perfect escalation recall, auto-everything gets perfect
coverage, and a canned "DM us" reply scores respectably on a reply-quality rubric.
TAR has no trivial winner.

**12. `send_ready` is a deterministic threshold (`min(all four dimensions) >= 4`),
not the judge's own `send_as_is` boolean.** The judge's boolean is looser than its own
numeric scores — it is reported separately in Table 2 and the gap is discussed. Deriving
the decision from the scores makes the threshold a policy knob I can defend rather
than a mood the judge was in.

**13. Spotify's own reply is scored by the same judge, as a reference row.**
This is the single most useful line in the results table, and it is uncomfortable: it
lets "our agent beats the humans" be examined instead of claimed. It is the main
evidence that the rubric rewards something other than real-world resolution.

**14. The baselines are deliberately given an advantage the agent never gets.**
B0 (majority class) and B1 (TF-IDF + logistic regression) are fitted with 5-fold
cross-validation *on the golden labels*. The LLM systems are zero-shot and never see
a gold label. If the agent wins, it wins against baselines that were allowed to
cheat; if it loses, the loss is real.

**15. Every LLM call is cached by a content hash of (provider, model, temperature,
system, user).** This is why `make repro` recomputes every number in the report in
seconds, why the three agent variants share their identical retrieval work, and why a
crashed run resumes for free. It also means the committed results are exactly
reproducible from the committed cache, without a single new token being generated.

---

### What I deliberately did not build

- **No multi-turn dialogue policy.** The agent drafts one reply; it does not own the
  conversation, does not track state across turns, and does not decide when to close.
- **No Banking77 transfer.** The optional dataset would have let me report a clean
  77-class number, but that number would say nothing about this brand's inbox. I
  looked at it and dropped it.
- **No fine-tuning.** With 200 labels the honest ceiling is prompting plus retrieval.
- **No DM flow.** Every escalation ends at "a human will pick this up"; what happens
  backstage is out of scope and invisible in this dataset.
- **No deflection or CSAT measurement.** I cannot observe whether a drafted reply
  would have resolved anything. That gap is the biggest single caveat in the report.
