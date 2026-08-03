"""
Single source of truth for what makes assets/backtest_release/v*/ a valid,
untampered, non-overclaiming release package.

Used by two callers that must never drift apart:
  - scripts/dev/validate_release_assets.py (standalone CLI gate, run before
    any push/deploy)
  - pages/15_台美股策略回測.py (runtime guard, refuses to render the showcase
    page on an invalid or tampered release)

Every check here is read-only. Nothing in this module writes to the release
package or to exports/.
"""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

# Forbidden promotional/overclaiming phrases -- must never appear in any
# release text file (reports, manifest text fields, CSV label columns).
# Mirrors the forbidden-phrase list locked in PHASE3_TW_US_COMBINED_REPORT.md
# and enforced on the dashboard page.
FORBIDDEN_PHRASES = [
    "最佳投資策略", "穩定獲利", "高報酬低風險", "打敗市場", "AI精準選股",
    "已證明可以獲利", "優於被動基準", "打敗基準", "創造超額報酬", "已驗證高報酬",
    "beats the passive benchmark", "outperforms the passive benchmark",
]

# Characters that, immediately preceding a forbidden phrase, negate it into
# the correct/required claim instead of the prohibited one (e.g. "未優於被動基準"
# = "did NOT outperform the benchmark" -- the accurate finding -- contains
# "優於被動基準" as a raw substring but must not be flagged).
NEGATION_PREFIXES = ("未", "不", "非", "沒", "無法")

# Secret / personal-data patterns. Deliberately broad and cheap (regex only,
# no entropy scoring) -- a release package should contain zero matches.
SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS access key"),
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI-style secret key"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub personal access token"),
    (r"(?i)api[_-]?key\s*[:=]\s*['\"][^'\"]{8,}", "inline api_key=... value"),
    (r"(?i)(secret|token|password)\s*[:=]\s*['\"][^'\"]{6,}", "inline secret/token/password value"),
    (r"[Cc]:\\Users\\[^\\\"'\s]+", "absolute Windows user path"),
    (r"/home/[^/\"'\s]+", "absolute Unix home path"),
]

REQUIRED_COLUMNS = {
    "core_metrics.csv": [
        "active_fixed5050_median_cagr_pct", "active_fixed5050_median_mdd_pct",
        "benchmark_0050_qqq_cagr_pct", "benchmark_0050_qqq_mdd_pct",
        "pct_seeds_beating_benchmark", "pct_seeds_positive_cagr",
        "worst_seed_cagr_pct", "best_seed_cagr_pct",
    ],
    "strategy_comparison.csv": [
        "strategy_key", "label_zh", "cagr_pct", "mdd_pct", "verdict", "category",
    ],
    "multi_seed_summary.csv": [
        "allocation", "n_seeds", "median_cagr_pct", "p10_cagr_pct", "p90_cagr_pct",
        "median_mdd_pct", "pct_beating_0050_qqq_benchmark",
        "worst_seed_cagr_pct", "worst_seed_positive", "best_seed_cagr_pct",
    ],
    "subperiod_summary.csv": [
        "period", "start", "end", "cagr_pct", "mdd_pct",
        "benchmark_0050_qqq_cagr_pct", "excess_vs_benchmark_pp",
    ],
    "cost_stress_summary.csv": [
        "allocation", "cost_scenario", "cagr_pct", "mdd_pct",
        "still_below_0050_qqq_benchmark",
    ],
    "drawdown_summary.csv": [
        "strategy", "cagr_pct", "mdd_pct", "longest_drawdown_days",
        "drawdown_recovery_days",
    ],
    "remove_best_year_summary.csv": [
        "config", "baseline_cagr_pct", "version",
    ],
    "annual_returns.csv": ["year", "annual_return_pct"],
    "monthly_returns.csv": ["year", "month", "monthly_return_pct"],
}

