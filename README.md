# StreamVault Licensing Analysis

## Overview
This repository contains the data ingestion, analysis, and decision framework for StreamVault's $14M content acquisition licensing review. The analysis evaluates candidate films using the TMDb API to provide data-driven recommendations on acquiring franchise bundles versus standalone titles.

## Project Structure
- `id_list.csv`: Candidate movie IDs provided for evaluation
- `.example.env`: Example environment variables template
- `requirements.txt`: Project Python dependencies
- `.gitattributes`: Git attribute configurations for line ending consistency
- `.gitignore`: Files and directories ignored by Git

## Getting Started

### Prerequisites
- Python 3.11+
- Git

### Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd streamvault_licensing_analysis_samuel_quaigraine
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell
   .venv\Scripts\Activate.ps1
   # macOS/Linux
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   Copy `.example.env` to `.env` and fill in your TMDb API credentials:
   ```bash
   cp .example.env .env
   ```
   Add your TMDb API Key and Read Access Token in `.env`.

## Data Protection & Secrets
Never commit `.env` or any sensitive API keys to version control. Keep credentials secured within local environment variables.
