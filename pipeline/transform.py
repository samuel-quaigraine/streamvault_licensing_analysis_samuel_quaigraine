"""
Stations 2, 3, 4, and 5: Relational Flattening, Labeling, Financial Filtering, Scoring, and Talent Scouting.

Factory Line Functions (from h3lp/mathematical_formulation_of_the_streamvault_pipeline.md):
- Station 2: The Labeler (`classify_movie`)
  Unpacks nested JSON into 3 distinct grains (films, cast, crew) and tags Franchise vs Standalone.
- Station 3: The Quality Filter (`is_reliable`)
  Discards $0 unpopulated money placeholders and slices into Window A (All Years) vs Window B (2000+).
- Station 4: The Scorekeeper (`score_options`)
  Calculates Return Multiple (Rev/Budget), Medians vs Means, Bundle Totals, Top 3 Franchises & Top 5 Standalones.
- Station 5: The Talent Scout (`rate_talent`)
  Ranks Directors & Lead Actors with the Fairness Rule (minimum appearances >= 2).

Course Lessons Applied from @materials-learning:
- "Learning Path: Parsing and flattening nested JSON"
- "Learning Path: When json_normalize is not enough"
- "Learning Path: Missing data"
- "Learning Path: Judging a cleaning decision by its impact"
- "Learning Path: Vectorisation versus apply"
- "Learning Path: GroupBy and aggregation for KPIs"
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from pipeline.config import (
    ERA_CUTOFF_YEAR,
    COMMERCIAL_HIT_THRESHOLD,
    COMMERCIAL_MODERATE_THRESHOLD,
    TOTAL_ACQUISITION_BUDGET,
    MIN_TALENT_APPEARANCES,
    LEAD_ACTOR_ORDER_LIMIT,
)


# ==============================================================================
# STATION 2: THE LABELER (`classify_movie`)
# Unpacks nested JSON into 3 clean relational grains and labels collection tags.
# ==============================================================================

def flatten_movie_details_and_credits(
    movies_dict: Dict[int, Dict[str, Any]]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    STATION 2 (The Labeler): Flatten nested JSON into three clean relational tables.

    Lesson: "Parsing and flattening nested JSON" & "When json_normalize is not enough"
    Plain English: A film has one box office total, but dozens of actors and crew.
    If we mashed them all into one flat table, the box office numbers would get repeated
    for every actor, artificially inflating revenue by 50x!
    So we create three separate tables with distinct 'grains':
      1. Films Table  (Grain: 1 row per film)
      2. Cast Table   (Grain: 1 row per film per cast member)
      3. Crew Table   (Grain: 1 row per film per crew member)

    Returns:
        films_df: 1 row per film with metadata, collection labels, and box office.
        cast_df: 1 row per actor appearance with billing order.
        crew_df: 1 row per crew member with job title and department.
    """
    film_rows = []
    cast_records = []
    crew_records = []

    for movie_id, data in movies_dict.items():
        details = data.get("details", {})
        credits_data = data.get("credits", {})

        # Step A: The Labeler checks belongs_to_collection
        # If TMDb links it to a series, we capture the collection ID and name
        collection = details.get("belongs_to_collection")
        coll_id = collection.get("id") if collection else None
        coll_name = collection.get("name") if collection else None
        is_franchise = coll_id is not None

        # Step B: Extract Genres as comma-separated string
        genres_list = details.get("genres", [])
        genre_names = ", ".join([g.get("name", "") for g in genres_list if g.get("name")])

        # Step C: Extract Release Year and Era Window
        release_date = details.get("release_date")
        release_year = None
        if release_date and len(str(release_date)) >= 4:
            try:
                release_year = int(str(release_date)[:4])
            except ValueError:
                release_year = None

        era_window = "2000-Onward" if release_year and release_year >= ERA_CUTOFF_YEAR else "Pre-2000"

        # Step D: Build Film Record (Grain: exactly 1 row per film)
        film_rows.append({
            "movie_id": movie_id,
            "title": details.get("title", f"Movie_{movie_id}"),
            "release_date": release_date,
            "release_year": release_year,
            "era": era_window,
            "budget": float(details.get("budget", 0) or 0),
            "revenue": float(details.get("revenue", 0) or 0),
            "vote_average": float(details.get("vote_average", 0.0) or 0.0),
            "vote_count": int(details.get("vote_count", 0) or 0),
            "popularity": float(details.get("popularity", 0.0) or 0.0),
            "runtime": details.get("runtime"),
            "status": details.get("status"),
            "is_franchise": is_franchise,
            "collection_id": coll_id,
            "collection_name": coll_name,
            "genres": genre_names,
            "original_language": details.get("original_language"),
        })

        # Step E: Build Cast Records (Grain: 1 row per film per actor)
        for actor in credits_data.get("cast", []):
            cast_records.append({
                "movie_id": movie_id,
                "cast_id": actor.get("id"),
                "actor_name": actor.get("name"),
                "character_name": actor.get("character"),
                "cast_order": actor.get("order", 999),
            })

        # Step F: Build Crew Records (Grain: 1 row per film per crew member)
        for member in credits_data.get("crew", []):
            crew_records.append({
                "movie_id": movie_id,
                "crew_id": member.get("id"),
                "crew_name": member.get("name"),
                "job": member.get("job"),
                "department": member.get("department"),
            })

    # Assemble into DataFrames
    films_df = pd.DataFrame(film_rows)
    cast_df = pd.DataFrame(cast_records) if cast_records else pd.DataFrame(
        columns=["movie_id", "cast_id", "actor_name", "character_name", "cast_order"]
    )
    crew_df = pd.DataFrame(crew_records) if crew_records else pd.DataFrame(
        columns=["movie_id", "crew_id", "crew_name", "job", "department"]
    )

    return films_df, cast_df, crew_df