MDD_COLUMNS = {
    "strategy_comparison.csv": ["mdd_pct"],
    "multi_seed_summary.csv": ["median_mdd_pct", "p10_mdd_pct", "p90_mdd_pct"],
    "subperiod_summary.csv": ["mdd_pct"],
    "cost_stress_summary.csv": ["mdd_pct"],
    "drawdown_summary.csv": ["mdd_pct"],
    "core_metrics.csv": ["active_fixed5050_median_mdd_pct", "benchmark_0050_qqq_mdd_pct"],
}


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def run_all_checks(release_dir: Path) -> list[dict]:
    """Run every release-integrity check and return a list of
    {"name": str, "passed": bool, "detail": str} dicts, one per check.
    Never raises -- a check that errors is recorded as a failure."""
    results: list[dict] = []

    def record(name, passed, detail):
        results.append({"name": name, "passed": passed, "detail": detail})

    manifest_path = release_dir / "manifest.json"
    if not manifest_path.exists():
        record("manifest.json exists and is valid JSON", False, f"missing: {manifest_path}")
        return results  # nothing else can be checked without a manifest

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        record("manifest.json exists and is valid JSON", True, "OK")
    except Exception as exc:
        record("manifest.json exists and is valid JSON", False, f"{type(exc).__name__}: {exc}")
        return results

    manifest_files = {f["path"]: f for f in manifest.get("files", [])}

    # 2. all manifest-listed files exist
    try:
        missing = [p for p in manifest_files if not (release_dir / p).exists()]
        record("all manifest-listed files exist on disk", not missing,
               "OK" if not missing else f"missing files: {missing}")
    except Exception as exc:
        record("all manifest-listed files exist on disk", False, str(exc))

    # 3. checksums match
    try:
        mismatches = []
        for rel_path, entry in manifest_files.items():
            full = release_dir / rel_path
            if not full.exists():
                continue
            if _sha256_of(full) != entry["sha256"]:
                mismatches.append(rel_path)
        record("SHA-256 checksums match for every manifest-listed file", not mismatches,
               "OK" if not mismatches else f"checksum mismatch: {mismatches}")
    except Exception as exc:
        record("SHA-256 checksums match for every manifest-listed file", False, str(exc))

    # 4. no unexpected files
    try:
        on_disk = {
            str(p.relative_to(release_dir)).replace("\\", "/")
            for p in release_dir.rglob("*")
            if p.is_file() and p.name != "manifest.json"
        }
        unexpected = on_disk - set(manifest_files.keys())
        record("no unexpected files present beyond manifest + manifest.json itself", not unexpected,
               "OK" if not unexpected else f"untracked files present: {sorted(unexpected)}")
    except Exception as exc:
        record("no unexpected files present beyond manifest + manifest.json itself", False, str(exc))

    # 5. primary_result_type
    v = manifest.get("primary_result_type")
    record('manifest.primary_result_type == "multi_seed_median"', v == "multi_seed_median", f"got {v!r}")

    # 6. random_seed_count
    v = manifest.get("random_seed_count")
    record("manifest.random_seed_count == 30", v == 30, f"got {v!r}")

    # 7. strategy/benchmark names match
    try:
        strat_key = manifest.get("primary_strategy_key")
        bench_key = manifest.get("primary_benchmark_key")
        comp = pd.read_csv(release_dir / "strategy_comparison.csv")
        ms = pd.read_csv(release_dir / "multi_seed_summary.csv")
        problems = []
        if strat_key not in set(comp["strategy_key"]):
            problems.append(f"primary_strategy_key {strat_key!r} not in strategy_comparison.csv")
        if strat_key not in set(ms["allocation"]):
            problems.append(f"primary_strategy_key {strat_key!r} not in multi_seed_summary.csv")
        if bench_key not in set(comp["strategy_key"]):
            problems.append(f"primary_benchmark_key {bench_key!r} not in strategy_comparison.csv")
        eliminated = set(manifest.get("eliminated_strategy_keys", []))
        retained = set(manifest.get("retained_strategy_keys", []))
        if eliminated & retained:
            problems.append(f"strategy_key listed as both eliminated and retained: {eliminated & retained}")
        record("primary strategy/benchmark keys match the formal release", not problems,
               "OK" if not problems else "; ".join(problems))
    except Exception as exc:
        record("primary strategy/benchmark keys match the formal release", False, str(exc))

    # 8. required columns
    try:
        problems = []
        for fname, required_cols in REQUIRED_COLUMNS.items():
            path = release_dir / fname
            if not path.exists():
                problems.append(f"{fname}: file missing")
                continue
            cols = set(pd.read_csv(path, nrows=0).columns)
            missing_cols = [c for c in required_cols if c not in cols]
            if missing_cols:
                problems.append(f"{fname}: missing columns {missing_cols}")
        record("required columns present in every release CSV", not problems,
               "OK" if not problems else "; ".join(problems))
    except Exception as exc:
        record("required columns present in every release CSV", False, str(exc))

    # 9. percentage unit consistency
    try:
        problems = []
        for csv_path in sorted(release_dir.glob("*.csv")):
            df = pd.read_csv(csv_path)
            pct_cols = [c for c in df.columns if c.endswith("_pct") or c.endswith("_pp")]
            for col in pct_cols:
                vals = pd.to_numeric(df[col], errors="coerce").dropna()
                if vals.empty:
                    continue
                if vals.abs().max() <= 1.0 and (vals == 0).any() and (vals == 1).any():
                    problems.append(f"{csv_path.name}:{col} looks like a 0/1 fraction under a '_pct' name")
                out_of_band = vals[(vals > 500) | (vals < -500)]
                if not out_of_band.empty:
                    problems.append(f"{csv_path.name}:{col} out-of-band value(s)")
        record("percentage-suffixed columns use a consistent scale", not problems,
               "OK" if not problems else "; ".join(problems))
    except Exception as exc:
        record("percentage-suffixed columns use a consistent scale", False, str(exc))

    # 10. MDD sign
    try:
        problems = []
        for fname, cols in MDD_COLUMNS.items():
            path = release_dir / fname
            if not path.exists():
                continue
            df = pd.read_csv(path)
            for col in cols:
                if col not in df.columns:
                    continue
                vals = pd.to_numeric(df[col], errors="coerce").dropna()
                positive = vals[vals > 0]
                if not positive.empty:
                    problems.append(f"{fname}:{col} has positive MDD value(s)")
        record("all MDD columns are <= 0", not problems, "OK" if not problems else "; ".join(problems))
    except Exception as exc:
        record("all MDD columns are <= 0", False, str(exc))

    # 11. dates valid
    try:
        problems = []

        def check_date_str(label, s):
            try:
                dt = datetime.fromisoformat(str(s)[:10])
            except ValueError:
                problems.append(f"{label}: unparsable date {s!r}")
                return
            if not (2015 <= dt.year <= 2030):
                problems.append(f"{label}: date {s!r} outside sane bound")

        window = manifest.get("source_sample_window", "")
        if " to " in window:
            start_s, end_s = window.split(" to ")
            check_date_str("source_sample_window start", start_s)
            check_date_str("source_sample_window end", end_s)

        sp = pd.read_csv(release_dir / "subperiod_summary.csv")
        for _, row in sp.iterrows():
            check_date_str(f"subperiod start ({row['period']})", row["start"])
            check_date_str(f"subperiod end ({row['period']})", row["end"])

        dd = pd.read_csv(release_dir / "drawdown_summary.csv")
        for _, row in dd.iterrows():
            if pd.notna(row.get("max_drawdown_date")):
                check_date_str(f"max_drawdown_date ({row['strategy']})", row["max_drawdown_date"])

        ar = pd.read_csv(release_dir / "annual_returns.csv")
        bad_years = ar[(ar["year"] < 2015) | (ar["year"] > 2030)]
        if not bad_years.empty:
            problems.append(f"annual_returns.csv out-of-bound year(s): {list(bad_years['year'])}")

        record("date fields parse and fall within a sane bound (2015-2030)", not problems,
               "OK" if not problems else "; ".join(problems))
    except Exception as exc:
        record("date fields parse and fall within a sane bound (2015-2030)", False, str(exc))

    # 12. source commit present
    commit = manifest.get("source_commit", "")
    commit_ok = bool(commit) and commit != "unknown" and bool(re.fullmatch(r"[0-9a-f]{7,40}", commit))
    record("manifest.source_commit is present and looks like a real git hash", commit_ok,
           f"got {commit!r}" if not commit_ok else f"OK ({commit[:12]})")

    # 13. secrets scan
    try:
        problems = []
        text_files = list(release_dir.rglob("*.json")) + list(release_dir.rglob("*.csv")) + \
            list(release_dir.rglob("*.md")) + list(release_dir.rglob("*.html"))
        for path in text_files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern, label in SECRET_PATTERNS:
                m = re.search(pattern, text)
                if m:
                    problems.append(f"{path.relative_to(release_dir)}: possible {label}")
        record("no API keys, tokens, personal paths, or secrets", not problems,
               "OK" if not problems else "; ".join(problems))
    except Exception as exc:
        record("no API keys, tokens, personal paths, or secrets", False, str(exc))

    # 14. seed 42 not primary
    seed42_ok = manifest.get("seed_42_is_primary") is False and manifest.get("primary_result_type") == "multi_seed_median"
    record("seed 42 is not the primary result", seed42_ok,
           "OK" if seed42_ok else f"seed_42_is_primary={manifest.get('seed_42_is_primary')!r}")

    # 15. forbidden phrases
    try:
        problems = []
        text_files = list(release_dir.rglob("*.json")) + list(release_dir.rglob("*.csv")) + \
            list(release_dir.rglob("*.md")) + list(release_dir.rglob("*.html"))
        for path in text_files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for phrase in FORBIDDEN_PHRASES:
                start = 0
                while True:
                    idx = text.find(phrase, start)
                    if idx == -1:
                        break
                    preceding_char = text[idx - 1] if idx > 0 else ""
                    if preceding_char not in NEGATION_PREFIXES:
                        problems.append(f"{path.relative_to(release_dir)}: forbidden phrase {phrase!r}")
                    start = idx + len(phrase)
        record("no prohibited promotional/overclaiming phrases", not problems,
               "OK" if not problems else "; ".join(problems))
    except Exception as exc:
        record("no prohibited promotional/overclaiming phrases", False, str(exc))

    return results


def is_release_valid(release_dir: Path) -> tuple[bool, list[dict]]:
    """Convenience wrapper: (all_passed, results)."""
    results = run_all_checks(release_dir)
    all_passed = bool(results) and all(r["passed"] for r in results)
    return all_passed, results
