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

### Table 2 - Judge rubric means (1-5, higher is better)

| system | grounded | resolution | tone | safety | overall | chars | % with unsupported claims |
|---|---|---|---|---|---|---|---|
| B0 trivial (escalate all + canned reply) | 3.61 | 3.06 | 4.61 | 3.23 | 3.63 | 105 | 24.0% |
| B0 trivial (auto all + canned reply) | 3.61 | 3.06 | 4.61 | 3.23 | 3.63 | 105 | 24.0% |
| B1 simple (TF-IDF+LogReg / lexicon / NN reply) | 4.79 | 3.46 | 4.45 | 4.99 | 4.42 | 122 | 2.0% |
| S2 agent, no retrieval (ablation) | 3.65 | 2.97 | 4.76 | 4.37 | 3.94 | 136 | 29.0% |
| S4 agent, LLM router (ablation) | 4.25 | 3.27 | 4.65 | 4.85 | 4.25 | 113 | 6.0% |
| S3 agent (headline) | 4.26 | 3.23 | 4.68 | 4.79 | 4.24 | 113 | 5.5% |
| HUMAN @SpotifyCares reply actually sent | 4.00 | 3.18 | 4.51 | 4.73 | 4.11 | 132 | 15.5% |

### Table 4 - Where the headline hides things (S3 agent)

| slice | n | intent acc | unsafe auto-handle | send-ready |
|---|---|---|---|---|
| opening message | 140 | 67.1% | 7.1% | 25.7% |
| mid-thread follow-up | 60 | 80.0% | 5.0% | 23.3% |
| annotator: clear | 154 | 77.3% | 3.2% | 27.3% |
| annotator: judgement call | 46 | 50.0% | 17.4% | 17.4% |
| stratum: churn_human | 16 | 31.2% | 0.0% | 18.8% |
| stratum: general | 120 | 73.3% | 8.3% | 24.2% |
| stratum: money | 18 | 66.7% | 5.6% | 11.1% |
| stratum: non_english | 10 | 70.0% | 0.0% | 40.0% |
| stratum: safety_legal | 10 | 90.0% | 10.0% | 20.0% |
| stratum: security | 16 | 87.5% | 0.0% | 31.2% |
| stratum: vague_short | 10 | 70.0% | 10.0% | 50.0% |

### Table 6 - Judge vs human on 48 blind-scored replies

| dimension | human mean | judge mean | judge bias | within 1 | QWK | Spearman |
|---|---|---|---|---|---|---|
| groundedness | 4.12 | 4.40 | +0.27 | 83.3% | 0.26 | 0.28 |
| resolution | 3.33 | 3.35 | +0.02 | 77.1% | 0.21 | 0.32 |
| tone | 3.19 | 4.52 | +1.33 | 54.2% | 0.06 | 0.17 |
| safety | 4.06 | 4.69 | +0.62 | 77.1% | 0.28 | 0.40 |

Send-ready decision: human 29.2%, judge 37.5%, raw agreement 66.7%, kappa 0.2558. The judge waved through 10 replies a human would block and blocked 6 a human would send (false-pass rate 20.8% [0.12, 0.34]).

System ranking by mean rubric score - human: S3_agent > HUMAN_brand_reply > B1_simple > B0_trivial_escalate_all; judge: B1_simple > S3_agent > HUMAN_brand_reply > B0_trivial_escalate_all; identical: **False**.

### Table 7 - Annotator second pass (n=40)

Intent agreement 100.0% (kappa 1.0), route agreement 100.0% (kappa 1.0). Read the caveat in the report before believing this number.
