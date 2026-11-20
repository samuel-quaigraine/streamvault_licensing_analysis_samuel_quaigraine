"""
Unit tests for join validation, fan-out prevention, and pre-load QA gates.

Lessons tested from @materials-learning:
- "Learning Path: Merging, and proving the join"
- "Combining Data in pandas With merge(), .join(), and concat()"
"""

import pytest
import pandas as pd
from pipeline.validate import safe_merge_one_to_one, validate_cast_crew_grain
from pipeline.checks import check_before_load, ReconciliationError


def test_safe_merge_one_to_one_success():
    """Confirms safe_merge_one_to_one succeeds when keys are unique."""
    df_left = pd.DataFrame({"movie_id": [1, 2, 3], "title": ["Film 1", "Film 2", "Film 3"]})
    df_right = pd.DataFrame({"movie_id": [1, 2, 3], "revenue": [100, 200, 300]})

    merged, report = safe_merge_one_to_one(df_left, df_right, on="movie_id")
    assert len(merged) == 3
    assert report["fan_out_factor"] == 1.0
    assert report["matched_both"] == 3


def test_safe_merge_detects_fan_out():
    """Simulates duplicate keys causing fan-out and asserts exception is raised."""
    df_left = pd.DataFrame({"movie_id": [1, 2], "title": ["Film 1", "Film 2"]})
    df_right = pd.DataFrame({"movie_id": [1, 1, 2], "actor": ["Actor A", "Actor B", "Actor C"]})

    with pytest.raises(Exception):
        _ = safe_merge_one_to_one(df_left, df_right, on="movie_id")


def test_check_before_load_qa_gate_passes():
    """QA GATE TEST: Asserts QA check passes when conservation and referential integrity hold."""
    films = pd.DataFrame([{"movie_id": 1, "budget": 100, "revenue": 300}])
    cast = pd.DataFrame([{"movie_id": 1, "cast_id": 10}])
    crew = pd.DataFrame([{"movie_id": 1, "crew_id": 20}])

    res = check_before_load(
        total_raw_count=10,
        verified_films_count=9,
        dropped_candidates_count=1,
        films_df=films,
        cast_df=cast,
        crew_df=crew
    )
    assert res["status"] == "PASSED"
    assert res["total_raw"] == 10


def test_check_before_load_qa_gate_fails_on_broken_conservation():
    """QA GATE TEST: Asserts ReconciliationError is raised if row conservation fails."""
    films = pd.DataFrame([{"movie_id": 1, "budget": 100, "revenue": 300}])
    cast = pd.DataFrame([{"movie_id": 1, "cast_id": 10}])
    crew = pd.DataFrame([{"movie_id": 1, "crew_id": 20}])

    with pytest.raises(ReconciliationError):
        # 10 != 8 + 1
        _ = check_before_load(
            total_raw_count=10,
            verified_films_count=8,
            dropped_candidates_count=1,
            films_df=films,
            cast_df=cast,
            crew_df=crew
        )
