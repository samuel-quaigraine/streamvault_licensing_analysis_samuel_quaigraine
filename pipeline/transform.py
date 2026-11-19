"""
Data transformation, feature engineering, and KPI computation module.
Enforces strict table grains with explicit comments.
Parameterizes cleaning choices so KPIs can be computed across multiple assumptions.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from pipeline.config import ERA_CUTOFF_YEAR, TOTAL_ACQUISITION_BUDGET


def flatten_movies_data(
    movies_dict: Dict[int, Dict[str, Any]]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Flatten nested JSON responses into three tabular structures with distinct grains.
    
    Returns:
        films_df: Grain: one row per film
        cast_df: Grain: one row per film per cast member
        crew_df: Grain: one row per film per crew member
    """
    film_rows = []
    cast_records = []
    crew_records = []

    for movie_id, data in movies_dict.items():
        details = data.get("details", {})
        credits_data = data.get("credits", {})

        # Extract collection info (scalar reduction of nested dict)
        collection = details.get("belongs_to_collection")
        coll_id = collection.get("id") if collection else None
        coll_name = collection.get("name") if collection else None

        # Genres (reduce list to count and comma-separated string)
        genres_list = details.get("genres", [])
        genre_names = ", ".join([g.get("name", "") for g in genres_list if g.get("name")])

        # Release year parsing
        release_date = details.get("release_date")
        release_year = None
        if release_date and len(release_date) >= 4:
            try:
                release_year = int(release_date[:4])
            except ValueError:
                release_year = None

        era = "2000-Onward" if release_year and release_year >= ERA_CUTOFF_YEAR else "Pre-2000"

        # Film table grain: # grain: one row per film
        film_rows.append({
            "movie_id": movie_id,
            "title": details.get("title", ""),
            "original_title": details.get("original_title", ""),
            "release_date": release_date,
            "release_year": release_year,
            "era": era,
            "budget": float(details.get("budget", 0) or 0),
            "revenue": float(details.get("revenue", 0) or 0),
            "runtime": float(details.get("runtime", 0) or 0),
            "vote_average": float(details.get("vote_average", 0.0) or 0.0),
            "vote_count": int(details.get("vote_count", 0) or 0),
            "popularity": float(details.get("popularity", 0.0) or 0.0),
            "status": details.get("status", ""),
            "collection_id": coll_id,
            "collection_name": coll_name,
            "is_franchise": bool(coll_id is not None),
            "genres_count": len(genres_list),
            "genre_names": genre_names,
        })

        # Cast records: prepare for json_normalize
        cast_list = credits_data.get("cast", [])
        for c in cast_list:
            cast_records.append({
                "movie_id": movie_id,
                "cast_id": c.get("id"),
                "actor_name": c.get("name"),
                "character_name": c.get("character"),
                "cast_order": c.get("order"),
            })

        # Crew records: directors and key creators
        crew_list = credits_data.get("crew", [])
        for cr in crew_list:
            crew_records.append({
                "movie_id": movie_id,
                "crew_id": cr.get("id"),
                "crew_name": cr.get("name"),
                "job": cr.get("job"),
                "department": cr.get("department"),
            })

    # 1. Films Table (# grain: one row per film)
    films_df = pd.DataFrame(film_rows)

    # 2. Cast Table (# grain: one row per film per cast member)
    cast_df = pd.DataFrame(cast_records) if cast_records else pd.DataFrame(
        columns=["movie_id", "cast_id", "actor_name", "character_name", "cast_order"]
    )

    # 3. Crew Table (# grain: one row per film per crew member)
    crew_df = pd.DataFrame(crew_records) if crew_records else pd.DataFrame(
        columns=["movie_id", "crew_id", "crew_name", "job", "department"]
    )

    return films_df, cast_df, crew_df


def engineer_financial_metrics(
    films_df: pd.DataFrame,
    treat_zero_revenue_as_missing: bool = True
) -> pd.DataFrame:
    """
    Compute derived financial metrics with parameterized handling of zero revenue.
    Vectorized computation without row loops.
    """
    df = films_df.copy()

    # Profit = Revenue - Budget
    df["profit"] = df["revenue"] - df["budget"]

    # Calculate Return on Cost: Revenue / Budget
    # Check conditions: budget > 0
    valid_budget = df["budget"] > 0

    if treat_zero_revenue_as_missing:
        # Treat $0 revenue as missing data (unknown box office)
        valid_return = valid_budget & (df["revenue"] > 0)
        df["return_on_cost"] = np.where(
            valid_return,
            df["revenue"] / df["budget"],
            np.nan
        )
    else:
        # Treat $0 revenue as genuine commercial flop ($0 return)
        df["return_on_cost"] = np.where(
            valid_budget,
            df["revenue"] / df["budget"],
            np.nan
        )

    # Commercial outcome classifications (Vectorized np.select)
    conditions = [
        df["return_on_cost"].isna(),
        df["return_on_cost"] < 1.0,
        (df["return_on_cost"] >= 1.0) & (df["return_on_cost"] < 2.5),
        df["return_on_cost"] >= 2.5
    ]
    choices = ["Unknown", "Flop / Loss", "Moderate Return", "Blockbuster Hit"]
    df["commercial_tier"] = np.select(conditions, choices, default="Unknown")

    return df


