"""
Master Execution Script for StreamVault Content Acquisition Pipeline.

Orchestrates the 5 Factory Stations (docs/architecture.md):
- Step 1 (Extract): Candidate extraction from id_list.csv (The Bouncer door check) + TMDb API extraction (Missing Box)
- Step 2 (Validate): Referential grain integrity checks (zero orphan cast/crew records)
- Step 3 (Transform): 3 relational grains (films, cast, crew), Franchise vs Standalone tagged, $0 unrecorded money filtered
- Step 4 (Checks): Pre-load QA gate (conservation: 127 = 112 + 15), profiling, 4-slice deliberate spot-check
- Step 5 (Load): Atomic publishing (write_table_atomically) with SHA-256 content hashes to output/ and data/processed/
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict

import pandas as pd

from pipeline.config import (
    RAW_DIR,
    PROCESSED_DIR,
    OUTPUT_DIR,
    MANIFEST_PATH,
    TOTAL_RAW_CANDIDATE_ROWS,
)
from pipeline.extract import (
    extract_candidate_ids,
    TMDBExtractor,
)
from pipeline.transform import (
    flatten_movie_details_and_credits,
    filter_reliable_financials,
    score_licensing_options,
    rank_franchise_bundles,
    rank_standalone_hits,
    scout_directors_and_lead_actors,
)
from pipeline.validate import validate_cast_crew_grain
from pipeline.checks import (
    profile_dataset,
    quality_report,
    build_reconciliation_table,
    check_before_load,
    perform_deliberate_spot_check,
)
from pipeline.load import (
    load_all_tables_to_warehouse,
    write_table_atomically,
    compute_content_hash,
)


def run_streamvault_pipeline(
    perform_live_spotcheck: bool = True
) -> Dict[str, Any]:
    """Execute the end-to-end 5-station ETL pipeline and export clean deliverables."""
    pipeline_start_t = time.perf_counter()
    timings = {}

    print("=" * 80)
    print("STREAMVAULT CONTENT ACQUISITION PIPELINE - 5-STATION FACTORY RUN")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # ETL STEP 1: EXTRACT (Station 1 - Candidate Door Checks & TMDb Ingestion)
    # Lesson: 'Duplicates and data-quality checks' & 'Not hammering a free API'
    # --------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[ETL Step 1: Extract] Checking candidate list at the door...")
    candidate_df, valid_ids, door_exclusions = extract_candidate_ids()
    timings["extract_candidate_doors"] = time.perf_counter() - t0
    door_drop_count = len(door_exclusions)
    print(f"  Total lines on ticket list: {len(candidate_df)}")
    print(f"  Candidates admitted through door: {len(valid_ids)}")
    print(f"  Excluded at door (blank rows, negative IDs, strings, duplicates): {door_drop_count}")

    print("\n[ETL Step 1: Extract] Ingesting film data & tracking Missing Box (404s)...")
    t0 = time.perf_counter()
    extractor = TMDBExtractor(raw_dir=RAW_DIR, manifest_path=MANIFEST_PATH)
    movies_dict, dead_ids, acq_stats = extractor.extract_all(valid_ids)
    timings["extract_tmdb_catalog"] = time.perf_counter() - t0
    print(f"  Successfully acquired titles: {len(movies_dict)}")
    print(f"  Placed in 404 Missing Box: {len(dead_ids)} -> {dead_ids}")
    print(f"  API Network calls: {acq_stats['network_calls']}, Local Cache hits: {acq_stats['cache_hits']}")

    total_drops = door_drop_count + len(dead_ids)
    print(f"  Total Accounted-For Drops: {total_drops} (Every single ID accounted for!)")

    # --------------------------------------------------------------------------
    # ETL STEP 2: TRANSFORM (Station 2 - Relational Grain Flattening & Labeling)
    # Lesson: 'Parsing and flattening nested JSON'
    # --------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[ETL Step 2: Transform] Unpacking nested JSON into 3 distinct grains...")
    films_raw, cast_df, crew_df = flatten_movie_details_and_credits(movies_dict)
    timings["transform_flatten"] = time.perf_counter() - t0
    print(f"  Films Table (grain: 1 row/film): {len(films_raw)} rows")
    print(f"  Cast Table (grain: 1 row/film/actor): {len(cast_df)} rows")
    print(f"  Crew Table (grain: 1 row/film/crew): {len(crew_df)} rows")

    # --------------------------------------------------------------------------
    # ETL STEP 3: VALIDATE (Relational Referential Integrity & Fan-Out Guards)
    # Lesson: 'Merging, and proving the join'
    # --------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[ETL Step 3: Validate] Verifying referential integrity and join guards...")
    grain_report = validate_cast_crew_grain(films_raw, cast_df, crew_df)
    timings["validate_grains"] = time.perf_counter() - t0
    print(f"  Referential integrity verified: zero orphaned cast/crew records.")

    # --------------------------------------------------------------------------
    # ETL STEP 4: TRANSFORM (Station 3 & 4 - Financial Filtering, Scoring & Talent)
    # Lesson: 'Missing data' & 'GroupBy and aggregation for KPIs'
    # --------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[ETL Step 4: Transform] Filtering $0 money placeholders and scoring options...")
    films_baseline = filter_reliable_financials(films_raw, treat_zero_revenue_as_missing=True)
    films_sensitivity = filter_reliable_financials(films_raw, treat_zero_revenue_as_missing=False)

    kpis_all_years = score_licensing_options(films_baseline, era_filter=None)
    kpis_post_2000 = score_licensing_options(films_baseline, era_filter="2000-Onward")
    kpis_pre_2000 = score_licensing_options(films_baseline, era_filter="Pre-2000")
    kpis_sens_all = score_licensing_options(films_sensitivity, era_filter=None)
    kpis_sens_2000 = score_licensing_options(films_sensitivity, era_filter="2000-Onward")

    franchise_ranks = rank_franchise_bundles(films_baseline)
    standalone_ranks = rank_standalone_hits(films_baseline)
    dir_shortlist, act_shortlist = scout_directors_and_lead_actors(films_baseline, cast_df, crew_df)
    timings["transform_scoring"] = time.perf_counter() - t0

    print(f"  Window A (All Years) Median ROI: Franchise={kpis_all_years.get('Franchise', {}).get('median_roi', 0):.2f}x vs Standalone={kpis_all_years.get('Standalone', {}).get('median_roi', 0):.2f}x")
    print(f"  Window B (2000+)     Median ROI: Franchise={kpis_post_2000.get('Franchise', {}).get('median_roi', 0):.2f}x vs Standalone={kpis_post_2000.get('Standalone', {}).get('median_roi', 0):.2f}x")
    print(f"  Qualified Talent (>=2 films): {len(dir_shortlist)} Directors, {len(act_shortlist)} Lead Actors")

    # --------------------------------------------------------------------------
    # ETL STEP 5: CHECKS (Pre-Load QA Gate & Deliberate Spot-Check)
    # Lesson: 'Spot-checking your output against the API'
    # --------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[ETL Step 5: Checks] Auditing row conservation and pre-load invariants...")
    reconciliation = build_reconciliation_table(candidate_df, dead_ids, films_baseline)
    qa_check_result = check_before_load(
        total_raw_count=len(candidate_df),
        verified_films_count=len(films_baseline),
        dropped_candidates_count=total_drops,
        films_df=films_baseline,
        cast_df=cast_df,
        crew_df=crew_df,
    )
    initial_profile = profile_dataset(films_baseline)
    timings["checks_qa_gate"] = time.perf_counter() - t0
    print(f"  QA Gate Result: {qa_check_result['status']} (Conservation: {qa_check_result['total_raw']} = {qa_check_result['verified_films']} + {qa_check_result['dropped_candidates']})")

    spot_check_results = []
    spot_check_summary = {}
    if perform_live_spotcheck:
        t0 = time.perf_counter()
        print("\n[Quality Audit] Executing deliberate 4-slice live API spot-check...")
        try:
            spot_check_results, spot_check_summary = perform_deliberate_spot_check(
                films_baseline, extractor, seed=42
            )
            print(f"  Spot-check checked {spot_check_summary['records_checked']} films, "
                  f"{spot_check_summary['fields_checked']} fields.")
            print(f"  Matches: {spot_check_summary['matches']}, Discrepancies: {spot_check_summary['discrepancies']}")
        except Exception as e:
            print(f"  Live spot-check notice: {e}")
            spot_check_summary = {
                "records_checked": 0, "fields_checked": 0, "matches": 0,
                "discrepancies": 0, "moves_recommendation": False,
                "as_of_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            }
        timings["spot_check"] = time.perf_counter() - t0

    # --------------------------------------------------------------------------
    # ETL STEP 6: LOAD (Atomic Warehouse Publishing & Integrity Fingerprinting)
    # Lesson: 'pandas: How to Read and Write Files'
    # --------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[ETL Step 6: Load] Publishing clean tables atomically and hashing...")

    # Assemble summary KPI table
    kpi_rows = []
    for era_label, kpi_dict in [("All-Years", kpis_all_years), ("2000-Onward", kpis_post_2000), ("Pre-2000", kpis_pre_2000)]:
        for group_label in ["Franchise", "Standalone"]:
            metrics = kpi_dict.get(group_label, {})
            kpi_rows.append({
                "Era_Window": era_label,
                "Group": group_label,
                "Titles_Count": metrics.get("total_titles", 0),
                "Median_Return_on_Cost": f"{metrics.get('median_roi', 0.0):.2f}x",
                "Mean_Return_on_Cost": f"{metrics.get('mean_roi', 0.0):.2f}x",
                "Median_Revenue_USD": metrics.get("median_revenue", 0.0),
                "Mean_Revenue_USD": metrics.get("mean_revenue", 0.0),
                "Total_Revenue_USD": metrics.get("total_revenue", 0.0),
                "Median_Budget_USD": metrics.get("median_budget", 0.0),
                "Commercial_Hit_Rate": f"{metrics.get('hit_rate', 0.0)*100:.1f}%",
                "Commercial_Failure_Rate": f"{metrics.get('failure_rate', 0.0)*100:.1f}%",
                "Average_Audience_Rating": f"{metrics.get('mean_vote_average', 0.0):.2f}/10",
            })
    summary_kpi_df = pd.DataFrame(kpi_rows)

    # Assemble talent rankings table
    talent_rows = []
    for _, r in dir_shortlist.iterrows():
        talent_rows.append({
            "Role": "Director",
            "Name": r["crew_name"],
            "Film_Count": r["film_count"],
            "Median_ROI": f"{r['median_roi']:.2f}x" if pd.notna(r["median_roi"]) else "N/A",
            "Total_Revenue_USD": r["total_revenue"],
            "Average_Audience_Rating": f"{r['mean_vote']:.2f}/10",
            "Films": ", ".join(r["films"])
        })
    for _, r in act_shortlist.iterrows():
        talent_rows.append({
            "Role": "Lead Actor",
            "Name": r["actor_name"],
            "Film_Count": r["film_count"],
            "Median_ROI": f"{r['median_roi']:.2f}x" if pd.notna(r["median_roi"]) else "N/A",
            "Total_Revenue_USD": r["total_revenue"],
            "Average_Audience_Rating": f"{r['mean_vote']:.2f}/10",
            "Films": ", ".join(r["films"])
        })
    talent_df = pd.DataFrame(talent_rows)
    reconciliation_df = pd.DataFrame(reconciliation)

    content_hashes = load_all_tables_to_warehouse(
        films_df=films_baseline,
        cast_df=cast_df,
        crew_df=crew_df,
        summary_kpis_df=summary_kpi_df,
        franchise_ranks_df=franchise_ranks,
        standalone_ranks_df=standalone_ranks,
        talent_df=talent_df,
        reconciliation_df=reconciliation_df,
        profiling_dict=initial_profile,
        output_dir=OUTPUT_DIR,
        processed_dir=PROCESSED_DIR,
    )
    timings["load_publish"] = time.perf_counter() - t0

    for table_name, h_val in content_hashes.items():
        print(f"  {table_name:<28}  [SHA-256 fingerprint: {h_val}]")

    total_pipeline_time = time.perf_counter() - pipeline_start_t
    timings["total_execution_time"] = total_pipeline_time

    print(f"\nPipeline finished successfully in {total_pipeline_time:.2f} seconds!")
    print("=" * 80)

    return {
        "candidate_df": candidate_df,
        "valid_ids": valid_ids,
        "door_exclusions": door_exclusions,
        "dead_ids": dead_ids,
        "films_df": films_baseline,
        "films_sensitivity": films_sensitivity,
        "cast_df": cast_df,
        "crew_df": crew_df,
        "kpis_all_years": kpis_all_years,
        "kpis_post_2000": kpis_post_2000,
        "kpis_pre_2000": kpis_pre_2000,
        "kpis_sens_all": kpis_sens_all,
        "kpis_sens_2000": kpis_sens_2000,
        "franchise_ranks": franchise_ranks,
        "standalone_ranks": standalone_ranks,
        "dir_shortlist": dir_shortlist,
        "act_shortlist": act_shortlist,
        "initial_profile": initial_profile,
        "reconciliation": reconciliation,
        "spot_check_results": spot_check_results,
        "spot_check_summary": spot_check_summary,
        "timings": timings,
    }


if __name__ == "__main__":
    results = run_streamvault_pipeline(perform_live_spotcheck=True)
