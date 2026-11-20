"""
ETL Step: LOAD (Atomic Table Publishing, Hashing & Deliverables Export).

Analogies & Concept:
Like the final dispatch loading bay in the factory:
1. Receives clean, validated, and transformed analytical tables from upstream stations.
2. Writes each table to a scratch file (.tmp.csv) first, then swaps it into place
   in one atomic operating-system rename (os.replace).
   If the power is cut or an error occurs mid-write, the destination warehouse table is NEVER corrupted!
3. Calculates a stable 12-character SHA-256 content fingerprint for every published file.
4. Provides a central load_all_tables_to_warehouse() helper to publish the complete delivery package.

Course Lessons Applied from @materials-learning:
- "pandas: How to Read and Write Files"
- "Learning Path: Loading data and large files"
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import pandas as pd

from pipeline.config import RAW_DIR, PROCESSED_DIR, OUTPUT_DIR

# Backward-compatibility re-exports: ensures any existing tests or legacy scripts
# that import candidate loading from pipeline.load continue working without breaking!
from pipeline.extract import (
    extract_candidate_ids as load_candidate_ids,
    extract_candidate_ids as bounce_and_clean_candidates,
)


def write_table_atomically(dataframe: pd.DataFrame, target_path: Path) -> Path:
    """
    Atomically write a DataFrame to CSV using a temporary file and atomic replace.

    Lesson: 'pandas: How to Read and Write Files'
    Plain English: Write to a scratch file first, then swap it into place in one
    instant move. If the process is interrupted, the destination file is never corrupted.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp.csv")

    try:
        dataframe.to_csv(temp_path, index=False)
        os.replace(temp_path, target_path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

    return target_path


def compute_content_hash(dataframe: pd.DataFrame) -> str:
    """
    Compute a deterministic SHA-256 hash of a DataFrame's CSV representation.

    Plain English: A unique 12-char fingerprint of the data. If even a single
    character or number changes, the fingerprint changes completely.
    """
    csv_bytes = dataframe.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()[:12]


def load_all_tables_to_warehouse(
    films_df: pd.DataFrame,
    cast_df: pd.DataFrame,
    crew_df: pd.DataFrame,
    summary_kpis_df: pd.DataFrame,
    franchise_ranks_df: pd.DataFrame,
    standalone_ranks_df: pd.DataFrame,
    talent_df: pd.DataFrame,
    reconciliation_df: pd.DataFrame,
    profiling_dict: Dict[str, Any],
    output_dir: Path = OUTPUT_DIR,
    processed_dir: Path = PROCESSED_DIR,
) -> Dict[str, str]:
    """
    LOAD: Central publishing function that atomically writes all warehouse tables
    and returns a dictionary of published table names and their content hashes.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    hashes = {}

    # 1. Intermediate Clean Relational Tables (data/processed/)
    write_table_atomically(films_df, processed_dir / "films_analytical.csv")
    write_table_atomically(cast_df, processed_dir / "cast_analytical.csv")
    write_table_atomically(crew_df, processed_dir / "crew_analytical.csv")

    # 2. Executive Deliverable Tables (output/)
    write_table_atomically(films_df, output_dir / "clean_films.csv")
    hashes["clean_films.csv"] = compute_content_hash(films_df)

    write_table_atomically(cast_df, output_dir / "clean_cast.csv")
    hashes["clean_cast.csv"] = compute_content_hash(cast_df)

    write_table_atomically(crew_df, output_dir / "clean_crew.csv")
    hashes["clean_crew.csv"] = compute_content_hash(crew_df)

    write_table_atomically(summary_kpis_df, output_dir / "summary_kpis.csv")
    hashes["summary_kpis.csv"] = compute_content_hash(summary_kpis_df)

    write_table_atomically(franchise_ranks_df, output_dir / "franchise_rankings.csv")
    hashes["franchise_rankings.csv"] = compute_content_hash(franchise_ranks_df)

    write_table_atomically(standalone_ranks_df, output_dir / "standalone_rankings.csv")
    hashes["standalone_rankings.csv"] = compute_content_hash(standalone_ranks_df)

    write_table_atomically(talent_df, output_dir / "talent_rankings.csv")
    hashes["talent_rankings.csv"] = compute_content_hash(talent_df)

    write_table_atomically(reconciliation_df, output_dir / "candidate_reconciliation.csv")
    hashes["candidate_reconciliation.csv"] = compute_content_hash(reconciliation_df)

    # 3. Profiling JSON
    with open(output_dir / "profiling_summary.json", "w", encoding="utf-8") as f:
        json.dump(profiling_dict, f, indent=2, default=str)

    return hashes


def load_cached_movie_data(
    movie_id: int,
    raw_dir: Path = RAW_DIR
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Load movie details and credits JSON responses from disk cache."""
    details_path = raw_dir / f"movie_{movie_id}.json"
    credits_path = raw_dir / f"credits_{movie_id}.json"

    details = None
    credits_data = None

    if details_path.exists():
        with open(details_path, "r", encoding="utf-8") as f:
            details = json.load(f)

    if credits_path.exists():
        with open(credits_path, "r", encoding="utf-8") as f:
            credits_data = json.load(f)

    return details, credits_data
