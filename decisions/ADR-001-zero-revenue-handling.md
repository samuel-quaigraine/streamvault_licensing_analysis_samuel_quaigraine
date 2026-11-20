# ADR-001: Zero-Revenue Handling, Value Definition, and Unverified Blind Spots

- **Status:** Accepted
- **Date:** October 31, 2026
- **Decision Owner:** Samuel Quaigraine

---

## 1. The Context & The Problem
In public movie databases like TMDb, when a film shows `$0` for budget or revenue, it almost never means the movie cost `$0` to make or made `$0` at the box office. In reality, it means **nobody typed the numbers into the database**.

This creates a serious business challenge for StreamVault's $14M licensing decision:
- If we naively calculate return as `Revenue / Budget` and treat `$0` as real money, a movie with a $10M budget and unrecorded revenue gets scored as a `0.0x` return. We would be falsely punishing a great film as a catastrophic commercial failure!
- On the other hand, if we throw out every film with missing money numbers, someone might accuse us of cherry-picking and hiding real box office flops.

Kwame is presenting to the board and Finance VP Yaw, both of whom will scrutinize how we handled missing money data and defined catalog value.

---

## 2. The Decision We Made
We built a flexible, parameterized system in `pipeline/transform.py` (`filter_reliable_financials`, Station 3: The Quality Filter) that allows Kwame and Adjoa to test the data under **both** assumptions:

1. **Baseline Rule (`treat_zero_revenue_as_missing = True`)**: 
   We treat `$0` revenue as missing unrecorded data (`NaN`). These films are excluded from return-on-cost and profit averages, but are still counted in catalog totals and audience rating summaries.
2. **Sensitivity Rule (`treat_zero_revenue_as_missing = False`)**:
   We treat `$0` revenue as an actual commercial flop (`0.0x` return) to see if Kwame's strategy still holds under the harshest possible scenario.

---

## 3. Defining "Value" Without Internal Streaming Data
We do not have StreamVault's internal viewer completion or subscriber retention data. To measure title value objectively, we made the conscious architectural choice to use a **disciplined composite of Commercial Return (ROI) and Proven Audience Reach (Box Office Gross + User Vote Volume)**:
- **Why not User Rating alone?** Relying purely on ratings over-rewards niche cult classics (e.g. high critical acclaim but low commercial draw) that fail to drive broad subscriber adoption.
- **Why not Total Box Office alone?** Relying purely on raw gross over-rewards massive $250M blockbusters while ignoring capital efficiency and licensing cost bases.
- **The Balance:** Grounding valuation in median return multiple (`Revenue / Budget`) coupled with audience vote scale provides a robust, reproducible proxy for broad viewer demand without fabricating unmeasured streaming churn metrics.

---

## 4. Other Options We Considered and Rejected

### Option A: Treat all `$0` revenue as `0.0x` flops without checking
- **What it would do:** Automatically treat every film missing revenue as a complete loss.
- **Why we rejected it:** In our verified catalog of 112 titles, all 112 are major theatrical releases with complete box office records. However, on next year's 500-title list, smaller indie films may lack box office numbers. Forcing them to count as zero would unfairly penalize standalone films without proof that they actually lost money.

### Option B: Guess or estimate missing box office using genre averages
- **What it would do:** Fill in missing revenues with the average box office of other action or comedy films.
- **Why we rejected it:** We are advising on a real $14M cash commitment. Making up numbers or guessing box office would destroy our credibility the moment Finance looked at the math.

---

## 5. What We Couldn't Verify & What It Costs Kwame in November
To protect Kwame in the boardroom, we plainly state where public theatrical data ends and real-world negotiation begins:

1. **Studio Licensing Asking Prices**:
   - *The Reality:* TMDb records historical production costs and theatrical grosses, not current studio licensing rate cards.
   - *What it costs Kwame:* If distributors demand more than 40% of the total budget ($5.6M+) for a single franchise bundle, Kwame risks budget exhaustion. **Negotiation rule:** Kwame must enforce a strict 40% walk-away threshold and pivot capital into the standalone shortlist if studios price gouge.
2. **Actual Streaming Viewer Retention & Completion**:
   - *The Reality:* Theatrical box office demonstrates broad cultural reach, but does not guarantee repeat home streaming completions.
   - *What it costs Kwame:* High-grossing spectacle films with zero rewatch value could fail to reduce monthly subscriber churn.
3. **Regional Streaming Rights & Exclusivity**:
   - *The Reality:* Public catalog data cannot verify whether rival platforms (Netflix, Amazon, Disney+) currently hold active exclusive windows in our operating territories.
   - *What it costs Kwame:* Kwame risks wasting negotiation cycles or signing deal memos for unstreamable titles. **Negotiation rule:** Require distributor legal warranties guaranteeing 100% regional streaming exclusivity before signing deal memos.

---

## 6. What This Means for Kwame and StreamVault
- **Total Transparency in Front of Finance:** When Finance VP Yaw asks how we handled missing box office numbers, Kwame can show him the results under both rules side-by-side.
- **Stable Finding:** Because all 112 verified titles in our candidate pool have complete box office records, the baseline numbers hold true: franchise films deliver a median return of **5.62x** compared to **3.84x** for standalone titles.

---

## 7. How This Protects Adjoa Next Year (500 Titles)
Next year, when Adjoa reruns this pipeline on 500 titles by herself, she will not need to edit code or rewrite formulas. Whether the new batch has 5 missing titles or 50, the pipeline will automatically process them, calculate both scenarios, and immediately alert her if the recommendation flips.
