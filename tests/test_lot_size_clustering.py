# tests/test_lot_size_clustering.py
import pandas as pd
import pytest
from investigations.lot_size_clustering.fetch import _bin_lot_sizes


def test_bin_lot_sizes_rounds_to_nearest_500():
    df = pd.DataFrame({
        "LOT_SIZE": [100, 400, 600, 900, 7500, 10000]
    })
    result = _bin_lot_sizes(df)
    assert list(result["lot_size_bin"]) == [0, 500, 500, 1000, 7500, 10000]


def test_bin_lot_sizes_does_not_mutate_input():
    df = pd.DataFrame({"LOT_SIZE": [1000]})
    _bin_lot_sizes(df)
    assert "lot_size_bin" not in df.columns


def test_bin_lot_sizes_preserves_other_columns():
    df = pd.DataFrame({"LOT_SIZE": [6000], "LOC_ID": ["F_123_456"], "SITE_ADDR": ["1 MAIN ST"]})
    result = _bin_lot_sizes(df)
    assert "LOC_ID" in result.columns
    assert "SITE_ADDR" in result.columns