def compute_kpis(
    df: pd.DataFrame,
    era_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compute executive KPIs comparing Franchise Bundles vs. Standalone Titles.
    Vectorized aggregation using pandas groupby.
    """
    data = df if era_filter is None else df[df["era"] == era_filter].copy()

    kpis = {}
    for is_franchise, group in data.groupby("is_franchise"):
        label = "Franchise" if is_franchise else "Standalone"
        
        # Valid financial records
        valid_rev = group[group["revenue"] > 0]
        valid_roi = group[group["return_on_cost"].notna()]
        flops = group[group["return_on_cost"] < 1.0]
        hits = group[group["return_on_cost"] >= 2.5]

        kpis[label] = {
            "total_titles": len(group),
            "titles_with_revenue": len(valid_rev),
            "titles_with_roi": len(valid_roi),
            "total_revenue": float(group["revenue"].sum()),
            "mean_revenue": float(valid_rev["revenue"].mean()) if len(valid_rev) > 0 else 0.0,
            "median_revenue": float(valid_rev["revenue"].median()) if len(valid_rev) > 0 else 0.0,
            "mean_budget": float(group[group["budget"] > 0]["budget"].mean()) if (group["budget"] > 0).any() else 0.0,
            "median_budget": float(group[group["budget"] > 0]["budget"].median()) if (group["budget"] > 0).any() else 0.0,
            "mean_roi": float(valid_roi["return_on_cost"].mean()) if len(valid_roi) > 0 else 0.0,
            "median_roi": float(valid_roi["return_on_cost"].median()) if len(valid_roi) > 0 else 0.0,
            "failure_rate": float(len(flops) / len(valid_roi)) if len(valid_roi) > 0 else 0.0,
            "hit_rate": float(len(hits) / len(valid_roi)) if len(valid_roi) > 0 else 0.0,
            "mean_vote_average": float(group["vote_average"].mean()) if len(group) > 0 else 0.0,
        }

    return kpis


def get_franchise_rankings(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate performance per franchise/collection."""
    franchises = df[df["is_franchise"] & df["collection_name"].notna()].copy()
    
    ranked = franchises.groupby("collection_name").agg(
        film_count=("movie_id", "count"),
        total_revenue=("revenue", "sum"),
        mean_revenue=("revenue", "mean"),
        median_roi=("return_on_cost", "median"),
        mean_vote=("vote_average", "mean"),
        earliest_release=("release_year", "min"),
        latest_release=("release_year", "max"),
        movie_ids=("movie_id", list),
        titles=("title", list)
    ).reset_index()

    return ranked.sort_values(by=["total_revenue", "median_roi"], ascending=False)


def get_standalone_rankings(df: pd.DataFrame) -> pd.DataFrame:
    """Rank top standalone titles by ROI and commercial performance."""
    standalones = df[~df["is_franchise"]].copy()
    valid = standalones[standalones["return_on_cost"].notna()].copy()
    
    return valid.sort_values(by=["return_on_cost", "revenue"], ascending=False)


def rank_talent(
    films_df: pd.DataFrame,
    cast_df: pd.DataFrame,
    crew_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Rank directors and lead actors by commercial outperformance without distorting grains.
    """
    # 1. Directors (from crew)
    directors = crew_df[crew_df["job"] == "Director"].copy()
    m_dir = directors.merge(films_df[["movie_id", "title", "revenue", "return_on_cost", "era"]], on="movie_id", how="inner")
    
    dir_summary = m_dir.groupby("crew_name").agg(
        film_count=("movie_id", "nunique"),
        total_revenue=("revenue", "sum"),
        mean_revenue=("revenue", "mean"),
        median_roi=("return_on_cost", "median"),
        films=("title", list)
    ).reset_index().sort_values(by=["median_roi", "total_revenue"], ascending=False)

    # 2. Lead Actors (cast_order == 0)
    lead_actors = cast_df[cast_df["cast_order"] == 0].copy()
    m_act = lead_actors.merge(films_df[["movie_id", "title", "revenue", "return_on_cost", "era"]], on="movie_id", how="inner")

    act_summary = m_act.groupby("actor_name").agg(
        film_count=("movie_id", "nunique"),
        total_revenue=("revenue", "sum"),
        mean_revenue=("revenue", "mean"),
        median_roi=("return_on_cost", "median"),
        films=("title", list)
    ).reset_index().sort_values(by=["median_roi", "total_revenue"], ascending=False)

    return dir_summary, act_summary
