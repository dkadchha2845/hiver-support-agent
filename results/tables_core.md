### Table 1 - Headline comparison (n = 200 golden units)

| system | intent macro-F1 | intent acc | escalation recall | unsafe auto-handle | auto coverage | send-ready | TAR |
|---|---|---|---|---|---|---|---|
| B0 trivial (escalate all + canned reply) | 0.031 | 18.5% | 100.0% | 0.0% | 0.0% | 10.0% | 0.0% |
| B0 trivial (auto all + canned reply) | 0.031 | 18.5% | 0.0% | 49.0% | 100.0% | 10.0% | 2.0% |
| B1 simple (TF-IDF+LogReg / lexicon / NN reply) | 0.295 | 41.0% | 71.4% | 14.0% | 58.5% | 50.5% | 21.0% |
| S2 agent, no retrieval (ablation) | 0.727 | 75.0% | 93.3% | 3.0% | 48.0% | 3.0% | 3.0% |
| S4 agent, LLM router (ablation) | 0.727 | 75.0% | 55.6% | 20.0% | 73.0% | 26.0% | 13.0% |
| S3 agent (headline) | 0.670 | 71.0% | 86.7% | 6.5% | 50.0% | 25.0% | 10.5% |
| HUMAN @SpotifyCares reply actually sent | - | - | - | - | - | 19.0% | - |

### Table 6 - Judge vs human on 48 blind-scored replies

| dimension | human mean | judge mean | judge bias | within 1 | QWK | Spearman |
|---|---|---|---|---|---|---|
| groundedness | 4.12 | 4.40 | +0.27 | 83.3% | 0.26 | 0.28 |
| resolution | 3.33 | 3.35 | +0.02 | 77.1% | 0.21 | 0.32 |
| tone | 3.19 | 4.52 | +1.33 | 54.2% | 0.06 | 0.17 |
| safety | 4.06 | 4.69 | +0.62 | 77.1% | 0.28 | 0.40 |

Send-ready decision: human 29.2%, judge 37.5%, raw agreement 66.7%, kappa 0.2558. The judge waved through 10 replies a human would block and blocked 6 a human would send (false-pass rate 20.8% [0.12, 0.34]).

System ranking by mean rubric score - human: S3_agent > HUMAN_brand_reply > B1_simple > B0_trivial_escalate_all; judge: B1_simple > S3_agent > HUMAN_brand_reply > B0_trivial_escalate_all; identical: **False**.
