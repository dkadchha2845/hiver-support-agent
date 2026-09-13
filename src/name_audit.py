"""Audit of a bias I found in my OWN hand-scoring, not in the agent.

While blind-scoring replies I repeatedly deducted tone points for "greeting the wrong
customer by name". That is a real defect when the name was lifted from a *retrieved*
conversation. But the dataset anonymises Twitter handles (`@115712` -> `@customer`)
while leaving first names in the reply body intact - so when Spotify's own agent greeted
the real customer by their real name, I had no way to verify it and scored it as wrong.

This script separates the two cases:
  * name_in_thread      - the name appears in the visible thread: verifiable, fine
  * name_in_evidence    - the name appears in retrieved evidence but NOT in the thread:
                          a genuine defect (the agent copied someone else's name)
  * name_unverifiable   - neither: probably the real customer's name, invisible to me
"""
from __future__ import annotations

import json
import re

from config import BRAND, GOLDEN, PROCESSED, RESULTS
from retrieval import HistoryIndex

GREET_RE = re.compile(
    r"\b(?:hi|hey|hello|dear|thanks)\b[, ]+([A-Z][a-z]{2,15})\b", re.I
)
# Words that follow a greeting but are not names. Matched case-insensitively.
STOPWORDS = {
    w
    for w in (
        "there here everyone all again for and but the you your yours we our us "
        "spotify premium family free team community sorry thanks thank help got "
        "just please can could would should let give keep not good great awesome "
        "alright anytime dear friend folks fam guys people back much very"
    ).split()
}


def first_names(text: str) -> list[str]:
    return [m for m in GREET_RE.findall(text or "") if m.lower() not in STOPWORDS]




# ---------------------------------------------------------------------------
# Correcting my own scores.
#
# The audit above shows my "wrong name" tone deductions split cleanly in two:
#   * 5 of them are on B1's verbatim retrieved replies, where the name provably comes
#     from a DIFFERENT customer's thread. Those deductions stand.
#   * 5 of them are on Spotify's OWN replies, where the name appears nowhere I could
#     see - because the dataset masks handles, not names. Those deductions are almost
#     certainly wrong: the agent was greeting the real customer.
#
# Reverting the second group is a sensitivity analysis, not a re-score. The original
# blind scores stay the primary record; this produces a parallel file so the report can
# show how much of the agent-beats-human gap was my own annotation artefact.
ADJUSTMENTS = {
    # blind_id: (field, original, corrected, why)
    10: [("tone", 2, 4, "'Corey' is unverifiable, not provably wrong")],
    32: [
        ("tone", 2, 4, "'Sophia' unverifiable"),
        ("safety", 3, 4, "safety deduction was for the same unverified name"),
    ],
    45: [("tone", 2, 4, "'Stephan' unverifiable")],
    53: [
        ("tone", 2, 4, "'Summer' unverifiable"),
        ("safety", 3, 4, "safety deduction was for the same unverified name"),
    ],
    58: [("tone", 2, 5, "'Kay' unverifiable; the rest of the reply is correct")],
}


def write_adjusted() -> dict:
    src = GOLDEN / "human_judge_scores.jsonl"
    rows = [json.loads(l) for l in src.open()]
    applied = []
    for r in rows:
        for field, orig, corrected, why in ADJUSTMENTS.get(r["blind_id"], []):
            if r[field] == orig:
                r[field] = corrected
                applied.append(
                    {"blind_id": r["blind_id"], "field": field, "from": orig, "to": corrected, "why": why}
                )
            r["name_adjusted"] = True
    out = GOLDEN / "human_judge_scores_name_adjusted.jsonl"
    with out.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {"n_adjustments": len(applied), "adjustments": applied, "file": out.name}


