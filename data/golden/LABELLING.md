# The golden set: how it was sampled and how it was labelled

200 units, hand-labelled. `golden_set.jsonl` is the joined artefact; `frame.jsonl` is
the sampling frame; `labels.jsonl` is the raw annotation; `frame_report.json` has the
exact stratum populations and weights.

## What a "unit" is

One customer message that `@SpotifyCares` actually answered, plus up to four preceding
turns of the same thread. `position: 0` means it opened the thread; `position > 0`
means it is a mid-conversation follow-up. Units come only from the held-out 30% of
threads, split time-ordered by thread start, so nothing in the golden set is in the
retrieval index.

## Sampling: stratified, with exact weights

The eval pool has 11,971 answered customer turns. I de-duplicated near-identical
messages (normalised prefix match) down to 11,644, then partitioned that pool into 7
strata by regex, first match wins — so the partition is exact and the weights are exact.

| stratum | pool population | share of pool | sampled | weight |
|---|---|---|---|---|
| `general` (no keyword hit) | 8,882 | 76.3% | 120 | 74.02 |
| `money` | 1,087 | 9.3% | 18 | 60.39 |
| `vague_short` (≤40 chars) | 1,083 | 9.3% | 10 | 108.30 |
| `security` | 284 | 2.4% | 16 | 17.75 |
| `churn_human` | 212 | 1.8% | 16 | 13.25 |
| `non_english` | 56 | 0.5% | 10 | 5.60 |
| `safety_legal` | 40 | 0.3% | 10 | 4.00 |

`weight = pool population / sampled`, stored on every unit. This is why the harness can
report both an on-sample rate and a Horvitz–Thompson population estimate. Seed 20250913;
`golden.py sample` reproduces the identical frame.

**Why not uniform.** A uniform 200 would have contained ~5 security cases, ~1
non-English message and probably 0 legal ones. The escalation behaviour most worth
measuring would have been invisible. The cost of enriching is that every on-sample
number is a biased estimate of production behaviour — which is why the reweighted
column exists and why §5.1 of the report leads with this.

**Known frame noise.** The strata are keyword buckets, not gold categories, and they
misfire: one unit landed in `safety_legal` because it contained "press cancel", and one
in `non_english` for the phrase "por favor" inside an otherwise English sentence. This
does not bias the estimator — the weights depend on the partition, not on the partition
being semantically correct — but it does mean stratum names are approximate.

## Labelling protocol

**One annotator (me).** Working from `../taxonomy.yaml`, which was written *before*
labelling started by reading ~450 threads from the history split.

**What the annotator saw:** the customer message and up to four earlier turns.

**What was withheld:** the reply Spotify actually sent. `golden.py` keeps it under the
`_brand_reply` key and `golden.py show` does not print it. This matters: if I had
labelled with Spotify's reply visible, my "should this escalate?" judgement would have
collapsed into "did Spotify ask for a DM?", and the evaluation would then have been
comparing the agent against a proxy for itself. Spotify's DM behaviour is preserved as
a separate weak signal (`brand_asked_for_dm`) for exactly that comparison.

**Fields recorded per unit**

| field | meaning |
|---|---|
| `gold_intent` | the single best code from the codebook |
| `gold_intent_alt` | a second code I would also accept — enables a lenient accuracy alongside the strict one |
| `gold_route` | `auto` or `escalate` under the stated risk appetite |
| `gold_driver` | the single most operative reason for escalating (`none` if auto) |
| `hard` | true where I made a genuine judgement call |
| `note` | free text, mostly recording *why* a hard case went the way it did |

**Order of work.** Eight batches of 25, in the frame's seeded shuffled order, so
strata were interleaved rather than labelled in blocks.

**Two definitions were tightened mid-labelling**, after the first ~100 units showed
they were too loose. The affected earlier units were then re-labelled:

- `money_involved` now fires only when money has moved, failed to move, or is about to
  move wrongly *for this customer*. It no longer fires on general price, offer or
  payment-method questions, which have the same answer for everyone.
- `churn_threat` now requires leaving to be framed as a consequence of
  dissatisfaction. Routine "how do I cancel my auto-renew" admin, and obvious jokes
  ("I may have to cancel my subscription over that pun"), no longer fire it.

Three units were revised as a result (frame indices 11, 35, 75). Changing a definition
part-way is a real methodological wart; the alternative — keeping a definition I knew
was wrong — would have been worse, and re-labelling from scratch was not possible in
the time available.

## Label difficulty

**46 of 200 units (23%) are flagged `hard`.** The recurring reasons:

1. **Bug or account problem?** "Can't log in — says no internet connection, but I'm on
   wifi and a VPN" is a client-connectivity bug wearing an authentication costume.
   Resolved by asking which *action* Spotify would take: a public troubleshooting
   question means `playback_bug`, a DM means `account_access`.
2. **How-to or feature request?** "Can you save a queue as a playlist?" depends on
   whether the feature exists, which the annotator has to know.
3. **Is the churn real?** Handled by the tightened definition above, but "I'll switch
   to Apple Music if this keeps happening" is still a coin-flip.
4. **Image-only referents.** "why is there limit for this? <url>" cannot be labelled
   from text. These went to `other_unclear`, which is a convention, not a truth.
5. **Taxonomy gaps.** Three units are creator-side or promo requests (artist-page
   claims, podcast submissions, tour presale codes) that no code fits well. They are
   labelled `how_to` with a note. A v2 codebook needs a `creator_support` code.

## Second pass, and why its result is worthless

I re-labelled a 40-unit random subset in a second pass with the items reshuffled and
the first-pass labels hidden, and got 100% agreement on both intent and route
(`results/annotator_agreement.json`).

**Do not read that as reliability.** It was the same person on the same day, and I
recognised the items. It measures recall, not reproducibility. The honest position is
that label uncertainty here is unmeasured; the closest available proxy is the 23%
`hard` rate, and the per-slice breakdown in the report shows the agent performs
measurably worse on exactly those units. Getting a second annotator is the first item
on the one-more-week list.
