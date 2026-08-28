"""
Critical remediation runner.

This script intentionally separates:
1. Existing selected-universe corrected results.
2. Bias-controlled results, which remain blocked unless complete historical
   listed/delisted/renamed/merged/suspended universe data is available.

The runner does not fetch network data and does not back-select stocks using
today's liquidity or market cap. It uses only the local, ignored cache files
already required by the V1 study replay.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
import json
import pickle
import platform
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GIT_COMMAND = ["git", "-c", "core.quotePath=false"]

from modules.cross_sectional_ic import (
    build_return_panel,
    build_trading_calendar,
    calc_cross_sectional_ic_series,
)
from modules.factor_portfolio import (
    ANNUAL_FACTOR,
    align_factor_panel_to_execution,
    build_quantile_portfolios,
    calc_portfolio_metrics,
    get_factor_availability_rule,
)
from modules.stats_utils import holm_adjust, spearman_ic_stats
from modules.transaction_cost import (
    TW_ONE_WAY_COST_BASE,
    calc_daily_turnover,
    calc_tc_adjusted_returns,
)
from modules.universe_pit import (
    V1_TICKERS,
    build_v1_selected_universe_snapshot,
    empty_bias_controlled_universe_snapshot,
)


START_DATE = "2021-01-01"
END_DATE = "2026-06-19"
AS_OF_DATE = "2026-06-19"
LAG = 1
N_QUANTILES = 5
MIN_STOCKS = 5
RANDOM_SEED = 42
ONE_WAY_COST = TW_ONE_WAY_COST_BASE

OUT_DIR = ROOT / "results" / "remediation"
UNIVERSE_DIR = OUT_DIR / "universe"
SELECTED_DIR = OUT_DIR / "selected_universe_corrected"
BIAS_DIR = OUT_DIR / "bias_controlled"

UNIVERSE_CACHE = ROOT / "results" / "data" / "universe_data.pkl"
FACTOR_CACHE = ROOT / "results" / "data" / "factor_panels.pkl"

EXPECTED_INPUT_HASHES = {
    "results/data/universe_data.pkl": "ea49d59e4293caa6f77602fe16428cdf704795f18b625d348192909e43a7ee92",
    "results/data/factor_panels.pkl": "0d641852f25fcac8ce9aedc94a47446a24aebeff4dd479e5a75a59ff9f9ecfee",
}

SOURCE_PROVENANCE_DIR = OUT_DIR / "source_provenance"

DIRECT_DEPENDENCIES = [
    "pandas",
    "numpy",
    "scipy",
    "yfinance",
    "requests",
    "plotly",
    "python-dateutil",
    "pytz",
    "streamlit",
    "matplotlib",
    "SQLAlchemy",
    "ta",
    "scikit-learn",
    "openpyxl",
    "pytest",
    "python-dotenv",
]

OLD_OUTPUT_PATHS = [
    "results/metadata.json",
    "results/data/return_panel.csv",
    "results/data/ic_summary_all_factors.csv",
    "results/data/ic_factor_correlations.csv",
    "results/H1/H1_summary.md",
    "results/H1/table_c1_fmb_model_a.csv",
    "results/H1/table_c1_fmb_model_b.csv",
    "results/H1/table_c1_fmb_model_c.csv",
    "results/H1/table_c1_model_comparison.csv",
    "results/H1/table_c2_wald_test.csv",
    "results/H1/table_c3_vif_model_c.csv",
    "results/H2/H2_summary.md",
    "results/H2/table_d1_icir_comparison.csv",
    "results/H2/table_d2_event_ic_quarterly.csv",
    "results/H2/table_d3_h2b_nwhac_summary.csv",
    "results/H3/H3_summary.md",
    "results/H3/table_e1_alpha_by_cap.csv",
    "results/H3/table_e2_ic_by_cap.csv",
    "results/H4/H4_summary.md",
    "results/H4/table_f1_fold_results.csv",
    "results/H4/table_f2_performance_summary.csv",
    "results/H4/table_f3_robustness.csv",
    "results/H4/table_f4_tx_cost_breakeven.csv",
]

CONFIG = {
    "study_name": "critical_remediation_selected_universe_v1",
    "start_date": START_DATE,
    "end_date": END_DATE,
    "as_of_date": AS_OF_DATE,
    "lag": LAG,
    "n_quantiles": N_QUANTILES,
    "min_stocks": MIN_STOCKS,
    "random_seed": RANDOM_SEED,
    "one_way_cost": ONE_WAY_COST,
    "formal_reproduction_command": "python scripts/run_critical_remediation.py",
    "cache_policy": (
        "Read results/data/universe_data.pkl and results/data/factor_panels.pkl "
        "only after verifying pinned SHA-256 hashes before pickle "
        "deserialization; if absent or mismatched, stop rather than fetching "
        "live data or fabricating data. Cache hashes are documented in "
        "results/data/CACHE_INPUTS.md."
    ),
    "execution_policy": (
        "Factor rows are shifted to the first exchange-session close after "
        "their available_at timestamp; lag-1 returns are then computed from "
        "that execution close to the next exchange-session close."
    ),
}

BIAS_BLOCK_REASON = (
    "Blocked: the repository does not contain a complete historical Taiwan "
    "equity universe with delisted, merged, renamed, and suspended securities "
    "plus point-in-time liquidity eligibility. No formal bias-controlled "
    "performance is produced."
)

CLEAN_ENV_STATUS_PATH = OUT_DIR / "clean_env_install_status.json"


def _rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_current_run_output_hashes(generated_paths: list[Path]) -> dict[str, str | None]:
    output_hashes: dict[str, str | None] = {}
    out_root = OUT_DIR.resolve()
    seen: set[Path] = set()
    resolved_paths: list[Path] = []
    for raw_path in generated_paths:
        path = Path(raw_path).resolve()
        if path in seen:
            continue
        seen.add(path)
        resolved_paths.append(path)

    for path in sorted(resolved_paths, key=lambda p: _rel(p)):
        if path.name in {"manifest.json", "manifest.sha256"}:
            continue
        if not path.is_file():
            continue
        try:
            path.relative_to(out_root)
        except ValueError as exc:
            raise RuntimeError(
                "Generated output path is outside the remediation output directory: "
                f"{path.as_posix()}"
            ) from exc
        output_hashes[_rel(path)] = _hash_file(path)
    return output_hashes


def _json_ready(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        val = float(value)
        return val if np.isfinite(val) else None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return _rel(value)
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    return str(value)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_json_ready(data), ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def _validate_universe_cache(data: Any) -> None:
    if not isinstance(data, dict) or not data:
        raise RuntimeError("Universe cache schema is invalid; expected a non-empty ticker dictionary.")
    required = {"date", "open", "high", "low", "close", "volume"}
    for ticker, df in data.items():
        if not isinstance(ticker, str) or not ticker:
            raise RuntimeError("Universe cache schema is invalid; ticker keys must be non-empty strings.")
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise RuntimeError(f"Universe cache schema is invalid for {ticker}; expected a non-empty DataFrame.")
        missing = required.difference(df.columns)
        if missing:
            raise RuntimeError(f"Universe cache schema is invalid for {ticker}; missing columns {sorted(missing)}.")
        dates = pd.to_datetime(df["date"], errors="coerce")
        if dates.notna().sum() == 0:
            raise RuntimeError(f"Universe cache schema is invalid for {ticker}; no parseable dates.")
        close = pd.to_numeric(df["close"], errors="coerce")
        if close.notna().sum() == 0:
            raise RuntimeError(f"Universe cache schema is invalid for {ticker}; no numeric close prices.")


def _validate_factor_cache(data: Any) -> None:
    if not isinstance(data, dict) or not data:
        raise RuntimeError("Factor cache schema is invalid; expected a non-empty factor dictionary.")
    for factor, panel in data.items():
        if not isinstance(factor, str) or not factor:
            raise RuntimeError("Factor cache schema is invalid; factor keys must be non-empty strings.")
        if not isinstance(panel, pd.DataFrame) or panel.empty:
            raise RuntimeError(f"Factor cache schema is invalid for {factor}; expected a non-empty DataFrame.")
        idx = pd.to_datetime(panel.index, errors="coerce")
        if pd.isna(idx).all():
            raise RuntimeError(f"Factor cache schema is invalid for {factor}; no parseable date index.")
        numeric = panel.apply(pd.to_numeric, errors="coerce")
        if numeric.notna().sum().sum() == 0:
            raise RuntimeError(f"Factor cache schema is invalid for {factor}; no numeric factor values.")


def _load_cache(path: Path, expected_sha256: str) -> tuple[Any, dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(
            f"Required local cache is missing: {_rel(path)}. "
            "Restore the exact snapshot documented in results/data/CACHE_INPUTS.md. "
            "The remediation runner stops here to avoid live-data drift."
        )
    actual_sha256 = _hash_file(path)
    expected_sha256 = expected_sha256.lower()
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            "Required local cache hash mismatch before deserialization: "
            f"{_rel(path)} expected {expected_sha256}, observed {actual_sha256}. "
            "The formal runner refuses to open an unverified pickle."
        )
    with path.open("rb") as handle:
        obj = pickle.load(handle)
    meta = {
        "path": _rel(path),
        "sha256": actual_sha256,
        "expected_sha256": expected_sha256,
        "hash_verified_before_deserialization": True,
        "format": "raw_pickle",
        "schema_validated_after_deserialization": False,
    }
    if isinstance(obj, dict) and "__cache_key__" in obj and "data" in obj:
        meta["format"] = "versioned_cache_bundle"
        meta["cache_key"] = obj.get("__cache_key__")
        return obj["data"], meta
    return obj, meta


def _run_git(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            [*GIT_COMMAND, *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return (completed.stdout or completed.stderr).strip()
    except Exception as exc:
        return f"git unavailable: {exc}"


def _dependency_versions() -> dict[str, str | None]:
    versions = {}
    for name in DIRECT_DEPENDENCIES:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _pip_freeze() -> list[str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return [f"pip freeze failed: {completed.stderr.strip()}"]
    return sorted(line.strip() for line in completed.stdout.splitlines() if line.strip())


def _run_git_bytes(args: list[str]) -> tuple[int, bytes, bytes]:
    try:
        completed = subprocess.run(
            [*GIT_COMMAND, *args],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        return completed.returncode, completed.stdout, completed.stderr
    except Exception as exc:
        return 1, b"", str(exc).encode("utf-8", errors="replace")


def _decode_git_path_line(line: str) -> str:
    stripped = line.strip()
    if not (len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"'):
        return stripped

    decoded_bytes = bytearray()
    index = 1
    end = len(stripped) - 1
    while index < end:
        char = stripped[index]
        if char != "\\":
            decoded_bytes.extend(char.encode("utf-8"))
            index += 1
            continue

        index += 1
        if index >= end:
            decoded_bytes.append(ord("\\"))
            break

        escaped = stripped[index]
        if escaped in "01234567":
            octal = escaped
            index += 1
            while index < end and len(octal) < 3 and stripped[index] in "01234567":
                octal += stripped[index]
                index += 1
            decoded_bytes.append(int(octal, 8))
            continue

        escape_map = {
            "a": b"\a",
            "b": b"\b",
            "f": b"\f",
            "n": b"\n",
            "r": b"\r",
            "t": b"\t",
            "v": b"\v",
            "\\": b"\\",
            '"': b'"',
        }
        decoded_bytes.extend(escape_map.get(escaped, escaped.encode("utf-8")))
        index += 1

    return decoded_bytes.decode("utf-8", errors="replace")


def _run_git_lines(args: list[str]) -> list[str]:
    code, stdout, _stderr = _run_git_bytes(args)
    if code != 0:
        return []
    return [
        _decode_git_path_line(line).replace("\\", "/")
        for line in stdout.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]


SOURCE_EXCLUDE_PREFIXES = (
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".venv/",
    "venv/",
    "__pycache__/",
    "docs/screenshots/",
    "results/",
)

SOURCE_EXCLUDE_SUFFIXES = (
    ".pyc",
    ".pyo",
)

SOURCE_DIFF_EXCLUDE_PATTERNS = (
    "results/**",
    "data/**",
    "exports/**",
    ".mypy_cache/**",
    ".pytest_cache/**",
    ".ruff_cache/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    "docs/screenshots/**",
)


def _is_source_file(rel_path: str) -> bool:
    rel = rel_path.replace("\\", "/")
    if any(rel.startswith(prefix) for prefix in SOURCE_EXCLUDE_PREFIXES):
        return False
    if any(rel.endswith(suffix) for suffix in SOURCE_EXCLUDE_SUFFIXES):
        return False
    return (ROOT / rel).is_file()


def _source_file_candidates() -> list[str]:
    tracked = set(_run_git_lines(["ls-files"]))
    untracked = set(_run_git_lines(["ls-files", "--others", "--exclude-standard"]))
    return sorted(rel for rel in tracked.union(untracked) if _is_source_file(rel))


def _working_tree_patch_args() -> list[str]:
    excludes = [f":(exclude){pattern}" for pattern in SOURCE_DIFF_EXCLUDE_PATTERNS]
    return ["diff", "--binary", "HEAD", "--", ".", *excludes]


def _write_source_provenance(generated_paths: list[Path]) -> dict[str, Any]:
    SOURCE_PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    source_files = _source_file_candidates()
    patch_code, patch_stdout, patch_stderr = _run_git_bytes(_working_tree_patch_args())

    file_rows = []
    for rel in source_files:
        path = ROOT / rel
        file_rows.append({
            "path": rel,
            "sha256": _hash_file(path),
            "size_bytes": path.stat().st_size,
        })

    file_hashes_path = SOURCE_PROVENANCE_DIR / "source_file_hashes.csv"
    pd.DataFrame(file_rows).to_csv(file_hashes_path, index=False)
    generated_paths.append(file_hashes_path)

    snapshot_path = SOURCE_PROVENANCE_DIR / "source_snapshot.zip"
    with zipfile.ZipFile(snapshot_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for rel in source_files:
            path = ROOT / rel
            info = zipfile.ZipInfo(rel)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    generated_paths.append(snapshot_path)

    patch_path = SOURCE_PROVENANCE_DIR / "working_tree_patch.diff"
    patch_path.write_bytes(patch_stdout)
    generated_paths.append(patch_path)

    untracked_source_files = [
        rel for rel in _run_git_lines(["ls-files", "--others", "--exclude-standard"])
        if _is_source_file(rel)
    ]
    provenance = {
        "git_commit": _run_git(["rev-parse", "HEAD"]),
        "git_status_short": _run_git(["status", "--short", "--branch"]),
        "source_snapshot_path": _rel(snapshot_path),
        "source_snapshot_sha256": _hash_file(snapshot_path),
        "source_file_hashes_path": _rel(file_hashes_path),
        "source_file_hashes_sha256": _hash_file(file_hashes_path),
        "source_file_count": len(source_files),
        "working_tree_patch_path": _rel(patch_path),
        "working_tree_patch_sha256": _hash_file(patch_path),
        "working_tree_patch_returncode": patch_code,
        "working_tree_patch_stderr": patch_stderr.decode("utf-8", errors="replace").strip(),
        "untracked_source_files": sorted(untracked_source_files),
        "exclusions": {
            "generated_results_and_cache_inputs_excluded_from_source_snapshot": True,
            "generated_results_and_cache_paths_excluded_from_working_tree_patch": True,
            "input_caches_hashed_separately": sorted(EXPECTED_INPUT_HASHES),
            "excluded_prefixes": SOURCE_EXCLUDE_PREFIXES,
            "working_tree_patch_excluded_patterns": SOURCE_DIFF_EXCLUDE_PATTERNS,
        },
        "reproduction_note": (
            "Checking out git_commit alone is insufficient when this field "
            "contains a dirty worktree. Apply the recorded working-tree patch "
            "and restore the source snapshot/untracked source files to "
            "reproduce the exact runner and source used for these outputs."
        ),
    }
    provenance_path = SOURCE_PROVENANCE_DIR / "source_provenance.json"
    _write_json(provenance_path, provenance)
    generated_paths.append(provenance_path)
    provenance["source_provenance_path"] = _rel(provenance_path)
    provenance["source_provenance_sha256"] = _hash_file(provenance_path)
    return provenance


def _read_clean_env_status() -> dict[str, Any]:
    if not CLEAN_ENV_STATUS_PATH.exists():
        return {
            "status": "not_recorded",
            "note": "No clean-env install status file was present when the runner executed.",
        }
    historical = json.loads(CLEAN_ENV_STATUS_PATH.read_text(encoding="utf-8"))
    return {
        "status": "not_attempted_for_current_source",
        "note": (
            "The existing clean-env status file is a historical artifact and is "
            "not reused as current verification after the runtime split. The "
            "main project baseline is requirements.txt on Python 3.11; the "
            "2026-08-02 remediation replay dependency set is requirements.lock.txt."
        ),
        "historical_status_path": _rel(CLEAN_ENV_STATUS_PATH),
        "historical_attempted_on": historical.get("attempted_on"),
        "historical_status": historical.get("status"),
        "historical_failure_stage": historical.get("failure_stage"),
    }


def _data_range(universe_data: dict[str, pd.DataFrame]) -> dict[str, str | None]:
    starts: list[pd.Timestamp] = []
    ends: list[pd.Timestamp] = []
    for df in universe_data.values():
        if "date" in df.columns:
            dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        else:
            dates = pd.to_datetime(df.index, errors="coerce")
            dates = pd.Series(dates).dropna()
        if len(dates):
            starts.append(dates.min())
            ends.append(dates.max())
    return {
        "min_date": min(starts).date().isoformat() if starts else None,
        "max_date": max(ends).date().isoformat() if ends else None,
    }


def _float_or_none(value: Any, digits: int | None = None) -> float | None:
    if value is None:
        return None
    try:
        val = float(value)
    except Exception:
        return None
    if not np.isfinite(val):
        return None
    return round(val, digits) if digits is not None else val


def _pct_or_none(value: Any, digits: int = 4) -> float | None:
    val = _float_or_none(value)
    return round(val * 100, digits) if val is not None else None


def _cagr(returns: pd.Series) -> float | None:
    ret = returns.dropna()
    if len(ret) < 5:
        return None
    total_return = float((1.0 + ret).prod())
    years = len(ret) / ANNUAL_FACTOR
    if total_return <= 0 or years <= 0:
        return None
    return total_return ** (1.0 / years) - 1.0


def _max_drawdown(returns: pd.Series) -> float | None:
    ret = returns.dropna()
    if len(ret) < 5:
        return None
    cumulative = (1.0 + ret).cumprod()
    drawdown = cumulative / cumulative.cummax() - 1.0
    return float(drawdown.min())


def _profit_loss_ratio(returns: pd.Series) -> float | None:
    ret = returns.dropna()
    wins = ret[ret > 0]
    losses = ret[ret < 0]
    if len(wins) == 0 or len(losses) == 0:
        return None
    avg_loss = abs(float(losses.mean()))
    if avg_loss <= 1e-12:
        return None
    return float(wins.mean()) / avg_loss


def _write_universe_outputs(generated_paths: list[Path]) -> pd.DataFrame:
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    selected_snapshot = build_v1_selected_universe_snapshot(
        START_DATE,
        END_DATE,
        AS_OF_DATE,
    )
    selected_path = UNIVERSE_DIR / "selected_universe_snapshot_v1.csv"
    selected_snapshot.to_csv(selected_path, index=False)
    generated_paths.append(selected_path)

    bias_schema = empty_bias_controlled_universe_snapshot()
    bias_schema_path = UNIVERSE_DIR / "bias_controlled_universe_snapshot_schema.csv"
    bias_schema.to_csv(bias_schema_path, index=False)
    generated_paths.append(bias_schema_path)

    bias_status = {
        "layer": "Bias-controlled result",
        "status": "blocked",
        "blocked_reason": BIAS_BLOCK_REASON,
        "required_schema": list(bias_schema.columns),
        "no_formal_performance_generated": True,
        "survivorship_bias_eliminated": False,
        "market_representativeness_claim": "Not supported",
    }
    bias_status_path = BIAS_DIR / "bias_controlled_status.json"
    _write_json(bias_status_path, bias_status)
    generated_paths.append(bias_status_path)
    return selected_snapshot


def _align_factor_panels_to_execution(
    factor_panels: dict[str, pd.DataFrame],
    trading_calendar: pd.DatetimeIndex,
    generated_paths: list[Path],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, list[dict[str, Any]]]:
    aligned_panels: dict[str, pd.DataFrame] = {}
    schedules = []
    rule_rows = []

    for factor in sorted(factor_panels):
        rule = get_factor_availability_rule(factor, return_lag_sessions=LAG)
        aligned, schedule = align_factor_panel_to_execution(
            factor_panels[factor],
            trading_calendar,
            factor_name=factor,
            availability_rule=rule,
            return_lag_sessions=LAG,
        )
        rule_rows.append(rule.to_dict())
        if not aligned.empty:
            aligned_panels[factor] = aligned
        if not schedule.empty:
            schedules.append(schedule)

    rules_path = SELECTED_DIR / "factor_availability_rules.json"
    _write_json(rules_path, {"rules": rule_rows})
    generated_paths.append(rules_path)

    schedule_df = pd.concat(schedules, ignore_index=True) if schedules else pd.DataFrame()
    schedule_path = SELECTED_DIR / "factor_execution_calendar_lag1.csv"
    schedule_df.to_csv(schedule_path, index=False)
    generated_paths.append(schedule_path)

    return aligned_panels, schedule_df, rule_rows


def _compute_ic_summary(
    factor_panels: dict[str, pd.DataFrame],
    return_panel: pd.DataFrame,
    generated_paths: list[Path],
) -> pd.DataFrame:
    rows = []
    ic_series_dict = {}
    for factor in sorted(factor_panels):
        print(f"[IC] {factor}", flush=True)
        panel = factor_panels[factor]
        ic_series = calc_cross_sectional_ic_series(panel, return_panel, min_stocks=MIN_STOCKS).dropna()
        if len(ic_series) < 10:
            rows.append({
                "layer": "Existing selected-universe result",
                "factor": factor,
                "status": "insufficient_observations",
                "T": len(ic_series),
            })
            continue
        ic_series_dict[factor] = ic_series
        stats = spearman_ic_stats(ic_series)
        q05, q25, q50, q75, q95 = np.nanpercentile(ic_series, [5, 25, 50, 75, 95])
        rows.append({
            "layer": "Existing selected-universe result",
            "factor": factor,
            "status": "corrected",
            "signal_execution_policy": "factor_available_at_shifted_to_next_exchange_session_close",
            "T": stats["T"],
            "L_nw": stats["L"],
            "mean_ic": _float_or_none(stats["mean_ic"], 6),
            "std_ic": _float_or_none(stats["std_ic"], 6),
            "icir": _float_or_none(stats["icir"], 4),
            "t_nw": _float_or_none(stats["t_nw"], 4),
            "p_nw": _float_or_none(stats["p_nw"], 6),
            "pct_positive": _float_or_none(stats["pct_positive"], 1),
            "ic_p05": _float_or_none(q05, 4),
            "ic_p25": _float_or_none(q25, 4),
            "ic_p50": _float_or_none(q50, 4),
            "ic_p75": _float_or_none(q75, 4),
            "ic_p95": _float_or_none(q95, 4),
        })

    ic_df = pd.DataFrame(rows)
    if not ic_df.empty and "p_nw" in ic_df.columns:
        valid = ic_df["p_nw"].notna()
        adjusted = [None] * len(ic_df)
        p_values = ic_df.loc[valid, "p_nw"].tolist()
        if p_values:
            for idx, value in zip(ic_df.index[valid], holm_adjust(p_values)):
                adjusted[idx] = round(value, 6)
        ic_df["p_holm"] = adjusted
        ic_df["sig_nw_05"] = ic_df["p_nw"].fillna(1.0) < 0.05
        ic_df["sig_holm_05"] = ic_df["p_holm"].fillna(1.0) < 0.05

    ic_path = SELECTED_DIR / "ic_summary_lag1.csv"
    ic_path.parent.mkdir(parents=True, exist_ok=True)
    ic_df.to_csv(ic_path, index=False)
    generated_paths.append(ic_path)

    if ic_series_dict:
        ic_series_path = SELECTED_DIR / "ic_series_lag1.csv"
        pd.DataFrame(ic_series_dict).to_csv(ic_series_path)
        generated_paths.append(ic_series_path)
    return ic_df


def _compute_portfolio_summary(
    factor_panels: dict[str, pd.DataFrame],
    return_panel: pd.DataFrame,
    generated_paths: list[Path],
) -> pd.DataFrame:
    gross_series: dict[str, pd.Series] = {}
    net_series: dict[str, pd.Series] = {}
    turnover_series: dict[str, pd.Series] = {}
    blocked_rows = []

    for factor in sorted(factor_panels):
        print(f"[Portfolio] {factor}", flush=True)
        panel = factor_panels[factor]
        qport = build_quantile_portfolios(
            panel,
            return_panel,
            n_quantiles=N_QUANTILES,
            min_stocks=MIN_STOCKS,
        )
        if qport.empty or "LS" not in qport.columns:
            blocked_rows.append({
                "layer": "Existing selected-universe result",
                "factor": factor,
                "status": "insufficient_observations",
                "blocked_reason": "No valid long-short quantile return series.",
            })
            continue

        turnover = calc_daily_turnover(
            panel,
            return_panel,
            n_quantiles=N_QUANTILES,
            min_stocks=MIN_STOCKS,
        )
        net = calc_tc_adjusted_returns(qport, turnover, one_way_cost=ONE_WAY_COST)
        gross_series[factor] = qport["LS"].dropna()
        net_series[factor] = net["LS"].dropna() if "LS" in net.columns else qport["LS"].dropna()
        if not turnover.empty and "LS_turnover" in turnover.columns:
            turnover_series[factor] = turnover["LS_turnover"].dropna()

    if not gross_series:
        metrics_df = pd.DataFrame(blocked_rows)
        metrics_path = SELECTED_DIR / "portfolio_metrics_lag1_common_period.csv"
        metrics_df.to_csv(metrics_path, index=False)
        generated_paths.append(metrics_path)
        return metrics_df

    gross_all = pd.DataFrame(gross_series).sort_index().dropna(how="any")
    net_all = pd.DataFrame(net_series).sort_index().reindex(gross_all.index).dropna(how="any")
    common_idx = gross_all.index.intersection(net_all.index)
    gross_common = gross_all.loc[common_idx]
    net_common = net_all.loc[common_idx]

    gross_path = SELECTED_DIR / "ls_returns_lag1_common_period.csv"
    net_path = SELECTED_DIR / "net_ls_returns_lag1_common_period.csv"
    gross_common.to_csv(gross_path)
    net_common.to_csv(net_path)
    generated_paths.extend([gross_path, net_path])

    rows = []
    for factor in gross_common.columns:
        gross = gross_common[factor].dropna()
        net = net_common[factor].dropna()
        metric = calc_portfolio_metrics(gross)
        net_metric = calc_portfolio_metrics(net)
        turnover = turnover_series.get(factor, pd.Series(dtype=float)).reindex(gross.index).dropna()
        rows.append({
            "layer": "Existing selected-universe result",
            "factor": factor,
            "status": "corrected",
            "signal_execution_policy": "factor_available_at_shifted_to_next_exchange_session_close",
            "common_start": gross.index.min().date().isoformat() if len(gross) else None,
            "common_end": gross.index.max().date().isoformat() if len(gross) else None,
            "cagr_pct": _pct_or_none(_cagr(gross), 4),
            "mdd_pct": _pct_or_none(_max_drawdown(gross), 4),
            "sharpe": _float_or_none(metric.get("sharpe"), 4),
            "win_rate_pct": _pct_or_none(metric.get("win_rate"), 2),
            "profit_loss_ratio": _float_or_none(_profit_loss_ratio(gross), 4),
            "sample_count": int(metric.get("n_obs") or 0),
            "avg_daily_turnover_pct": _float_or_none(turnover.mean() * 100, 4) if len(turnover) else None,
            "avg_annual_turnover_x": _float_or_none(turnover.mean() * ANNUAL_FACTOR, 4) if len(turnover) else None,
            "gross_total_return_pct": _float_or_none(((1.0 + gross).prod() - 1.0) * 100, 4),
            "net_after_cost_cagr_pct": _pct_or_none(_cagr(net), 4),
            "net_after_cost_sharpe": _float_or_none(net_metric.get("sharpe"), 4),
            "one_way_cost_bps": _float_or_none(ONE_WAY_COST * 10000, 1),
        })

    rows.extend(blocked_rows)
    metrics_df = pd.DataFrame(rows)
    metrics_path = SELECTED_DIR / "portfolio_metrics_lag1_common_period.csv"
    metrics_df.to_csv(metrics_path, index=False)
    generated_paths.append(metrics_path)

    comparison_rows = metrics_df.copy()
    bias_row = {
        "layer": "Bias-controlled result",
        "factor": "ALL",
        "status": "blocked",
        "common_start": None,
        "common_end": None,
        "cagr_pct": None,
        "mdd_pct": None,
        "sharpe": None,
        "win_rate_pct": None,
        "profit_loss_ratio": None,
        "sample_count": None,
        "avg_daily_turnover_pct": None,
        "avg_annual_turnover_x": None,
        "gross_total_return_pct": None,
        "net_after_cost_cagr_pct": None,
        "net_after_cost_sharpe": None,
        "one_way_cost_bps": _float_or_none(ONE_WAY_COST * 10000, 1),
        "blocked_reason": BIAS_BLOCK_REASON,
    }
    comparison_rows = pd.concat([comparison_rows, pd.DataFrame([bias_row])], ignore_index=True)
    comparison_path = OUT_DIR / "comparison_common_period.csv"
    comparison_rows.to_csv(comparison_path, index=False)
    generated_paths.append(comparison_path)

    return metrics_df


def _old_result_snapshot(generated_paths: list[Path]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "status": "superseded_or_invalidated",
        "old_results_preserved_in_place": True,
    }
    old_ic_path = ROOT / "results" / "data" / "ic_summary_all_factors.csv"
    if old_ic_path.exists():
        old_ic = pd.read_csv(old_ic_path)
        snapshot["old_ic_summary_head"] = old_ic.head(10).to_dict(orient="records")
    old_h4_path = ROOT / "results" / "H4" / "table_f2_performance_summary.csv"
    if old_h4_path.exists():
        old_h4 = pd.read_csv(old_h4_path)
        snapshot["old_h4_performance_summary"] = old_h4.to_dict(orient="records")
    old_metadata_path = ROOT / "results" / "metadata.json"
    if old_metadata_path.exists():
        snapshot["old_metadata"] = json.loads(old_metadata_path.read_text(encoding="utf-8"))

    snapshot_path = OUT_DIR / "old_result_snapshot.json"
    _write_json(snapshot_path, snapshot)
    generated_paths.append(snapshot_path)
    return snapshot


def _write_provenance(generated_paths: list[Path]) -> dict[str, Any]:
    old_outputs = []
    for rel_path in OLD_OUTPUT_PATHS:
        path = ROOT / rel_path
        old_outputs.append({
            "path": rel_path,
            "exists": path.exists(),
            "sha256": _hash_file(path),
            "status": "invalidated" if rel_path == "results/metadata.json" else "superseded",
            "reason": (
                "Old metadata records an environment inconsistent with prior "
                "requirements and notes the former forward-return issue."
                if rel_path == "results/metadata.json"
                else "Preserved in place; superseded by results/remediation outputs with explicit universe provenance."
            ),
        })

    corrected_outputs = []
    for path in sorted(generated_paths, key=lambda p: _rel(p)):
        if not path.exists():
            continue
        rel = _rel(path)
        status = "blocked" if "bias_controlled" in rel else "corrected"
        corrected_outputs.append({
            "path": rel,
            "sha256": _hash_file(path),
            "status": status,
        })

    provenance = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "old_outputs": old_outputs,
        "new_outputs": corrected_outputs,
        "policy": {
            "old_outputs_overwritten": False,
            "selected_universe_and_bias_controlled_separated": True,
            "bias_controlled_formal_result_generated": False,
            "survivorship_bias_eliminated": False,
        },
    }
    provenance_path = OUT_DIR / "provenance.json"
    _write_json(provenance_path, provenance)
    generated_paths.append(provenance_path)
    return provenance


def _write_report(
    ic_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    selected_snapshot: pd.DataFrame,
    generated_paths: list[Path],
) -> None:
    top_ic = ic_df[ic_df.get("status", "") == "corrected"].copy() if not ic_df.empty else pd.DataFrame()
    if not top_ic.empty and "mean_ic" in top_ic.columns:
        top_ic = top_ic.sort_values("mean_ic", ascending=False).head(5)
    metrics_view = metrics_df[metrics_df.get("status", "") == "corrected"].copy() if not metrics_df.empty else pd.DataFrame()
    if not metrics_view.empty and "sharpe" in metrics_view.columns:
        metrics_view = metrics_view.sort_values("sharpe", ascending=False).head(5)
    top_ic_text = top_ic.to_string(index=False) if not top_ic.empty else "No IC rows generated."
    metrics_text = metrics_view.to_string(index=False) if not metrics_view.empty else "No portfolio rows generated."
    clean_status = _read_clean_env_status()

    report = [
        "# Critical Remediation Report",
        "",
        "## Universe Finding",
        "",
        f"- V1 uses {len(selected_snapshot)} hardcoded selected tickers: {', '.join(V1_TICKERS)}.",
        "- The selection date and ex-ante liquidity rule are not encoded in the source data.",
        "- The list contains only currently selected surviving securities available in the V1 cache.",
        "- Complete delisted, merged, renamed, and suspended companies are not available in this repository.",
        "- Therefore V1 is not a complete point-in-time Taiwan equity universe.",
        "",
        "## Result Layers",
        "",
        "- Existing selected-universe result: regenerated under `results/remediation/selected_universe_corrected`.",
        "- Factor signals are shifted from signal date to the first exchange-session close after `available_at`; no close-derived or flow-derived signal receives the same close as its entry price.",
        "- Bias-controlled result: blocked; only schema and status files were generated.",
        "",
        "## Corrected IC Top Rows",
        "",
        "```text",
        top_ic_text,
        "```",
        "",
        "## Corrected Portfolio Top Rows",
        "",
        "```text",
        metrics_text,
        "```",
        "",
        "## Conclusion",
        "",
        "Conclusions are downgraded to the selected 16-stock universe only. They do not represent the full Taiwan stock market.",
        "",
        "## Clean Environment",
        "",
        f"Status: {clean_status.get('status', 'not_recorded')}.",
        clean_status.get("policy", clean_status.get("note", "")),
    ]
    report_path = OUT_DIR / "critical_remediation_report.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    generated_paths.append(report_path)


def main() -> int:
    t0 = time.perf_counter()
    np.random.seed(RANDOM_SEED)
    for path in [OUT_DIR, UNIVERSE_DIR, SELECTED_DIR, BIAS_DIR]:
        path.mkdir(parents=True, exist_ok=True)

    generated_paths: list[Path] = []
    source_provenance = _write_source_provenance(generated_paths)

    universe_data, universe_cache_meta = _load_cache(
        UNIVERSE_CACHE,
        EXPECTED_INPUT_HASHES[_rel(UNIVERSE_CACHE)],
    )
    factor_panels, factor_cache_meta = _load_cache(
        FACTOR_CACHE,
        EXPECTED_INPUT_HASHES[_rel(FACTOR_CACHE)],
    )
    if not isinstance(universe_data, dict) or not isinstance(factor_panels, dict):
        raise RuntimeError("Cache format is invalid; expected dictionaries.")
    _validate_universe_cache(universe_data)
    _validate_factor_cache(factor_panels)
    universe_cache_meta["schema_validated_after_deserialization"] = True
    factor_cache_meta["schema_validated_after_deserialization"] = True

    selected_snapshot = _write_universe_outputs(generated_paths)
    universe_hash = _hash_bytes(selected_snapshot.to_csv(index=False).encode("utf-8"))

    trading_calendar = build_trading_calendar(universe_data)
    aligned_factor_panels, execution_schedule, availability_rules = _align_factor_panels_to_execution(
        factor_panels,
        trading_calendar,
        generated_paths,
    )
    if not aligned_factor_panels:
        raise RuntimeError("No factor panels remained after execution-date alignment.")

    return_panel = build_return_panel(universe_data, lag=LAG, trading_calendar=trading_calendar)
    return_panel_path = SELECTED_DIR / "return_panel_lag1.csv"
    return_panel.to_csv(return_panel_path)
    generated_paths.append(return_panel_path)

    ic_df = _compute_ic_summary(aligned_factor_panels, return_panel, generated_paths)
    metrics_df = _compute_portfolio_summary(aligned_factor_panels, return_panel, generated_paths)
    old_snapshot = _old_result_snapshot(generated_paths)
    _write_report(ic_df, metrics_df, selected_snapshot, generated_paths)
    provenance = _write_provenance(generated_paths)

    config_hash = _hash_bytes(
        json.dumps(CONFIG, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )
    output_hashes = _build_current_run_output_hashes(generated_paths)

    manifest = {
        "manifest_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "execution_time_seconds": round(time.perf_counter() - t0, 3),
        "git_commit": _run_git(["rev-parse", "HEAD"]),
        "git_status_short": _run_git(["status", "--short", "--branch"]),
        "source_provenance": source_provenance,
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "dependency_versions": _dependency_versions(),
        "pip_freeze": _pip_freeze(),
        "data_range": {
            "configured_start": START_DATE,
            "configured_end": END_DATE,
            "cache_coverage": _data_range(universe_data),
            "canonical_trading_calendar": {
                "source": "union_of_observed_local_cache_dates",
                "session_count": len(trading_calendar),
                "start": trading_calendar.min().date().isoformat() if len(trading_calendar) else None,
                "end": trading_calendar.max().date().isoformat() if len(trading_calendar) else None,
            },
        },
        "universe": {
            "layer": "Existing selected-universe result",
            "ticker_count": len(V1_TICKERS),
            "tickers": V1_TICKERS,
            "snapshot_path": "results/remediation/universe/selected_universe_snapshot_v1.csv",
            "universe_hash_sha256": universe_hash,
            "not_complete_point_in_time": True,
            "survivorship_bias_eliminated": False,
        },
        "bias_controlled": {
            "status": "blocked",
            "blocked_reason": BIAS_BLOCK_REASON,
            "formal_result_generated": False,
            "snapshot_schema_path": "results/remediation/universe/bias_controlled_universe_snapshot_schema.csv",
            "status_path": "results/remediation/bias_controlled/bias_controlled_status.json",
        },
        "config": CONFIG,
        "config_hash_sha256": config_hash,
        "execution_alignment": {
            "policy": CONFIG["execution_policy"],
            "factor_availability_rules": availability_rules,
            "execution_calendar_path": "results/remediation/selected_universe_corrected/factor_execution_calendar_lag1.csv",
            "execution_calendar_rows": int(len(execution_schedule)),
            "return_panel_index": "execution_date",
            "same_close_entry_allowed": False,
        },
        "input_hashes": {
            universe_cache_meta["path"]: universe_cache_meta["sha256"],
            factor_cache_meta["path"]: factor_cache_meta["sha256"],
        },
        "pickle_deserialization_guard": {
            "policy": "expected SHA-256 verified before pickle.load; schema validated after load",
            "all_pickle_inputs_hash_verified_before_deserialization": all(
                meta.get("hash_verified_before_deserialization")
                for meta in [universe_cache_meta, factor_cache_meta]
            ),
            "expected_input_hashes": EXPECTED_INPUT_HASHES,
        },
        "input_cache_metadata": {
            "universe_data": universe_cache_meta,
            "factor_panels": factor_cache_meta,
        },
        "old_result_snapshot": old_snapshot,
        "provenance_summary": provenance["policy"],
        "clean_environment_verification": _read_clean_env_status(),
        "output_hashes": output_hashes,
        "formal_outputs": {
            "selected_universe_ic": "results/remediation/selected_universe_corrected/ic_summary_lag1.csv",
            "selected_universe_portfolio": "results/remediation/selected_universe_corrected/portfolio_metrics_lag1_common_period.csv",
            "fair_comparison": "results/remediation/comparison_common_period.csv",
            "manifest": "results/remediation/manifest.json",
            "provenance": "results/remediation/provenance.json",
            "source_provenance": "results/remediation/source_provenance/source_provenance.json",
        },
    }

    manifest_path = OUT_DIR / "manifest.json"
    _write_json(manifest_path, manifest)
    manifest_sha_path = OUT_DIR / "manifest.sha256"
    manifest_sha_path.write_text(_hash_file(manifest_path) + "  manifest.json\n", encoding="utf-8")

    print(f"Wrote remediation outputs to {_rel(OUT_DIR)}")
    print(f"Manifest: {_rel(manifest_path)}")
    print("Bias-controlled result: blocked; see bias_controlled/bias_controlled_status.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
