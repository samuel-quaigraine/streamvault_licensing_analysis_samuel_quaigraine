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

The candidate file contains **127 rows** beneath the `tmdb_id` header. The ingestion engine in [`pipeline/load.py`](pipeline/load.py) audits every row sequentially using defensive parsing:

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

During API acquisition in [`pipeline/extract.py`](pipeline/extract.py), five IDs failed to resolve on TMDb:
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

## 5. Data Types Used and Architectural Rationale

Every column across the raw, transformed, and analytical layers is assigned an explicit, deliberate data type. Choosing the right data type is not just a formatting detail—it is the first line of defense against silent data corruption, floating-point precision drift, memory bloat, and unexpected pipeline crashes.

### Summary Data Type Ledger

| Entity / Layer | Column Name | Chosen Data Type | Why This Type Was Chosen | Risk Prevented |
|---|---|---|---|---|
| **Ingestion** | `raw_id` | `String` (Text) | Preserves untrusted input verbatim before cleaning. | Prevents crashes on blank line 69, `'N/A'`, or `tt0468569`. Prevents pandas from coercing IDs to floats with `NaN`. |
| **Film Key** | `movie_id` | `Int64` (Integer) | Discrete surrogate primary key from TMDb. | Avoids floating-point precision drift (`155.0`) in dictionary lookups and joins. |
| **Parent IP** | `collection_id` | `Nullable Int64` | Foreign key referencing parent franchise; null for standalones. | Allows missing values without forcing the whole column to become a float. |
| **Cast / Crew Keys** | `cast_id`, `crew_id` | `Int64` (Integer) | Discrete surrogate keys for actor and crew credit records. | Ensures deterministic 1-to-many joins between films, cast, and crew. |
| **Billing Rank** | `cast_order` | `Int32` (Integer) | Discrete ordinal rank (0 = top-billed lead actor, 1 = second, etc.). | Allows exact integer threshold filtering (e.g. `cast_order < 3` for lead stars). |
| **Calendar Date** | `release_date` | `ISO-8601 String` / `datetime64` | Standard `YYYY-MM-DD` date representation. | Enables chronological sorting, calendar math, and year extraction. |
| **Release Year** | `release_year` | `Int32` (Integer) | 4-digit calendar year (e.g., `2008`). | High-speed numeric boundary evaluation (`year >= 2000`) in NumPy without repeated date parsing. |
| **Era Split** | `era` | `Categorical String` | Low-cardinality label (`"Pre-2000"` vs `"2000-Onward"`). | Clear, descriptive dimension matching Finance VP Yaw's audit requirement. |
| **Money Metrics** | `budget`, `revenue`, `profit` | `Float64` (USD) | Continuous double-precision monetary figures scaling to billions. | Prevents 32-bit integer overflow on $2.8B grosses and supports continuous financial math. |
| **Efficiency Metric** | `return_on_cost` | `Float64` (Multiple) | Continuous commercial multiple (`Revenue / Budget`). | Captures fractional multiples (e.g., 5.62x vs 3.84x) without integer floor truncation. |
| **Audience Rating** | `vote_average` | `Float64` (Score) | Continuous rating on a 0.0 to 10.0 scale (e.g., `8.37`). | Preserves fine-grained critical score differences between candidates. |
| **Rating Volume** | `vote_count` | `Int64` (Count) | Discrete non-negative count of human votes submitted. | Prevents fractional votes; supports exact threshold checks (`vote_count >= 1000`). |
| **Engagement** | `popularity` | `Float64` (Index) | Continuous decay-weighted engagement metric from TMDb. | Accommodates logarithmic fractional popularity indices. |
| **Franchise Flag** | `is_franchise` | `Boolean` (`bool`) | Binary True/False flag. | Enables vectorized Boolean masking (`films[films['is_franchise']]`) in NumPy at C-speed. |
| **Business Tier** | `commercial_tier` | `Categorical String` | Fixed business buckets (`"Blockbuster Hit"`, `"Moderate Return"`, `"Flop / Loss"`). | Human-readable business reporting without fragile numeric code lookups. |
| **Text Names** | `title`, `name`, `character` | `UTF-8 String` | Variable-length Unicode text. | Preserves international characters (accents, Japanese kanji for *Spirited Away*, non-Latin names) without encoding corruption. |

---

### Detailed Rationale by Layer

#### 1. Ingestion: Why `raw_id` Must Start as a String
When loading `id_list.csv`, a naive engineer might use `pd.read_csv()` or `int(row)`. This immediately fails in production:
- **Crash on Format Faults**: Line 69 is an empty string `""`, Line 111 is `'N/A'`, and Line 95 is `'tt0468569'`. Calling `int()` directly crashes with `ValueError: invalid literal for int()`.
- **The Float Coercion Trap**: In pandas, if an integer column contains missing values, pandas historically converts the entire column to `float64`. As a result, integer ID `155` becomes `155.0`. Floating-point numbers can suffer precision loss at large values and fail exact string or hash-set lookups.
- **Our Defensive Approach**: We read raw candidate lines as pure strings, strip whitespace, run regex checks (`^tt\d+` for IMDb, `^-?\d+$` for integers), record audit logs for anomalies, and only cast valid entries to `int` once they pass the admission gates.

