# ADR-003: Strict Table Grain Definition and Fan-Out Prevention

- **Status:** Accepted
- **Date:** 2026-10-31
- **Decision owner:** Samuel Quaigraine

## Context
A TMDb API response is hierarchical: a movie details payload has scalar fields (`title`, `revenue`, `budget`), nested dictionary objects (`belongs_to_collection`), and nested arrays (`genres`, `cast`, `crew`). If a developer flattens cast members (averaging 70 actors per film) and joins that back to the movie table before computing financial totals, every film's revenue is multiplied by its cast count. In our dataset, this would fan out 112 films into 7,827 rows, artificially inflating total revenue from \$67.1B to over \$4.7 Trillion—a fatal analytical corruption.

## Decision
I established a strict relational grain boundary in `pipeline/transform.py` (`flatten_movie_details_and_credits` under Station 2: The Labeler) and `pipeline/validate.py`:
1. **Films Analytical Table**: Fixed strictly at `# grain: one row per film` (112 rows). All financial KPIs, budgets, revenues, and return multiples are computed exclusively on this table.
2. **Cast Table**: Fixed at `# grain: one row per film per cast member` (7,827 rows).
3. **Crew Table**: Fixed at `# grain: one row per film per crew member` (24,932 rows).
4. **Join Integrity**: Any join onto the film table must use `validate="one_to_one"` and assert `len(merged) == len(films)` via `safe_merge_one_to_one`, turning potential silent row multiplications into immediate loud errors.

## Alternatives considered

### Alternative A: Denormalize everything into a single wide DataFrame
- **How it would work:** Repeat movie revenue on every cast member row so users can query everything from one table.
- **Why it is attractive:** Simple for quick ad-hoc queries.
- **Why rejected:** Highly prone to accidental aggregation errors; anyone running `df['revenue'].sum()` produces a corrupted number inflated by a factor of 70x.

### Alternative B: Omit cast and crew entirely
- **How it would work:** Ingest only the movie details endpoint.
- **Why it is attractive:** Guarantees no fan-out possible.
- **Why rejected:** Kwame specifically requested an analysis of which directors and lead actors reliably signal a title worth licensing to use as leverage in studio negotiations.

## Consequences
- **What this buys:** Absolute mathematical integrity. Zero revenue fan-out, zero duplicate counting, and clean isolation between commercial metrics and talent evaluation.
- **What this costs:** Requires maintaining three separate DataFrames and performing validated joins only when evaluating talent signals.
- **What it costs the client if I am wrong:** There is no scenario where aggregating revenue at the cast grain is correct. This choice guarantees accurate totals.
- **What would make me revisit this:** If StreamVault transitions to a dedicated star-billing royalty model where actor-level revenue sharing must be tracked.

## What this survives
This decision survives Adjoa rerunning the pipeline on 500 titles next year: even if a film has 200 cast members, the assertion `assert len(merged) == len(films)` guarantees that the analytical film grain remains intact.
