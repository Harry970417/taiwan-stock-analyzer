"""Render docs/PHASE3_TW_US_COMBINED_REPORT.md to a standalone HTML file."""
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent.parent
MD_PATH = ROOT / "docs" / "PHASE3_TW_US_COMBINED_REPORT.md"
OUT_DIR = ROOT / "exports" / "tw_us_backtest" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

md_text = MD_PATH.read_text(encoding="utf-8")
body_html = markdown.markdown(md_text, extensions=["tables", "fenced_code"])

html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Phase 3 -- TW+US Combined Portfolio Report</title>
<style>
body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 0.9rem; }}
th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
th {{ background: #f0f0f0; }}
code {{ background: #f5f5f5; padding: 1px 4px; border-radius: 3px; }}
h1, h2, h3 {{ border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }}
hr {{ border: none; border-top: 1px solid #ddd; margin: 2rem 0; }}
</style></head><body>
{body_html}
</body></html>"""

out_path = OUT_DIR / "PHASE3_TW_US_COMBINED_REPORT.html"
out_path.write_text(html, encoding="utf-8")
print(f"Wrote {out_path}")
