# Data findings — StreamVault Content Acquisition

## Summary
An exhaustive audit of the 127 candidate film identifiers provided for StreamVault's $14M content acquisition review revealed severe data hygiene issues across all historical intake streams. The candidate list contained missing records, invalid data types, duplicate entries, foreign platform identifiers, and permanently deprecated titles. Following systematic validation, deduplication, and verification against live data systems, exactly 112 titles were verified and incorporated into the analytical baseline. Every single identifier from the original 127 records is fully accounted for.

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
2. **Station 2: The Labeler (`pipeline/transform.py`)**: Unpacks nested JSON into 3 distinct relational grains (`films`, `cast`, `crew`), mathematically preventing a catastrophic $4.7 Trillion revenue fan-out.
3. **Station 3: The Quality Filter (`pipeline/transform.py`)**: Parameterizes $0 money handling and slices the portfolio across both era windows (All-Years vs. 2000-Onward).
4. **Station 4: The Scorekeeper (`pipeline/transform.py`)**: Neutralizes **F-05** (extreme outliers like *Avengers: Endgame*) by emphasizing median returns over skewed arithmetic means.
5. **Station 5: The Talent Scout (`pipeline/transform.py`)**: Filters out lucky one-hit wonders using the fairness rule (minimum >= 2 appearances) before recommending director and actor levers.

---

## Findings, ranked by risk to Kwame's decision

### Rank 1 (Critical Risk) — Partial Franchise Bundles in the Candidate List
- **What it is:** Studios license franchises on an all-or-nothing basis (e.g. license the entire series or none). However, the stitched-together candidate list contains only partial subsets of several major franchises: e.g., only 1 *Jaws* film (out of 4), 4 *Terminator* films (out of 6), 3 *Jurassic Park* films (missing *Jurassic World* entries), and 4 *Alien* films (out of 6+).
- **How I detected it:** Cross-referenced candidate film counts against TMDb `belongs_to_collection` identifiers in `pipeline/transform.py` (`rank_franchise_bundles`).
- **Scale:** 9 franchise collections on the candidate list represent incomplete subsets.
- **Effect on the client's number:** Evaluating an incomplete franchise on only its legacy hits hides weak, expensive sequels. If Kwame agrees to a bundle price based on *Jaws 1* (19x ROI), but the distributor forces StreamVault to take the disastrous sequels (*Jaws 2*, *Jaws 3-D*, *Jaws: The Revenge*), StreamVault severely overpays. Conversely, our top recommended targets (*Harry Potter* [8 films], *The Dark Knight* [3 films], *The Lord of the Rings* [3 films]) are complete collections on the list where every single installment has been evaluated.
- **What I did about it:** Built whole-bundle rollups measuring both total collection return and the `min_roi` (weakest-link floor). Advised Kwame to restrict upfront bundle bids to complete series and demand a complete title list before pricing partial franchises.
- **Residual risk:** If studios insist on including unlisted modern sequels in negotiation packages, Adjoa must drop the updated IDs into the pipeline to recalculate whole-bundle economics.

### Rank 2 (High Risk) — Zero-Value Financial Fields ($0 Budget / $0 Revenue)
- **What it is:** In TMDb, unrecorded budgets and revenues appear as `$0` rather than `null`. A naive calculation of `Revenue / Budget` produces division-by-zero errors or falsely scores unrecorded titles as complete commercial failures (`0.0x`).
- **How I detected it:** Automated profiling in `pipeline/checks.py` scanning for `revenue == 0` and `budget == 0`.
- **Scale:** In our verified 112 titles, exactly **0 titles reported $0 revenue** and **0 titles reported $0 budget** (all 112 are major theatrical releases with complete reporting). However, on next year's 500-title list, unrecorded titles will inevitably appear.
- **Effect on the client's number:** Treating missing figures as real zeros would artificially drag down standalone averages and distort ROI comparisons.
- **What I did about it:** Implemented `filter_reliable_financials` in `pipeline/transform.py`, parameterizing `$0` handling (`treat_zero_revenue_as_missing = True`) to exclude unrecorded titles from financial return metrics without dropping them from catalog totals.
- **Residual risk:** None. Transparently auditable under both assumptions.

