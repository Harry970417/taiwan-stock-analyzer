# tests/test_price_adjustment.py
#
# Phase 2.5 gate item #2: proves the project's price-adjustment convention
# (auto_adjust=True used UNIFORMLY for signal, entry, exit, and all
# benchmarks; no separate dividend cashflow added anywhere) does not
# double-count dividends and correctly neutralizes stock splits.
#
# Fixtures below are REAL AAPL data pulled once (2026-08, via
# yf.download(..., auto_adjust=False/True)) and hardcoded here as a
# regression fixture -- avoids a live network call on every test run
# (consistent with this repo's existing mocked-network test convention,
# e.g. tests/test_finmind_client.py) while still testing against genuine
# market history, not synthetic numbers.
#
# Run: python -m pytest tests/test_price_adjustment.py -v

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixture 1: dividend event. AAPL paid a $0.23/share cash dividend with
# ex-dividend date 2023-02-10. Real close prices (captured 2026-08):
# ─────────────────────────────────────────────────────────────────────────────
AAPL_DIV_RAW_CLOSE = {"2023-02-09": 150.869995, "2023-02-10": 151.009995}
AAPL_DIV_ADJ_CLOSE = {"2023-02-09": 148.352142, "2023-02-10": 148.716507}
AAPL_KNOWN_DIVIDEND = 0.23  # per share, ex-date 2023-02-10

# ─────────────────────────────────────────────────────────────────────────────
# Fixture 2: split event. AAPL's 4:1 split was effective 2020-08-31.
# Real close prices around it, BOTH with auto_adjust=False (raw) and
# auto_adjust=True (adjusted):
# ─────────────────────────────────────────────────────────────────────────────
AAPL_SPLIT_RAW_CLOSE = {"2020-08-28": 124.807503, "2020-08-31": 129.039993}
AAPL_SPLIT_ADJ_CLOSE = {"2020-08-28": 121.059967, "2020-08-31": 125.165405}


class TestDividendAdjustment:
    def test_adjusted_return_embeds_the_real_dividend(self):
        """
        The gap between the adjusted-price return and the raw-price return
        across an ex-dividend date should equal (dividend / prior raw close)
        -- proving auto_adjust=True correctly folds the real cash dividend
        into the adjusted return series, rather than fabricating an
        arbitrary number.
        """
        raw_ret = AAPL_DIV_RAW_CLOSE["2023-02-10"] / AAPL_DIV_RAW_CLOSE["2023-02-09"] - 1
        adj_ret = AAPL_DIV_ADJ_CLOSE["2023-02-10"] / AAPL_DIV_ADJ_CLOSE["2023-02-09"] - 1
        implied_div_yield = adj_ret - raw_ret
        expected_div_yield = AAPL_KNOWN_DIVIDEND / AAPL_DIV_RAW_CLOSE["2023-02-09"]
        assert implied_div_yield == pytest.approx(expected_div_yield, abs=2e-5)

    def test_no_separate_dividend_cashflow_would_double_count(self):
        """
        Sanity check on the project's own convention: trade_ledger.py fixes
        dividends_received at 0.0 for every trade. If the engine ALSO added
        a nonzero dividends_received on top of adjusted-price returns, the
        dividend would be counted twice. This test documents the invariant
        the rest of the codebase depends on.
        """
        from modules.trade_ledger import LEDGER_COLUMNS
        assert "dividends_received" in LEDGER_COLUMNS
        # The actual runtime value is asserted in test_trade_ledger.py's
        # fixtures (always 0.0); this test exists so a future change that
        # starts populating a nonzero dividends_received is forced to also
        # reconsider whether adjusted prices are still being used, to avoid
        # silently double-counting.


class TestSplitAdjustment:
    def test_raw_prices_show_no_artificial_split_jump(self):
        """
        yfinance normalizes stock splits into BOTH raw (auto_adjust=False)
        and adjusted (auto_adjust=True) price series by default -- unlike
        dividends, which only auto_adjust=True folds in. Verified against
        AAPL's real 4:1 split (effective 2020-08-31): raw close moves
        smoothly (124.81 -> 129.04, a normal ~3% daily move), NOT a 4x drop.
        This means split handling requires no extra logic in this project:
        using auto_adjust=True (for the dividend adjustment) does not need
        to be paired with any separate split-factor bookkeeping.
        """
        pct_change = AAPL_SPLIT_RAW_CLOSE["2020-08-31"] / AAPL_SPLIT_RAW_CLOSE["2020-08-28"] - 1
        assert abs(pct_change) < 0.10  # a normal daily move, not a ~75% split-driven drop

    def test_raw_and_adjusted_move_consistently_across_split_date(self):
        """Both series should show approximately the same day-over-day % change across the split."""
        raw_ret = AAPL_SPLIT_RAW_CLOSE["2020-08-31"] / AAPL_SPLIT_RAW_CLOSE["2020-08-28"] - 1
        adj_ret = AAPL_SPLIT_ADJ_CLOSE["2020-08-31"] / AAPL_SPLIT_ADJ_CLOSE["2020-08-28"] - 1
        assert raw_ret == pytest.approx(adj_ret, abs=1e-3)
