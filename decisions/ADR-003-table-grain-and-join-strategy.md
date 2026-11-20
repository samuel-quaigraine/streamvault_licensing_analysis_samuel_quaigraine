# ADR-003: Strict Table Grain Boundaries and Preventing the $4.7 Trillion Mistake

- **Status:** Accepted
- **Date:** October 31, 2026
- **Decision Owner:** Samuel Quaigraine

---

## 1. The Context & The Problem
When TMDb sends data for a movie, it sends back a complex, nested package. Inside that package is a single box office number (like $1 billion for *The Dark Knight*), but also a list of dozens of actors and hundreds of crew members.

In data engineering, the most dangerous mistake you can make with this kind of data is a **fan-out merge**:
- In our catalog, films have an average of **70 actors** in their cast list.
- If an engineer takes the movie data, flattens the actors, and joins them together into one big flat table *before* calculating total box office, the movie's revenue gets repeated on every single actor's row!
- A $1 billion movie is suddenly counted 70 times as $70 billion.
- Across our 112 titles, the real worldwide box office of **$67.1 billion** would be multiplied into an absurd **$4.7 Trillion**!

If Kwame walked into the board meeting with a slide showing $4.7 Trillion in box office, the board would immediately throw out his presentation.

---

## 2. The Decision We Made
We established strict relational grain boundaries in `pipeline/transform.py` (`flatten_movie_details_and_credits`, Station 2: The Labeler) and enforced them with automated guards in `pipeline/validate.py`:

1. **Films Analytical Table (Grain: 1 row per film — 112 rows)**:
   Every movie appears exactly once. All financial metrics (budgets, box office, profits, ROI multiples, and commercial tiers) are calculated exclusively on this table.
2. **Cast Table (Grain: 1 row per film per actor — 7,827 rows)**:
   Kept separate. Used only when evaluating actor billing orders and star power.
3. **Crew Table (Grain: 1 row per film per crew member — 24,932 rows)**:
   Kept separate. Used only when evaluating directors and writers.
4. **Guarded Joins (`safe_merge_one_to_one`)**:
   Any time the pipeline joins data back to the film table, it uses pandas `validate="one_to_one"` and asserts `len(merged) == len(films)`. If a duplicate key ever tries to multiply rows, the pipeline raises an immediate error rather than silently corrupting the numbers.

---

## 3. Other Options We Considered and Rejected

### Option A: Put everything into one single wide table
- **What it would do:** Repeat the movie title, budget, and revenue on every actor and crew row so users could see everything in one sheet.
- **Why we rejected it:** It is a disaster waiting to happen. Anyone running a simple `sum()` on the revenue column would produce an inflated number 70 times higher than reality.

### Option B: Don't collect cast and crew data at all
- **What it would do:** Ingest only the film details and ignore cast and crew completely.
- **Why we rejected it:** Kwame specifically asked for talent negotiation levers. His team needs to know which directors and lead actors consistently deliver profitable hits so they can negotiate better licensing terms with studios.

---

## 4. What This Means for Kwame and StreamVault
- **100% Mathematical Trust:** Kwame can stand behind every single dollar figure in the presentation. There is zero double-counting and zero revenue inflation.
- **Clean Talent Insights:** Kwame's negotiators can review proven director track records (like Christopher Nolan and Peter Jackson) without distorting the underlying financial returns of the films themselves.

---

## 5. How This Protects Adjoa Next Year (500 Titles)
Next year, when the list expands to 500 titles and cast credits grow to over 35,000 rows, the `safe_merge_one_to_one` guard will continuously enforce the boundary. Adjoa will never have to worry about accidental fan-out errors.
