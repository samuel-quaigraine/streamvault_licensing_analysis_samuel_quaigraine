"""
ETL Step: EXTRACT (Station 1: Candidate Ingestion & TMDb API Acquisition).

Handles all data extraction across two upstream sources:
1. Source A: id_list.csv (Candidate ID tickets, dynamic format/duplicate inspection)
2. Source B: TMDb REST API (Movie details & credits, local disk cache, Missing Box 404s)

Analogies & Concept:
Like a diligent bouncer and a disciplined delivery scout working together:
1. Scans tickets dynamically: rejects blank rows, unreadable text, negative numbers, and duplicates.
2. Checks the local filing cabinet (data/raw/) first to avoid unnecessary phone calls.
3. Queries TMDb politely with exponential backoff and rate pacing (50ms).
4. Moves confirmed missing titles (404s) to the permanent 'Missing Box' (dead_ids.json) without crashing.
5. Keeps a timestamped audit ledger of every transaction in manifest.csv.

Course Lessons Applied from @materials-learning:
- "Learning Path: Duplicates and data-quality checks"
- "Learning Path: Loading data and large files"
- "Learning Path: Not hammering a free API"
- "Learning Path: Pagination, rate limits and backoff"
- "REST API Calls for Data Engineers: A Practical Guide with Examples"
- "Python's Requests Library (Guide)"
"""

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Dict, List, Optional, Set, Tuple, Any
import pandas as pd
import requests

from pipeline.config import (
    TMDB_API_KEY,
    TMDB_API_READ_ACCESS_TOKEN,
    MOVIE_ENDPOINT,
    CREDITS_ENDPOINT,
    FIND_ENDPOINT,
    REQUEST_TIMEOUT,
    USER_AGENT,
    RATE_LIMIT_SLEEP,
    RAW_DIR,
    MANIFEST_PATH,
    ID_LIST_PATH,
    TOTAL_RAW_CANDIDATE_ROWS,
)


# ==============================================================================
# EXTRACT SOURCE A: Candidate ID Extraction & Dynamic Door Checks
# ==============================================================================

