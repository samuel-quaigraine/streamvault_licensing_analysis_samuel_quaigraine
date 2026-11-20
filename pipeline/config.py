"""
Configuration module for StreamVault Licensing Analysis Pipeline.
Sets the global parameters, thresholds, and file paths across the 5 pipeline stations.

Aligned with course lessons from @materials-learning:
- "Working inside a time budget"
- "Not hammering a free API"
- "Judging a cleaning decision by its impact"
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ==============================================================================
# SECTION: Base Workspace Paths
# Course concept: Predictable project layout enabling reproducible runs
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load confidential credentials from .env without hardcoding secrets in source code
load_dotenv(PROJECT_ROOT / ".env")

# ==============================================================================
# SECTION: TMDb API Credentials & Endpoints
# Course concept: REST API Calls for Data Engineers
# ==============================================================================
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_API_READ_ACCESS_TOKEN = os.getenv("TMDB_API_READ_ACCESS_TOKEN", "")

TMDB_BASE_URL = "https://api.themoviedb.org/3"
MOVIE_ENDPOINT = f"{TMDB_BASE_URL}/movie/{{movie_id}}"
CREDITS_ENDPOINT = f"{TMDB_BASE_URL}/movie/{{movie_id}}/credits"
FIND_ENDPOINT = f"{TMDB_BASE_URL}/find/{{external_id}}"

# ==============================================================================
# SECTION: Network Pacing & Timeouts
# Lesson: "Not hammering a free API" & "Pagination, rate limits and backoff"
# Rule: Connect fast, read with patience, sleep between calls, identify yourself.
# ==============================================================================
REQUEST_TIMEOUT = (3.05, 10)  # (3.05s connect timeout, 10s socket read timeout)
USER_AGENT = "StreamVault-Licensing-Analysis/1.0 (AmaliTech DE02; Samuel Quaigraine)"
RATE_LIMIT_SLEEP = 0.05  # Polite pause (50ms) between live requests to avoid 429 rate limits

# ==============================================================================
# SECTION: Storage Directories
# Lesson: "pandas_ How to Read and Write Files"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"
ID_LIST_PATH = PROJECT_ROOT / "id_list.csv"
MANIFEST_PATH = DATA_DIR / "manifest.csv"

# Automatically ensure all necessary directories exist on any OS / environment
for directory in (DATA_DIR, RAW_DIR, PROCESSED_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# SECTION: 5-Station Factory Line Parameters & Business Rules
# Formulated in h3lp/mathematical_formulation_of_the_streamvault_pipeline.md
# ==============================================================================

# Station 1: The Bouncer (Candidate Validation & Ingestion)
TOTAL_RAW_CANDIDATE_ROWS = 127
MAX_ACCEPTABLE_QUARANTINE_SHARE = 0.15  # Up to 15% missing/dropped rows before raising QA alert

# Station 2: The Labeler (Collection & Grain Rules)
# A collection with >= 1 titles in our candidate list is analyzed for bundle viability

# Station 3: The Quality Filter (Time Windows & Missing Financials)
# Lesson: "Missing data" & "Judging a cleaning decision by its impact"
ERA_CUTOFF_YEAR = 2000
TREAT_ZERO_REVENUE_AS_MISSING = True

# Station 4: The Scorekeeper (Financial Evaluation & Licensing Budget)
COMMERCIAL_HIT_THRESHOLD = 2.5       # Return on Cost >= 2.5x indicates commercial hit
COMMERCIAL_MODERATE_THRESHOLD = 1.0  # Return on Cost >= 1.0x indicates breakeven
TOTAL_ACQUISITION_BUDGET = 14_000_000.0  # Kwame's $14M licensing budget

# Station 5: The Talent Scout (Director & Lead Actor Evaluation)
# Lesson: "GroupBy and aggregation for KPIs"
# Fairness rule: Only rank talent with at least 2 titles on our list to avoid 1-hit wonder bias
MIN_TALENT_APPEARANCES = 2
LEAD_ACTOR_ORDER_LIMIT = 2  # Top 3 billed cast members (cast_order 0, 1, 2)
