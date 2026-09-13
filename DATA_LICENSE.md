# Data provenance and licence

## Source dataset

**Customer Support on Twitter** — Stuart Axelbrooke, via Kaggle
(`thoughtvector/customer-support-on-twitter`).
Licence: **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
(CC BY-NC-SA 4.0)** — https://creativecommons.org/licenses/by-nc-sa/4.0/

`scripts/download_data.sh` fetches it from Kaggle when credentials are present, otherwise
from a byte-identical mirror of `twcs.csv` on the Hugging Face Hub so that a reviewer with
no Kaggle account can still reproduce the pipeline.

## What this repository redistributes

`data/processed/*.jsonl` are **derived works**: `@SpotifyCares` conversations reconstructed
from the source dump, reshaped into threads and eval units. They are committed so that
`make repro` works without a 516 MB download. Under CC BY-NC-SA 4.0 these derivatives are
shared under the **same licence**, with attribution as above, for **non-commercial** use.

`data/raw/twcs.csv` is **not** committed (see `.gitignore`).

### Privacy handling

The source dataset is already pseudonymised by its author: customer Twitter handles are
replaced with numeric ids (`@115712`), and some inline identifiers are masked
(`__email__`, `__credit_card__`). On top of that, `src/data_prep.py:clean_text` masks,
before any text reaches a model or is written to disk:

- URLs → `<url>`
- email addresses → `<email>`
- phone numbers and any digit run of 7+ → `<number>`
- numeric customer handles → `@customer`

What remains and is **not** removed: first names where a support agent used them in the
reply body, and free-text detail customers volunteered publicly. Report §4 F1 is about a
consequence of exactly that asymmetry. All of it was already public on Twitter/X at the
time of collection, and none of it is re-identified or aggregated here.

## Models

- `Qwen2.5-7B-Instruct` — Alibaba Cloud, Apache-2.0.
- `Llama-3.1-8B-Instruct` — Meta, Llama 3.1 Community License.

Both run locally through [Ollama](https://ollama.com); no data leaves the machine.

## This repository's own code

The code in `src/`, `scripts/`, `tests/` and the prose in `README.md`, `REPORT.md`,
`DECISIONS.md` are released under the MIT licence (see `LICENSE`). The **data** under
`data/` remains CC BY-NC-SA 4.0 per the above, which is the stricter of the two — treat the
repository as non-commercial as a whole.