def extract_candidate_ids(
    candidate_filepath: Path = ID_LIST_PATH,
) -> Tuple[pd.DataFrame, List[int], List[Dict[str, Any]]]:
    """
    EXTRACT SOURCE A (The Bouncer): Extract and audit raw candidate IDs from CSV.

    Dynamically scans all lines:
    - Finds ANY blank or whitespace-only lines anywhere in the file.
    - Isolates non-numeric formats (e.g. 'N/A', 'tt0468569').
    - Isolates domain violations (negative integers like -1).
    - Detects duplicate entries dynamically using a tracking set.
    - Yields clean, verified integer IDs for TMDb acquisition.

    Returns:
        candidate_audit_df: Full ledger of all 127 lines with their status and reasons.
        valid_numeric_ids: Clean list of unique positive integer IDs.
        door_exclusion_log: Detailed log of every line rejected at the door.
    """
    if not candidate_filepath.exists():
        raise FileNotFoundError(f"Candidate file not found at: {candidate_filepath}")

    with open(candidate_filepath, "r", encoding="utf-8") as file_handle:
        raw_lines = [line.rstrip("\r\n") for line in file_handle]

    if not raw_lines or raw_lines[0].strip() != "tmdb_id":
        raise ValueError(
            f"Expected first line to be 'tmdb_id', got: '{raw_lines[0] if raw_lines else 'empty'}'"
        )

    data_lines = raw_lines[1:]
    total_lines = len(data_lines)
    assert total_lines == TOTAL_RAW_CANDIDATE_ROWS, (
        f"Expected {TOTAL_RAW_CANDIDATE_ROWS} candidate lines, but found {total_lines}."
    )

    audit_records: List[Dict[str, Any]] = []
    seen_ids: set[int] = set()
    door_exclusion_log: List[Dict[str, Any]] = []

    for zero_based_idx, raw_value in enumerate(data_lines):
        line_number = zero_based_idx + 2  # Line 1 is the CSV header
        trimmed_value = raw_value.strip()

        # Check A: Dynamic Empty Line Detection
        if not trimmed_value:
            rejection_reason = "Empty row / missing identifier"
            audit_records.append({
                "line_number": line_number,
                "raw_id": raw_value,
                "parsed_id": None,
                "status": "EXCLUDED",
                "reason": rejection_reason,
                "category": "Format Error"
            })
            door_exclusion_log.append({
                "line": line_number,
                "raw_id": "<EMPTY>",
                "reason": rejection_reason,
                "stage": "Door Bouncer Ingestion"
            })
            continue

        # Check B: Literal Missing String Markers
        if trimmed_value.upper() in ("N/A", "NA", "NULL", "NONE"):
            rejection_reason = f"Literal missing string marker: '{trimmed_value}'"
            audit_records.append({
                "line_number": line_number,
                "raw_id": raw_value,
                "parsed_id": None,
                "status": "EXCLUDED",
                "reason": rejection_reason,
                "category": "Format Error"
            })
            door_exclusion_log.append({
                "line": line_number,
                "raw_id": raw_value,
                "reason": rejection_reason,
                "stage": "Door Bouncer Ingestion"
            })
            continue

        # Check C: External Identifier Formats (e.g. IMDb 'tt0468569')
        if trimmed_value.startswith("tt"):
            rejection_reason = "IMDb alphanumeric format instead of TMDb numeric integer"
            audit_records.append({
                "line_number": line_number,
                "raw_id": raw_value,
                "parsed_id": None,
                "status": "EXTERNAL_FORMAT",
                "reason": rejection_reason,
                "category": "Format Error"
            })
            door_exclusion_log.append({
                "line": line_number,
                "raw_id": raw_value,
                "reason": rejection_reason,
                "stage": "Door Bouncer Ingestion"
            })
            continue

        # Check D: Dynamic Integer Parsing
        try:
            parsed_integer_id = int(trimmed_value)
        except ValueError:
            rejection_reason = f"Non-numeric identifier: '{raw_value}'"
            audit_records.append({
                "line_number": line_number,
                "raw_id": raw_value,
                "parsed_id": None,
                "status": "EXCLUDED",
                "reason": rejection_reason,
                "category": "Format Error"
            })
            door_exclusion_log.append({
                "line": line_number,
                "raw_id": raw_value,
                "reason": rejection_reason,
                "stage": "Door Bouncer Ingestion"
            })
            continue

        # Check E: Domain Constraint (TMDb IDs must be strictly positive)
        if parsed_integer_id <= 0:
            rejection_reason = f"Negative integer identifier ({parsed_integer_id})"
            audit_records.append({
                "line_number": line_number,
                "raw_id": raw_value,
                "parsed_id": parsed_integer_id,
                "status": "EXCLUDED",
                "reason": rejection_reason,
                "category": "Domain Error"
            })
            door_exclusion_log.append({
                "line": line_number,
                "raw_id": raw_value,
                "reason": rejection_reason,
                "stage": "Door Bouncer Ingestion"
            })
            continue

        # Check F: Dynamic Duplicate Detection
        if parsed_integer_id in seen_ids:
            rejection_reason = f"Duplicate identifier of earlier entry ({parsed_integer_id})"
            audit_records.append({
                "line_number": line_number,
                "raw_id": raw_value,
                "parsed_id": parsed_integer_id,
                "status": "DUPLICATE",
                "reason": rejection_reason,
                "category": "Duplicate"
            })
            door_exclusion_log.append({
                "line": line_number,
                "raw_id": raw_value,
                "reason": rejection_reason,
                "stage": "Door Bouncer Ingestion"
            })
            continue

        # Check G: Admission Granted!
        seen_ids.add(parsed_integer_id)
        audit_records.append({
            "line_number": line_number,
            "raw_id": raw_value,
            "parsed_id": parsed_integer_id,
            "status": "VALID",
            "reason": "Passed initial door validation",
            "category": "Valid"
        })

    candidate_audit_df = pd.DataFrame(audit_records)
    valid_numeric_ids = sorted([
        record["parsed_id"] for record in audit_records if record["status"] == "VALID"
    ])

    return candidate_audit_df, valid_numeric_ids, door_exclusion_log


