# tests/test_trade_ledger.py
# Run: python -m pytest tests/test_trade_ledger.py -v

import numpy as np
import pandas as pd
import pytest

from modules.trade_ledger import build_trade_ledger, LEDGER_COLUMNS

DATES = pd.to_datetime(["2024-01-02", "2024-02-01", "2024-03-01", "2024-04-01"])


def _universe(prices: dict) -> dict:
    """prices: {symbol: [open/close price at each of the 4 DATES]} (open==close for simplicity)."""
    out = {}
    for sym, vals in prices.items():
        out[sym] = pd.DataFrame({"date": DATES, "open": vals, "close": vals})
    return out


def _rec(period_index, entry_date, exit_date, weights, fold=1, capital=1_000_000.0):
    return {
        "period_index": period_index, "fold": fold,
        "train_start": pd.Timestamp("2020-01-01"), "train_end": pd.Timestamp("2023-01-01"),
        "test_start": DATES[0], "test_end": DATES[-1],
        "signal_date": entry_date - pd.Timedelta(days=1),
        "entry_date": entry_date, "exit_date": exit_date,
        "weights": pd.Series(weights), "capital_at_entry": capital,
    }


class TestBuildTradeLedger:
    def test_empty_period_records(self):
        df = build_trade_ledger("TW", "balanced", [], {}, DATES)
        assert df.empty
        assert list(df.columns) == LEDGER_COLUMNS

    def test_continuing_vs_dropped_vs_still_open(self):
        # A held periods 0,1,2 (continuing -> open at end)
        # B held period 0 only (dropped after period 0)
        # C held periods 1,2 (new at period 1, continuing -> open at end)
        universe = _universe({
            "A": [100.0, 100.0, 100.0, 100.0],
            "B": [100.0, 110.0, 110.0, 110.0],
            "C": [100.0, 100.0, 100.0, 130.0],
        })
        period_records = [
            _rec(0, DATES[0], DATES[1], {"A": 0.5, "B": 0.5}),
            _rec(1, DATES[1], DATES[2], {"A": 0.5, "C": 0.5}),
            _rec(2, DATES[2], DATES[3], {"A": 0.5, "C": 0.5}),
        ]
        ledger = build_trade_ledger("TW", "balanced", period_records, universe, DATES, one_way_cost=0.0)

        a = ledger[ledger["symbol"] == "A"]
        assert len(a) == 1
        assert a.iloc[0]["status"] == "open"
        assert a.iloc[0]["entry_date"] == DATES[0]

        b = ledger[ledger["symbol"] == "B"]
        assert len(b) == 1
        assert b.iloc[0]["status"] == "closed"
        assert b.iloc[0]["exit_reason"] == "rebalance_drop"
        assert b.iloc[0]["entry_date"] == DATES[0]
        assert b.iloc[0]["exit_date"] == DATES[1]
        # entry_price=100, exit_price=110, allocation=0.5*1_000_000=500_000, shares=5000
        # gross_pnl = 5000*(110-100) = 50_000, no cost -> net_pnl == gross_pnl
        assert b.iloc[0]["gross_pnl"] == pytest.approx(50_000.0)
        assert b.iloc[0]["net_pnl"] == pytest.approx(50_000.0)
        assert b.iloc[0]["return_pct"] == pytest.approx(50_000.0 / 500_000.0)

        c = ledger[ledger["symbol"] == "C"]
        assert len(c) == 1
        assert c.iloc[0]["status"] == "open"
        assert c.iloc[0]["entry_date"] == DATES[1]  # entered when it first appeared, not period 0

    def test_entry_cost_and_exit_cost_applied(self):
        universe = _universe({"B": [100.0, 110.0, 110.0, 110.0]})
        period_records = [
            _rec(0, DATES[0], DATES[1], {"B": 1.0}),
            _rec(1, DATES[1], DATES[2], {}),  # B dropped
        ]
        ledger = build_trade_ledger("TW", "balanced", period_records, universe, DATES, one_way_cost=0.01)
        row = ledger.iloc[0]
        # allocation = 1_000_000, shares = 10_000, entry_cost = 1_000_000*0.01=10_000
        # exit value = 10_000*110 = 1_100_000, exit_cost = 1_100_000*0.01 = 11_000
        # gross_pnl = 10_000*(110-100) = 100_000 ; net_pnl = 100_000 - 10_000 - 11_000 = 79_000
        assert row["entry_cost"] == pytest.approx(10_000.0)
        assert row["exit_cost"] == pytest.approx(11_000.0)
        assert row["net_pnl"] == pytest.approx(79_000.0)

    def test_stop_loss_triggers_within_continuing_run(self):
        # Position held periods 0 and 1 continuously; price crashes -20% on day 3 (2024-03-01)
        # with a 10% stop -> should close early at that date, not ride to period 1's natural exit.
        universe = _universe({"X": [100.0, 100.0, 80.0, 80.0]})
        period_records = [
            _rec(0, DATES[0], DATES[1], {"X": 1.0}),
            _rec(1, DATES[1], DATES[2], {"X": 1.0}),
        ]
        ledger = build_trade_ledger(
            "TW", "balanced", period_records, universe, DATES,
            stop_loss_pct=0.10, one_way_cost=0.0,
        )
        row = ledger.iloc[0]
        assert row["status"] == "closed"
        assert row["exit_reason"] == "stop_loss"
        assert row["exit_date"] == DATES[2]
        assert row["exit_price"] == pytest.approx(100.0 * 0.90)  # entry*(1-stop_pct)

    def test_missing_price_data_skips_symbol(self):
        period_records = [_rec(0, DATES[0], DATES[1], {"GHOST": 1.0})]
        ledger = build_trade_ledger("TW", "balanced", period_records, {}, DATES)
        assert ledger.empty
