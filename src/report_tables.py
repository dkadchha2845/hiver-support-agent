"""Render the markdown tables the report and README quote, straight from metrics.json.

Nothing in the report is typed by hand; if a number changes, `make eval` changes it.
"""
from __future__ import annotations

import json

from config import RESULTS

LABELS = {
    "B0_trivial_escalate_all": "B0 trivial (escalate all + canned reply)",
    "B0_trivial_auto_all": "B0 trivial (auto all + canned reply)",
    "B1_simple": "B1 simple (TF-IDF+LogReg / lexicon / NN reply)",
    "S2_agent_noretrieval": "S2 agent, no retrieval (ablation)",
    "S4_agent_llmrouter": "S4 agent, LLM router (ablation)",
    "S3_agent": "S3 agent (headline)",
    "HUMAN_brand_reply": "HUMAN @SpotifyCares reply actually sent",
}
ORDER = list(LABELS)


def fmt(x, pct: bool = False) -> str:
    if x is None:
        return "-"
    if isinstance(x, (list, tuple)):
        return f"[{x[0]:.2f}, {x[1]:.2f}]"
    return f"{x*100:.1f}%" if pct else f"{x:.3f}"


def main() -> None:
    m = json.loads((RESULTS / "metrics.json").read_text())
    S = m["systems"]
    lines: list[str] = []

    lines.append("### Table 1 - Headline comparison (n = %d golden units)\n" % m["golden_set"]["n"])
    lines.append(
        "| system | intent macro-F1 | intent acc | escalation recall | unsafe auto-handle | "
        "auto coverage | send-ready | TAR |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for k in ORDER:
        if k not in S:
            continue
        r = S[k]
        i = r.get("intent", {})
        rt = r.get("routing", {})
        q = r.get("reply_quality", {})
        t = r.get("TAR", {})
        lines.append(
            f"| {LABELS[k]} | {fmt(i.get('macro_f1'))} | {fmt(i.get('accuracy_strict'), True)} | "
            f"{fmt(rt.get('escalation_recall'), True)} | {fmt(rt.get('unsafe_auto_rate'), True)} | "
            f"{fmt(rt.get('auto_coverage'), True)} | {fmt(q.get('send_ready_rate'), True)} | "
            f"{fmt(t.get('rate'), True)} |"
        )

    lines.append("\n### Table 2 - Judge rubric means (1-5, higher is better)\n")
    lines.append("| system | grounded | resolution | tone | safety | overall | chars | % with unsupported claims |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for k in ORDER:
        q = S.get(k, {}).get("reply_quality")
        if not q:
            continue
        ms = q["mean_scores"]
        lines.append(
            f"| {LABELS[k]} | {ms['groundedness']:.2f} | {ms['resolution']:.2f} | "
            f"{ms['tone']:.2f} | {ms['safety']:.2f} | {q['mean_overall']:.2f} | "
            f"{q['mean_reply_chars']:.0f} | {fmt(q['pct_with_unsupported_claims'], True)} |"
        )

    lines.append("\n### Table 3 - Confidence intervals on the numbers that matter\n")
    lines.append("| system | send-ready [95% CI] | unsafe auto [95% CI] | TAR [95% CI] | TAR reweighted to inbox mix |")
    lines.append("|---|---|---|---|---|")
    for k in ORDER:
        r = S.get(k, {})
        q, rt, t = r.get("reply_quality"), r.get("routing"), r.get("TAR")
        if not (q or rt):
            continue
        lines.append(
            f"| {LABELS[k]} | {fmt(q['send_ready_rate'], True) if q else '-'} "
            f"{fmt(q['send_ready_ci95']) if q else ''} | "
            f"{fmt(rt['unsafe_auto_rate'], True) if rt else '-'} "
            f"{fmt(rt['unsafe_auto_rate_ci95']) if rt else ''} | "
            f"{fmt(t['rate'], True) if t else '-'} {fmt(t['ci95']) if t else ''} | "
            f"{fmt(t['rate_weighted'], True) if t else '-'} |"
        )

    lines.append("\n### Table 3b - Handoff compliance on escalate-routed drafts\n")
    lines.append("| system | escalate-routed | draft mentions a handoff | compliance |")
    lines.append("|---|---|---|---|")
    for k in ORDER:
        h = S.get(k, {}).get("handoff_compliance")
        if not h:
            continue
        lines.append(
            f"| {LABELS[k]} | {h['n_escalate_routed']} | {h['mentions_handoff']} | "
            f"{fmt(h['rate'], True)} |"
        )

    lines.append(
        "\n### Table 3c - Fabricated agent signatures (the draft prompt forbids sign-offs)\n"
    )
    lines.append("| system | n | replies ending in an agent signature | rate |")
    lines.append("|---|---|---|---|")
    for k in ORDER:
        v = S.get(k, {}).get("style_leakage")
        if not v:
            continue
        lines.append(
            f"| {LABELS[k]} | {v['n']} | {v['replies_ending_in_an_agent_signature']} | "
            f"{fmt(v['rate'], True)} |"
        )

    sl = m.get("slices_S3_agent", {})
    if sl:
        lines.append("\n### Table 4 - Where the headline hides things (S3 agent)\n")
        lines.append("| slice | n | intent acc | unsafe auto-handle | send-ready |")
        lines.append("|---|---|---|---|---|")
        groups = [
            ("opening message", sl["by_position"].get("opener", {})),
            ("mid-thread follow-up", sl["by_position"].get("follow_up", {})),
            ("annotator: clear", sl["by_annotator_difficulty"].get("clear", {})),
            ("annotator: judgement call", sl["by_annotator_difficulty"].get("flagged_hard", {})),
        ]
        for name, blk in sl["by_stratum"].items():
            groups.append((f"stratum: {name}", blk))
        for name, blk in groups:
            if not blk:
                continue
            lines.append(
                f"| {name} | {blk['n']} | {fmt(blk.get('intent_strict_acc'), True)} | "
                f"{fmt(blk.get('unsafe_auto_rate'), True)} | {fmt(blk.get('send_ready_rate'), True)} |"
            )

    if sl.get("by_gold_intent"):
        lines.append("\n### Table 5 - Per-intent performance (S3 agent)\n")
        lines.append("| gold intent | n | intent acc | unsafe auto-handle | send-ready |")
        lines.append("|---|---|---|---|---|")
        for name, blk in sorted(sl["by_gold_intent"].items(), key=lambda kv: -kv[1]["n"]):
            lines.append(
                f"| {name} | {blk['n']} | {fmt(blk.get('intent_strict_acc'), True)} | "
                f"{fmt(blk.get('unsafe_auto_rate'), True)} | {fmt(blk.get('send_ready_rate'), True)} |"
            )

    mc = m.get("matched_ablation_comparison", {})
    if mc:
        lines.append(
            "\n### Table 5b - Ablations, compared on the same units as the headline system\n"
        )
        lines.append(
            "| ablation | n | system | intent macro-F1 | intent acc | escalation recall | "
            "unsafe auto | auto coverage | send-ready |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for abl, blk in mc.items():
            for name in ("S3_agent", abl):
                v = blk.get(name)
                if not v:
                    continue
                lines.append(
                    f"| {LABELS.get(abl, abl)} | {blk['n_shared_units']} | "
                    f"{LABELS.get(name, name)} | {fmt(v.get('intent_macro_f1'))} | "
                    f"{fmt(v.get('intent_strict_acc'), True)} | "
                    f"{fmt(v.get('escalation_recall'), True)} | "
                    f"{fmt(v.get('unsafe_auto_rate'), True)} | "
                    f"{fmt(v.get('auto_coverage'), True)} | "
                    f"{fmt(v.get('send_ready_rate'), True)} |"
                )

    ja_path = RESULTS / "judge_agreement_primary.json"
    if ja_path.exists():
        ja = json.loads(ja_path.read_text())
        lines.append(f"\n### Table 6 - Judge vs human on {ja['n']} blind-scored replies\n")
        lines.append("| dimension | human mean | judge mean | judge bias | within 1 | QWK | Spearman |")
        lines.append("|---|---|---|---|---|---|---|")
        for d, v in ja["per_dimension"].items():
            lines.append(
                f"| {d} | {v['human_mean']:.2f} | {v['judge_mean']:.2f} | "
                f"{v['bias_judge_minus_human']:+.2f} | {fmt(v['within_1'], True)} | "
                f"{v['qwk']:.2f} | {v['spearman']:.2f} |"
            )
        sr = ja["send_ready"]
        lines.append(
            f"\nSend-ready decision: human {fmt(sr['human_rate'], True)}, judge "
            f"{fmt(sr['judge_rate'], True)}, raw agreement {fmt(sr['agreement'], True)}, "
            f"kappa {sr['kappa']}. The judge waved through "
            f"{sr['judge_waved_through_human_would_block']} replies a human would block "
            f"and blocked {sr['judge_blocked_human_would_send']} a human would send "
            f"(false-pass rate {fmt(sr['false_pass_rate'], True)} "
            f"{fmt(sr['false_pass_rate_ci95'])})."
        )
        lines.append(
            f"\nSystem ranking by mean rubric score - human: {' > '.join(ja['system_ranking']['human'])}; "
            f"judge: {' > '.join(ja['system_ranking']['judge'])}; "
            f"identical: **{ja['system_ranking']['ranking_identical']}**."
        )

    aa_path = RESULTS / "annotator_agreement.json"
    if aa_path.exists():
        aa = json.loads(aa_path.read_text())
        lines.append(
            f"\n### Table 7 - Annotator second pass (n={aa['n']})\n\n"
            f"Intent agreement {fmt(aa['intent_agreement'], True)} (kappa {aa['intent_kappa']}), "
            f"route agreement {fmt(aa['route_agreement'], True)} (kappa {aa['route_kappa']}). "
            "Read the caveat in the report before believing this number."
        )

    out = "\n".join(lines) + "\n"
    (RESULTS / "tables.md").write_text(out)

    # The report has a page budget, so it embeds only the four tables an argument
    # cannot be made without. The rest stay in results/tables.md.
    CORE = ("### Table 1", "### Table 6")
    blocks: list[list[str]] = []
    for raw in lines:
        line = raw.lstrip("\n")
        if line.startswith("### Table"):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(raw)
    core = [
        "\n".join(b).strip()
        for b in blocks
        if any(b[0].startswith(c) for c in CORE)
    ]
    (RESULTS / "tables_core.md").write_text("\n\n".join(core) + "\n")
    print(out)
    print(f"[wrote results/tables.md ({len(blocks)} tables) and tables_core.md ({len(core)})]")


if __name__ == "__main__":
    main()