# Backward-compatible aliases
bounce_and_clean_candidates = extract_candidate_ids
load_candidate_ids = extract_candidate_ids


# ==============================================================================
# EXTRACT SOURCE B: TMDb API Polite Extraction & Caching
# ==============================================================================

class TMDBExtractor:
    """
    Polite, cached TMDb API extractor.
    Implements local disk caching, requests.Session() reuse, rate limiting,
    exponential backoff, non-crashing 404 handling, and manifest audit logging.
    """

    def __init__(self, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH):
        self.raw_dir = raw_dir
        self.manifest_path = manifest_path
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })
        if TMDB_API_READ_ACCESS_TOKEN:
            self.session.headers.update({
                "Authorization": f"Bearer {TMDB_API_READ_ACCESS_TOKEN}"
            })

        self.dead_ids_file = self.raw_dir / "dead_ids.json"
        self._init_manifest()

    def _get_cached_dead_ids(self) -> Set[int]:
        if self.dead_ids_file.exists():
            try:
                with open(self.dead_ids_file, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception:
                return set()
        return set()

    def _cache_dead_id(self, movie_id: int) -> None:
        dead_ids = self._get_cached_dead_ids()
        dead_ids.add(movie_id)
        with open(self.dead_ids_file, "w", encoding="utf-8") as f:
            json.dump(sorted(list(dead_ids)), f, indent=2)

    def _init_manifest(self) -> None:
        if not self.manifest_path.exists():
            with open(self.manifest_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "movie_id", "endpoint_type", "http_status",
                    "cache_or_network", "timestamp_utc", "latency_ms", "error_message"
                ])

    def _log_manifest(
        self,
        movie_id: int,
        endpoint_type: str,
        http_status: Optional[int],
        source: str,
        timestamp_utc: str,
        latency_ms: float,
        error_message: str = ""
    ) -> None:
        with open(self.manifest_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                movie_id, endpoint_type, http_status or "",
                source, timestamp_utc, f"{latency_ms:.1f}", error_message
            ])

    def _fetch_with_backoff(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        initial_backoff: float = 1.0
    ) -> requests.Response:
        if params is None:
            params = {}
        if TMDB_API_KEY and "api_key" not in params and "Authorization" not in self.session.headers:
            params["api_key"] = TMDB_API_KEY

        backoff = initial_backoff
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    sleep_time = float(retry_after) if retry_after else backoff
                    time.sleep(sleep_time)
                    backoff *= 2
                    continue
                elif response.status_code >= 500:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                return response
            except (requests.ConnectionError, requests.Timeout):
                if attempt == max_retries - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2

        return self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)

    def get_movie_details(self, movie_id: int) -> Tuple[Optional[Dict[str, Any]], str, Optional[int]]:
        if movie_id in self._get_cached_dead_ids():
            return None, "cache", 404

        cache_file = self.raw_dir / f"movie_{movie_id}.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, timezone.utc).isoformat()
            self._log_manifest(movie_id, "movie_details", 200, "cache", mtime, 0.0)
            return data, "cache", 200

        time.sleep(RATE_LIMIT_SLEEP)
        url = MOVIE_ENDPOINT.format(movie_id=movie_id)
        start_t = time.perf_counter()
        now_utc = datetime.now(timezone.utc).isoformat()

        try:
            resp = self._fetch_with_backoff(url)
            elapsed_ms = (time.perf_counter() - start_t) * 1000

            if resp.status_code == 200:
                data = resp.json()
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                self._log_manifest(movie_id, "movie_details", 200, "network", now_utc, elapsed_ms)
                return data, "network", 200
            elif resp.status_code == 404:
                self._cache_dead_id(movie_id)
                self._log_manifest(movie_id, "movie_details", 404, "network", now_utc, elapsed_ms, "Not Found")
                return None, "network", 404
            else:
                self._log_manifest(movie_id, "movie_details", resp.status_code, "network", now_utc, elapsed_ms, resp.text[:100])
                return None, "network", resp.status_code
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            self._log_manifest(movie_id, "movie_details", None, "network", now_utc, elapsed_ms, str(e))
            raise

    def get_movie_credits(self, movie_id: int) -> Tuple[Optional[Dict[str, Any]], str, Optional[int]]:
        cache_file = self.raw_dir / f"credits_{movie_id}.json"

        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, timezone.utc).isoformat()
            self._log_manifest(movie_id, "movie_credits", 200, "cache", mtime, 0.0)
            return data, "cache", 200

        time.sleep(RATE_LIMIT_SLEEP)
        url = CREDITS_ENDPOINT.format(movie_id=movie_id)
        start_t = time.perf_counter()
        now_utc = datetime.now(timezone.utc).isoformat()

        try:
            resp = self._fetch_with_backoff(url)
            elapsed_ms = (time.perf_counter() - start_t) * 1000

            if resp.status_code == 200:
                data = resp.json()
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                self._log_manifest(movie_id, "movie_credits", 200, "network", now_utc, elapsed_ms)
                return data, "network", 200
            elif resp.status_code == 404:
                self._log_manifest(movie_id, "movie_credits", 404, "network", now_utc, elapsed_ms, "Not Found")
                return None, "network", 404
            else:
                self._log_manifest(movie_id, "movie_credits", resp.status_code, "network", now_utc, elapsed_ms, resp.text[:100])
                return None, "network", resp.status_code
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            self._log_manifest(movie_id, "movie_credits", None, "network", now_utc, elapsed_ms, str(e))
            raise

    def resolve_imdb_id(self, imdb_id: str) -> Optional[int]:
        time.sleep(RATE_LIMIT_SLEEP)
        url = FIND_ENDPOINT.format(external_id=imdb_id)
        try:
            resp = self._fetch_with_backoff(url, params={"external_source": "imdb_id"})
            if resp.status_code == 200:
                data = resp.json()
                movie_results = data.get("movie_results", [])
                if movie_results:
                    return movie_results[0].get("id")
        except Exception:
            pass
        return None

    def extract_all(
        self,
        valid_ids: List[int]
    ) -> Tuple[Dict[int, Dict[str, Any]], List[int], Dict[str, int]]:
        movies_dict = {}
        dead_ids = []
        stats = {"network_calls": 0, "cache_hits": 0, "404_count": 0}

        for movie_id in valid_ids:
            details, d_src, d_status = self.get_movie_details(movie_id)
            if d_status == 404 or details is None:
                dead_ids.append(movie_id)
                stats["404_count"] += 1
                if d_src == "network":
                    stats["network_calls"] += 1
                else:
                    stats["cache_hits"] += 1
                continue

            credits_data, c_src, c_status = self.get_movie_credits(movie_id)

            if d_src == "network":
                stats["network_calls"] += 1
            else:
                stats["cache_hits"] += 1

            if c_src == "network":
                stats["network_calls"] += 1
            else:
                stats["cache_hits"] += 1

            movies_dict[movie_id] = {
                "details": details,
                "credits": credits_data or {"cast": [], "crew": []}
            }

        return movies_dict, dead_ids, stats


def fetch_tmdb_catalog_with_polite_caching(
    valid_numeric_ids: List[int],
    raw_dir: Path = RAW_DIR,
    manifest_path: Path = MANIFEST_PATH
) -> Tuple[Dict[int, Dict[str, Any]], List[int], Dict[str, int]]:
    extractor = TMDBExtractor(raw_dir=raw_dir, manifest_path=manifest_path)
    return extractor.extract_all(valid_numeric_ids)
