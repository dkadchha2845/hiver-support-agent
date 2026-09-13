"""Assemble REPORT.md from report/*.md, substituting live numbers.

Placeholders:
  {{TABLES}}                      -> results/tables_core.md (the page-budget subset)
  {{N:dotted.path.in.json}}       -> a raw number
  {{P:dotted.path.in.json}}       -> the same number as a percentage, 1dp
  {{F:file.json:dotted.path}}     -> a value from another results/*.json file
  {{FP:file.json:dotted.path}}    -> the same, as a percentage

This exists so no number in the report can drift from the artefacts that produced it:
`make eval` regenerates the metrics and then rebuilds the report from them.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REPORT_DIR = ROOT / "report"
OUT = ROOT / "REPORT.md"

_cache: dict[str, dict] = {}


def load(name: str) -> dict:
    if name not in _cache:
        _cache[name] = json.loads((RESULTS / name).read_text())
    return _cache[name]


def dig(obj, path: str):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def fmt_num(v) -> str:
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return str(v)


def fmt_pct(v) -> str:
    return f"{float(v) * 100:.1f}%"


PATTERN = re.compile(r"\{\{(TABLES|N|P|FP|F):?([^}]*)\}\}")


def substitute(text: str) -> tuple[str, list[str]]:
    missing: list[str] = []

    def repl(m: re.Match) -> str:
        kind, arg = m.group(1), m.group(2)
        try:
            if kind == "TABLES":
                return (RESULTS / "tables_core.md").read_text().strip()
            if kind in {"F", "FP"}:
                fname, path = arg.split(":", 1)
                value = dig(load(fname), path)
                return fmt_pct(value) if kind == "FP" else fmt_num(value)
            value = dig(load("metrics.json"), arg)
            return fmt_pct(value) if kind == "P" else fmt_num(value)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{m.group(0)} -> {type(exc).__name__}: {exc}")
            return f"**[MISSING: {arg}]**"

    return PATTERN.sub(repl, text), missing


README_HEADLINE = """### Headline

| | agent (S3) | copy-paste baseline (B1) | trivial (B0) |
|---|---|---|---|
| **Trustworthy Automation Rate** — send-ready *and* correctly auto-routed | **{tar}** ({tar_w} reweighted) | **{tar_b}** ({tar_bw}) | {tar_0} |
| **Unsafe auto-handle rate** — judge-independent, gates deployment | **{unsafe}** [{u_lo}, {u_hi}] | {unsafe_b} | {unsafe_0} |
| Escalation recall | **{esc}** | {esc_b} | 100% (escalates everything) |
| Intent macro-F1 / strict acc / lenient acc | **{f1}** / {acc} / {lacc} | {f1_b} / {acc_b} / - | {f1_0} |
| Judge send-ready rate | {sr} | {sr_b} | {sr_0} |

Spotify's own replies, scored blind by the same judge: **{sr_h}** send-ready.

**The agent loses to the copy-paste baseline on my own headline metric, and wins on every
axis the judge does not touch.** That is the central finding, not a footnote — see
[REPORT.md](REPORT.md) §3.3 and §5.1-5.3 for why I believe the judge is wrong about B1 and
why that is a flaw in a rubric I wrote. The judge's false-pass rate against my own blind
hand-scoring is **{fp}**, and it disagrees with itself on **{flip}** of replies when
resampled.
"""


def render_readme_headline() -> None:
    """Keep the README's headline block in sync with results/metrics.json."""
    readme = ROOT / "README.md"
    text = readme.read_text()
    if "<!-- HEADLINE -->" not in text:
        return
    sysmap = load("metrics.json")["systems"]
    m, b = sysmap["S3_agent"], sysmap["B1_simple"]
    z, h = sysmap["B0_trivial_escalate_all"], sysmap["HUMAN_brand_reply"]
    ja = load("judge_agreement_primary.json")
    sens = load("judge_sensitivity.json")
    block = README_HEADLINE.format(
        tar=fmt_pct(m["TAR"]["rate"]),
        tar_w=fmt_pct(m["TAR"]["rate_weighted"]),
        tar_b=fmt_pct(b["TAR"]["rate"]),
        tar_bw=fmt_pct(b["TAR"]["rate_weighted"]),
        tar_0=fmt_pct(z["TAR"]["rate"]),
        unsafe=fmt_pct(m["routing"]["unsafe_auto_rate"]),
        u_lo=fmt_pct(m["routing"]["unsafe_auto_rate_ci95"][0]),
        u_hi=fmt_pct(m["routing"]["unsafe_auto_rate_ci95"][1]),
        unsafe_b=fmt_pct(b["routing"]["unsafe_auto_rate"]),
        unsafe_0=fmt_pct(z["routing"]["unsafe_auto_rate"]),
        esc=fmt_pct(m["routing"]["escalation_recall"]),
        esc_b=fmt_pct(b["routing"]["escalation_recall"]),
        f1=fmt_num(m["intent"]["macro_f1"]),
        f1_b=fmt_num(b["intent"]["macro_f1"]),
        f1_0=fmt_num(z["intent"]["macro_f1"]),
        acc=fmt_pct(m["intent"]["accuracy_strict"]),
        acc_b=fmt_pct(b["intent"]["accuracy_strict"]),
        lacc=fmt_pct(m["intent"]["accuracy_lenient"]),
        sr=fmt_pct(m["reply_quality"]["send_ready_rate"]),
        sr_b=fmt_pct(b["reply_quality"]["send_ready_rate"]),
        sr_0=fmt_pct(z["reply_quality"]["send_ready_rate"]),
        sr_h=fmt_pct(h["reply_quality"]["send_ready_rate"]),
        fp=fmt_pct(ja["send_ready"]["false_pass_rate"]),
        flip=fmt_pct(sens["stability"]["S3_agent"]["send_ready_flip_rate"]),
    )
    start = text.index("<!-- HEADLINE -->") + len("<!-- HEADLINE -->")
    end = text.index("<!-- /HEADLINE -->")
    readme.write_text(text[:start] + "\n" + block.strip() + "\n" + text[end:])
    print("refreshed the README headline block")


def main() -> None:
    parts = sorted(REPORT_DIR.glob("*.md"))
    if not parts:
        sys.exit("no report/*.md sections found")
    body = "\n\n".join(p.read_text().strip() for p in parts)
    out, missing = substitute(body)
    OUT.write_text(out.rstrip() + "\n")
    words = len(out.split())
    print(f"built {OUT.name} from {len(parts)} sections: {words:,} words")
    try:
        render_readme_headline()
    except Exception as exc:  # noqa: BLE001
        print(f"(README headline not refreshed: {exc})")
    if missing:
        print("UNRESOLVED PLACEHOLDERS:")
        for m in missing:
            print("  -", m)
        sys.exit(1)


if __name__ == "__main__":
    main()
