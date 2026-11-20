# ADR-004: Two-Window Era Segmentation (All-Years vs. 2000-Onward)

- **Status:** Accepted
- **Date:** 2026-10-31
- **Decision owner:** Samuel Quaigraine

## Context
Finance VP Yaw strongly distrusts pre-2000 theatrical data due to historical inflation, currency exchange variability, and differences in legacy box office reporting standards. Conversely, half of Kwame's acquisitions team believes older evergreen classics (*Star Wars*, *The Godfather*, *Pulp Fiction*) offer immense return-on-cost value that modern big-budget films cannot match. Suppressing the pre-2000 data or failing to present both perspectives would cause the board review to derail over methodological disagreements.

## Decision
I implemented dual-window KPI evaluation across the entire analytical model (`score_licensing_options` in `pipeline/transform.py` under Station 4: The Scorekeeper):
1. **Window 1: All-Years Baseline** (112 titles: 96 Franchises, 16 Standalones).
2. **Window 2: 2000-Onward Baseline** (71 titles: 63 Franchises, 8 Standalones).
The pipeline evaluates whether the core strategic recommendation (Franchise Bundles vs. Standalone Titles) holds across both windows or flips, and reports the findings prominently.

## Alternatives considered

### Alternative A: Report only 2000-Onward data to appease Finance
- **How it would work:** Filter out all films released before January 1, 2000 prior to analysis.
- **Why it is attractive:** Avoids arguments with Yaw about inflation and currency adjustments.
- **Why rejected:** Drops 41 titles (36.6% of verified catalog), including iconic franchise anchors like the original *Star Wars* trilogy and top-tier standalones like *Pulp Fiction* and *The Shawshank Redemption*.

### Alternative B: Report only All-Years data and add a footnote for Finance
- **How it would work:** Aggregate all titles and add a small disclaimer about pre-2000 inflation.
- **Why it is attractive:** Simple single-table presentation.
- **Why rejected:** The brief explicitly warns that footnoting an era disagreement is fatal. Yaw will challenge the numbers in the room unless his time window is addressed head-on.

## Consequences
- **What this buys:** Total defensibility and consensus in the board room:
  - In **All-Years**: Franchise median return is **5.62x** vs. Standalone **3.84x** (Franchise leads by +1.78x).
  - In **2000-Onward**: Franchise median return is **5.05x** vs. Standalone **3.84x** (Franchise leads by +1.21x).
  - **Critical Finding:** The strategic recommendation **does not flip**. Franchises win on capital efficiency and commercial volume in both windows, completely defusing Yaw's objection before he speaks.
- **What this costs:** Requires presenting dual tables for portfolio totals, budgets, and hit rates.
- **What it costs the client if I am wrong:** If pre-2000 consumer demand does not translate to streaming viewer hours, overpaying for older catalog titles would waste capital. However, because we provide the 2000-onward filter, Kwame can negotiate exclusively from post-2000 data if the board demands it.
- **What would make me revisit this:** If internal StreamVault telemetry demonstrates that subscribers exclusively stream content released within the last 10 years.

## What this survives
This decision survives Adjoa rerunning the pipeline next year: the cutoff year is parameterized, allowing her to test any cutoff year (e.g., 2005 or 2010) on the fly using `streamvault_tool.py --sensitivity`.
