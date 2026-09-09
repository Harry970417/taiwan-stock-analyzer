"""P1-11 (Financial Foundations Adversarial Audit) prospective cross-project
signal logging. Historical cross-project correlation with stock-ai-project's
signals stays UNRESOLVED -- no historical daily signal data exists for either
side, and none is fabricated here. This module only lets real data
accumulate going forward, on the shared schema in
Desktop/FINANCIAL_FOUNDATIONS_ADVERSARIAL_AUDIT_2026-09/
CROSS_PROJECT_SIGNAL_LOG_SCHEMA.md (identical field set to
stock-ai-project's backend/services/signal_log.py).

Not wired into any scheduled job -- call this explicitly from wherever a
factor/signal value is produced when the user decides to start collecting.
"""
import json
from pathlib import Path

REQUIRED_FIELDS = (
    "date", "ticker", "signal_name", "raw_signal", "normalized_signal",
    "rank", "universe", "available_at", "first_tradeable_at",
    "model_version", "commit_hash",
)


def log_signal_snapshot(
    *,
    log_path: Path,
    date: str,
    ticker: str,
    signal_name: str,
    raw_signal: float | None,
    normalized_signal: float | None,
    rank: int | None,
    universe: str,
    available_at: str,
    first_tradeable_at: str,
    model_version: str,
    commit_hash: str,
) -> None:
    """Appends one JSONL row. Never overwrites -- append-only, so a row
    once written cannot later be silently edited to look like it always
    said something else."""
    row = {
        "date": date, "ticker": ticker, "signal_name": signal_name,
        "raw_signal": raw_signal, "normalized_signal": normalized_signal,
        "rank": rank, "universe": universe, "available_at": available_at,
        "first_tradeable_at": first_tradeable_at, "model_version": model_version,
        "commit_hash": commit_hash,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
