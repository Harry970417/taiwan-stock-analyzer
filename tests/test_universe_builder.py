import pandas as pd

from modules.universe_builder import build_universe


def _synthetic_df(n_days: int, early_volume: float, late_volume: float, split: int) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    volume = [early_volume] * split + [late_volume] * (n_days - split)
    return pd.DataFrame({
        "date": dates,
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
        "volume": volume,
    })


def test_liquidity_filter_uses_only_the_earliest_min_days_not_whole_period_mean(monkeypatch):
    # A ticker that was illiquid for its first 60 trading days (below the
    # 500k threshold) and only became liquid much later. Its whole-period
    # mean volume clears the threshold, but at selection time (using only
    # the earliest min_days) it should not — PROJECT_AUDIT_2026.md C6.
    df = _synthetic_df(n_days=300, early_volume=100_000, late_volume=2_000_000, split=60)

    monkeypatch.setattr(
        "modules.universe_builder.get_stock_data",
        lambda ticker, period="2y", force_refresh=False: df,
    )

    result = build_universe(["LATE_LIQUID"], min_days=60, min_avg_volume_k=500)

    assert "LATE_LIQUID" not in result["data"]
    assert "LATE_LIQUID" in result["excluded"]
    assert "流動性不足" in result["excluded"]["LATE_LIQUID"]


def test_liquidity_filter_passes_a_ticker_liquid_from_the_start(monkeypatch):
    df = _synthetic_df(n_days=300, early_volume=2_000_000, late_volume=2_000_000, split=60)

    monkeypatch.setattr(
        "modules.universe_builder.get_stock_data",
        lambda ticker, period="2y", force_refresh=False: df,
    )

    result = build_universe(["EARLY_LIQUID"], min_days=60, min_avg_volume_k=500)

    assert "EARLY_LIQUID" in result["data"]