### Rank 3 (Medium Risk) — Duplicate & Malformed IDs from Merged Trackers
- **What it is:** Merging three legacy spreadsheets introduced 15 administrative errors:
  - 1 completely blank row (line 69).
  - 1 negative identifier (`-1` on line 30).
  - 1 literal text placeholder (`'N/A'` on line 111).
  - 1 external IMDb identifier (`tt0468569` on line 95, resolving to duplicate ID `155`).
  - 6 exact duplicate submissions (`155`, `278`, `550`, `603`, `680`, `1891`).
  - 5 deprecated IDs returning live HTTP 404 Not Found (`7733901`, `8471293`, `8471294`, `9412887`, `9412888`).
- **How I detected it:** Dynamic line-by-line inspection in `pipeline/extract.py` and persistent logging in `data/raw/dead_ids.json`.
- **Scale:** 15 of 127 candidate rows (11.8%).
- **Effect on the client's number:** Naive loaders would either crash on line 69 or silently drop rows, leaving Kwame unable to explain why his candidate count fell from 127 to 112. Retaining duplicates would artificially inflate box office totals by double-counting blockbusters.
- **What I did about it:** Built a dynamic bouncer and permanent Missing Box. Guaranteed 100% mathematical reconciliation: `127 Input IDs = 112 Valid Baseline + 10 Excluded at Door + 5 Live 404s`.
- **Residual risk:** Zero residual risk to calculations; 100% accounted for in reconciliation.

### Rank 4 (Contextual Risk) — Unadjusted Historical Dollars & Extreme Outliers
- **What it is:** Pre-2000 theatrical gross is unadjusted for ticket inflation, and multi-billion-dollar blockbusters (*Avengers: Endgame* at $2.80B, *Avengers: Infinity War* at $2.05B) skew arithmetic means upward.
- **How I detected it:** IQR distribution fences in `pipeline/checks.py` and era segmentation in `pipeline/transform.py`.
- **Scale:** Outlier fence threshold at $1.73B; 41 pre-2000 titles vs 71 post-2000 titles.
- **Effect on the client's number:** Relying on arithmetic means overstates expected returns ($8.54x mean vs $5.62x median for franchises). Over-indexing on pre-2000 classics invites immediate rejection from Finance VP Yaw.
- **What I did about it:** Anchored all business recommendations in median returns, and evaluated all portfolio KPIs across both time windows (All-Years vs. 2000-Onward), proving the franchise recommendation never flips ($5.05x vs $3.84x in the modern era).
- **Residual risk:** Low. The median provides an honest, achievable performance baseline.

---

## Looked wrong, is not wrong

| Apparent problem | Why it looks wrong | Why it is actually fine |
|---|---|---|
| Zero $0 Revenue for 112 Acquired Titles | Most movie datasets suffer from missing or $0 box office figures. | The 112 successfully acquired titles in this specific candidate list represent major theatrical releases where TMDb holds complete, verified worldwide box office and budget records. |
| Standalone Titles Outscore Franchises on Ratings (8.37 vs 7.46) | If franchises generate higher box office, one might expect higher audience review scores. | Standalone titles in this list (*The Shawshank Redemption*, *Pulp Fiction*, *Schindler's List*, *Spirited Away*) are universally acclaimed critical masterpieces, whereas franchise bundles include mid-tier sequels that dilute average ratings despite strong box office. |
| Franchise Revenue Volatility (Min $104M to Max $2.8B) | Large spread between the lowest-grossing sequel and top-tier blockbuster. | Commercial reality of studio film series; audience demand varies across sequels, which reinforces the necessity of negotiating bundle discounts rather than paying peak rates for middle entries. |

---

## Could not verify
- **Actual Studio Asking Prices**: TMDb records historical production budgets and worldwide box office grosses, but does not publish current licensing rights costs demanded by distributors. Recommended allocations assume licensing fees scale proportionately with historical commercial value.
- **Regional Streaming Rights Availability**: Certain titles (e.g. older catalogue entries from Warner Bros or Disney) may have active exclusivity windows with competing streaming platforms that cannot be verified via public API data. Kwame's negotiating team must confirm territory clearance with distributors before signing deal memos.
