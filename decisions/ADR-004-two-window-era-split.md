# ADR-004: Two-Window Era Split (All-Years vs. 2000-Onward)

- **Status:** Accepted
- **Date:** October 31, 2026
- **Decision Owner:** Samuel Quaigraine

---

## 1. The Context & The Problem
In the boardroom, **Finance VP Yaw** strongly distrusts theatrical numbers from before the year 2000. He points out that historical inflation, currency exchange shifts, and legacy reporting methods make older box office figures unreliable.

At the same time, half of Kwame's acquisitions team passionately believes that older evergreen classics (*Star Wars*, *The Godfather*, *Pulp Fiction*) offer massive return-on-cost value that modern $200M blockbusters cannot match.

If we only show pre-2000 numbers, Yaw will reject the analysis on the spot. But if we quietly filter out older films without telling anyone, we drop 41 iconic titles (over a third of our catalog) and hide valuable data.

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
| **Franchise Hit Rate (>= 2.5x)** | **94.8%** | **95.2%** | Almost zero commercial flops |
| **Standalone Hit Rate (>= 2.5x)** | **75.0%** | **87.5%** | Higher risk of underperforming |
| **Does the Recommendation Flip?** | **NO** | **NO** | **Franchises win in both eras** |

Even when Adjoa tests alternative cutoff years between 1990 and 2015 using our scenario tool, franchises consistently maintain a **1.2x to 1.8x return advantage** over standalones.

---

## 4. Other Options We Considered and Rejected

### Option A: Show only 2000-onward data to keep Finance happy
- **What it would do:** Filter out all films released before January 1, 2000 before running calculations.
- **Why we rejected it:** It throws away 41 titles, including franchise anchors like the original *Star Wars* trilogy and top-tier standalones like *The Shawshank Redemption*.

### Option B: Show all years and bury Finance's concern in a footnote
- **What it would do:** Present one combined table and add an asterisk mentioning inflation.
- **Why we rejected it:** Footnoting an objection that a board member has explicitly raised is a guaranteed way to lose the room. Addressing Yaw's mandate directly in the presentation disarms his objection before he even speaks.

---

## 5. What This Means for Kwame and Adjoa
- **Kwame Controls the Room:** Kwame can present the All-Years numbers, then immediately switch to the 2000-Onward view and say: *"Even under Finance's strictest criteria, franchise bundles still deliver a 5.05x return versus 3.84x for standalones."*
- **Turnkey Sensitivity Tool for Adjoa:** If anyone in the room suggests a different cutoff year during the meeting (like 1995 or 2005), Adjoa can run `python streamvault_tool.py --sensitivity` live and display the updated table in 20 milliseconds.
