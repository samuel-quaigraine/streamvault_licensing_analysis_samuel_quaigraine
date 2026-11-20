# ADR-004: Two-Window Era Split, Franchise Rollup Rules, and Shortlist Selection

- **Status:** Accepted
- **Date:** October 31, 2026
- **Decision Owner:** Samuel Quaigraine

---

## 1. The Context & The Problem
In the boardroom, **Finance VP Yaw** strongly distrusts theatrical numbers from before the year 2000. He points out that historical inflation, currency exchange shifts, and legacy reporting methods make older box office figures unreliable.

At the same time, half of Kwame's acquisitions team passionately believes that older evergreen classics (*Star Wars*, *The Godfather*, *Pulp Fiction*) offer massive return-on-cost value that modern $200M blockbusters cannot match.

If we only show pre-2000 numbers, Yaw will reject the analysis on the spot. But if we quietly filter out older films without telling anyone, we drop 41 iconic titles (over a third of our catalog) and hide valuable data. Furthermore, evaluating franchises requires understanding how studios actually package and sell them.

---

## 2. The Decision We Made
We implemented a dual-window evaluation system across the entire analytical pipeline (`score_licensing_options` in `pipeline/transform.py`, Station 4: The Scorekeeper):

1. **Window 1: All-Years Baseline (112 titles: 96 Franchises, 16 Standalones)**:
   Evaluates every single verified title regardless of release year.
2. **Window 2: 2000-Onward Baseline (71 titles: 63 Franchises, 8 Standalones)**:
   Restricts the evaluation exclusively to titles released in the modern era (Finance VP Yaw's mandate).

We then compared both windows head-to-head to see if the core recommendation—**Franchise Bundles vs. Standalone Titles**—holds true or flips.

---

## 3. The Decisive Finding: The Recommendation Never Flips!
The numbers delivered an overwhelming, definitive answer:

| Metric | Window 1: All-Years | Window 2: 2000-Onward (Finance View) | Advantage for Franchises |
|---|---|---|---|
| **Franchise Median ROI** | **5.62x** | **5.05x** | Higher in both windows |
| **Standalone Median ROI** | **3.84x** | **3.84x** | Baseline remains steady |
| **Franchise Hit Rate (>= 2.5x)** | **94.8%** | **95.2%** | Superior commercial floor |
| **Standalone Hit Rate (>= 2.5x)** | **75.0%** | **87.5%** | Higher risk of underperforming |
| **Does the Recommendation Flip?** | **NO** | **NO** | **Franchises win in both eras** |

Even when Adjoa tests alternative cutoff years between 1990 and 2015 using our scenario tool, franchises consistently maintain a **1.2x to 1.8x return advantage** over standalones.

---

## 4. The Franchise Rollup Rule & Exposing the "Partial Bundle Trap"
Studios sell franchises as all-or-nothing bundles. In `pipeline/transform.py` (`rank_franchise_bundles`), we evaluate entire collections together rather than cherry-picking individual sequels:
1. **Whole-Bundle Economics**: We sum total revenue against total production budget across the entire series and track the `min_roi` (the weakest link in the chain).
2. **The "Partial Bundle Trap"**:
   - The candidate list contains several incomplete franchises: *Jaws* (only 1 film on the list out of 4), *The Terminator* (only 4 of 6), and *Alien* (only 4 of 6+).
   - If Kwame prices a bundle based on *Jaws 1* (19x ROI), but Universal forces StreamVault to buy *Jaws 2*, *3-D*, and *The Revenge*, StreamVault absorbs massive dead weight.
   - **The Defense:** We advise Kwame to focus upfront capital exclusively on **complete, audited series** where every entry is accounted for.

---

## 5. The Negotiation Shortlists (Why Each Made the Cut)

### Top 3 Franchise Bundles (Complete Series with Proven Commercial Floors):
1. **Harry Potter Collection** (8 films): $7.76B total gross, 6.17x median ROI, **3.74x worst-case floor** (even its lowest entry grossed $795M). An unmatched 8-film viewing marathon with zero commercial failures.
2. **The Dark Knight Trilogy** (3 films): $2.46B total gross, 4.32x median ROI, **8.01/10 rating**. Combines multi-billion-dollar superhero box office with Oscar-level prestige.
3. **The Lord of the Rings Collection** (3 films): $2.92B total gross, **11.73x median ROI**, 8.47/10 rating. Unmatched capital efficiency (made for $266M total).

### Top 5 Modern Standalone Hits (2000-Onward):
1. **Spirited Away** (2001): 14.47x ROI, 8.54 rating. Exceptional capital efficiency and universal family audience draw.
2. **Inception** (2010): 5.24x ROI, 8.37 rating, $839M gross. Elite modern sci-fi classic with high rewatch appeal.
3. **Interstellar** (2014): 4.52x ROI, 8.50 rating, $747M gross. Proven modern emotional spectacle.
4. **Memento** (2000): 4.45x ROI, 8.18 rating. Efficient indie prestige ($9M budget).
5. **The Departed** (2006): 3.24x ROI, 8.16 rating, $291M gross. Star-studded Oscar-winning crime anchor.

---

## 6. One-Paragraph Deal Note: Harry Potter Collection
- **Valuation Cap:** Cap opening valuation at **$4.5M (32% of our total $14M licensing budget)**, preserving $9.5M headroom to secure a second franchise and the standalone shortlist.
- **The Decisive Anchor Number:** **$970 Million average box office per film**, with its weakest entry still grossing **$795 Million**. In movie history, most series degrade by film 3. *Harry Potter* is an 8-car train where every single car is an engine, guaranteeing subscriber value across the entire bundle.

---

## 7. Other Options We Considered and Rejected

### Option A: Show only 2000-onward data to keep Finance happy
- **What it would do:** Filter out all films released before January 1, 2000 before running calculations.
- **Why we rejected it:** It throws away 41 titles, including franchise anchors like the original *Star Wars* trilogy and top-tier standalones like *The Shawshank Redemption*.

### Option B: Show all years and bury Finance's concern in a footnote
- **What it would do:** Present one combined table and add an asterisk mentioning inflation.
- **Why we rejected it:** Footnoting an objection that a board member has explicitly raised is a guaranteed way to lose the room. Addressing Yaw's mandate directly in the presentation disarms his objection before he even speaks.

---

## 8. What This Means for Kwame and Adjoa
- **Kwame Controls the Room:** Kwame can present the All-Years numbers, then immediately switch to the 2000-Onward view and say: *"Even under Finance's strictest criteria, franchise bundles still deliver a 5.05x return versus 3.84x for standalones."*
- **Turnkey Sensitivity Tool for Adjoa:** If anyone in the room suggests a different cutoff year during the meeting (like 1995 or 2005), Adjoa can run `python streamvault_tool.py --sensitivity` live and display the updated table in 20 milliseconds.
