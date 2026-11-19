"""
Unit tests for join validation and fan-out prevention.
"""

import pytest
import pandas as pd
from pipeline.validate import safe_merge_one_to_one, validate_cast_crew_grain


def test_safe_merge_one_to_one_success():
    df_left = pd.DataFrame({"movie_id": [1, 2, 3], "title": ["Film 1", "Film 2", "Film 3"]})
    df_right = pd.DataFrame({"movie_id": [1, 2, 3], "revenue": [100, 200, 300]})

    merged, report = safe_merge_one_to_one(df_left, df_right, on="movie_id")
    assert len(merged) == 3
    assert report["fan_out_factor"] == 1.0
    assert report["matched_both"] == 3


def test_safe_merge_detects_fan_out():
    # Right table has duplicate keys (would cause fan-out)
    df_left = pd.DataFrame({"movie_id": [1, 2], "title": ["Film 1", "Film 2"]})
    df_right = pd.DataFrame({"movie_id": [1, 1, 2], "actor": ["Actor A", "Actor B", "Actor C"]})

    with pytest.raises(Exception):
        _ = safe_merge_one_to_one(df_left, df_right, on="movie_id")
