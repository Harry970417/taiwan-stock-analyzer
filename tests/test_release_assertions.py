# tests/test_release_assertions.py
# Loads the SAME release source the dashboard page reads (via
# modules.display_mode, showcase mode) and asserts the locked, formal
# headline numbers and verdicts have not silently drifted. Uses numeric
# tolerances (pytest.approx), not brittle formatted-string comparisons --
# a value stored as 12.67000001 must still pass, and a value that has
# actually changed to 12.5 must still fail.
#
# This is a release-integrity regression test, not a place to re-derive or
# re-justify the numbers: if a check here ever needs to change, that means
# the underlying release package changed, and the reason belongs in a
# commit message / the Phase 3.5 report, not a loosened tolerance here.
#
# Run: python -m pytest tests/test_release_assertions.py -v

from pathlib import Path

import pandas as pd
import pytest

from modules.display_mode import SHOWCASE, get_data_root, get_dataset_path
from modules.release_validation import FORBIDDEN_PHRASES, NEGATION_PREFIXES

ROOT = Path(__file__).resolve().parent.parent
TOL = 0.01  # absolute tolerance for stored percentage figures


@pytest.fixture(scope="module")
def core_metrics():
    return pd.read_csv(get_dataset_path(ROOT, "core_metrics", SHOWCASE)).iloc[0]


@pytest.fixture(scope="module")
def strategy_comparison():
    return pd.read_csv(get_dataset_path(ROOT, "strategy_comparison", SHOWCASE))


@pytest.fixture(scope="module")
def manifest():
    import json
    return json.loads((get_data_root(ROOT, SHOWCASE) / "manifest.json").read_text(encoding="utf-8"))


def test_active_strategy_cagr(core_metrics):
    assert core_metrics["active_fixed5050_median_cagr_pct"] == pytest.approx(12.67, abs=TOL)


def test_active_strategy_mdd(core_metrics):
    assert core_metrics["active_fixed5050_median_mdd_pct"] == pytest.approx(-17.08, abs=TOL)


def test_benchmark_cagr(core_metrics):
    assert core_metrics["benchmark_0050_qqq_cagr_pct"] == pytest.approx(18.04, abs=TOL)


def test_benchmark_mdd(core_metrics):
    assert core_metrics["benchmark_0050_qqq_mdd_pct"] == pytest.approx(-22.55, abs=TOL)


def test_pct_seeds_beating_benchmark_is_zero(core_metrics):
    assert core_metrics["pct_seeds_beating_benchmark"] == pytest.approx(0.0, abs=TOL)


def test_pct_seeds_positive_cagr_is_full(core_metrics):
    assert core_metrics["pct_seeds_positive_cagr"] == pytest.approx(100.0, abs=TOL)


def test_active_result_type_is_multi_seed_median(manifest):
    assert manifest["primary_result_type"] == "multi_seed_median"


def test_seed_42_is_not_the_primary_kpi(manifest):
    assert manifest["seed_42_is_primary"] is False
    assert manifest["random_seed_count"] == 30


def test_risk_parity_is_rejected(strategy_comparison):
    row = strategy_comparison.set_index("strategy_key").loc["risk_parity"]
    assert "淘汰" in row["verdict"]
    assert "保留" not in row["verdict"]


def test_dynamic_allocation_is_rejected(strategy_comparison):
    row = strategy_comparison.set_index("strategy_key").loc["dynamic"]
    assert "淘汰" in row["verdict"]
    assert "保留" not in row["verdict"]


def test_fixed_5050_is_retained_for_drawdown_control_research(strategy_comparison):
    row = strategy_comparison.set_index("strategy_key").loc["fixed_50_50"]
    assert "保留" in row["verdict"]
    assert "淘汰" not in row["verdict"]


def test_manifest_agrees_with_csv_on_eliminated_and_retained_keys(manifest, strategy_comparison):
    comp = strategy_comparison.set_index("strategy_key")
    for key in manifest["eliminated_strategy_keys"]:
        assert "淘汰" in comp.loc[key, "verdict"], f"{key} should be eliminated per manifest but CSV disagrees"
    for key in manifest["retained_strategy_keys"]:
        assert "保留" in comp.loc[key, "verdict"], f"{key} should be retained per manifest but CSV disagrees"


def _contains_unnegated_phrase(text: str, phrase: str) -> bool:
    start = 0
    while True:
        idx = text.find(phrase, start)
        if idx == -1:
            return False
        preceding = text[idx - 1] if idx > 0 else ""
        if preceding not in NEGATION_PREFIXES:
            return True
        start = idx + len(phrase)


def test_no_prohibited_claims_in_first_screen_text(core_metrics, manifest):
    """'First screen' = the one-line verdict + KPI card labels/sub-text, i.e.
    exactly what a viewer sees without scrolling. Reconstructs that text from
    the same manifest.formal_verdict string the page renders verbatim."""
    first_screen_text = manifest["formal_verdict"]
    violations = [p for p in FORBIDDEN_PHRASES if _contains_unnegated_phrase(first_screen_text, p)]
    assert not violations, f"forbidden phrase(s) found in first-screen verdict text: {violations}"
