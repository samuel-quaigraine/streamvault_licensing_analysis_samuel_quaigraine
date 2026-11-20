# ADR-001: Parameterized Zero-Revenue and Missing Money Handling

- **Status:** Accepted
- **Date:** October 31, 2026
- **Decision Owner:** Samuel Quaigraine

---

## 1. The Context & The Problem
In public movie databases like TMDb, when a film shows `$0` for budget or revenue, it almost never means the movie cost `$0` to make or made `$0` at the box office. In reality, it means **nobody typed the numbers into the database**.

This creates a serious business challenge for StreamVault's $14M licensing decision:
- If we naively calculate return as `Revenue / Budget` and treat `$0` as real money, a movie with a $10M budget and unrecorded revenue gets scored as a `0.0x` return. We would be falsely punishing a great film as a catastrophic commercial failure!
- On the other hand, if we throw out every film with missing money numbers, someone might accuse us of cherry-picking and hiding real box office flops.

Kwame is presenting to the board and Finance VP Yaw, both of whom will scrutinize how we handled missing money data.

---

## 2. The Decision We Made
We built a flexible, parameterized system in `pipeline/transform.py` (`filter_reliable_financials`, Station 3: The Quality Filter) that allows Kwame and Adjoa to test the data under **both** assumptions:

1. **Baseline Rule (`treat_zero_revenue_as_missing = True`)**: 
   We treat `$0` revenue as missing unrecorded data (`NaN`). These films are excluded from return-on-cost and profit averages, but are still counted in catalog totals and audience rating summaries.
2. **Sensitivity Rule (`treat_zero_revenue_as_missing = False`)**:
   We treat `$0` revenue as an actual commercial flop (`0.0x` return) to see if Kwame's strategy still holds under the harshest possible scenario.

---

## 3. Other Options We Considered and Rejected

### Option A: Treat all `$0` revenue as `0.0x` flops without checking
- **What it would do:** Automatically treat every film missing revenue as a complete loss.
- **Why we rejected it:** In our verified catalog of 112 titles, all 112 are major theatrical releases with complete box office records. However, on next year's 500-title list, smaller indie films may lack box office numbers. Forcing them to count as zero would unfairly penalize standalone films without proof that they actually lost money.

### Option B: Guess or estimate missing box office using genre averages
- **What it would do:** Fill in missing revenues with the average box office of other action or comedy films.
- **Why we rejected it:** We are advising on a real $14M cash commitment. Making up numbers or guessing box office would destroy our credibility the moment Finance looked at the math.

---

## 4. What This Means for Kwame and StreamVault
- **Total Transparency in Front of Finance:** When Finance VP Yaw asks how we handled missing box office numbers, Kwame can show him the results under both rules side-by-side.
- **Stable Finding:** Because all 112 verified titles in our candidate pool have complete box office records, the baseline numbers hold true: franchise films deliver a median return of **5.62x** compared to **3.84x** for standalone titles.
- **Risk if Wrong:** If future films with unrecorded revenues were true box office disasters, our baseline might look slightly more optimistic. That is exactly why we built the sensitivity toggle so Kwame can test the worst-case scenario at any moment.

---

## 5. How This Protects Adjoa Next Year (500 Titles)
Next year, when Adjoa reruns this pipeline on 500 titles by herself, she will not need to edit code or rewrite formulas. Whether the new batch has 5 missing titles or 50, the pipeline will automatically process them, calculate both scenarios, and immediately alert her if the recommendation flips.
