"""
Merge validation and grain integrity enforcement module.
Uses pandas validate= and indicator=True to convert silent fan-outs into immediate errors.
"""

from typing import Any, Dict, Optional, Tuple
import pandas as pd


def safe_merge_one_to_one(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    on: str,
    how: str = "left",
    left_name: str = "left",
    right_name: str = "right"
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Merge two DataFrames asserting a strict 1-to-1 relationship.
    Prevents silent row fan-out and records merge indicator statistics.
    """
    before_len = len(left_df)
    
    # Perform validated merge with indicator
    merged = left_df.merge(
        right_df,
        on=on,
        how=how,
        validate="one_to_one",
        indicator=True
    )
    
    # Assert row count preserved
    after_len = len(merged)
    assert after_len == before_len, (
        f"Fan-out detected in merge between {left_name} and {right_name}! "
        f"Expected {before_len} rows, got {after_len} rows."
    )

    indicator_counts = merged["_merge"].value_counts().to_dict()
    report = {
        "left_table": left_name,
        "right_table": right_name,
        "key": on,
        "before_rows": before_len,
        "after_rows": after_len,
        "fan_out_factor": after_len / before_len if before_len > 0 else 1.0,
        "matched_both": indicator_counts.get("both", 0),
        "left_only": indicator_counts.get("left_only", 0),
        "right_only": indicator_counts.get("right_only", 0),
    }

    # Drop indicator column before returning clean frame
    clean_merged = merged.drop(columns=["_merge"])
    return clean_merged, report


def validate_cast_crew_grain(
    films_df: pd.DataFrame,
    cast_df: pd.DataFrame,
    crew_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Validate that cast and crew tables preserve referential integrity
    without multiplying films.
    """
    film_ids = set(films_df["movie_id"])
    cast_film_ids = set(cast_df["movie_id"]) if not cast_df.empty else set()
    crew_film_ids = set(crew_df["movie_id"]) if not crew_df.empty else set()

    # Cast members should belong to known films
    unmatched_cast_films = cast_film_ids - film_ids
    unmatched_crew_films = crew_film_ids - film_ids

    # Films with no cast or crew
    films_without_cast = film_ids - cast_film_ids
    films_without_crew = film_ids - crew_film_ids

    report = {
        "total_films": len(films_df),
        "films_in_cast": len(cast_film_ids),
        "films_in_crew": len(crew_film_ids),
        "unmatched_cast_film_ids": list(unmatched_cast_films),
        "unmatched_crew_film_ids": list(unmatched_crew_films),
        "films_without_cast_count": len(films_without_cast),
        "films_without_crew_count": len(films_without_crew),
        "total_cast_rows": len(cast_df),
        "total_crew_rows": len(crew_df),
        "avg_cast_per_film": len(cast_df) / len(films_df) if len(films_df) > 0 else 0.0,
        "avg_crew_per_film": len(crew_df) / len(films_df) if len(films_df) > 0 else 0.0,
    }

    assert len(unmatched_cast_films) == 0, f"Found cast records pointing to non-existent films: {unmatched_cast_films}"
    assert len(unmatched_crew_films) == 0, f"Found crew records pointing to non-existent films: {unmatched_crew_films}"

    return report
