"""
Merge Validation & Relational Grain Integrity Module.

Analogies & Concept:
Like a precision gatekeeper that monitors joins:
1. Prevents silent row fan-out when merging tables using validate='one_to_one'.
2. Uses indicator=True to record merge audit statistics.
3. Asserts referential integrity between child tables (cast/crew) and the parent table (films).

Course Lessons Applied from @materials-learning:
- "Learning Path: Merging, and proving the join"
- "Combining Data in pandas With merge(), .join(), and concat()"
- "Merge, join, concatenate and compare — pandas documentation"
"""

from typing import Any, Dict, Tuple
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

    Lesson: "Merging, and proving the join"
    Plain English: In relational data, joining two tables on an identifier must never
    silently multiply rows. If a key appears multiple times in the right table,
    pandas throws an immediate exception rather than producing phantom rows!
    """
    before_len = len(left_df)

    # Execute Guarded 1-to-1 Merge
    merged = left_df.merge(
        right_df,
        on=on,
        how=how,
        validate="one_to_one",
        indicator=True
    )

    # Mathematically assert zero fan-out
    after_len = len(merged)
    assert after_len == before_len, (
        f"Fan-out detected in merge between {left_name} and {right_name}! "
        f"Expected {before_len} rows, got {after_len} rows."
    )

    # Build merge audit indicator report
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

    clean_merged = merged.drop(columns=["_merge"])
    return clean_merged, report


def validate_cast_crew_grain(
    films_df: pd.DataFrame,
    cast_df: pd.DataFrame,
    crew_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Validate referential integrity: ensures every cast and crew credit
    belongs to a verified film in the films table.
    """
    film_ids = set(films_df["movie_id"])
    cast_film_ids = set(cast_df["movie_id"]) if not cast_df.empty else set()
    crew_film_ids = set(crew_df["movie_id"]) if not crew_df.empty else set()

    unmatched_cast_films = cast_film_ids - film_ids
    unmatched_crew_films = crew_film_ids - film_ids

    assert len(unmatched_cast_films) == 0, f"Found cast pointing to non-existent films: {unmatched_cast_films}"
    assert len(unmatched_crew_films) == 0, f"Found crew pointing to non-existent films: {unmatched_crew_films}"

    return {
        "total_films": len(films_df),
        "total_cast_rows": len(cast_df),
        "total_crew_rows": len(crew_df),
        "films_in_cast": len(cast_film_ids),
        "films_in_crew": len(crew_film_ids),
        "avg_cast_per_film": len(cast_df) / len(films_df) if len(films_df) > 0 else 0.0,
        "avg_crew_per_film": len(crew_df) / len(films_df) if len(films_df) > 0 else 0.0,
        "orphan_cast_count": len(unmatched_cast_films),
        "orphan_crew_count": len(unmatched_crew_films),
        "unmatched_cast_film_ids": list(unmatched_cast_films),
        "unmatched_crew_film_ids": list(unmatched_crew_films),
    }
