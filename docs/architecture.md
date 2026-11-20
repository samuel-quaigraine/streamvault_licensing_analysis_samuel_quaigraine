# StreamVault System Architecture & Entity-Relationship Model

This document provides the visual architectural blueprints, Entity-Relationship Diagram (ERD), and data dictionary for the StreamVault Content Acquisition Pipeline.

---

## 1. Entity-Relationship Diagram (ERD)

The data model enforces strict grain isolation and referential integrity. Financial metrics exist exclusively at the **FILM** grain (`# grain: one row per film`) to prevent fan-out multiplication when associating cast and crew records.

```mermaid
erDiagram
    CANDIDATE_LIST ||--o| FILM : "reconciles to"
    FILM ||--o| COLLECTION : "belongs to (optional)"
    FILM ||--|{ FILM_GENRE : "categorized by"
    FILM ||--|{ FILM_CAST : "features (1-to-many)"
    FILM ||--|{ FILM_CREW : "directed/written by (1-to-many)"
    
    CANDIDATE_LIST {
        int line_number "1 to 127 (line 69 is empty)"
        string raw_id "Value as provided in CSV"
        string status "VALID, DUPLICATE, EXCLUDED, EXTERNAL_FORMAT"
        string reason "Explanation for exclusion or duplicate"
    }

    FILM {
        int movie_id PK "TMDb unique integer identifier"
        string title "Canonical release title"
        date release_date "Theatrical release date (YYYY-MM-DD)"
        int release_year "Derived release year"
        string era "Pre-2000 vs 2000-Onward"
        float budget "Production budget in USD"
        float revenue "Worldwide box office gross in USD"
        float return_on_cost "Revenue / Budget multiple"
        float profit "Revenue - Budget in USD"
        float vote_average "Audience rating score (0.0 - 10.0)"
        int vote_count "Number of audience ratings"
        float popularity "TMDb popularity metric"
        int collection_id FK "Nullable collection identifier"
        string collection_name "Franchise title if member"
        boolean is_franchise "True if part of a collection"
        string commercial_tier "Blockbuster Hit, Moderate Return, Flop / Loss"
    }

    COLLECTION {
        int collection_id PK "TMDb collection identifier"
        string collection_name "Franchise name"
        int film_count "Verified films in candidate catalog"
        float total_revenue "Aggregate franchise gross USD"
        float median_return_on_cost "Median return multiple"
        float mean_vote "Average franchise rating"
    }

    FILM_GENRE {
        int movie_id FK "Film identifier"
        int genre_id PK "Genre identifier"
        string genre_name "Genre label (e.g. Action, Drama, Sci-Fi)"
    }

    FILM_CAST {
        int movie_id FK "Film identifier"
        int cast_id PK "TMDb cast credit identifier"
        string actor_name "Actor / Actress name"
        string character_name "Character portrayed"
        int cast_order "Billing order (0 = Lead Actor)"
    }

    FILM_CREW {
        int movie_id FK "Film identifier"
        int crew_id PK "TMDb crew credit identifier"
        string crew_name "Crew member name"
        string job "Role (e.g. Director, Screenplay, Producer)"
        string department "Department (e.g. Directing, Writing)"
    }
```

---

## 2. End-to-End Pipeline Architecture Flowchart

The pipeline decouples network acquisition from local computation, guarantees idempotent execution, and enforces automated quality gates at every transformation step.

```mermaid
flowchart TD
    subgraph Inputs & Configuration
        ENV[".env / .env.example"] --> CFG["pipeline/config.py"]
        CSV["id_list.csv (127 lines)"] --> LOAD["pipeline/load.py"]
        CFG --> LOAD
    end

    subgraph Data Acquisition & Caching
        LOAD -->|Parsed IDs + Empty Line 69 audit| EXT["pipeline/extract.py"]
        CFG --> EXT
        EXT <-->|Check cache before network call| CACHE[("data/raw/ (JSON Disk Cache)")]
        EXT -->|Log timestamp, status, source| MANIFEST["data/manifest.csv"]
        EXT <-->|Rate-limited session & backoff| TMDB["TMDb Live API (api.themoviedb.org)"]
    end

    subgraph Relational Grain Flattening
        EXT -->|Raw JSON payloads| TRF["pipeline/transform.py"]
        TRF -->|Grain: 1 row / film| T_FILM["Films Analytical Table (112 rows)"]
        TRF -->|Grain: 1 row / film / cast| T_CAST["Cast Table (7,827 rows)"]
        TRF -->|Grain: 1 row / film / crew| T_CREW["Crew Table (24,932 rows)"]
    end

    subgraph Validation & Integrity Gates
        T_FILM --> VAL["pipeline/validate.py"]
        T_CAST --> VAL
        T_CREW --> VAL
        VAL -->|validate='one_to_one', indicator=True| V_PASS["Zero Fan-Out Verified"]
    end

    subgraph Profiling & Quality Checks
        V_PASS --> CHK["pipeline/checks.py"]
        CHK -->|Schema, $0 rev checks, IQR outliers| PROF["Data Profiling Report"]
        CHK -->|6-stage reconciliation| RECON["Candidate Reconciliation Table"]
        CHK <-->|Deliberate 4-slice live check| TMDB
    end

    subgraph KPI Modeling & Scenarios
        CHK -->|Validated Data| TRF
        TRF -->|All-Years & 2000-Onward KPIs| KPIS["Dual-Window KPI Models"]
        TRF -->|Talent metrics| TALENT["Director & Actor Signals"]
        KPIS --> TOOL["streamvault_tool.py (Interactive CLI)"]
    end

    subgraph Output Deliverables Package
        T_FILM --> OUT1["output/clean_films.csv"]
        T_CAST --> OUT2["output/clean_cast.csv"]
        T_CREW --> OUT3["output/clean_crew.csv"]
        KPIS --> OUT4["output/summary_kpis.csv"]
        KPIS --> OUT5["output/franchise_rankings.csv"]
        KPIS --> OUT6["output/standalone_rankings.csv"]
        RECON --> OUT7["output/candidate_reconciliation.csv"]
        PROF --> OUT8["output/profiling_summary.json"]

        RECON & PROF --> D1["Deliverable 1: data_findings.md"]
        LOAD & EXT & TRF & VAL --> D2["Deliverable 2: Working Analysis (run_pipeline.py)"]
        VAL & TRF --> D3["Deliverable 3: decisions/ADR-001..005.md"]
        KPIS & TALENT --> D4["Deliverable 4: client_memo.md (1-page executive memo)"]
        TOOL --> D5["Deliverable 5: improvement.md + streamvault_tool.py"]
    end
```

