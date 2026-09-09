"""P1-11 (Financial Foundations Adversarial Audit) prospective cross-project
signal logging. Historical cross-project correlation with stock-ai-project's
signals stays UNRESOLVED -- no historical daily signal data exists for either
side, and none is fabricated here. This module only lets real data
accumulate going forward, on the shared schema in
Desktop/FINANCIAL_FOUNDATIONS_ADVERSARIAL_AUDIT_2026-09/
CROSS_PROJECT_SIGNAL_LOG_SCHEMA.md (identical schema/format to
stock-ai-project's backend/services/signal_log.py, so the two repos' JSONL
files can later be merged directly)."""
import json

from modules.signal_log import REQUIRED_FIELDS, log_signal_snapshot


def test_log_signal_snapshot_writes_one_jsonl_row_per_call(tmp_path):
    log_path = tmp_path / "2026-09.jsonl"
    log_signal_snapshot(
        log_path=log_path, date="2026-09-09", ticker="2330.TW",
        signal_name="eps_growth", raw_signal=12.3, normalized_signal=0.9,
        rank=1, universe="V1_16", available_at="2026-09-09T18:00:00+08:00",
        first_tradeable_at="2026-09-10T09:00:00+08:00", model_version="v1", commit_hash="abc1234",
    )
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["ticker"] == "2330.TW"
    assert set(REQUIRED_FIELDS) <= set(row.keys())


def test_log_signal_snapshot_appends_not_overwrites(tmp_path):
    log_path = tmp_path / "2026-09.jsonl"
    for i in range(3):
        log_signal_snapshot(
            log_path=log_path, date="2026-09-09", ticker=f"000{i}.TW",
            signal_name="test", raw_signal=1.0, normalized_signal=1.0, rank=i,
            universe="u", available_at="2026-09-09T00:00:00+08:00",
            first_tradeable_at="2026-09-10T00:00:00+08:00", model_version="v1", commit_hash="x",
        )
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3


def test_schema_matches_stock_ai_project_field_set():
    """Both repos must use the exact same field set so the two JSONL
    streams can be merged directly without a translation layer."""
    expected = {
        "date", "ticker", "signal_name", "raw_signal", "normalized_signal",
        "rank", "universe", "available_at", "first_tradeable_at",
        "model_version", "commit_hash",
    }
    assert set(REQUIRED_FIELDS) == expected
