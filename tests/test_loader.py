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
    """
    BLOCK: Test Total Candidate Accounting & Invariant Closure
    What it does: Confirms that load_candidate_ids() accurately accounts for every candidate line,
    verifying that total rows equal unique valid IDs plus logged exclusions.
    """
    candidate_df, valid_ids, exclusion_log = load_candidate_ids()

    # Invariants derived from candidate table status accounting
    expected_valid_count = len(candidate_df[candidate_df["status"] == "VALID"])
    expected_exclusions_count = len(candidate_df[candidate_df["status"] != "VALID"])

    assert len(candidate_df) == expected_valid_count + expected_exclusions_count
    assert len(valid_ids) == expected_valid_count, f"Expected {expected_valid_count} valid IDs, got {len(valid_ids)}"
    assert len(valid_ids) == len(set(valid_ids)), "All valid IDs must be unique"
    assert len(exclusion_log) == expected_exclusions_count, f"Expected {expected_exclusions_count} exclusions, got {len(exclusion_log)}"


def test_line_69_empty_row_detection():
    """
    BLOCK: Test Empty Line 69 Detection
    What it does: Confirms that line 69 is explicitly detected as an empty row,
    flagged as EXCLUDED, and documented in the exclusion log.
    """
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
    """
    BLOCK: Test Format & Domain Errors
    What it does: Verifies that negative ID -1 (line 30), IMDb ID tt0468569 (line 95),
    and string 'N/A' (line 111) are properly caught and classified.
    """
    candidate_df, valid_ids, exclusion_log = load_candidate_ids()

    # Line 30: Negative integer -1
    line_30 = candidate_df[candidate_df["line_number"] == 30].iloc[0]
    assert line_30["status"] == "EXCLUDED"
    assert "Negative" in line_30["reason"]

    # Line 95: External IMDb alphanumeric format tt0468569
    line_95 = candidate_df[candidate_df["line_number"] == 95].iloc[0]
    assert line_95["status"] == "EXTERNAL_FORMAT"
    assert "IMDb" in line_95["reason"]

    # Line 111: Text missing marker 'N/A'
    line_111 = candidate_df[candidate_df["line_number"] == 111].iloc[0]
    assert line_111["status"] == "EXCLUDED"
    assert "missing string" in line_111["reason"]


def test_duplicate_identifications():
    """
    BLOCK: Test Exact Duplicate Detection
    What it does: Verifies that all 6 duplicate IDs (155, 278, 550, 603, 680, 1891)
    are recognized and flagged as DUPLICATE.
    """
    candidate_df, valid_ids, exclusion_log = load_candidate_ids()

    duplicates = candidate_df[candidate_df["status"] == "DUPLICATE"]
    assert len(duplicates) == 6
    dup_ids = set(duplicates["parsed_id"])
    expected_dups = {155, 278, 550, 603, 680, 1891}
    assert dup_ids == expected_dups
