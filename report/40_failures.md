## 4. Failure analysis: the five things that actually go wrong

Every example is a verbatim row from `results/failures.json`.

### F1. The retrieval baseline greets the wrong customer — and I mis-scored the humans for it

This starts as a finding about the system and ends as a finding about my evaluation. It is
the most useful thing I learned.

**What I saw while hand-scoring.** Several replies greeted someone by a first name that
appeared nowhere in the conversation — "Hey **Jade**", "Hey **Jeremy**", "Hi **Allison**",
"Hey **Sam**", "Hey **Tim**". I deducted tone points each time.

**Then I wrote a script to check my own annotations** (`src/name_audit.py`). It extracts
every greeting name and asks where it came from: this thread, the retrieved evidence only,
or nowhere.

| system | greets by name | name in this thread | name only in retrieved evidence | name unverifiable |
|---|---|---|---|---|
| B1 simple (verbatim nearest neighbour) | {{F:name_audit.json:by_system.B1_simple.greeted_by_name}} | {{F:name_audit.json:by_system.B1_simple.in_thread}} | **{{F:name_audit.json:by_system.B1_simple.in_evidence_only}}** | {{F:name_audit.json:by_system.B1_simple.unverifiable}} |
| HUMAN (Spotify's own reply) | {{F:name_audit.json:by_system.HUMAN_brand_reply.greeted_by_name}} | {{F:name_audit.json:by_system.HUMAN_brand_reply.in_thread}} | {{F:name_audit.json:by_system.HUMAN_brand_reply.in_evidence_only}} | **{{F:name_audit.json:by_system.HUMAN_brand_reply.unverifiable}}** |
| S3 agent | **0** | – | – | – |

**(a) It is B1's defect, not the agent's.** All of B1's named greetings use a name that
provably belongs to a *different customer's* thread — the inevitable consequence of
replaying a retrieved reply verbatim. The agent never greets anyone by name at all, which
costs it warmth and removes this failure mode entirely. My first draft of this section
blamed the agent; the script corrected me.

**(b) I penalised Spotify's real agents for being right.** Five of the six named greetings
in Spotify's own replies use a name I could not find anywhere — because the dataset
anonymises Twitter *handles* (`@115712` → `@customer`) but leaves first names in the reply
body intact. The real agent could see the handle; I could not. Those were almost certainly
the customer's actual name, and I marked them wrong.

**(c) Correcting it erases the result I was most pleased with.** Reverting only those five
deductions (item-by-item in `src/name_audit.py`; original blind scores kept as the primary
record):

| | agent, mean rubric | Spotify's own replies | agent send-ready | Spotify send-ready |
|---|---|---|---|---|
| as I scored it blind | {{F:name_audit.json:human_score_variants.as_scored_blind.S3_agent.mean_overall}} | {{F:name_audit.json:human_score_variants.as_scored_blind.HUMAN_brand_reply.mean_overall}} | {{F:name_audit.json:human_score_variants.as_scored_blind.S3_agent.send_ready}}/15 | {{F:name_audit.json:human_score_variants.as_scored_blind.HUMAN_brand_reply.send_ready}}/15 |
| after correcting my artefact | {{F:name_audit.json:human_score_variants.name_adjusted.S3_agent.mean_overall}} | **{{F:name_audit.json:human_score_variants.name_adjusted.HUMAN_brand_reply.mean_overall}}** | {{F:name_audit.json:human_score_variants.name_adjusted.S3_agent.send_ready}}/15 | **{{F:name_audit.json:human_score_variants.name_adjusted.HUMAN_brand_reply.send_ready}}/15** |

The agent-over-human margin goes from
+{{F:name_audit.json:human_score_variants.agent_minus_human_mean_overall.as_scored_blind}}
to **{{F:name_audit.json:human_score_variants.agent_minus_human_mean_overall.name_adjusted}}**,
and on send-ready the humans move ahead. **The most flattering result in this project was
an artefact of the dataset's anonymisation interacting with my annotation procedure**, and
it survived until I wrote 60 lines of Python to interrogate my own labels. I have no reason
to think it is the only one.

### F2. The risk signals barely work — the intent is doing the escalating

| gold escalation driver | n | model fired that signal | still escalated |
|---|---|---|---|
| `churn_threat` | {{F:failures.json:risk_signal_detection.churn_threat.gold_n}} | **{{FP:failures.json:risk_signal_detection.churn_threat.signal_recall}}** | {{FP:failures.json:risk_signal_detection.churn_threat.route_recall}} |
| `money_involved` | {{F:failures.json:risk_signal_detection.money_involved.gold_n}} | {{FP:failures.json:risk_signal_detection.money_involved.signal_recall}} | {{FP:failures.json:risk_signal_detection.money_involved.route_recall}} |
| `security_or_privacy` | {{F:failures.json:risk_signal_detection.security_or_privacy.gold_n}} | {{FP:failures.json:risk_signal_detection.security_or_privacy.signal_recall}} | {{FP:failures.json:risk_signal_detection.security_or_privacy.route_recall}} |
| `account_specific` | {{F:failures.json:risk_signal_detection.account_specific.gold_n}} | **{{FP:failures.json:risk_signal_detection.account_specific.signal_recall}}** | {{FP:failures.json:risk_signal_detection.account_specific.route_recall}} |
| `vague_no_detail` | {{F:failures.json:risk_signal_detection.vague_no_detail.gold_n}} | {{FP:failures.json:risk_signal_detection.vague_no_detail.signal_recall}} | {{FP:failures.json:risk_signal_detection.vague_no_detail.route_recall}} |
| `non_english` | {{F:failures.json:risk_signal_detection.non_english.gold_n}} | **{{FP:failures.json:risk_signal_detection.non_english.signal_recall}}** | {{FP:failures.json:risk_signal_detection.non_english.route_recall}} |
| `legal_or_regulatory` | {{F:failures.json:risk_signal_detection.legal_or_regulatory.gold_n}} | **{{FP:failures.json:risk_signal_detection.legal_or_regulatory.signal_recall}}** | {{FP:failures.json:risk_signal_detection.legal_or_regulatory.route_recall}} |

Read the `non_english` row carefully. On the surface it looks fine — most non-English
messages were escalated. But the language signal fired **once in thirteen**. I traced every
one: **all 11 escalations happened because the model read the intent as `billing_charge`,
`account_access` or `other_unclear`, which are never auto-handled anyway.** The two that
leaked to auto-send were exactly the two whose intent was auto-eligible (Norwegian: "has
Discover Weekly changed?", and an offer-eligibility question). The system has no language
policy; it has a coincidence. A non-English feature request would be answered in English,
publicly, with no human involved.

`legal_or_regulatory` never fires at all, and `account_specific` — the largest escalation
driver in the golden set — is missed 39% of the time.

**Hypothesis.** Ten booleans in one call is too many. The model catches signals with loud
lexical markers ("cancel", "charged", "hacked") and misses those requiring an inference
about *what answering would require* (`account_specific`) or a judgement about the message
as an artefact rather than its content (`non_english`). The fix is not a better prompt:
language ID is solved and belongs in deterministic code before the LLM runs.

### F3. Escalate-routed drafts try to solve the problem anyway

Of the {{F:failures.json:missed_escalation_severity.n_missed}} missed escalations,
**{{F:failures.json:missed_escalation_severity.draft_attempted_to_resolve}} produced a draft
that attempted public resolution**; the other
{{F:failures.json:missed_escalation_severity.draft_still_handed_off}} said "DM us" anyway,
making them label errors with little consequence. Routing and drafting are separate calls
and nothing forces them to agree — hence handoff compliance as its own metric (Table 3b, `results/tables.md`).

> **Customer:** "(One previous thread here `<url>`" *(a fragment pointing elsewhere)*
> **Draft:** "Thanks for reaching out, Jonny! We noticed your issue. Let's try restarting
> your device by holding the Home + Lock button for 10 seconds."

A name from nowhere, invented hardware steps for an unknown device, and a confident fix for a
message containing no problem statement. **Fix:** when `route == escalate`, pick a handoff
template and let the model fill only the acknowledgement.

### F4. It invents plausible specifics when the evidence is generic

| draft | the problem |
|---|---|
| "It sounds like **Auto Skip** might be on" | The evidence says *Autoplay*; "Auto Skip" is not a Spotify feature. |
| "we'll **re-tune Discover Weekly for you on Monday**" | No such commitment exists in the evidence. |
| "Your monthly will **pause automatically**" | An invented billing policy. |
| "Suggest it in our Community: **[link]**" | An unfilled placeholder that would have been published. |

**Grounding also imports surface artefacts.** Spotify's agents sign replies with their
initials (`/JX`); the draft prompt explicitly forbids signing off.
**{{P:systems.S3_agent.style_leakage.rate}} of grounded drafts end in a fabricated agent
signature anyway, against {{P:systems.S2_agent_noretrieval.style_leakage.rate}} for the same
model with no evidence in the prompt** — the ablation makes the causal claim cheap. Retrieval
teaches the model to invent a colleague's initials, and a written instruction does not stop
it. Same mechanism as F1, different token.

**Hypothesis.** My `resolution` anchors punish "acknowledges and redirects" as a 3, so the
prompt rewards concreteness while the evidence is often generic. Asked to be specific with
nothing specific available, a 7B model produces specificity-shaped text. **My rubric creates
the failure it then penalises**: `resolution` and `groundedness` are in tension and I set both.

### F5. No abstention: vague messages get confident answers

> **Customer:** "@SpotifyCares @customer" *(two bare mentions, no content)*
> **Draft:** "Hey there! We've got your back. You can remove songs from your library if
> needed." *(routed **auto**)*

By contrast, for "why is there limit for this? `<url>`" (referent inside an image) the agent
asked a clarifying question and routed auto — exactly right. A clarifying question is the
safest automatable reply there is, and my policy escalates `other_unclear` instead. That is
the `clarify` tier in §6.

### Intent confusions, and the baselines

Intent mismatches: {{P:systems.S3_agent.intent.accuracy_strict}} strict accuracy, so 58/200
disagree with my first-choice label — but
{{F:failures.json:counts.intent_wrong_but_matched_alt}} of those hit the alternative label I
had already written down as defensible, leaving
{{F:failures.json:counts.intent_wrong_strict}} genuine errors
({{P:systems.S3_agent.intent.accuracy_lenient}} lenient). Top confusions:
`subscription_plan`→`billing_charge`, `playback_bug`→`complaint_no_ask`,
`playback_bug`→`account_access`, `content_availability`→`feature_request`,
`other_unclear`→`complaint_no_ask`. Two patterns: **lexical pull** (money words drag
classification to billing regardless of what is asked — the same mechanism as the keyword
baseline it should beat) and **reluctance to abstain** (`other_unclear` under-predicted, the
classifier-side version of F5).

B1 fails differently and more dangerously — always fluent, sometimes about another subject:

> **Customer:** "put [artist]'s *Welcome to Forever* album on Spotify please"
> **B1:** "**Taylor Swift's 'Reputation'** isn't available to stream just yet – stay tuned!"

A fluent wrong answer is worse than an obviously unhelpful one, because nobody reviews it.
