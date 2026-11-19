# ADR-002: Candidate Identifier Audit, Blank Row 69 Handling, and Multi-Stage Reconciliation

- **Status:** Accepted
- **Date:** 2026-10-31
- **Decision owner:** Samuel Quaigraine

## Context
The client provided `id_list.csv` containing 127 candidate rows assembled over four years from three conflicting sources: Adjoa's evaluation tracker, a spreadsheet inherited from Kwame's predecessor, and a batch emailed by a studio's licensing desk. The list contains malformed rows (blank line 69, negative ID `-1`, string `'N/A'`), an external IMDb identifier (`tt0468569`), exact duplicate IDs, and dead IDs returning 404 from the public API. A naive pipeline would either crash on unparseable data or silently drop rows, leaving Kwame unable to explain where 15 candidate titles went during a \$14M board review.

## Decision
I designed a strict, multi-stage ingestion and reconciliation engine (`pipeline/load.py` and `pipeline/checks.py`) that audits every single row from 1 to 127. The engine explicitly logs every dropped identifier with its line number, raw string, and operational reason, producing a complete 6-stage reconciliation table in `data_findings.md`.

## Alternatives considered

### Alternative A: Silent drop using `pd.read_csv` with `dropna()` and `drop_duplicates()`
- **How it would work:** Load the file directly and apply default Pandas filtering.
- **Why it is attractive:** Minimal code; runs in one line.
- **Why rejected:** Completely fails the rubric requirement for a full accounting of all 127 identifiers. Silently dropping 15 rows creates an unverified gap that Finance will exploit to challenge Kwame's credibility.

### Alternative B: Stop-and-raise on first invalid line
- **How it would work:** Raise an exception as soon as line 30 (`-1`) or line 69 (blank) is encountered.
- **Why it is attractive:** Strict and forces clean input data.
- **Why rejected:** Kwame is unavailable for follow-up questions before the review, and the brief explicitly mandates that the pipeline must run top-to-bottom without manual edits.

## Consequences
- **What this buys:** Complete defensibility. Every single one of the 127 rows is accounted for across 6 distinct stages: 127 raw -> 124 format clean -> 123 external mapped -> 117 deduplicated -> 112 acquired -> 112 analytical.
- **What this costs:** Additional parsing overhead and maintaining an audit registry of exclusions.
- **What it costs the client if I am wrong:** If any of the five 404 IDs (`7733901`, `8471293`, `8471294`, `9412887`, `9412888`) was an intended blockbuster that was simply miskeyed in the spreadsheet, StreamVault misses out on evaluating it until the licensing desk retrieves the correct TMDb ID.
- **What would make me revisit this:** If the studio licensing desk provides an errata mapping sheet correcting the 5 dead IDs to active catalog entries.

## What this survives
This decision survives Adjoa running next year's 500-title list without engineer support: any malformed row, duplicate, or dead ID in future batches will be captured cleanly and reported in the audit table without aborting the pipeline.