# Backward-compatible alias
flatten_movies_data = flatten_movie_details_and_credits


# ==============================================================================
# STATION 3: THE QUALITY FILTER (`is_reliable`)
# Parameterized zero-revenue handling and era window segmentation.
# ==============================================================================

def filter_reliable_financials(
    films_df: pd.DataFrame,
    treat_zero_revenue_as_missing: bool = True
) -> pd.DataFrame:
    """
    STATION 3 (The Quality Filter): Filter out disguised nulls and compute ROI.

    Lesson: "Missing data", "Judging a cleaning decision", & "Vectorisation versus apply"
    Plain English: In TMDb, a $0 budget or $0 revenue means 'nobody typed it in',
    not that the film cost $0 to produce!
    If we compute $0 / $10M = 0x, we falsely punish the movie as a catastrophic commercial failure.
    - If treat_zero_revenue_as_missing is True (Baseline):
      We treat $0 revenue as missing data (NaN), so it is excluded from profit/ROI averages.
    - If treat_zero_revenue_as_missing is False (Sensitivity check):
      We treat $0 as a flop (0x return) to test if Kwame's decision holds under harsh assumptions.
    """
    df = films_df.copy()

    # Vectorized profit: Revenue - Budget (dollars)
    df["profit"] = df["revenue"] - df["budget"]

    # Lesson: "Vectorisation versus apply"
    # Using np.where instead of slow row-by-row lambda/apply
    valid_budget = df["budget"] > 0

    if treat_zero_revenue_as_missing:
        valid_return = valid_budget & (df["revenue"] > 0)
        df["return_on_cost"] = np.where(
            valid_return,
            df["revenue"] / df["budget"],
            np.nan
        )
    else:
        df["return_on_cost"] = np.where(
            valid_budget,
            df["revenue"] / df["budget"],
            np.nan
        )

    # Commercial Tier Classification:
    # - Blockbuster Hit: Return >= 2.5x (covers production + marketing + theater cuts)
    # - Moderate Return: 1.0x to 2.5x (broke even or modest profit)
    # - Flop / Loss: < 1.0x (lost money)
    # - Unknown: Missing budget or missing revenue
    tier_conditions = [
        df["return_on_cost"].isna(),
        df["return_on_cost"] < COMMERCIAL_MODERATE_THRESHOLD,
        (df["return_on_cost"] >= COMMERCIAL_MODERATE_THRESHOLD) & (df["return_on_cost"] < COMMERCIAL_HIT_THRESHOLD),
        df["return_on_cost"] >= COMMERCIAL_HIT_THRESHOLD,
    ]
    tier_labels = ["Unknown", "Flop / Loss", "Moderate Return", "Blockbuster Hit"]
    df["commercial_tier"] = np.select(tier_conditions, tier_labels, default="Unknown")

    return df


# Backward-compatible alias
engineer_financial_metrics = filter_reliable_financials


# ==============================================================================
# STATION 4: THE SCOREKEEPER (`score_options`)
# Computes dual-window KPIs, medians vs means, bundle economics, and top shortlists.
# ==============================================================================

