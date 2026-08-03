"""
BACKTEST_DISPLAY_MODE=showcase|research

Showcase (default): reads ONLY the versioned, git-tracked release package
under assets/backtest_release/v1/. No external API, no network, no
gitignored exports/ directory, no backtest execution, no financial-data
download. This is the deployment default and the only mode a fresh
`git clone` needs to render the dashboard page.

Research: may read the complete (gitignored, regenerated-by-pipeline)
exports/tw_us_backtest/ working directory, for local development and
audit workflows. Not the deployment default -- must be explicitly opted
into via the environment variable.

get_data_root()'s showcase branch is the ONLY return statement reachable
when mode == SHOWCASE -- there is no conditional path in this function by
which showcase mode can resolve to exports/. tests/test_display_mode.py
asserts this directly (including for garbage/unset env var values, which
fall back to showcase, never to research).
"""
import os
from pathlib import Path

SHOWCASE = "showcase"
RESEARCH = "research"
VALID_MODES = (SHOWCASE, RESEARCH)

# Logical dataset name -> relative path, per mode. Showcase paths are the
# flat, curated release filenames; research paths are the raw Phase 3/3.5
# working-directory layout under exports/tw_us_backtest/.
SHOWCASE_PATHS = {
    "strategy_comparison": "strategy_comparison.csv",
    "core_metrics": "core_metrics.csv",
    "multi_seed_summary": "multi_seed_summary.csv",
    "subperiod_summary": "subperiod_summary.csv",
    "cost_stress_summary": "cost_stress_summary.csv",
    "remove_best_year_summary": "remove_best_year_summary.csv",
    "drawdown_summary": "drawdown_summary.csv",
}
RESEARCH_PATHS = {
    "strategy_comparison": "summary/final_comparison_table.csv",
    "core_metrics": "summary/final_kpi_headline.csv",
    "multi_seed_summary": "robustness/combined_multi_seed_summary.csv",
    "subperiod_summary": "combined/combined_subperiod_results.csv",
    "cost_stress_summary": "combined/combined_cost_stress.csv",
    "remove_best_year_summary": "combined/combined_remove_best_year.csv",
    "drawdown_summary": "combined/combined_mdd_quantification.csv",
}


def get_display_mode() -> str:
    """Reads BACKTEST_DISPLAY_MODE from the environment. Any value other
    than exactly 'research' (case-insensitive) resolves to 'showcase' --
    unset, empty, misspelled, or garbage input all fail safe to showcase."""
    raw = os.environ.get("BACKTEST_DISPLAY_MODE", SHOWCASE).strip().lower()
    return RESEARCH if raw == RESEARCH else SHOWCASE


def get_data_root(root: Path, mode: str | None = None) -> Path:
    """Resolve the data root directory for the given display mode.
    mode=None reads BACKTEST_DISPLAY_MODE from the environment."""
    resolved_mode = mode if mode in VALID_MODES else get_display_mode()
    if resolved_mode == RESEARCH:
        return root / "exports" / "tw_us_backtest"
    return root / "assets" / "backtest_release" / "v1"


def get_dataset_path(root: Path, dataset_key: str, mode: str | None = None) -> Path:
    """Resolve the full path to a named dataset for the given mode."""
    resolved_mode = mode if mode in VALID_MODES else get_display_mode()
    rel_map = RESEARCH_PATHS if resolved_mode == RESEARCH else SHOWCASE_PATHS
    if dataset_key not in rel_map:
        raise KeyError(f"Unknown dataset key {dataset_key!r} for mode {resolved_mode!r}")
    data_root = get_data_root(root, resolved_mode)
    return data_root / rel_map[dataset_key]
