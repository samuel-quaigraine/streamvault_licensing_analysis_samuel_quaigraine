"""
Unit and integration tests for streamvault_tool.py (Deliverable 5).
Verifies era cutoff sensitivity modeling, interactive portfolio budget simulations,
and CLI execution flags.
"""

import subprocess
import sys
import pytest
import pandas as pd

from pipeline.config import PROCESSED_DIR
from streamvault_tool import run_era_sensitivity_analysis, simulate_portfolio_allocation


@pytest.fixture
def clean_films():
    """Loads clean analytical films table or synthetic fallback."""
    films_path = PROCESSED_DIR / "films_analytical.csv"
    if films_path.exists():
        return pd.read_csv(films_path)
    return pd.DataFrame([
        {"movie_id": 1, "title": "Series A1", "is_franchise": True, "collection_name": "Series A",
         "budget": 100.0, "revenue": 600.0, "return_on_cost": 6.0, "vote_average": 8.0, "release_year": 1995},
        {"movie_id": 2, "title": "Series A2", "is_franchise": True, "collection_name": "Series A",
         "budget": 150.0, "revenue": 750.0, "return_on_cost": 5.0, "vote_average": 8.2, "release_year": 2002},
        {"movie_id": 3, "title": "Standalone 1", "is_franchise": False, "collection_name": None,
         "budget": 50.0, "revenue": 200.0, "return_on_cost": 4.0, "vote_average": 8.5, "release_year": 2008},
        {"movie_id": 4, "title": "Standalone 2", "is_franchise": False, "collection_name": None,
         "budget": 80.0, "revenue": 240.0, "return_on_cost": 3.0, "vote_average": 8.1, "release_year": 2012},
    ])


def test_era_sensitivity_analysis_structure(clean_films):
    """
    TOOL TEST: Sensitivity Analysis Grid
    Verifies that run_era_sensitivity_analysis evaluates all required cutoff years
    [1990, 1995, 2000, 2005, 2010, 2015] and outputs all decision columns.
    """
    sens_df = run_era_sensitivity_analysis(clean_films)

    expected_cols = [
        "Cutoff Year", "Franchise Titles", "Standalone Titles",
        "Franchise Median ROI", "Standalone Median ROI",
        "Franchise Median Rev ($M)", "Standalone Median Rev ($M)",
        "Recommendation", "Flips?"
    ]
    for col in expected_cols:
        assert col in sens_df.columns, f"Missing expected column '{col}' in sensitivity output"

    expected_years = [1990, 1995, 2000, 2005, 2010, 2015]
    assert list(sens_df["Cutoff Year"]) == expected_years
    assert len(sens_df) == 6


def test_simulate_portfolio_allocation_default(clean_films):
    """
    TOOL TEST: Default $14M 70/30 Budget Split Simulation
    Verifies that default allocation produces exact dollar commitments
    ($9.80M for franchises, $4.20M for standalones).
    """
    sim = simulate_portfolio_allocation(clean_films, total_budget=14_000_000, franchise_allocation_pct=0.70)

    assert sim["total_budget"] == 14_000_000
    assert sim["franchise_budget"] == pytest.approx(9_800_000)
    assert sim["standalone_budget"] == pytest.approx(4_200_000)

    # Ensure target recommendations are populated
    assert len(sim["target_franchises"]) > 0
    assert len(sim["target_standalones"]) > 0


def test_simulate_portfolio_allocation_custom_splits(clean_films):
    """
    TOOL TEST: Custom Budget & Allocation Split Simulation
    Verifies flexible budget inputs (e.g. $10M budget with 80% franchise focus).
    """
    sim = simulate_portfolio_allocation(clean_films, total_budget=10_000_000, franchise_allocation_pct=0.80)

    assert sim["total_budget"] == 10_000_000
    assert sim["franchise_budget"] == pytest.approx(8_000_000)
    assert sim["standalone_budget"] == pytest.approx(2_000_000)


def test_tool_cli_execution():
    """
    TOOL TEST: Command-Line Interface Execution
    Verifies that invoking streamvault_tool.py via CLI executes without error
    and returns exit code 0.
    """
    result = subprocess.run(
        [sys.executable, "streamvault_tool.py", "--sensitivity", "--budget", "14.0", "--franchise-pct", "70"],
        capture_output=True,
        text=True,
        timeout=10
    )
    assert result.returncode == 0, f"CLI tool failed with error: {result.stderr}"
    assert "STREAMVAULT CONTENT ACQUISITION STRATEGY TOOL" in result.stdout
    assert "ERA CUTOFF SENSITIVITY TABLE" in result.stdout
    assert "PORTFOLIO ALLOCATION: $14.0M BUDGET" in result.stdout
    assert "$9.80M" in result.stdout
