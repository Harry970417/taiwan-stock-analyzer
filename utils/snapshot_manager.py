"""
utils/snapshot_manager.py
==========================
Data snapshot management for Phase 1 reproducibility.

Spec: docs/data_snapshot_protocol.md
Goal: Any reviewer, given the snapshot directory, can reproduce results
      bit-for-bit by running the pipeline in offline mode.
"""

import hashlib
import json
import os
import pickle
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Metadata construction
# ─────────────────────────────────────────────────────────────────────────────

def _git_commit() -> str:
    """Return current git HEAD hash (short), or 'unknown'."""
    try:
        result = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return result.strip()
    except Exception:
        return "unknown"


def _package_versions() -> Dict[str, str]:
    """Return version strings for key packages."""
    versions = {}
    for pkg in ["pandas", "numpy", "yfinance", "scipy", "statsmodels", "scikit-learn"]:
        try:
            mod = __import__(pkg)
            versions[pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[pkg] = "not_installed"
    return versions


def _file_sha256(path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def create_snapshot_metadata(
    ticker_universe: list,
    api_provider: str,
    query_period: str,
    data_dir: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Build a metadata dict conforming to data_snapshot_protocol.md §4.

    Parameters
    ----------
    ticker_universe : list of ticker strings
    api_provider    : 'yfinance' | 'finmind' | 'mixed'
    query_period    : 'YYYY-MM-DD/YYYY-MM-DD'
    data_dir        : directory containing raw data files (for hashing)
    extra           : additional key-value pairs to include

    Returns
    -------
    dict ready to serialise as metadata.json
    """
    git_hash = _git_commit()
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        + f"_{git_hash}"
    )

    # Hash all files in data_dir if provided
    file_hashes: Dict[str, str] = {}
    if data_dir and os.path.isdir(data_dir):
        for fname in sorted(os.listdir(data_dir)):
            fpath = os.path.join(data_dir, fname)
            if os.path.isfile(fpath) and not fname.startswith("."):
                try:
                    file_hashes[fname] = _file_sha256(fpath)
                except Exception:
                    file_hashes[fname] = "hash_failed"

    meta = {
        "run_id":             run_id,
        "download_timestamp": datetime.now(timezone.utc).isoformat(),
        "api_provider":       api_provider,
        "query_period":       query_period,
        "ticker_universe":    ticker_universe,
        "ticker_count":       len(ticker_universe),
        "git_commit_hash":    git_hash,
        "python_version":     sys.version,
        "platform":           platform.platform(),
        "package_versions":   _package_versions(),
        "random_seeds":       {"numpy_seed": 42, "sklearn_random_state": 42},
        "file_hashes":        file_hashes,
        "known_limitations": [
            "SB-1: V1 16-stock list uses survivors only (see docs/known_issues.md)",
            "DL-3: ffill limit=90 applied to fundamental data",
            "REP-1: pandas/numpy versions may differ from original run",
        ],
    }

    if extra:
        meta.update(extra)

    return meta


# ─────────────────────────────────────────────────────────────────────────────
# Save / load snapshot
# ─────────────────────────────────────────────────────────────────────────────

def save_snapshot(
    universe_data: Dict[str, Any],
    output_dir: str,
    ticker_universe: list,
    api_provider: str = "mixed",
    query_period: str = "",
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Persist universe_data dict and metadata.json to output_dir.

    The snapshot is stored as a pickle file (universe_data.pkl) alongside
    the metadata JSON. For distribution, convert to parquet per ticker.

    Parameters
    ----------
    universe_data : {ticker: OHLCV DataFrame}
    output_dir    : destination directory (created if absent)
    ...

    Returns
    -------
    Path to output_dir
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Save universe data
    pkl_path = out / "universe_data.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(universe_data, f, protocol=4)

    # Save individual CSVs per ticker (human-readable)
    csv_dir = out / "raw_csv"
    csv_dir.mkdir(exist_ok=True)
    for ticker, df in universe_data.items():
        safe_name = ticker.replace(".", "_")
        df.to_csv(csv_dir / f"{safe_name}.csv", index=False)

    # Build and save metadata
    meta = create_snapshot_metadata(
        ticker_universe=ticker_universe,
        api_provider=api_provider,
        query_period=query_period,
        data_dir=str(csv_dir),
        extra=extra_meta,
    )
    meta_path = out / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=str)

    print(f"[snapshot] Saved {len(universe_data)} tickers → {out}")
    print(f"[snapshot] metadata.json: run_id={meta['run_id']}")
    return out


def load_snapshot(snapshot_dir: str) -> Dict[str, Any]:
    """
    Load universe_data from a snapshot directory.

    Tries pickle first (fast), then reconstructs from CSVs if pickle absent.

    Parameters
    ----------
    snapshot_dir : path created by save_snapshot()

    Returns
    -------
    dict: {'universe_data': {ticker: df}, 'metadata': dict}
    """
    snap = Path(snapshot_dir)
    if not snap.exists():
        raise FileNotFoundError(f"Snapshot directory not found: {snap}")

    # Load metadata
    meta_path = snap / "metadata.json"
    metadata = {}
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    # Load universe data (pickle preferred)
    pkl_path = snap / "universe_data.pkl"
    if pkl_path.exists():
        with open(pkl_path, "rb") as f:
            universe_data = pickle.load(f)
        print(f"[snapshot] Loaded {len(universe_data)} tickers from pickle ({snap.name})")
        return {"universe_data": universe_data, "metadata": metadata}

    # Fallback: reconstruct from CSVs
    import pandas as pd
    csv_dir = snap / "raw_csv"
    if not csv_dir.exists():
        raise FileNotFoundError(f"No pickle or CSV data in {snap}")

    universe_data = {}
    for csv_file in sorted(csv_dir.glob("*.csv")):
        ticker = csv_file.stem.replace("_TW", ".TW").replace("_TWO", ".TWO")
        try:
            df = pd.read_csv(csv_file, parse_dates=["date"])
            universe_data[ticker] = df
        except Exception as e:
            print(f"[snapshot] Warning: could not load {csv_file.name}: {e}")

    print(f"[snapshot] Loaded {len(universe_data)} tickers from CSVs ({snap.name})")
    return {"universe_data": universe_data, "metadata": metadata}


# ─────────────────────────────────────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────────────────────────────────────

def verify_snapshot_hash(snapshot_dir: str) -> Dict[str, bool]:
    """
    Re-compute SHA-256 for each file and compare to stored metadata.json.

    Returns
    -------
    {filename: True (match) | False (mismatch) | None (not in metadata)}
    """
    snap = Path(snapshot_dir)
    meta_path = snap / "metadata.json"
    if not meta_path.exists():
        return {}

    with open(meta_path, "r") as f:
        meta = json.load(f)

    stored_hashes = meta.get("file_hashes", {})
    results = {}
    csv_dir = snap / "raw_csv"
    if csv_dir.exists():
        for fname in sorted(os.listdir(csv_dir)):
            fpath = csv_dir / fname
            if not os.path.isfile(fpath):
                continue
            current_hash = _file_sha256(str(fpath))
            stored = stored_hashes.get(fname)
            results[fname] = (current_hash == stored) if stored else None

    return results
