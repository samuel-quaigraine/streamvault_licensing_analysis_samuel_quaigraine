# StreamVault Data Diagnosis Methodology & Technical Reference

This directory provides the technical guide, code patterns, and execution scripts for the **Data Diagnosis** deliverable. It explains exactly how every flaw in the candidate dataset was detected, how each decision was evaluated, and how the complete 127-row reconciliation was proved.

---

## 1. Executive Context & Purpose

The brief defines data engineering not merely as computing numbers, but as deciding what the numbers should be, discovering what is wrong with the source, and defending both to a stakeholder whose job depends on the answer.

Kwame Boateng is entering a board review with $14M at stake. The candidate list (`id_list.csv`) was compiled over four years across three unverified sources:
1. Adjoa's evaluation tracker
2. An inherited spreadsheet from Kwame's predecessor
3. Ad-hoc batches emailed from studio licensing desks

Nobody had cleaned it. If our pipeline silently dropped rows or crashed on malformed inputs, Kwame would face immediate credibility failure when Finance questioned why candidate totals did not match.

---

## 2. How the Candidate List Ingestion & Reconciliation Was Done

The candidate file contains **127 rows** beneath the `tmdb_id` header. The ingestion engine in [`pipeline/load.py`](file:///c:/Users/SamuelQuaigraine/workspace2/streamvault_licensing_analysis_samuel_quaigraine/pipeline/load.py) audits every row sequentially using defensive parsing:

### A. Detecting the Blank Line 69
- **Problem**: Row 69 of `id_list.csv` contains zero characters (empty newline). A standard `int()` conversion raises `ValueError`, and naive loaders silently drop it.
- **Code to Detect**:
  ```python
  trimmed = raw_val.strip()
  if not trimmed:
      reason = "Empty row / missing identifier"
      records.append({
          "line_number": line_num,
          "raw_id": "<EMPTY>",
          "status": "EXCLUDED",
          "reason": reason
      })
  ```
- **Consequence**: Line 69 is explicitly logged in the audit trail as a format fault rather than a vanished record.

### B. Detecting Domain and Type Errors (`-1` and `'N/A'`)
- **Problem**: Line 30 contains `-1` (invalid negative ID), and Line 111 contains the string `'N/A'` (missing value marker).
- **Code to Detect**:
  ```python
  if trimmed.upper() in ("N/A", "NA", "NULL", "NONE"):
      # Log as missing string marker
      ...
  parsed_id = int(trimmed)
  if parsed_id < 0:
      # Log as domain error (negative identifier)
      ...
  ```
- **Consequence**: Both invalid entries are removed before hitting network endpoints, saving wasted API calls.

### C. Detecting and Harmonizing External IMDb Formats (`tt0468569`)
- **Problem**: Line 95 contained an alphanumeric string starting with `tt`, representing an IMDb title code rather than a numeric TMDb ID.
- **Code to Detect**:
  ```python
  if trimmed.startswith("tt"):
      # Query TMDb /find/{imdb_id}?external_source=imdb_id
      tmdb_id = ext.resolve_imdb_id(trimmed)
      # Resolved tt0468569 -> TMDb ID 155 (The Dark Knight)
  ```
- **Consequence**: Resolving `tt0468569` showed it is *The Dark Knight* (TMDb ID `155`). Because ID `155` was already present on Line 2, Line 95 was identified as a cross-system duplicate!

### D. Detecting the 6 Duplicate Identifiers
- **Problem**: Six movie IDs appeared twice: `155` (*The Dark Knight*), `278` (*The Shawshank Redemption*), `550` (*Fight Club*), `603` (*The Matrix*), `680` (*Pulp Fiction*), and `1891` (*The Empire Strikes Back*).
- **Code to Detect**:
  ```python
  if parsed_id in seen_ids:
      # Found duplicate occurrence
      records.append({
          "line_number": line_num,
          "raw_id": raw_val,
          "status": "DUPLICATE",
          "reason": f"Duplicate identifier of earlier entry ({parsed_id})"
      })
  else:
      seen_ids.add(parsed_id)
  ```
- **Consequence**: Deduplicating prevents counting top-tier blockbusters twice, which would have artificially inflated group revenues.

---

## 3. How Dead Identifiers (404 Not Found) Were Caught

During API acquisition in [`pipeline/extract.py`](file:///c:/Users/SamuelQuaigraine/workspace2/streamvault_licensing_analysis_samuel_quaigraine/pipeline/extract.py), five IDs failed to resolve on TMDb:
`[7733901, 8471293, 8471294, 9412887, 9412888]`

### Code Implementation:
```python
resp = session.get(f"https://api.themoviedb.org/3/movie/{movie_id}", timeout=(3.05, 10))
if resp.status_code == 404:
    # A 404 is a coverage fact, not an exception.
    # Record it, cache it, and do NOT retry.
    dead_ids.append(movie_id)
    self._cache_dead_id(movie_id)
else:
    resp.raise_for_status()
    records.append(resp.json())
```
- **Key Best Practice**: We cache 404 IDs into `data/raw/dead_ids.json`. A 404 is a permanent failure; requesting it repeatedly wastes bandwidth and slows the pipeline. Caching dead IDs allows subsequent runs to execute 100% offline from disk.

---

## 4. The 6-Stage Candidate Reconciliation Table

| Stage | Rows | Delta | Reason |
|---|---|---|---|
| **1. Raw CSV Ingestion** | **127** | 0 | Starting intake list from tracker, spreadsheet, and studio emails. |
| **2. Format Validation** | **124** | -3 | Line 69 was blank; line 30 was `-1`; line 111 was `'N/A'`. |
| **3. External Harmonization** | **123** | -1 | IMDb ID `tt0468569` (line 95) resolved to TMDb `155` (*The Dark Knight*, line 2). |
| **4. Exact Deduplication** | **117** | -6 | Removed duplicate IDs: `155`, `278`, `550`, `603`, `680`, `1891`. |
| **5. Live Catalog 404s** | **112** | -5 | Deprecated/obsolete IDs: `7733901`, `8471293`, `8471294`, `9412887`, `9412888`. |
| **6. Final Verified Catalog** | **112** | 0 | Verified analytical dataset strictly at one row per film. |

**Total Accounting**: 112 + 5 + 6 + 1 + 3 = 127 rows. Zero unaccounted gaps!

---

## 5. Exploratory Data Profiling & Outlier Mathematics

Data profiling was executed in [`pipeline/checks.py`](file:///c:/Users/SamuelQuaigraine/workspace2/streamvault_licensing_analysis_samuel_quaigraine/pipeline/checks.py) to inspect distributions and detect disguised nulls.

### Disguised Nulls ($0 Revenue & Budget)
In film datasets, unrecorded box office often appears as $0.00 rather than `NaN`.
- In our verified 112 titles, exactly **0 films reported $0 revenue** and **0 films reported $0 budget**.
- All 112 verified titles represent major theatrical releases with complete financial reporting.

### Outlier Detection (Interquartile Range Rule)
We used the standard Tukey Boxplot method:
- `IQR = Q3 - Q1`
- `Upper Fence = Q3 + (1.5 * IQR)`
- `Extreme Fence = Q3 + (3.0 * IQR)`

For worldwide gross:
- Q1 (25th Percentile): **$338.4 Million**
- Q2 (Median): **$535.8 Million**
- Q3 (75th Percentile): **$895.9 Million**
- IQR: **$557.5 Million**
- Upper Outlier Fence: `$895.9M + (1.5 * $557.5M) = $1.732 Billion`

Two extreme outliers exceeded this fence:
1. *Avengers: Infinity War* ($2.05 Billion gross)
2. *Avengers: Endgame* ($2.80 Billion gross)

**Strategic Implication**: The presence of multi-billion dollar outliers inflates the mean return to 8.54x, while the median is 5.62x. Relying on means would mislead Kwame into expecting $800M+ returns on every acquisition. We anchored Kwame's strategy on the **median return**, which is immune to extreme skew.

---

## 6. Table Grain & Preventing Fan-Out Corruption

In [`pipeline/validate.py`](file:///c:/Users/SamuelQuaigraine/workspace2/streamvault_licensing_analysis_samuel_quaigraine/pipeline/validate.py), we enforced strict grain discipline:
- **Films Table**: `# grain: one row per film` (112 rows)
- **Cast Table**: `# grain: one row per film per cast member` (7,827 rows)
- **Crew Table**: `# grain: one row per film per crew member` (24,932 rows)

### Why This Matters:
A film has an average of 70 cast members. If a developer joins the cast table back to the film table before totaling revenue:
`Inflated Revenue = Sum(Revenue * Cast Count) ~ 70 * Actual Revenue`

In our dataset, this would explode total revenue from **$67.1 Billion to over $4.7 Trillion**!

To prevent this silent corruption:
```python
merged = films.merge(details, on="movie_id", validate="one_to_one", indicator=True)
assert len(merged) == len(films), "Fan-out detected: row count multiplied!"
```

---

## 7. How to Run the Diagnosis Script

Run the standalone diagnosis script from your terminal:
```bash
python diagnosis/diagnose.py
```
This script audits `id_list.csv`, inspects all excluded lines, displays the 6-stage reconciliation table, and prints the distribution statistics directly to your screen.
