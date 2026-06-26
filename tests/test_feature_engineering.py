import pandas as pd

from modules.feature_engineering import build_full_features, create_labels


def _make_price_df() -> pd.DataFrame:
    close = [10.0, 11.0, 9.0, 12.0, 12.0, 8.0, 13.0]
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=len(close), freq="B"),
        "open": close,
        "high": [price + 0.5 for price in close],
        "low": [price - 0.5 for price in close],
        "close": close,
        "volume": [1000, 1200, 900, 1500, 1100, 1300, 1600],
    })


def test_create_labels_keeps_unknown_future_rows_as_nan():
    df = create_labels(_make_price_df())

    assert {"label_1d", "label_3d", "label_5d"}.issubset(df.columns)

    assert df["label_1d"].tail(1).isna().all()
    assert df["label_3d"].tail(3).isna().all()
    assert df["label_5d"].tail(5).isna().all()


def test_create_labels_sets_known_future_labels_correctly():
    df = create_labels(_make_price_df())

    assert df.loc[0, "label_1d"] == 1.0
    assert df.loc[1, "label_1d"] == 0.0
    assert df.loc[0, "label_3d"] == 1.0
    assert df.loc[1, "label_3d"] == 1.0
    assert df.loc[0, "label_5d"] == 0.0
    assert df.loc[1, "label_5d"] == 1.0


def test_build_full_features_preserves_tail_nan_labels():
    df = build_full_features(_make_price_df(), include_labels=True)

    assert df["label_1d"].tail(1).isna().all()
    assert df["label_3d"].tail(3).isna().all()
    assert df["label_5d"].tail(5).isna().all()
