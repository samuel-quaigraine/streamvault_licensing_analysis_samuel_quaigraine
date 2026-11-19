"""
Unit tests for data transformations, table grains, and KPI computations.
"""

import pytest
import pandas as pd
import numpy as np

from pipeline.config import PROCESSED_DIR
from pipeline.transform import engineer_financial_metrics, compute_kpis


@pytest.fixture
def sample_films():
    films_path = PROCESSED_DIR / "films_analytical.csv"
    if films_path.exists():
        return pd.read_csv(films_path)
    # Synthetic fallback for isolated unit testing
    return pd.DataFrame([
        {"movie_id": 1, "title": "Film A", "is_franchise": True, "budget": 100, "revenue": 500, "release_year": 2005, "era": "2000-Onward"},
        {"movie_id": 2, "title": "Film B", "is_franchise": True, "budget": 150, "revenue": 600, "release_year": 2008, "era": "2000-Onward"},
        {"movie_id": 3, "title": "Film C", "is_franchise": False, "budget": 50, "revenue": 200, "release_year": 1995, "era": "Pre-2000"},
        {"movie_id": 4, "title": "Film D", "is_franchise": False, "budget": 80, "revenue": 160, "release_year": 2012, "era": "2000-Onward"},
    ])


def test_table_grain_integrity(sample_films):
    # Verify grain is strictly 1 row per film
    assert sample_films["movie_id"].is_unique
    assert len(sample_films) > 0


def test_parameterized_cleaning_financials():
    test_df = pd.DataFrame([
        {"movie_id": 10, "budget": 100.0, "revenue": 300.0, "is_franchise": True, "era": "2000-Onward"},
        {"movie_id": 20, "budget": 100.0, "revenue": 0.0, "is_franchise": True, "era": "2000-Onward"},
    ])

    # Case A: treat zero revenue as missing
    df_missing = engineer_financial_metrics(test_df, treat_zero_revenue_as_missing=True)
    assert df_missing.loc[df_missing["movie_id"] == 10, "return_on_cost"].iloc[0] == 3.0
    assert np.isnan(df_missing.loc[df_missing["movie_id"] == 20, "return_on_cost"].iloc[0])

    # Case B: treat zero revenue as commercial flop
    df_zero = engineer_financial_metrics(test_df, treat_zero_revenue_as_missing=False)
    assert df_zero.loc[df_zero["movie_id"] == 20, "return_on_cost"].iloc[0] == 0.0


def test_kpi_computation_two_windows(sample_films):
    cleaned = engineer_financial_metrics(sample_films, treat_zero_revenue_as_missing=True)
    
    kpis_all = compute_kpis(cleaned, era_filter=None)
    kpis_post = compute_kpis(cleaned, era_filter="2000-Onward")

    assert "Franchise" in kpis_all
    assert "Standalone" in kpis_all
    assert "Franchise" in kpis_post
    assert "Standalone" in kpis_post

    # Verify no division by zero or NaN failures
    assert kpis_all["Franchise"]["median_roi"] > 0
    assert kpis_all["Standalone"]["median_roi"] > 0
