import pandas as pd

from modules.universe_pit import (
    UNIVERSE_SNAPSHOT_COLUMNS,
    V1_TICKERS,
    build_v1_selected_universe_snapshot,
    empty_bias_controlled_universe_snapshot,
)


def test_v1_selected_universe_snapshot_schema_and_limitations():
    snapshot = build_v1_selected_universe_snapshot(
        start_date="2021-01-01",
        end_date="2026-06-19",
        as_of_date="2026-06-19",
    )

    assert list(snapshot.columns) == UNIVERSE_SNAPSHOT_COLUMNS
    assert len(snapshot) == len(V1_TICKERS)
    assert set(snapshot["ticker"]) == set(V1_TICKERS)
    assert (snapshot["selection_reason"] == "Existing hardcoded V1 selected survivor list").all()
    assert (snapshot["liquidity_rule"] == "No historical ex-ante liquidity rule encoded").all()
    assert (snapshot["delisted_at"] == "").all()


def test_bias_controlled_snapshot_is_schema_only_when_historical_data_absent():
    snapshot = empty_bias_controlled_universe_snapshot()

    assert isinstance(snapshot, pd.DataFrame)
    assert list(snapshot.columns) == UNIVERSE_SNAPSHOT_COLUMNS
    assert snapshot.empty
