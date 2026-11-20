# Data findings — StreamVault Content Acquisition

## Summary
An exhaustive audit of the 127 candidate film identifiers provided for StreamVault's \$14M content acquisition review revealed severe data hygiene issues across all historical intake streams. The candidate list contained missing records, invalid data types, duplicate entries, foreign platform identifiers, and permanently deprecated titles. Following systematic validation, deduplication, and verification against live data systems, exactly 112 titles were verified and incorporated into the analytical baseline. Every single identifier from the original 127 records is fully accounted for.

---

## Reconciliation

| Stage | Rows | Delta | Reason |
|---|---|---|---|
| 1. Raw Candidate CSV Input | 127 | 0 | Initial candidate list assembled over four years from Adjoa's tracker, predecessor spreadsheet, and studio licensing emails. |
| 2. Ingestion Format Validation | 124 | -3 | Dynamically excluded blank row at line 69, negative identifier `-1` at line 30, and literal text `'N/A'` at line 111. |
| 3. External Identifier Harmonization | 123 | -1 | IMDb identifier `tt0468569` at line 95 resolved to TMDb ID `155` (*The Dark Knight*), which is already present on line 2. |
| 4. Exact Deduplication | 117 | -6 | Removed exact repeated movie IDs: `603` (line 43), `278` (line 60), `1891` (line 90), `155` (line 91), `550` (line 94), `680` (line 102). |
| 5. Live System Resolution (404s) | 112 | -5 | Live catalog returned 404 Not Found for five deprecated IDs (`7733901`, `8471293`, `8471294`, `9412887`, `9412888`). |
| 6. Final Analytical Baseline | 112 | 0 | Validated analytical dataset strictly enforced at one row per film. |

---

## Mapping Findings to the 5-Station Factory Line

The anomalies discovered map directly into the defensive stations of the StreamVault factory line (`h3lp/mathematical_formulation_of_the_streamvault_pipeline.md`):

1. **Station 1: The Bouncer (`pipeline/extract.py`)**: Intercepts **F-01** (routes 404s to `dead_ids.json`), **F-02** (dynamically catches blank rows, negative values, and text), **F-03** (resolves IMDb IDs), and **F-04** (drops duplicate admission passes).
2. **Station 2: The Labeler (`pipeline/transform.py`)**: Unpacks nested JSON into 3 distinct relational grains (`films`, `cast`, `crew`), mathematically preventing a catastrophic \$4.7 Trillion revenue fan-out.
3. **Station 3: The Quality Filter (`pipeline/transform.py`)**: Parameterizes \$0 money handling and slices the portfolio across both era windows (All-Years vs. 2000-Onward).
4. **Station 4: The Scorekeeper (`pipeline/transform.py`)**: Neutralizes **F-05** (extreme outliers like *Avengers: Endgame*) by emphasizing median returns over skewed arithmetic means.
5. **Station 5: The Talent Scout (`pipeline/transform.py`)**: Filters out lucky one-hit wonders using the fairness rule (minimum $\ge 2$ appearances) before recommending director and actor levers.

---

## Findings, ranked by risk

### F-01: Deprecated Identifiers (404 Not Found) — Severity: High
- **What it is:** Five identifiers (`7733901`, `8471293`, `8471294`, `9412887`, `9412888`) generated HTTP 404 Not Found errors during live catalog acquisition.
- **How I detected it:** Monitored HTTP status codes during data extraction in `pipeline/extract.py` with explicit branching on `404` rather than letting network calls raise unhandled exceptions.
- **Scale:** 5 out of 127 identifiers (3.9% of candidate list).
- **Effect on the client's number:** These titles represent lost opportunities from older intake spreadsheets. If these 5 films were major commercial drivers, their omission could theoretically bias the portfolio. However, since they no longer exist in the system of record, they cannot be licensed under these IDs.
- **What I did about it:** Recorded all 5 IDs in the permanent Missing Box (`data/raw/dead_ids.json`) and `manifest.csv`, logged their exclusion, and omitted them from downstream calculations without halting pipeline execution.
- **Residual risk:** If any of these titles was a specific priority target for Kwame, the licensing desk must request updated system IDs from the selling studio.

### F-02: Format Invalidation & Dynamic Empty Row Detection — Severity: Medium
- **What it is:** Line 69 of `id_list.csv` was completely blank. Line 30 contained `-1`, and line 111 contained the text string `'N/A'`.
- **How I detected it:** Programmatic line-by-line inspection scanning for `not trimmed`, attempting integer parsing, and enforcing positive domain rules without hardcoding line numbers.
- **Scale:** 3 of 127 lines (2.4%).
- **Effect on the client's number:** A naive loader would either crash on blank lines or silently drop rows without logging, leaving Kwame unable to explain why his candidate count changed from 127 to 124.
- **What I did about it:** Implemented a dynamic door auditor in `pipeline/extract.py` that records the exact line number, raw string, and failure reason.
- **Residual risk:** Zero residual risk to calculations; 100% accounted for in reconciliation.

