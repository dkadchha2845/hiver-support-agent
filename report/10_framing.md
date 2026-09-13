## 1. Problem framing: what "good" means, and what I did not build

Spotify's public support handle answered {{F:data_profile.json:n_answered_customer_turns}}
customer turns across {{F:data_profile.json:n_threads}} threads here; the median thread is
{{F:data_profile.json:median_thread_turns}} turns and the average reply
{{F:data_profile.json:mean_brand_reply_chars}} characters. I read ~450 threads before
writing code. Three facts shaped everything after.

**It is a triage desk, not a resolution desk.** The commonest outbound action is a *next
step*, not an answer: ask for device/OS/version, or ask for the account email in DM.
{{FP:data_profile.json:brand_reply_action_patterns.asks_for_dm}} of replies request a DM.
So "a good reply" here usually means *the correct next step*. Evaluating on "did it solve
the problem" would measure something Spotify's own agents do not do in public.

**The automatable and the risky separate cleanly — and not by topic.** Anything needing a
look at *this customer's* account, plan or money goes to DM every time. Everything else —
a missing album, a feature request, a device bug, a thank-you — is answered publicly with
a stable, near-templated response. That is the automation boundary, and it is why routing
keys off *risk signals* rather than intent alone.

**The tail carries the damage.** In the held-out pool, money is
{{FP:data_profile.json:eval_pool_stratum_share.money}} of volume, security
{{FP:data_profile.json:eval_pool_stratum_share.security}}, churn-or-human-request
{{FP:data_profile.json:eval_pool_stratum_share.churn_human}}, non-English
{{FP:data_profile.json:eval_pool_stratum_share.non_english}}, legal/fraud
{{FP:data_profile.json:eval_pool_stratum_share.safety_legal}}. A uniform sample of 200
would hold ~5 security cases, ~1 non-English message and probably zero legal ones — it
could not measure the thing most worth measuring. Hence a stratified golden set.

### So "good" is three things, weighted unevenly

1. **Never auto-send something that needed a human.** The only hard constraint. A missed
   escalation on a fraud claim is real harm; an unnecessary escalation costs one
   agent-minute. Metric: **unsafe auto-handle rate**. I care about it more than anything
   else here.
2. **Automate enough volume to be worth deploying.** An agent that escalates everything
   is perfectly safe and perfectly useless. Metric: **auto coverage**, meaningless
   without (1).
3. **Draft replies a human would send unedited.** Not "reads nicely" — *ships*. Metric:
   **send-ready rate**, where any one rubric dimension below 4/5 fails the whole reply.

Combined into the headline, **Trustworthy Automation Rate (TAR)**: the share of all
messages where the agent chose auto, gold agrees that was safe, *and* the draft was
send-ready. A composite, because every single-axis metric here has a trivial winner. §5
is about how even TAR misleads.

### What I chose not to build

**Not a conversation owner** — one reply to one message, no cross-turn state, no DM flow.
**Not Banking77** — a clean 77-class number that would tell a Spotify support lead
nothing; I looked and dropped it. **No fine-tuning** — with 200 labels, prompting plus
retrieval is the honest ceiling. **No deflection/CSAT** — I cannot observe what a draft
would do to a real customer, and §5.9 says so. **No dedicated safety model** — self-harm
routes to a human via one risk signal, which is not good enough for production.
