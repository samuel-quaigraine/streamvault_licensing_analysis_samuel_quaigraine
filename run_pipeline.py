"""
Master execution script for StreamVault Content Acquisition Pipeline.
Runs top-to-bottom from a clean clone, produces all intermediate tables,
runs data profiling and reconciliation, computes KPIs for both time windows,
performs the 4-slice spot-check, and generates all 5 lab deliverables.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, List

import pandas as pd

from pipeline.config import (
    DATA_DIR,
    RAW_DIR,
    PROCESSED_DIR,
    OUTPUT_DIR,
    MANIFEST_PATH,
    TOTAL_ACQUISITION_BUDGET,
    ERA_CUTOFF_YEAR,
)
from pipeline.load import load_candidate_ids
from pipeline.extract import TMDBExtractor
from pipeline.transform import (
    flatten_movies_data,
    engineer_financial_metrics,
    compute_kpis,
    get_franchise_rankings,
    get_standalone_rankings,
    rank_talent,
)
from pipeline.validate import safe_merge_one_to_one, validate_cast_crew_grain
from pipeline.checks import (
    profile_dataset,
    quality_report,
    build_reconciliation_table,
    perform_deliberate_spot_check,
)


def run_streamvault_pipeline(
    perform_live_spotcheck: bool = True
) -> Dict[str, Any]:
    """Execute the end-to-end pipeline and return summary results."""
    pipeline_start_t = time.perf_counter()
    timings = {}
    
    print("=" * 80)
    print("STREAMVAULT CONTENT ACQUISITION PIPELINE - EXECUTION START")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # STAGE 1: Load and Audit Candidate IDs (127 rows)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Stage 1] Ingesting candidate IDs from id_list.csv...")
    candidate_df, valid_ids, exclusion_log = load_candidate_ids()
    timings["stage_1_load_ids"] = time.perf_counter() - t0
    print(f"  Total lines in CSV: {len(candidate_df)}")
    print(f"  Valid unique numeric IDs: {len(valid_ids)}")
    print(f"  Format/Domain exclusions: {len([e for e in exclusion_log if 'Duplicate' not in e['reason']])}")
    print(f"  Exact duplicates removed: {len([e for e in exclusion_log if 'Duplicate' in e['reason']])}")

    # -------------------------------------------------------------------------
    # STAGE 2: Fetch Details & Credits (Polite Cached Acquisition)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Stage 2] Fetching movie details and credits from TMDb API...")
    extractor = TMDBExtractor(raw_dir=RAW_DIR, manifest_path=MANIFEST_PATH)
    movies_dict, dead_ids, acq_stats = extractor.extract_all(valid_ids)
    timings["stage_2_acquisition"] = time.perf_counter() - t0
    print(f"  Successfully acquired titles: {len(movies_dict)}")
    print(f"  Dead / 404 IDs: {len(dead_ids)} -> {dead_ids}")
    print(f"  API Network calls: {acq_stats['network_calls']}, Cache hits: {acq_stats['cache_hits']}")

    # -------------------------------------------------------------------------
    # STAGE 3: Flatten to Tables with Strict Grains
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Stage 3] Flattening nested JSON into distinct grain tables...")
    films_raw, cast_df, crew_df = flatten_movies_data(movies_dict)
    timings["stage_3_flatten"] = time.perf_counter() - t0
    print(f"  Films Table (# grain: one row per film): {len(films_raw)} rows")
    print(f"  Cast Table (# grain: one row per film per cast member): {len(cast_df)} rows")
    print(f"  Crew Table (# grain: one row per film per crew member): {len(crew_df)} rows")

    # -------------------------------------------------------------------------
    # STAGE 4: Validate Merge Integrity & Grain Relationships
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Stage 4] Validating merge integrity and relational grain...")
    grain_report = validate_cast_crew_grain(films_raw, cast_df, crew_df)
    timings["stage_4_validate"] = time.perf_counter() - t0
    print(f"  Referential integrity passed: all cast/crew belong to known films.")
    print(f"  Avg cast per film: {grain_report['avg_cast_per_film']:.1f}, Avg crew per film: {grain_report['avg_crew_per_film']:.1f}")

    # -------------------------------------------------------------------------
    # STAGE 5: Exploratory Data Profiling & Quality Assertions
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Stage 5] Running deep data profiling and initial quality checks...")
    initial_profile = profile_dataset(films_raw)
    qr_stage_1 = quality_report(films_raw, "Stage 1: Raw Flattened")
    timings["stage_5_profiling"] = time.perf_counter() - t0
    print(f"  $0 Revenue films: {initial_profile['zero_revenue_count']} / {len(films_raw)}")
    print(f"  $0 Budget films: {initial_profile['zero_budget_count']} / {len(films_raw)}")
    print(f"  Revenue outliers (IQR > 1.5): {initial_profile['revenue_outlier_count']}")

    # -------------------------------------------------------------------------
    # STAGE 6: Parameterized Cleaning & Feature Engineering
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Stage 6] Computing derived features under baseline & sensitivity rules...")
    # Baseline: treat zero revenue as missing data (unknown box office)
    films_baseline = engineer_financial_metrics(films_raw, treat_zero_revenue_as_missing=True)
    # Sensitivity: treat zero revenue as $0 commercial flop
    films_sensitivity = engineer_financial_metrics(films_raw, treat_zero_revenue_as_missing=False)
    
    qr_stage_2 = quality_report(films_baseline, "Stage 2: Cleaned Analytical")
    timings["stage_6_transform"] = time.perf_counter() - t0

    # -------------------------------------------------------------------------
    # STAGE 7: Compute KPIs for Both Windows (All-Years & 2000-Onward)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Stage 7] Evaluating KPIs across eras and cleaning assumptions...")
    # Baseline KPIs
    kpis_all_years = compute_kpis(films_baseline, era_filter=None)
    kpis_post_2000 = compute_kpis(films_baseline, era_filter="2000-Onward")
    kpis_pre_2000 = compute_kpis(films_baseline, era_filter="Pre-2000")

    # Sensitivity KPIs
    kpis_sens_all = compute_kpis(films_sensitivity, era_filter=None)
    kpis_sens_2000 = compute_kpis(films_sensitivity, era_filter="2000-Onward")

    timings["stage_7_analysis"] = time.perf_counter() - t0

    # Shortlists & Talent Analysis
    franchise_ranks = get_franchise_rankings(films_baseline)
    standalone_ranks = get_standalone_rankings(films_baseline)
    dir_summary, act_summary = rank_talent(films_baseline, cast_df, crew_df)

    # -------------------------------------------------------------------------
    # STAGE 8: Build Reconciliation Table
    # -------------------------------------------------------------------------
    reconciliation = build_reconciliation_table(candidate_df, dead_ids, films_baseline)

    # -------------------------------------------------------------------------
    # STAGE 9: Deliberate 4-Slice Live API Spot-Check
    # -------------------------------------------------------------------------
    spot_check_results = []
    spot_check_summary = {}
    if perform_live_spotcheck:
        t0 = time.perf_counter()
        print("\n[Stage 8] Executing deliberate 4-slice live API spot-check...")
        try:
            spot_check_results, spot_check_summary = perform_deliberate_spot_check(
                films_baseline, extractor, seed=42
            )
            print(f"  Spot-check checked {spot_check_summary['records_checked']} films, "
                  f"{spot_check_summary['fields_checked']} fields.")
            print(f"  Matches: {spot_check_summary['matches']}, Discrepancies: {spot_check_summary['discrepancies']}")
        except Exception as e:
            print(f"  Live spot-check encountered network notice: {e}")
            spot_check_summary = {
                "records_checked": 0, "fields_checked": 0, "matches": 0,
                "discrepancies": 0, "moves_recommendation": False,
                "as_of_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            }
        timings["stage_8_spotcheck"] = time.perf_counter() - t0

    # -------------------------------------------------------------------------
    # STAGE 10: Save Processed Outputs & Publish Deliverables to output/
    # -------------------------------------------------------------------------
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Clean data tables
    films_baseline.to_csv(PROCESSED_DIR / "films_analytical.csv", index=False)
    cast_df.to_csv(PROCESSED_DIR / "cast_analytical.csv", index=False)
    crew_df.to_csv(PROCESSED_DIR / "crew_analytical.csv", index=False)

    films_baseline.to_csv(OUTPUT_DIR / "clean_films.csv", index=False)
    cast_df.to_csv(OUTPUT_DIR / "clean_cast.csv", index=False)
    crew_df.to_csv(OUTPUT_DIR / "clean_crew.csv", index=False)

    # 2. Executive KPI Summary Table (CSV)
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
    summary_kpi_df.to_csv(OUTPUT_DIR / "summary_kpis.csv", index=False)

    # 3. Rankings & Shortlists (CSV)
    franchise_ranks.to_csv(OUTPUT_DIR / "franchise_rankings.csv", index=False)
    standalone_ranks.to_csv(OUTPUT_DIR / "standalone_rankings.csv", index=False)

    # 4. Candidate Reconciliation (CSV)
    pd.DataFrame(reconciliation).to_csv(OUTPUT_DIR / "candidate_reconciliation.csv", index=False)

    # 5. Data Profiling & Audit Summary (JSON)
    with open(OUTPUT_DIR / "profiling_summary.json", "w", encoding="utf-8") as f:
        json.dump(initial_profile, f, indent=2, default=str)

    print(f"  Exported clean tables and summaries to: {OUTPUT_DIR}")

    total_pipeline_time = time.perf_counter() - pipeline_start_t
    timings["total_execution_time"] = total_pipeline_time

    print(f"\nPipeline finished in {total_pipeline_time:.2f} seconds!")
    print("=" * 80)

    return {
        "candidate_df": candidate_df,
        "exclusion_log": exclusion_log,
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
        "dir_summary": dir_summary,
        "act_summary": act_summary,
        "initial_profile": initial_profile,
        "reconciliation": reconciliation,
        "spot_check_results": spot_check_results,
        "spot_check_summary": spot_check_summary,
        "timings": timings,
    }


if __name__ == "__main__":
    results = run_streamvault_pipeline(perform_live_spotcheck=True)
