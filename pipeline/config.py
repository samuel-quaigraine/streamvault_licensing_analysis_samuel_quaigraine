"""
Configuration module for StreamVault Licensing Analysis Pipeline.
Handles environment variables, endpoints, timeouts, and project file paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ==============================================================================
# BLOCK: Project Base Directory
# What it does: Calculates the absolute path of the project folder so that all
# file paths work reliably across any operating system (Windows, Mac, or Linux).
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ==============================================================================
# BLOCK: Load Environment Variables
# What it does: Reads confidential API credentials from the local .env file.
# Why: Keeps private API keys out of source code and version control.
# ==============================================================================
load_dotenv(PROJECT_ROOT / ".env")

# ==============================================================================
# BLOCK: TMDb API Credentials
# What it does: Retrieves the TMDb API key and Read Access Token from the environment.
# ==============================================================================
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_API_READ_ACCESS_TOKEN = os.getenv("TMDB_API_READ_ACCESS_TOKEN", "")

# ==============================================================================
# BLOCK: TMDb API Endpoints
# What it does: Defines the web addresses used to fetch movie details, credits,
# and external ID lookups (like IMDb IDs) from TMDb.
# ==============================================================================
TMDB_BASE_URL = "https://api.themoviedb.org/3"
MOVIE_ENDPOINT = f"{TMDB_BASE_URL}/movie/{{movie_id}}"
CREDITS_ENDPOINT = f"{TMDB_BASE_URL}/movie/{{movie_id}}/credits"
FIND_ENDPOINT = f"{TMDB_BASE_URL}/find/{{external_id}}"

# ==============================================================================
# BLOCK: Polite Network Settings & Timeouts
# What it does: Configures connection limits and delays so our pipeline runs politely
# without overwhelming TMDb servers or getting blocked.
# ==============================================================================
REQUEST_TIMEOUT = (3.05, 10)  # (3.05s connect timeout, 10s read timeout)
USER_AGENT = "StreamVault-Licensing-Analysis/1.0 (AmaliTech DE02; Samuel Quaigraine)"
RATE_LIMIT_SLEEP = 0.05  # Polite delay (in seconds) between live API requests

# ==============================================================================
# BLOCK: Project Folder Paths
# What it does: Sets the standard destination folders for raw cached data,
# processed tables, and final executive deliverable exports.
# ==============================================================================
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"
ID_LIST_PATH = PROJECT_ROOT / "id_list.csv"
MANIFEST_PATH = DATA_DIR / "manifest.csv"

# ==============================================================================
# BLOCK: Strategic Business Parameters
# What it does: Sets the cutoff year (2000) for testing Finance's skepticism,
# and the total $14 Million acquisition budget under review by Kwame Boateng.
# ==============================================================================
ERA_CUTOFF_YEAR = 2000
TOTAL_ACQUISITION_BUDGET = 14_000_000.0  # $14M licensing budget