---

## 3. Data Dictionary: Processed Analytical Tables

### Table 1: `clean_films.csv` (`# grain: one row per film`)
- **`movie_id`** (Integer, Primary Key): Unique TMDb movie identifier.
- **`title`** (String): Official English release title.
- **`original_title`** (String): Original language title.
- **`release_date`** (Date String, `YYYY-MM-DD`): Theatrical premiere date.
- **`release_year`** (Integer): Extracted 4-digit release year.
- **`era`** (Categorical): `"2000-Onward"` if release year >= 2000, else `"Pre-2000"`.
- **`budget`** (Float, USD): Production budget as reported by studio filings.
- **`revenue`** (Float, USD): Worldwide cumulative theatrical box office gross.
- **`profit`** (Float, USD): Net gross `Revenue - Budget`.
- **`return_on_cost`** (Float): Return multiple `Revenue / Budget`.
- **`commercial_tier`** (Categorical): Categorization:
  - `Blockbuster Hit`: `Return >= 2.5x`
  - `Moderate Return`: `1.0x <= Return < 2.5x`
  - `Flop / Loss`: `Return < 1.0x`
- **`runtime`** (Float, Minutes): Feature film duration in minutes.
- **`vote_average`** (Float): Audience score average on a 10-point scale.
- **`vote_count`** (Integer): Total audience ratings submitted.
- **`popularity`** (Float): TMDb engagement and page-view index.
- **`status`** (String): Release status (e.g., `"Released"`).
- **`collection_id`** (Integer, Nullable Foreign Key): ID of parent franchise collection, or null if standalone.
- **`collection_name`** (String, Nullable): Name of franchise collection (e.g., `"Harry Potter Collection"`).
- **`is_franchise`** (Boolean): `True` if member of a collection; `False` if standalone film.
- **`genres_count`** (Integer): Number of assigned genre categories.
- **`genre_names`** (String): Comma-delimited list of genre labels.

### Table 2: `clean_cast.csv` (`# grain: one row per film per cast member`)
- **`movie_id`** (Integer, Foreign Key): References `clean_films.csv`.
- **`cast_id`** (Integer, Primary Key): TMDb actor credit identifier.
- **`actor_name`** (String): Billed name of the performer.
- **`character_name`** (String): Name of the role portrayed.
- **`cast_order`** (Integer): Order in the credits billing (0 = Top-billed Lead Actor).

### Table 3: `clean_crew.csv` (`# grain: one row per film per crew member`)
- **`movie_id`** (Integer, Foreign Key): References `clean_films.csv`.
- **`crew_id`** (Integer, Primary Key): TMDb crew credit identifier.
- **`crew_name`** (String): Name of the crew member.
- **`job`** (String): Specific credit (e.g., `"Director"`, `"Screenplay"`, `"Original Music Composer"`).
- **`department`** (String): Functional department (e.g., `"Directing"`, `"Writing"`).

---

## 4. Two-Phase Enterprise Content Architecture: Pre-Integration Baseline to Internal Ledger Extension

The data platform is intentionally engineered across two distinct commercial phases to mirror real-world consulting practice:

```mermaid
flowchart LR
    subgraph Phase 1: Current External Demand Baseline
        RAW["Raw Candidates (id_list.csv)"] --> FACTORY["5-Station Factory Pipeline"]
        TMDB["TMDb Public Data (Gross, Budget, Credits)"] --> FACTORY
        FACTORY --> CLEAN["clean_films.csv (1 row / film on movie_id)"]
        FACTORY --> SHORTLIST["Strategic Shortlists & 1-Page Memo"]
    end

    subgraph Phase 2: Future Internal Ledger Extension
        CLEAN --> JOIN{"safe_merge_one_to_one (on='movie_id')"}
        INTERNAL["StreamVault Internal Ledger (Cost-per-Stream, Retention Lift, Studio Price Cards)"] --> JOIN
        JOIN --> COMPOSITE["Blended Commercial P&L Portfolio Model"]
    end
```

### Architectural Principles:
1. **Phase 1 (External Market Demand Baseline)**:
   - Evaluates historical market demand, capital efficiency (`Revenue / Budget`), and creative talent consistency from public records.
   - Operates 100% offline from verified JSON disk cache.
   - Prepares Kwame Boateng with an unbiased, mathematically reconciled allocation strategy for the October 31 board review without fabricating internal streaming economics.
2. **Phase 2 (Internal Streaming & Deal Ledger Integration)**:
   - Because `clean_films.csv` strictly enforces `# grain: one row per film` on `movie_id`, it serves as an extensible integration hook.
   - When internal telemetry (e.g. streaming hours, subscriber retention lift) and studio licensing rate cards are finalized, they join directly via `movie_id` (`validate="one_to_one"`).
   - Zero refactoring of Station 1 (The Bouncer), Station 2 (The Labeler), or Station 3 (The Quality Filter) is required.
