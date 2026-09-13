"""Render REPORT.md to a print-ready PDF.

markdown -> styled HTML -> PDF via headless Chrome (no LaTeX, no pandoc).
Typography is tuned to keep the report inside its page budget while staying readable:
9.6pt base, tight tables, and no page breaks inside a table or across a heading.

    make pdf
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "REPORT.md"
HTML = ROOT / "results" / "REPORT.html"
PDF = ROOT / "REPORT.pdf"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
]

CSS = """
@page { size: A4; margin: 11mm 12mm 12mm 12mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  font-family: "Charter", "Georgia", "Times New Roman", serif;
  font-size: 9.05pt; line-height: 1.25; color: #15181c; margin: 0;
  hyphens: auto; -webkit-hyphens: auto;
}
h1 {
  font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  font-size: 15.5pt; line-height: 1.12; margin: 0 0 5pt; letter-spacing: -0.2pt;
  border-bottom: 1.6pt solid #15181c; padding-bottom: 5pt;
}
h2 {
  font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  font-size: 11.4pt; margin: 10pt 0 3.5pt; padding-bottom: 2pt;
  border-bottom: 0.6pt solid #c8ccd2; break-after: avoid; letter-spacing: -0.1pt;
}
h3 {
  font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  font-size: 9.9pt; margin: 8.5pt 0 2.5pt; break-after: avoid;
}
h2:first-of-type { margin-top: 10pt; }
p { margin: 0 0 4.1pt; orphans: 2; widows: 2; }
strong { color: #000; }
em { color: #2c3138; }
code, kbd {
  font-family: "SF Mono", "Menlo", "Consolas", monospace; font-size: 8.3pt;
  background: #f2f4f7; padding: 0.5pt 2.2pt; border-radius: 2pt; color: #1a3a5c;
}
a { color: #0b4f8a; text-decoration: none; }
table {
  border-collapse: collapse; width: 100%; margin: 6pt 0 8pt;
  font-size: 8.3pt; break-inside: avoid;
}
th, td {
  border: 0.4pt solid #ccd1d8; padding: 2pt 3.2pt; text-align: left;
  vertical-align: top;
}
th {
  background: #eef1f5; font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  font-weight: 600; font-size: 7.5pt;
}
tbody tr:nth-child(even) { background: #fafbfc; }
blockquote {
  margin: 5pt 0; padding: 3.2pt 8pt; border-left: 2pt solid #9aa4b1;
  background: #f7f8fa; font-size: 8.6pt; break-inside: avoid;
}
blockquote p { margin: 0 0 3pt; }
blockquote p:last-child { margin-bottom: 0; }
ul, ol { margin: 0 0 5pt; padding-left: 14pt; }
li { margin-bottom: 2pt; }
hr { border: none; border-top: 0.6pt solid #d4d8de; margin: 8pt 0; }
.footer {
  margin-top: 9pt; padding-top: 4pt; border-top: 0.6pt solid #d4d8de;
  font-size: 7.6pt; color: #5a636e; line-height: 1.3;
}
"""


def find_chrome() -> str:
    for path in CHROME_CANDIDATES:
        if path and Path(path).exists():
            return path
    sys.exit(
        "No Chrome/Chromium found. Install one, or convert REPORT.md with your own tool."
    )


def main() -> None:
    text = SRC.read_text()
    # The italic "Length:" note is a repo-navigation aid and spans several lines; the PDF
    # footer carries the same pointers, so drop the whole paragraph.
    text = re.sub(r"\n\*Length: this is the 6-page report\..*?\*\s*\n", "\n", text, flags=re.S)
    body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "sane_lists", "attr_list"]
    )
    html = f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Can we trust this agent? A support agent for @SpotifyCares</title>
<style>{CSS}</style></head>
<body>
{body}
<div class="footer">
<strong>Dhrumil Kadchha &middot; Hiver SDE intern take-home &middot;
github.com/dkadchha2845/hiver-support-agent</strong> &mdash;
<code>make setup &amp;&amp; make repro</code> regenerates every number above from committed
artefacts in <strong>49s</strong> on a fresh clone, byte-identically, without generating a
token. Decision log: <code>DECISIONS.md</code>; labelling protocol:
<code>data/golden/LABELLING.md</code>; remaining tables: <code>results/tables.md</code>.
</div>
</body></html>
"""
    HTML.write_text(html)
    chrome = find_chrome()
    subprocess.run(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=4000",
            f"--print-to-pdf={PDF}",
            HTML.as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    size_kb = PDF.stat().st_size // 1024
    print(f"wrote {PDF.relative_to(ROOT)} ({size_kb} KB) via {Path(chrome).name}")


if __name__ == "__main__":
    main()