def score_licensing_options(
    films_df: pd.DataFrame,
    era_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    STATION 4 (The Scorekeeper): Compute side-by-side KPIs for Franchises vs Standalones.

    Lesson: "GroupBy and aggregation for KPIs" & "Broadcasting — NumPy"
    Plain English: Calculates how well each licensing option performs.
    Crucial Rule: We report the MEDIAN return alongside the mean.
    A single $1B movie (like The Dark Knight) can drag an average skyward, making a group
    look safe when most films were mediocre. The median shows what a *typical* title achieves.
    """
    data = films_df if era_filter is None else films_df[films_df["era"] == era_filter].copy()
    scores = {}

    for is_franchise, group in data.groupby("is_franchise"):
        label = "Franchise" if is_franchise else "Standalone"

        valid_rev = group[group["revenue"] > 0]
        valid_roi = group[group["return_on_cost"].notna()]
        flops = group[group["return_on_cost"] < COMMERCIAL_MODERATE_THRESHOLD]
        hits = group[group["return_on_cost"] >= COMMERCIAL_HIT_THRESHOLD]

        scores[label] = {
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

    return scores


# Backward-compatible alias
compute_kpis = score_licensing_options


def rank_franchise_bundles(films_df: pd.DataFrame) -> pd.DataFrame:
    """
    STATION 4 (Scorekeeper): Rank Franchise Bundles with whole-bundle and weakest-film checks.

    Plain English: Since studios force StreamVault to buy the whole franchise together,
    we sum total revenue vs total budget across the entire collection and check the weakest film.
    One great opening film must not hide three money-losing sequels!
    """
    franchises = films_df[films_df["is_franchise"] & films_df["collection_name"].notna()].copy()

    bundle_ranks = franchises.groupby("collection_name").agg(
        film_count=("movie_id", "count"),
        total_revenue=("revenue", "sum"),
        total_budget=("budget", "sum"),
        mean_revenue=("revenue", "mean"),
        median_roi=("return_on_cost", "median"),
        min_roi=("return_on_cost", "min"),  # Weakest film in the bundle
        mean_vote=("vote_average", "mean"),
        earliest_release=("release_year", "min"),
        latest_release=("release_year", "max"),
        movie_ids=("movie_id", list),
        titles=("title", list)
    ).reset_index()

    # Bundle-level ROI: Total Revenue / Total Budget across the bundle
    valid_bundle_budget = bundle_ranks["total_budget"] > 0
    bundle_ranks["bundle_roi"] = np.where(
        valid_bundle_budget,
        bundle_ranks["total_revenue"] / bundle_ranks["total_budget"],
        np.nan
    )

    return bundle_ranks.sort_values(by=["total_revenue", "median_roi"], ascending=False)


# Backward-compatible alias
get_franchise_rankings = rank_franchise_bundles


def rank_standalone_hits(films_df: pd.DataFrame) -> pd.DataFrame:
    """
    STATION 4 (Scorekeeper): Rank Standalone Titles to find the top individual acquisitions.
    """
    standalones = films_df[~films_df["is_franchise"]].copy()
    valid_standalones = standalones[standalones["return_on_cost"].notna()].copy()

    return valid_standalones.sort_values(by=["return_on_cost", "revenue"], ascending=False)


# Backward-compatible alias
get_standalone_rankings = rank_standalone_hits


# ==============================================================================
# STATION 5: THE TALENT SCOUT (`rate_talent`)
# Identifies reliable directors and lead actors using the Fairness Rule.
# ==============================================================================

def scout_directors_and_lead_actors(
    films_df: pd.DataFrame,
    cast_df: pd.DataFrame,
    crew_df: pd.DataFrame,
    min_appearances: int = MIN_TALENT_APPEARANCES,
    lead_actor_cutoff: int = LEAD_ACTOR_ORDER_LIMIT
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    STATION 5 (The Talent Scout): Rank Directors and Lead Actors for Kwame's negotiators.

    Lesson: "Merging, and proving the join" & "GroupBy and aggregation for KPIs"
    Plain English: Evaluates who consistently delivers high returns and ratings.
    Fairness Rule: Only rank directors and actors who appear in at least 2 or 3 films
    on our list. A director who made 1 lucky hit shouldn't be crowned a proven guarantee!
    """
    film_metrics = films_df[["movie_id", "title", "revenue", "budget", "return_on_cost", "vote_average", "era"]]

    # Step 1: Scout Directors (crew member where job == 'Director')
    directors = crew_df[crew_df["job"] == "Director"].copy()
    director_merged = directors.merge(film_metrics, on="movie_id", how="inner")

    director_summary = director_merged.groupby("crew_name").agg(
        film_count=("movie_id", "nunique"),
        total_revenue=("revenue", "sum"),
        mean_revenue=("revenue", "mean"),
        median_roi=("return_on_cost", "median"),
        mean_vote=("vote_average", "mean"),
        films=("title", list)
    ).reset_index()

    # Apply fairness filter
    director_shortlist = director_summary[
        director_summary["film_count"] >= min_appearances
    ].sort_values(by=["median_roi", "total_revenue"], ascending=False)

    # Step 2: Scout Lead Actors (top billed cast members, cast_order <= cutoff)
    lead_actors = cast_df[cast_df["cast_order"] <= lead_actor_cutoff].copy()
    actor_merged = lead_actors.merge(film_metrics, on="movie_id", how="inner")

    actor_summary = actor_merged.groupby("actor_name").agg(
        film_count=("movie_id", "nunique"),
        total_revenue=("revenue", "sum"),
        mean_revenue=("revenue", "mean"),
        median_roi=("return_on_cost", "median"),
        mean_vote=("vote_average", "mean"),
        films=("title", list)
    ).reset_index()

    # Apply fairness filter
    actor_shortlist = actor_summary[
        actor_summary["film_count"] >= min_appearances
    ].sort_values(by=["median_roi", "total_revenue"], ascending=False)

    return director_shortlist, actor_shortlist


# Backward-compatible alias
rank_talent = scout_directors_and_lead_actors
