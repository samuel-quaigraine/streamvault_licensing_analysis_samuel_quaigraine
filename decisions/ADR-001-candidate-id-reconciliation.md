# ADR-001: Candidate ID Ingestion, Dynamic Empty Row Detection, and 100% Reconciliation

- **Status:** Accepted
- **Date:** October 31, 2026
- **Decision Owner:** Samuel Quaigraine

---

## 1. The Context & The Problem
The candidate list of 127 movie IDs (`id_list.csv`) was not a clean file. It was assembled over four years from three conflicting sources: Adjoa's evaluation tracker, an old spreadsheet inherited from Kwame's predecessor, and a batch emailed by a studio licensing desk.

Nobody had cleaned it up. When we opened it, we found:
- An entirely blank line (line 69).
- A negative number (`-1` on line 30).
- A literal text string (`'N/A'` on line 111).
- An external IMDb code (`tt0468569` on line 95) instead of a numeric TMDb ID.
- Six movie IDs entered twice (exact duplicates).
- Five old IDs that returned `404 Not Found` because studios had retired them.

A naive pipeline would either crash on the blank row or quietly drop records without telling anyone. But during a $14M board meeting, if Kwame says he started with 127 titles and ends with 112, Finance will ask: *"What happened to the missing 15 titles?"* If Kwame cannot explain every single row, he loses credibility immediately.

---

## 2. The Decision We Made
We built a strict, dynamic two-part auditing engine (Station 1: The Bouncer in `pipeline/extract.py`, verified by the Pre-Load QA Gate in `pipeline/checks.py`):

1. **Dynamic Door Scanner (No Hardcoded Line Numbers)**:
   The code inspects every single line dynamically. It scans for blank or whitespace-only rows, checks whether values can be converted to positive integers, tracks repeated ticket numbers using a tracking set, and logs the exact line number and reason for every drop.
2. **The 404 Missing Box**:
   When TMDb confirms an ID no longer exists, the pipeline puts it in a permanent file (`dead_ids.json`) and manifest log rather than crashing.
3. **100% Accounting Guarantee**:
   Every single one of the 127 rows is mathematically accounted for:
   `127 Raw Candidates = 112 Verified Films + 15 Accounted-For Drops`

---

## 3. Other Options We Considered and Rejected

### Option A: Silently drop bad rows using standard `dropna()` and `drop_duplicates()`
- **What it would do:** Filter out bad rows silently in one or two lines of code.
- **Why we rejected it:** This creates an invisible gap. If 15 titles vanish with no audit trail, Kwame cannot defend the numbers in the room.

### Option B: Stop and crash the program on the first bad row
- **What it would do:** Stop the script immediately with an error when it sees line 30 (`-1`) or line 69 (blank).
- **Why we rejected it:** Kwame is unavailable for questions before the board review. The brief explicitly states the pipeline must run from start to finish without needing manual file edits.

---

## 4. The 6-Stage Reconciliation Funnel
Every single row is tracked across 6 clear stages:

| Stage | Rows Remaining | Change | What Happened |
|---|---|---|---|
| **1. Raw CSV Input** | **127** | 0 | The starting candidate list from `id_list.csv`. |
| **2. Dynamic Format Check** | **124** | -3 | Dynamically removed blank line 69, negative ID `-1`, and `'N/A'` text. |
| **3. External ID Resolution** | **123** | -1 | IMDb code `tt0468569` resolved to TMDb ID `155` (*The Dark Knight*), which was already on line 2. |
| **4. Exact Deduplication** | **117** | -6 | Removed repeated movie IDs (`155`, `278`, `550`, `603`, `680`, `1891`). |
| **5. Live Catalog 404s** | **112** | -5 | Five retired IDs (`7733901`, `8471293`, `8471294`, `9412887`, `9412888`) placed in the Missing Box. |
| **6. Final Verified Catalog** | **112** | 0 | Exactly 112 clean, verified commercial releases ready for analysis. |

---

## 5. What This Means for Kwame and Adjoa
- **100% Defense Against Finance**: Kwame has a crystal-clear, 1-page paper trail showing where every title went.
- **Turnkey Scaling for Next Year**: Next year, when Adjoa runs the pipeline on 500 titles, any blank lines, duplicate rows, or retired IDs will be caught dynamically, audited, and logged without her touching a line of code.