### F-03: External IMDb Identifier Formatting — Severity: Medium
- **What it is:** Line 95 contained an IMDb title identifier (`tt0468569`) rather than a numeric TMDb ID.
- **How I detected it:** String prefix pattern detection matching `tt\d+`.
- **Scale:** 1 of 127 lines (0.8%).
- **Effect on the client's number:** If ignored, *The Dark Knight* would have been dropped from the analysis, underrepresenting franchise performance.
- **What I did about it:** Queried the external ID resolution endpoint in `pipeline/extract.py`, confirming `tt0468569` maps to TMDb ID `155` (*The Dark Knight*). Because ID `155` was already present on line 2, line 95 was identified as a cross-system semantic duplicate.
- **Residual risk:** None. Confirmed *The Dark Knight* is included in the analytical baseline.

### F-04: Candidate ID Duplication — Severity: Medium
- **What it is:** Six movie IDs were entered twice in the candidate list: `155` (*The Dark Knight*), `278` (*The Shawshank Redemption*), `550` (*Fight Club*), `603` (*The Matrix*), `680` (*Pulp Fiction*), and `1891` (*The Empire Strikes Back*).
- **How I detected it:** Uniqueness assertions using a tracking set `seen_ids` in `pipeline/extract.py`.
- **Scale:** 6 duplicate occurrences out of 127 rows (4.7%).
- **Effect on the client's number:** If duplicates were retained, high-performing titles would be counted twice, artificially inflating both franchise and standalone total revenues and skewing mean ROI upward.
- **What I did about it:** Deduplicated the ID list at ingestion, preserving the first instance and logging subsequent duplicates in the audit registry.
- **Residual risk:** None. The unique catalog accurately reflects 112 unique films.

### F-05: Skewness from Extreme Revenue Outliers — Severity: Low
- **What it is:** *The Avengers* (\$1.52B), *Avengers: Infinity War* (\$2.05B), and *Avengers: Endgame* (\$2.80B) represent extreme positive outliers on box office gross.
- **How I detected it:** Interquartile range (IQR) distribution profiling where values exceeded $Q3 + 1.5 \times IQR$ in `pipeline/checks.py`.
- **Scale:** 3 blockbuster titles in the franchise group.
- **Effect on the client's number:** While the mean franchise return is 8.54x, the median is 5.62x. Relying on the mean would overstate expected returns for typical franchise acquisitions.
- **What I did about it:** Reported median return multiples alongside means in all business recommendations to ensure decisions are robust against outlier distortion.
- **Residual risk:** Low. The median provides an honest, achievable performance baseline.

---

## Looked wrong, is not wrong

| Apparent problem | Why it looks wrong | Why it is actually fine |
|---|---|---|
| Zero \$0 Revenue for 112 Acquired Titles | Most movie datasets suffer from missing or \$0 box office figures. | The 112 successfully acquired titles in this specific candidate list represent major theatrical releases where TMDb holds complete, verified worldwide box office and budget records. |
| Standalone Titles Outscore Franchises on Ratings (8.37 vs 7.46) | If franchises generate higher box office, one might expect higher audience review scores. | Standalone titles in this list (*The Shawshank Redemption*, *Pulp Fiction*, *Schindler's List*, *Spirited Away*) are universally acclaimed critical masterpieces, whereas franchise bundles include mid-tier sequels that dilute average ratings despite strong box office. |
| Franchise Revenue Volatility (Min \$104M to Max \$2.8B) | Large spread between the lowest-grossing sequel and top-tier blockbuster. | Commercial reality of studio film series; audience demand varies across sequels, which reinforces the necessity of negotiating bundle discounts rather than paying peak rates for middle entries. |

---

## Could not verify
- **Actual Studio Asking Prices**: TMDb records historical production budgets and worldwide box office grosses, but does not publish current licensing rights costs demanded by distributors. Recommended allocations assume licensing fees scale proportionately with historical commercial value.
- **Regional Streaming Rights Availability**: Certain titles (e.g. older catalogue entries from Warner Bros or Disney) may have active exclusivity windows with competing streaming platforms that cannot be verified via public API data. Kwame's negotiating team must confirm territory clearance with distributors before signing deal memos.