def compare_variants() -> dict:
    blind = {json.loads(l)["blind_id"]: json.loads(l) for l in (GOLDEN / "judge_blind_worksheet.jsonl").open()}
    dims = ("groundedness", "resolution", "tone", "safety")
    out: dict = {}
    for label, fname in (
        ("as_scored_blind", "human_judge_scores.jsonl"),
        ("name_adjusted", "human_judge_scores_name_adjusted.jsonl"),
    ):
        rows = [json.loads(l) for l in (GOLDEN / fname).open()]
        by_sys: dict[str, list] = {}
        for r in rows:
            by_sys.setdefault(blind[r["blind_id"]]["system"], []).append(r)
        out[label] = {
            s: {
                "n": len(v),
                "mean_overall": round(sum(sum(r[d] for d in dims) / 4 for r in v) / len(v), 3),
                "mean_tone": round(sum(r["tone"] for r in v) / len(v), 3),
                "send_ready": sum(min(r[d] for d in dims) >= 4 for r in v),
            }
            for s, v in sorted(by_sys.items())
        }
    a, b = out["as_scored_blind"], out["name_adjusted"]
    if "S3_agent" in a and "HUMAN_brand_reply" in a:
        out["agent_minus_human_mean_overall"] = {
            "as_scored_blind": round(a["S3_agent"]["mean_overall"] - a["HUMAN_brand_reply"]["mean_overall"], 3),
            "name_adjusted": round(b["S3_agent"]["mean_overall"] - b["HUMAN_brand_reply"]["mean_overall"], 3),
        }
    return out


def main() -> None:
    golden = {json.loads(l)["unit_id"]: json.loads(l) for l in (GOLDEN / "golden_set.jsonl").open()}
    blind = {json.loads(l)["blind_id"]: json.loads(l) for l in (GOLDEN / "judge_blind_worksheet.jsonl").open()}
    human = {json.loads(l)["blind_id"]: json.loads(l) for l in (GOLDEN / "human_judge_scores.jsonl").open()}
    history = [json.loads(l) for l in (PROCESSED / f"{BRAND}_units_history.jsonl").open()]
    index = HistoryIndex(history)

    rows = []
    for bid, b in blind.items():
        names = first_names(b["reply"])
        if not names:
            continue
        g = golden[b["unit_id"]]
        thread_text = " ".join(
            [g["customer_message"]] + [t["text"] for t in g["context"]]
        )
        evidence = " ".join(
            n.brand_reply
            for n in index.search(
                g["customer_message"], k=4, exclude_conversation=g["conversation_id"]
            )
        )
        for name in names:
            in_thread = re.search(rf"\b{re.escape(name)}\b", thread_text) is not None
            in_evidence = re.search(rf"\b{re.escape(name)}\b", evidence) is not None
            rows.append(
                {
                    "blind_id": bid,
                    "system": b["system"],
                    "unit_id": b["unit_id"],
                    "name": name,
                    "in_thread": in_thread,
                    "in_evidence_only": (not in_thread) and in_evidence,
                    "unverifiable": (not in_thread) and (not in_evidence),
                    "human_tone": human.get(bid, {}).get("tone"),
                    "reply": b["reply"][:140],
                }
            )

    by_system: dict[str, dict] = {}
    for r in rows:
        blk = by_system.setdefault(
            r["system"],
            {"greeted_by_name": 0, "in_thread": 0, "in_evidence_only": 0, "unverifiable": 0},
        )
        blk["greeted_by_name"] += 1
        blk["in_thread"] += int(r["in_thread"])
        blk["in_evidence_only"] += int(r["in_evidence_only"])
        blk["unverifiable"] += int(r["unverifiable"])

    # Which of my tone deductions are defensible?
    penalised = [r for r in rows if (r["human_tone"] or 5) <= 2]
    out = {
        "n_replies_greeting_by_name": len(rows),
        "by_system": by_system,
        "my_tone_deductions_on_named_replies": {
            "n_penalised_tone_le_2": len(penalised),
            "of_which_name_provably_from_evidence": sum(r["in_evidence_only"] for r in penalised),
            "of_which_name_unverifiable": sum(r["unverifiable"] for r in penalised),
            "of_which_name_was_in_the_thread": sum(r["in_thread"] for r in penalised),
        },
        "rows": rows,
    }
    out["self_correction"] = write_adjusted()
    out["human_score_variants"] = compare_variants()
    (RESULTS / "name_audit.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=2))
    print("\nper-row detail:")
    for r in rows:
        tag = (
            "IN-THREAD    " if r["in_thread"]
            else "FROM-EVIDENCE" if r["in_evidence_only"]
            else "UNVERIFIABLE "
        )
        print(f"  [{r['blind_id']:>2}] {r['system']:<26} {tag} name={r['name']:<10} my_tone={r['human_tone']}")


if __name__ == "__main__":
    main()