#### 2. Relational Keys: Why IDs Must Be Pure Integers
Primary and foreign keys (`movie_id`, `cast_id`, `crew_id`) are stored as discrete 64-bit integers (`Int64`).
- **Deterministic Joins**: Relational merges between the film table (112 rows) and the cast table (7,827 rows) require exact, zero-tolerance key matching. Floating-point keys can introduce rounding errors where `155.00000000000003 != 155.0`.
- **Nullable Franchise Keys**: Standalone movies do not belong to a collection. We use pandas' nullable integer type (`pd.Int64Dtype()`) for `collection_id` so missing values remain distinct (`<NA>`) without coercing the entire column into floating-point numbers.

#### 3. Financial Figures: Why Money Is `Float64`
Production budgets and box office grosses are modeled as `Float64`:
- **Overflow Prevention**: Top blockbusters like *Avengers: Endgame* gross over $2.80 Billion ($2,800,000,000). Standard 32-bit signed integers overflow at $2.147 Billion (`2^31 - 1`), causing multi-billion-dollar figures to wrap around to negative numbers!
- **Division Without Floor Truncation**: Calculating commercial return multiples requires dividing revenue by budget (`Revenue / Budget`). In integer arithmetic, `7 / 2 = 3` (truncating 3.5x to 3x). Using `Float64` preserves exact ROI multiples (e.g. 5.62x vs 3.84x).
- **Vectorized Performance**: NumPy and BLAS libraries are heavily optimized for 64-bit floating-point SIMD vector registers, giving our calculations maximum execution speed.

#### 4. Binary Flags: Why `is_franchise` Is a Native Boolean
Instead of using strings like `"YES"`/`"NO"` or numbers `1`/`0`, franchise membership is stored as a native Python/NumPy `bool`.
- **Boolean Masking**: Allows lightning-fast subset filtering:
  ```python
  franchises = films[films["is_franchise"]]
  standalones = films[~films["is_franchise"]]
  ```
- **Clarity and Memory**: Booleans consume 1 byte per row, compared to 50+ bytes for string objects, and eliminate ambiguities caused by case mismatches (e.g. `"Yes"` vs `"yes"` vs `"Y"`).

#### 5. Textual Integrity: Why UTF-8 Strings Are Mandatory
Film titles, character names, and talent credits contain international names and symbols:
- Examples in our catalog: *千と千尋の神隠し* (*Spirited Away*), French accents, and diverse actor names.
- Enforcing UTF-8 encoding across all CSV inputs and outputs guarantees that character data renders correctly across all operating systems (Windows, Linux, macOS) without mojibake (garbled characters like `Ã©`).

---

## 6. Exploratory Data Profiling & Outlier Mathematics

Data profiling was executed in [`pipeline/checks.py`](pipeline/checks.py) to inspect distributions and detect disguised nulls.

### Disguised Nulls ($0 Revenue & Budget)
In film datasets, unrecorded box office often appears as $0.00 rather than `NaN`.
- In our verified 112 titles, exactly **0 films reported $0 revenue** and **0 films reported $0 budget**.
- All 112 verified titles represent major theatrical releases with complete financial reporting.

### The "Partial Bundle Trap" in Candidate Franchises
Studios license franchises on an all-or-nothing basis (e.g., license the entire series or none). In our catalog profiling:
- Collections like *Harry Potter* (8 films), *The Dark Knight* (3 films), and *The Lord of the Rings* (3 films) are complete collections on the candidate list where every entry has been audited.
- In contrast, series like *Jaws* (only 1 film on the list), *The Terminator* (only 4 of 6), and *Alien* (only 4 of 6+) are incomplete subsets.
- **Strategic Implication:** Evaluating an incomplete franchise on only its top legacy hits hides weak, expensive sequels. Our pipeline implements whole-bundle aggregation tracking `min_roi` (the weakest-link floor) so Kwame never bids on partial bundles without pricing in unlisted sequels.

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

## 7. Table Grain & Preventing Fan-Out Corruption

In [`pipeline/validate.py`](pipeline/validate.py), we enforced strict grain discipline:
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

## 8. How to Run the Diagnosis Script

Run the standalone diagnosis script from your terminal:
```bash
python diagnosis/diagnose.py
```
This script audits `id_list.csv`, inspects all excluded lines, displays the 6-stage reconciliation table, and prints the distribution statistics directly to your screen.
