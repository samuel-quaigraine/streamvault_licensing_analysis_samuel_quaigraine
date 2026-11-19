"""
Unit tests for join validation and fan-out prevention.
"""

import pytest
import pandas as pd
from pipeline.validate import safe_merge_one_to_one, validate_cast_crew_grain


def test_safe_merge_one_to_one_success():
    """
    BLOCK: Test Valid 1-to-1 Merge
    What it does: Confirms that safe_merge_one_to_one succeeds when keys are unique,
    maintains exact row count, and returns a fan-out factor of exactly 1.0.
    """
    df_left = pd.DataFrame({"movie_id": [1, 2, 3], "title": ["Film 1", "Film 2", "Film 3"]})
    df_right = pd.DataFrame({"movie_id": [1, 2, 3], "revenue": [100, 200, 300]})

    merged, report = safe_merge_one_to_one(df_left, df_right, on="movie_id")
    assert len(merged) == 3
    assert report["fan_out_factor"] == 1.0
    assert report["matched_both"] == 3


def test_safe_merge_detects_fan_out():
    """
    BLOCK: Test Fan-out Detection & Exception Trigger
    What it does: Simulates a merge where the right table has duplicate keys (fan-out)
    and verifies that the validation guard catches it and raises an immediate exception.
    """
    # Right table has duplicate keys (would cause fan-out)
    df_left = pd.DataFrame({"movie_id": [1, 2], "title": ["Film 1", "Film 2"]})
    df_right = pd.DataFrame({"movie_id": [1, 1, 2], "actor": ["Actor A", "Actor B", "Actor C"]})

    with pytest.raises(Exception):
        _ = safe_merge_one_to_one(df_left, df_right, on="movie_id")
