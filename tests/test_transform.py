"""
Unit tests for data transformations, table grains, and KPI computations.
Covers Stations 2, 3, 4, and 5 of the factory line.

Lessons tested from @materials-learning:
- "Learning Path: Parsing and flattening nested JSON"
- "Learning Path: Missing data"
- "Learning Path: Vectorisation versus apply"
- "Learning Path: GroupBy and aggregation for KPIs"
"""

import pytest
import pandas as pd
import numpy as np

from pipeline.config import PROCESSED_DIR
from pipeline.transform import (
    engineer_financial_metrics,
    filter_reliable_financials,
    compute_kpis,
    score_licensing_options,
    rank_franchise_bundles,
    rank_standalone_hits,
    scout_directors_and_lead_actors,
)


@pytest.fixture
def sample_films():
    """Test Fixture: Loads clean analytical films or returns a synthetic DataFrame."""
    films_path = PROCESSED_DIR / "films_analytical.csv"
    if films_path.exists():
        return pd.read_csv(films_path)
    return pd.DataFrame([
        {"movie_id": 1, "title": "Film A", "is_franchise": True, "budget": 100, "revenue": 500, "release_year": 2005, "era": "2000-Onward"},
        {"movie_id": 2, "title": "Film B", "is_franchise": True, "budget": 150, "revenue": 600, "release_year": 2008, "era": "2000-Onward"},
        {"movie_id": 3, "title": "Film C", "is_franchise": False, "budget": 50, "revenue": 200, "release_year": 1995, "era": "Pre-2000"},
        {"movie_id": 4, "title": "Film D", "is_franchise": False, "budget": 80, "revenue": 160, "release_year": 2012, "era": "2000-Onward"},
    ])


def test_table_grain_integrity(sample_films):
    """STATION 2 TEST: Asserts that every movie_id is strictly unique (1 row per film)."""
    assert sample_films["movie_id"].is_unique
    assert len(sample_films) > 0


def test_parameterized_cleaning_financials():
    """
    STATION 3 TEST: Verifies $0 revenue is handled appropriately under both rules:
    - Case A: Treated as missing data (NaN return on cost)
    - Case B: Treated as a commercial flop (0.0x return on cost)
    """
    test_df = pd.DataFrame([
        {"movie_id": 10, "budget": 100.0, "revenue": 300.0, "is_franchise": True, "era": "2000-Onward"},
        {"movie_id": 20, "budget": 100.0, "revenue": 0.0, "is_franchise": True, "era": "2000-Onward"},
    ])

    # Case A: treat zero revenue as missing data (NaN)
    df_missing = filter_reliable_financials(test_df, treat_zero_revenue_as_missing=True)
    assert df_missing.loc[df_missing["movie_id"] == 10, "return_on_cost"].iloc[0] == 3.0
    assert np.isnan(df_missing.loc[df_missing["movie_id"] == 20, "return_on_cost"].iloc[0])

    # Case B: treat zero revenue as a commercial flop (0.0x)
    df_zero = filter_reliable_financials(test_df, treat_zero_revenue_as_missing=False)
    assert df_zero.loc[df_zero["movie_id"] == 20, "return_on_cost"].iloc[0] == 0.0


def test_kpi_computation_two_windows(sample_films):
    """STATION 4 TEST: Confirms KPI metrics calculate cleanly across both time windows."""
    cleaned = filter_reliable_financials(sample_films, treat_zero_revenue_as_missing=True)
    kpis_all = score_licensing_options(cleaned, era_filter=None)
    kpis_post = score_licensing_options(cleaned, era_filter="2000-Onward")

    assert "Franchise" in kpis_all
    assert "Standalone" in kpis_all
    assert "Franchise" in kpis_post
    assert "Standalone" in kpis_post

    assert kpis_all["Franchise"]["median_roi"] > 0
    assert kpis_all["Standalone"]["median_roi"] > 0


def test_rank_franchise_bundles_weakest_link():
    """
    STATION 4 TEST: Test Franchise Bundle Ranking & Weakest Link Identification.
    Verifies that bundle ROI and weakest-film return (min_roi) are calculated.
    """
    synthetic_films = pd.DataFrame([
        {"movie_id": 1, "title": "Trilogy 1", "is_franchise": True, "collection_name": "Galaxy Series",
         "budget": 100.0, "revenue": 500.0, "return_on_cost": 5.0, "vote_average": 8.0, "release_year": 2000},
        {"movie_id": 2, "title": "Trilogy 2", "is_franchise": True, "collection_name": "Galaxy Series",
         "budget": 100.0, "revenue": 100.0, "return_on_cost": 1.0, "vote_average": 6.0, "release_year": 2003},
    ])
    ranked = rank_franchise_bundles(synthetic_films)
    assert len(ranked) == 1
    assert ranked.iloc[0]["collection_name"] == "Galaxy Series"
    assert ranked.iloc[0]["film_count"] == 2
    assert ranked.iloc[0]["min_roi"] == 1.0  # Weakest film identified
    assert ranked.iloc[0]["bundle_roi"] == 3.0  # (500+100) / (100+100) = 3.0x


def test_talent_scout_fairness_filter():
    """
    STATION 5 TEST: Test Talent Scout Fairness Filter (Min appearances >= 2).
    Verifies that 1-hit wonders are filtered out from the high-confidence shortlist.
    """
    films = pd.DataFrame([
        {"movie_id": 1, "title": "Film A", "revenue": 100, "budget": 50, "return_on_cost": 2.0, "vote_average": 7.0, "era": "2000-Onward"},
        {"movie_id": 2, "title": "Film B", "revenue": 200, "budget": 50, "return_on_cost": 4.0, "vote_average": 8.0, "era": "2000-Onward"},
        {"movie_id": 3, "title": "Film C", "revenue": 500, "budget": 50, "return_on_cost": 10.0, "vote_average": 9.0, "era": "2000-Onward"},
    ])
    crew = pd.DataFrame([
        {"movie_id": 1, "crew_name": "Director Reliable", "job": "Director"},
        {"movie_id": 2, "crew_name": "Director Reliable", "job": "Director"},
        {"movie_id": 3, "crew_name": "Director OneHitWonder", "job": "Director"},
    ])
    cast = pd.DataFrame([
        {"movie_id": 1, "actor_name": "Star Reliable", "cast_order": 0},
        {"movie_id": 2, "actor_name": "Star Reliable", "cast_order": 0},
        {"movie_id": 3, "actor_name": "Star OneHitWonder", "cast_order": 0},
    ])
    dirs, actors = scout_directors_and_lead_actors(films, cast, crew, min_appearances=2)
    assert "Director Reliable" in list(dirs["crew_name"])
    assert "Director OneHitWonder" not in list(dirs["crew_name"])
    assert "Star Reliable" in list(actors["actor_name"])
    assert "Star OneHitWonder" not in list(actors["actor_name"])
