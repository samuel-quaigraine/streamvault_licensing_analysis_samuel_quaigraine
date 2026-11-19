"""
Unit tests for candidate list loading and format reconciliation.
Verifies explicit tracking of line 69 empty row, non-numeric formats, and duplicates.
"""

from pathlib import Path
import pytest
import pandas as pd

from pipeline.config import ID_LIST_PATH
from pipeline.load import load_candidate_ids


def test_candidate_loader_counts():
    candidate_df, valid_ids, exclusion_log = load_candidate_ids()

    # Must account for exactly 127 candidate lines
    assert len(candidate_df) == 127, f"Expected 127 candidate lines, got {len(candidate_df)}"
    assert len(valid_ids) == 117, f"Expected 117 unique valid numeric IDs, got {len(valid_ids)}"
    assert len(exclusion_log) == 10, f"Expected 10 total exclusions, got {len(exclusion_log)}"


def test_line_69_empty_row_detection():
    candidate_df, valid_ids, exclusion_log = load_candidate_ids()

    # Line 69 is index 67 in data_lines (line 1 is header, line 69 is line_number 69)
    line_69_rows = candidate_df[candidate_df["line_number"] == 69]
    assert len(line_69_rows) == 1
    row = line_69_rows.iloc[0]
    assert row["status"] == "EXCLUDED"
    assert "Empty row" in row["reason"]

    # Verify present in exclusion log
    empty_exclusions = [e for e in exclusion_log if e["line"] == 69]
    assert len(empty_exclusions) == 1
    assert empty_exclusions[0]["raw_id"] == "<EMPTY>"


def test_non_numeric_and_negative_formats():
    candidate_df, valid_ids, exclusion_log = load_candidate_ids()

    # Line 30: -1
    line_30 = candidate_df[candidate_df["line_number"] == 30].iloc[0]
    assert line_30["status"] == "EXCLUDED"
    assert "Negative" in line_30["reason"]

    # Line 95: tt0468569
    line_95 = candidate_df[candidate_df["line_number"] == 95].iloc[0]
    assert line_95["status"] == "EXTERNAL_FORMAT"
    assert "IMDb" in line_95["reason"]

    # Line 111: N/A
    line_111 = candidate_df[candidate_df["line_number"] == 111].iloc[0]
    assert line_111["status"] == "EXCLUDED"
    assert "missing string" in line_111["reason"]


def test_duplicate_identifications():
    candidate_df, valid_ids, exclusion_log = load_candidate_ids()

    duplicates = candidate_df[candidate_df["status"] == "DUPLICATE"]
    assert len(duplicates) == 6
    dup_ids = set(duplicates["parsed_id"])
    expected_dups = {155, 278, 550, 603, 680, 1891}
    assert dup_ids == expected_dups
