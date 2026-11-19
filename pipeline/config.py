"""
Configuration module for StreamVault Licensing Analysis Pipeline.
Handles environment variables, endpoints, timeouts, and project file paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load local environment variables from .env
load_dotenv(PROJECT_ROOT / ".env")

# TMDb API Authentication
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_API_READ_ACCESS_TOKEN = os.getenv("TMDB_API_READ_ACCESS_TOKEN", "")

# TMDb Endpoints
TMDB_BASE_URL = "https://api.themoviedb.org/3"
MOVIE_ENDPOINT = f"{TMDB_BASE_URL}/movie/{{movie_id}}"
CREDITS_ENDPOINT = f"{TMDB_BASE_URL}/movie/{{movie_id}}/credits"
FIND_ENDPOINT = f"{TMDB_BASE_URL}/find/{{external_id}}"

# Network & Polite API Constants (per learning path rules)
REQUEST_TIMEOUT = (3.05, 10)  # (connect timeout, read timeout) in seconds
USER_AGENT = "StreamVault-Licensing-Analysis/1.0 (AmaliTech DE02; Samuel Quaigraine)"
RATE_LIMIT_SLEEP = 0.05  # Polite delay between live API network calls

# File Paths
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"
ID_LIST_PATH = PROJECT_ROOT / "id_list.csv"
MANIFEST_PATH = DATA_DIR / "manifest.csv"

# Analysis Parameters
ERA_CUTOFF_YEAR = 2000
TOTAL_ACQUISITION_BUDGET = 14_000_000.0  # $14M licensing budget
