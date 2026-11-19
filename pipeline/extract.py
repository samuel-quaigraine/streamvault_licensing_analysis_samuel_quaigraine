"""
Data acquisition module for TMDb API.
Implements polite API access: disk caching, session re-use, explicit timeouts,
rate limiting, exponential backoff, 404 tracking without crashing, and manifest logging.
"""

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Dict, List, Optional, Set, Tuple, Any
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
)


class TMDBExtractor:
    """
    Handles rate-limited, cached HTTP requests to TMDb.
    Ensures network efficiency, offline execution, and complete audit logging.
    """

    def __init__(self, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH):
        # ======================================================================
        # BLOCK: Initialize Directories & Network Session
        # What it does: Creates raw storage folders, sets up an HTTP session with
        # standard user-agent headers and authentication token if available.
        # ======================================================================
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
        """
        BLOCK: Load Cached Dead 404 IDs
        What it does: Reads the list of known non-existent IDs from disk so we
        never waste time or network bandwidth re-querying dead records.
        """
        if self.dead_ids_file.exists():
            try:
                with open(self.dead_ids_file, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception:
                return set()
        return set()

    def _cache_dead_id(self, movie_id: int) -> None:
        """
        BLOCK: Save Dead ID to Cache
        What it does: Records a confirmed 404 ID to dead_ids.json so future
        pipeline runs know immediately that this title does not exist.
        """
        dead_ids = self._get_cached_dead_ids()
        dead_ids.add(movie_id)
        with open(self.dead_ids_file, "w", encoding="utf-8") as f:
            json.dump(sorted(list(dead_ids)), f, indent=2)

    def _init_manifest(self) -> None:
        """
        BLOCK: Manifest CSV Initialization
        What it does: Creates the audit trail file (manifest.csv) with standard
        column headers if it does not already exist.
        """
        if not self.manifest_path.exists():
            with open(self.manifest_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "item_id",
                    "endpoint_type",
                    "status_code",
                    "source",
                    "timestamp_utc",
                    "elapsed_ms",
                    "error_message"
                ])

    def _log_manifest(
        self,
        item_id: Any,
        endpoint_type: str,
        status_code: Optional[int],
        source: str,
        timestamp_utc: str,
        elapsed_ms: float,
        error_message: str = ""
    ) -> None:
        """
        BLOCK: Manifest Logger
        What it does: Records every single data request (whether served from local
        cache or live network) with timing, status code, and timestamp.
        """
        with open(self.manifest_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                item_id,
                endpoint_type,
                status_code if status_code is not None else "",
                source,
                timestamp_utc,
                f"{elapsed_ms:.2f}",
                error_message
            ])

    def _fetch_with_backoff(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> requests.Response:
        """
        BLOCK: Polite HTTP Request with Exponential Backoff
        What it does: Sends HTTP requests to TMDb. If TMDb returns rate limit (429)
        or temporary server errors (500/502/503/504), it waits and retries safely.
        """
        attempt = 0
        current_params = dict(params or {})
        # If no bearer token header, attach query parameter API key
        if TMDB_API_KEY and "Authorization" not in self.session.headers:
            current_params["api_key"] = TMDB_API_KEY
        elif TMDB_API_KEY and "api_key" not in current_params:
            current_params["api_key"] = TMDB_API_KEY

        while attempt < max_retries:
            attempt += 1
            try:
                resp = self.session.get(url, params=current_params, timeout=REQUEST_TIMEOUT)
                
                # If rate limited, respect Retry-After header or backoff exponentially
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    sleep_time = int(retry_after) if retry_after and retry_after.isdigit() else (2 ** attempt)
                    time.sleep(sleep_time)
                    continue

                # If transient server hiccup, wait and retry
                if resp.status_code in (500, 502, 503, 504):
                    time.sleep(2 ** attempt)
                    continue

                return resp
            except (requests.ConnectionError, requests.Timeout):
                if attempt >= max_retries:
                    raise
                time.sleep(2 ** attempt)

        return resp

    def get_movie_details(self, movie_id: int) -> Tuple[Optional[Dict[str, Any]], str, Optional[int]]:
        """
        BLOCK: Fetch Movie Details
        What it does: Retrieves movie metadata (title, budget, revenue, release date).
        Checks local disk cache first; only calls live network if not cached.
        """
        # Step 1: Check if this ID is already known to be a dead 404 ID
        if movie_id in self._get_cached_dead_ids():
            return None, "cache", 404

        cache_file = self.raw_dir / f"movie_{movie_id}.json"
        
        # Step 2: Check local disk cache (fast, offline)
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc).isoformat()
            self._log_manifest(movie_id, "movie_details", 200, "cache", mtime, 0.0)
            return data, "cache", 200

        # Step 3: Fetch from live TMDb network (if not in cache)
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
                # Cache dead ID to avoid redundant future network calls
                self._cache_dead_id(movie_id)
                self._log_manifest(movie_id, "movie_details", 404, "network", now_utc, elapsed_ms, "404 Not Found")
                return None, "network", 404
            else:
                resp.raise_for_status()
                return None, "network", resp.status_code
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            self._log_manifest(movie_id, "movie_details", None, "network", now_utc, elapsed_ms, str(e))
            raise

    def get_movie_credits(self, movie_id: int) -> Tuple[Optional[Dict[str, Any]], str, Optional[int]]:
        """
        BLOCK: Fetch Movie Credits
        What it does: Retrieves cast and crew members for the movie.
        Checks local disk cache first before making any network call.
        """
        cache_file = self.raw_dir / f"credits_{movie_id}.json"
        
        # Step 1: Check local disk cache
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc).isoformat()
            self._log_manifest(movie_id, "movie_credits", 200, "cache", mtime, 0.0)
            return data, "cache", 200

        # Step 2: Fetch from live TMDb network
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
                self._log_manifest(movie_id, "movie_credits", 404, "network", now_utc, elapsed_ms, "404 Not Found")
                return None, "network", 404
            else:
                resp.raise_for_status()
                return None, "network", resp.status_code
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            self._log_manifest(movie_id, "movie_credits", None, "network", now_utc, elapsed_ms, str(e))
            raise

    def resolve_imdb_id(self, imdb_id: str) -> Optional[int]:
        """
        BLOCK: Resolve External IMDb Identifiers
        What it does: Calls TMDb's /find endpoint to convert an IMDb ID
        (e.g., 'tt0468569') into its corresponding TMDb movie integer ID (155).
        """
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
        """
        BLOCK: Extract All Movies in Batch
        What it does: Iterates over the list of valid candidate IDs, fetches details
        and credits for each, tracks 404s, and records network vs cache statistics.
        """
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
