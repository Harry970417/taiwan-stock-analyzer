import pandas as pd
import pytest

from utils.snapshot_manager import load_snapshot, save_snapshot


def _sample_universe():
    return {
        "2330.TW": pd.DataFrame({"date": ["2026-01-02"], "close": [600.0]}),
    }


def test_load_snapshot_round_trips_when_pickle_untampered(tmp_path):
    save_snapshot(_sample_universe(), str(tmp_path), ticker_universe=["2330.TW"])

    result = load_snapshot(str(tmp_path))

    assert set(result["universe_data"].keys()) == {"2330.TW"}
    assert result["metadata"]["file_hashes"]["universe_data.pkl"]


def test_load_snapshot_rejects_tampered_pickle(tmp_path):
    save_snapshot(_sample_universe(), str(tmp_path), ticker_universe=["2330.TW"])

    pkl_path = tmp_path / "universe_data.pkl"
    pkl_path.write_bytes(pkl_path.read_bytes() + b"tampered")

    with pytest.raises(RuntimeError, match="integrity check failed"):
        load_snapshot(str(tmp_path))
