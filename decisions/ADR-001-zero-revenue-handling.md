# ADR-001: Parameterized Zero-Revenue and Missing Return-on-Cost Treatment

- **Status:** Accepted
- **Date:** 2026-10-31
- **Decision owner:** Samuel Quaigraine

## Context
In film performance analytics, unrecorded or missing box office numbers often appear as \$0.00 rather than explicit nulls. When computing return-on-cost ($\text{Revenue} / \text{Budget}$), treating \$0 as genuine revenue drags the group mean and median downward as an artificial total loss. Conversely, discarding \$0 entries could artificially inflate performance by omitting genuine box office flops. Kwame is presenting to the board and Finance VP Yaw, both of whom will scrutinize how missing data was handled.

## Decision
I parameterized the financial metric calculation (`filter_reliable_financials` / `engineer_financial_metrics` in `pipeline/transform.py` under Station 3: The Quality Filter) with the argument `treat_zero_revenue_as_missing: bool` to evaluate portfolio returns under both assumptions. For the baseline recommendation, any entry with zero or missing revenue is excluded from return-on-cost metrics rather than coerced to a zero-multiple flop.

## Alternatives considered

### Alternative A: Coerce all \$0 revenues to 0.0x return
- **How it would work:** Every film with budget > 0 and revenue == 0 is assigned a 0.0 return-on-cost multiple.
- **Why it is attractive:** Simple to implement; treats non-reported revenue as complete commercial failure.
- **Why rejected:** In our verified dataset of 112 titles, exactly 0 films reported \$0 revenue (all 112 are major theatrical releases with complete box office records). However, on next year's 500-title list, smaller indie films may lack box office tracking; coercing them to zero flops would severely penalize standalone titles without proof of actual failure.

### Alternative B: Impute missing box office using genre medians
- **How it would work:** Fill missing revenues with the median box office of that film's primary genre.
- **Why it is attractive:** Preserves sample size across all titles.
- **Why rejected:** Fabricates financial figures for a \$14M capital commitment; the board would reject estimated revenue in an evidence-based review.

## Consequences
- **What this buys:** Defensibility and transparency in front of Finance. We can demonstrate the exact impact of both assumptions instantly.
- **What this costs:** Requires maintaining parameterized logic in the pipeline rather than hardcoding a single cleaning path.
- **What it costs the client if I am wrong:** If unrecorded box office titles on larger lists were true catastrophic losses that StreamVault buys, excluding them would make those acquisitions appear artificially safe. However, because our candidate list has verified box office across all 112 films, the baseline multiple (5.62x franchise median vs 3.84x standalone median) holds with zero distortion.
- **What would make me revisit this:** If distributor audit records confirm that unlisted titles were theatrical releases that failed to report box office due to sub-threshold theatrical performance.

## What this survives
This decision survives Adjoa running the pipeline next year on 500 titles: whether future titles contain 5 or 50 missing revenue figures, the pipeline will compute both metrics side-by-side and highlight any recommendation flip automatically.
