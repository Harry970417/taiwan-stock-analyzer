# modules/report_styles.py
# Academic A4 print-compatible stylesheet for the research report.
# Extracted from report_generator.py to keep the main module readable.

_REPORT_CSS = """
<style>
  /* ─── Reset & Base ─────────────────────────────────────────────────── */
  *, *::before, *::after { box-sizing: border-box; }

  body {
    font-family: "Times New Roman", Times, serif;
    font-size: 11pt;
    line-height: 1.55;
    color: #1a1a1a;
    background: #ffffff;
    margin: 0;
    padding: 0;
  }

  /* ─── Page layout (A4) ──────────────────────────────────────────────── */
  .page {
    max-width: 210mm;
    margin: 0 auto;
    padding: 20mm 25mm;
  }

  /* ─── Cover page ────────────────────────────────────────────────────── */
  .cover {
    text-align: center;
    padding: 40mm 20mm 20mm 20mm;
    border-bottom: 2px solid #1a3a5c;
    margin-bottom: 20px;
    page-break-after: always;
  }
  .cover h1 {
    font-size: 26pt;
    color: #1a3a5c;
    margin: 0 0 8px 0;
    letter-spacing: 0.05em;
  }
  .cover .subtitle {
    font-size: 14pt;
    color: #4a4a4a;
    margin-bottom: 10px;
  }
  .cover .date {
    font-size: 10pt;
    color: #6a6a6a;
  }
  .cover .platform {
    font-size: 9pt;
    color: #8a8a8a;
    margin-top: 30px;
  }
  .cover .disclaimer-box {
    border: 1px solid #cc9900;
    background: #fffbe6;
    padding: 10px 14px;
    margin-top: 24px;
    font-size: 8.5pt;
    text-align: left;
    color: #5a4a00;
    border-radius: 3px;
  }

  /* ─── Section headings ───────────────────────────────────────────────── */
  h2 {
    font-size: 14pt;
    color: #1a3a5c;
    border-bottom: 1.5px solid #1a3a5c;
    padding-bottom: 4px;
    margin-top: 24px;
    margin-bottom: 10px;
    page-break-after: avoid;
  }
  h3 {
    font-size: 11.5pt;
    color: #2c4a6c;
    margin-top: 16px;
    margin-bottom: 6px;
    page-break-after: avoid;
  }
  h4 {
    font-size: 10.5pt;
    color: #444;
    margin-top: 12px;
    margin-bottom: 4px;
  }

  /* ─── Section wrapper ────────────────────────────────────────────────── */
  .section {
    margin-bottom: 28px;
  }

  /* ─── Executive summary ──────────────────────────────────────────────── */
  .exec-summary {
    background: #f4f7fc;
    border-left: 4px solid #1a3a5c;
    padding: 12px 16px;
    margin-bottom: 18px;
    border-radius: 0 3px 3px 0;
  }
  .exec-summary ul {
    margin: 0;
    padding-left: 20px;
  }
  .exec-summary li {
    margin-bottom: 6px;
    font-size: 10.5pt;
  }

  /* ─── Tables ─────────────────────────────────────────────────────────── */
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9.5pt;
    margin: 10px 0 14px 0;
    page-break-inside: avoid;
  }
  thead tr {
    background: #1a3a5c;
    color: #ffffff;
  }
  thead th {
    padding: 6px 10px;
    text-align: left;
    font-weight: bold;
    font-size: 9pt;
    letter-spacing: 0.03em;
  }
  tbody tr:nth-child(even) {
    background: #f0f4f8;
  }
  tbody tr:hover {
    background: #e8eef5;
  }
  tbody td {
    padding: 5px 10px;
    border-bottom: 1px solid #dce3ec;
    vertical-align: top;
  }
  .col-num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-family: "Courier New", monospace;
  }
  .col-sig {
    color: #006600;
    font-weight: bold;
  }
  .col-warn {
    color: #cc3300;
  }
  .col-neutral {
    color: #444;
  }

  /* ─── Grade / score badges ───────────────────────────────────────────── */
  .grade-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-weight: bold;
    font-size: 11pt;
  }
  .grade-a-plus { background: #c8f0c8; color: #004400; }
  .grade-a      { background: #d8f0d0; color: #005500; }
  .grade-b      { background: #fff0c0; color: #664400; }
  .grade-c      { background: #ffe0c0; color: #883300; }
  .grade-d      { background: #ffc0c0; color: #880000; }

  /* ─── Chart figure ───────────────────────────────────────────────────── */
  .chart-container {
    margin: 12px 0;
    text-align: center;
    page-break-inside: avoid;
  }
  .chart-container img {
    max-width: 100%;
    height: auto;
    border: 1px solid #dce3ec;
    border-radius: 2px;
  }
  .chart-caption {
    font-size: 8.5pt;
    color: #666;
    margin-top: 4px;
    font-style: italic;
  }

  /* ─── Info boxes ─────────────────────────────────────────────────────── */
  .info-box {
    background: #f8f9fa;
    border: 1px solid #d0d7e0;
    padding: 10px 14px;
    margin: 10px 0;
    border-radius: 3px;
    font-size: 9.5pt;
  }
  .warn-box {
    background: #fff8e6;
    border: 1px solid #e0c060;
    padding: 10px 14px;
    margin: 10px 0;
    border-radius: 3px;
    font-size: 9.5pt;
  }
  .error-box {
    background: #fff0f0;
    border: 1px solid #e08080;
    padding: 10px 14px;
    margin: 10px 0;
    border-radius: 3px;
    font-size: 9.5pt;
    color: #880000;
  }

  /* ─── Methodology / footnote text ───────────────────────────────────── */
  .methodology {
    font-size: 8.5pt;
    color: #555;
    border-top: 1px solid #dce3ec;
    padding-top: 8px;
    margin-top: 16px;
  }

  /* ─── Print settings ─────────────────────────────────────────────────── */
  @media print {
    body { font-size: 10pt; }
    .page { padding: 15mm 20mm; }
    .no-print { display: none; }
    h2 { page-break-after: avoid; }
    table { page-break-inside: avoid; }
    .cover { page-break-after: always; }
  }
</style>
"""
