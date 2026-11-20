"""
End-to-end integration test suite for the StreamVault Content Acquisition Pipeline.
Verifies complete offline execution, output artifact creation, exact row counts,
and data integrity invariants.
"""

from pathlib import Path
import subprocess
import sys
import json
import pytest
import pandas as pd

from pipeline.config import OUTPUT_DIR, PROCESSED_DIR


def test_pipeline_offline_execution():
    """
    INTEGRATION TEST: Master Pipeline Execution
    Runs run_pipeline.py as a subprocess in offline mode and verifies clean exit (code 0).
    """
    result = subprocess.run(
        [sys.executable, "run_pipeline.py"],
        capture_output=True,
        text=True,
        timeout=180
    )
    assert result.returncode == 0, f"run_pipeline.py failed: {result.stderr}"
    assert (OUTPUT_DIR / "clean_films.csv").exists(), "clean_films.csv deliverable was not created"


def test_output_artifacts_exist_and_non_empty():
    """
    INTEGRATION TEST: Deliverable Artifact Verification
    Asserts that all 8 required deliverable files exist in output/ and are non-empty.
    """
    expected_files = [
        "clean_films.csv",
        "clean_cast.csv",
        "clean_crew.csv",
        "summary_kpis.csv",
        "franchise_rankings.csv",
        "standalone_rankings.csv",
        "candidate_reconciliation.csv",
        "profiling_summary.json",
    ]
    for filename in expected_files:
        file_path = OUTPUT_DIR / filename
        assert file_path.exists(), f"Expected deliverable output missing: {file_path}"
        assert file_path.stat().st_size > 0, f"Deliverable output is empty: {file_path}"


def test_output_table_row_invariants():
    """
    INTEGRATION TEST: Row Conservation & Table Grain Invariants
    Asserts derived row invariants across analytical deliverables:
    - clean_films.csv: matches verified final row count in candidate_reconciliation.csv
    - clean_cast.csv / clean_crew.csv: non-empty credits maintaining full referential integrity
    - candidate_reconciliation.csv: full reconciliation closure of raw inputs
    """
    films = pd.read_csv(OUTPUT_DIR / "clean_films.csv")
    cast = pd.read_csv(OUTPUT_DIR / "clean_cast.csv")
    crew = pd.read_csv(OUTPUT_DIR / "clean_crew.csv")
    recon = pd.read_csv(OUTPUT_DIR / "candidate_reconciliation.csv")

    expected_final_count = recon.loc[recon["Stage"].str.contains("Final", case=False), "Rows"].iloc[0]
    expected_raw_count = recon.loc[recon["Stage"].str.contains("Raw", case=False), "Rows"].iloc[0]

    assert len(films) == expected_final_count, f"Expected {expected_final_count} films, got {len(films)}"
    assert len(films) > 0, "Films table must not be empty"
    assert len(cast) > 0, "Cast table must not be empty"
    assert len(crew) > 0, "Crew table must not be empty"
    assert len(recon) == 6, f"Expected exactly 6 reconciliation stage rows, got {len(recon)}"
    assert "Stage" in recon.columns and "Rows" in recon.columns and "Delta" in recon.columns

    # Verify reconciliation closure: raw rows minus all drops equals final rows
    total_drops = abs(recon.loc[recon["Delta"] < 0, "Delta"].sum())
    assert expected_raw_count - total_drops == expected_final_count

    # Referential integrity assertion: no orphan cast or crew records
    film_ids = set(films["movie_id"])
    assert set(cast["movie_id"]).issubset(film_ids), "Found cast credits without matching film record"
    assert set(crew["movie_id"]).issubset(film_ids), "Found crew credits without matching film record"


def test_profiling_summary_invariants():
    """
    INTEGRATION TEST: Disguised Null Verification & Financial Invariants
    Verifies that output/profiling_summary.json confirms 0 zero-revenue and 0 zero-budget titles.
    """
    summary_path = OUTPUT_DIR / "profiling_summary.json"
    assert summary_path.exists()

    with open(summary_path, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    films = pd.read_csv(OUTPUT_DIR / "clean_films.csv")

    # In our verified titles, zero revenue and zero budget count must be strictly 0
    assert data["zero_revenue_count"] == 0, f"Expected 0 zero-revenue titles, got {data['zero_revenue_count']}"
    assert data["zero_budget_count"] == 0, f"Expected 0 zero-budget titles, got {data['zero_budget_count']}"
    assert data["total_records"] == len(films), f"Expected total_records {len(films)}, got {data['total_records']}"
    assert data["revenue_outlier_count"] >= 0, f"Outlier count must be non-negative, got {data['revenue_outlier_count']}"
