"""
Data loading and candidate ID ingestion module.
Explicitly accounts for all 127 candidate lines, including empty line 69,
non-numeric formats, duplicates, and negative identifiers.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from pipeline.config import ID_LIST_PATH, RAW_DIR


def load_candidate_ids(
    filepath: Path = ID_LIST_PATH,
) -> Tuple[pd.DataFrame, List[int], List[Dict[str, Any]]]:
    """
    Load and audit all 127 candidate rows from the candidate ID file.
    
    Returns:
        candidate_df: DataFrame containing every line with its classification and status.
        valid_ids: List of unique positive integer TMDb IDs ready for acquisition.
        exclusion_log: List of dictionaries documenting every excluded or duplicate line.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Candidate file not found at: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        raw_lines = [line.rstrip("\r\n") for line in f]

    # Verify header
    if not raw_lines or raw_lines[0].strip() != "tmdb_id":
        raise ValueError(f"Expected first line to be 'tmdb_id', got: {raw_lines[0] if raw_lines else 'empty'}")

    data_lines = raw_lines[1:]
    total_candidate_rows = len(data_lines)
    assert total_candidate_rows == 127, f"Expected 127 candidate rows, found {total_candidate_rows}"

    records = []
    seen_ids = set()
    exclusion_log = []

    for idx, raw_val in enumerate(data_lines):
        line_num = idx + 2  # 1-based index (header is line 1)
        trimmed = raw_val.strip()

        # Check for empty line (specifically line 69)
        if not trimmed:
            reason = "Empty row / missing identifier"
            records.append({
                "line_number": line_num,
                "raw_id": raw_val,
                "parsed_id": None,
                "status": "EXCLUDED",
                "reason": reason,
                "category": "Format Error"
            })
            exclusion_log.append({
                "line": line_num,
                "raw_id": "<EMPTY>",
                "reason": reason,
                "stage": "ID List Ingestion"
            })
            continue

        # Check for explicit string missing markers like N/A
        if trimmed.upper() in ("N/A", "NA", "NULL", "NONE"):
            reason = "Literal missing string marker"
            records.append({
                "line_number": line_num,
                "raw_id": raw_val,
                "parsed_id": None,
                "status": "EXCLUDED",
                "reason": reason,
                "category": "Format Error"
            })
            exclusion_log.append({
                "line": line_num,
                "raw_id": raw_val,
                "reason": reason,
                "stage": "ID List Ingestion"
            })
            continue

        # Check for IMDb format (e.g. tt0468569)
        if trimmed.startswith("tt"):
            reason = "IMDb alphanumeric format instead of TMDb numeric integer"
            records.append({
                "line_number": line_num,
                "raw_id": raw_val,
                "parsed_id": None,
                "imdb_id": trimmed,
                "status": "EXTERNAL_FORMAT",
                "reason": reason,
                "category": "Format Error"
            })
            exclusion_log.append({
                "line": line_num,
                "raw_id": raw_val,
                "reason": reason,
                "stage": "ID List Ingestion"
            })
            continue

        # Attempt integer parsing
        try:
            parsed_id = int(trimmed)
        except ValueError:
            reason = f"Non-numeric identifier: '{raw_val}'"
            records.append({
                "line_number": line_num,
                "raw_id": raw_val,
                "parsed_id": None,
                "status": "EXCLUDED",
                "reason": reason,
                "category": "Format Error"
            })
            exclusion_log.append({
                "line": line_num,
                "raw_id": raw_val,
                "reason": reason,
                "stage": "ID List Ingestion"
            })
            continue

        # Check for negative IDs
        if parsed_id < 0:
            reason = f"Negative integer identifier ({parsed_id})"
            records.append({
                "line_number": line_num,
                "raw_id": raw_val,
                "parsed_id": parsed_id,
                "status": "EXCLUDED",
                "reason": reason,
                "category": "Domain Error"
            })
            exclusion_log.append({
                "line": line_num,
                "raw_id": raw_val,
                "reason": reason,
                "stage": "ID List Ingestion"
            })
            continue

        # Check for duplicate IDs
        if parsed_id in seen_ids:
            reason = f"Duplicate identifier of earlier entry ({parsed_id})"
            records.append({
                "line_number": line_num,
                "raw_id": raw_val,
                "parsed_id": parsed_id,
                "status": "DUPLICATE",
                "reason": reason,
                "category": "Duplicate"
            })
            exclusion_log.append({
                "line": line_num,
                "raw_id": raw_val,
                "reason": reason,
                "stage": "ID List Ingestion"
            })
            continue

        # Valid candidate ID
        seen_ids.add(parsed_id)
        records.append({
            "line_number": line_num,
            "raw_id": raw_val,
            "parsed_id": parsed_id,
            "status": "VALID",
            "reason": "Passed initial validation",
            "category": "Valid"
        })

    candidate_df = pd.DataFrame(records)
    valid_ids = sorted([r["parsed_id"] for r in records if r["status"] == "VALID"])

    return candidate_df, valid_ids, exclusion_log


def load_cached_movie_data(
    movie_id: int,
    raw_dir: Path = RAW_DIR
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Load movie details and credits JSON responses from disk cache.
    """
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
