# Can we trust this agent? A support agent for @SpotifyCares

**What this is.** An AI support agent for Spotify's public Twitter/X support handle. It
classifies an incoming customer message into one of 10 intents induced from the data, drafts
a reply grounded in how Spotify actually handled similar messages, and decides auto-send vs
escalate-to-human with a stated reason. It runs on free open-weights models locally —
`qwen2.5:7b-instruct` for the agent, `llama3.1:8b` as judge, no API keys.

The build was the easy half. This report is mostly about the other half.

**The headline, stated the way I would defend it in a review:**

| | agent (S3) | copy-paste baseline (B1) |
|---|---|---|
| Trustworthy Automation Rate — send-ready **and** correctly auto-routed | **{{P:systems.S3_agent.TAR.rate}}** | **{{P:systems.B1_simple.TAR.rate}}** |
| Unsafe auto-handle rate — judge-independent, and the one that gates deployment | **{{P:systems.S3_agent.routing.unsafe_auto_rate}}** | {{P:systems.B1_simple.routing.unsafe_auto_rate}} |
| Escalation recall | **{{P:systems.S3_agent.routing.escalation_recall}}** | {{P:systems.B1_simple.routing.escalation_recall}} |
| Intent macro-F1 | **{{N:systems.S3_agent.intent.macro_f1}}** | {{N:systems.B1_simple.intent.macro_f1}} |

**My agent loses to a baseline that copies a retrieved reply verbatim, on my own headline
metric.** It wins on everything the judge does not touch. §3.3 and §5.3 argue — with
evidence, not indignation — that the judge is wrong about B1 and that the ranking is an
artefact of a rubric I wrote. But the composite as computed does not favour my system, and I
am not going to bury that in an appendix.

§5 is the full argument for discounting every number above, including two places where
auditing my own work destroyed a result I liked.

*Length: this is the 6-page report. Full tables are in `results/tables.md`; the 15
non-obvious design decisions in [DECISIONS.md](DECISIONS.md); the labelling protocol in
[data/golden/LABELLING.md](data/golden/LABELLING.md).*
