"""
Visual chart generation script for StreamVault Content Acquisition Analysis.
Generates 5 high-resolution trend charts saved to docs/images/:
1. era_trends_box_office.png: Release Year vs. Worldwide Gross (1970-2020)
2. franchise_vs_standalone_roi.png: Median and Mean Return-on-Cost Comparison
3. top_franchises_revenue.png: Highest-Grossing Franchise Collections
4. budget_vs_revenue_multiples.png: Production Budget vs. Box Office Gross
5. ratings_vs_return.png: Audience Score vs. Commercial Return Multiple
"""

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==============================================================================
# BLOCK: File Paths & Output Directory Setup
# What it does: Resolves project folders and ensures docs/images/ exists to store PNGs.
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
DOCS_IMAGES_DIR = PROJECT_ROOT / "docs" / "images"
DOCS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# BLOCK: Visual Styling Configuration
# What it does: Configures clean whitegrid styling, font settings, and high DPI.
# ==============================================================================
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'Arial'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300


def load_data():
    """
    BLOCK: Load Analytical Outputs
    What it does: Reads the verified clean_films.csv and summary_kpis.csv files from output/.
    """
    films_path = OUTPUT_DIR / "clean_films.csv"
    kpi_path = OUTPUT_DIR / "summary_kpis.csv"

    if not films_path.exists():
        raise FileNotFoundError(f"Clean films file missing at: {films_path}")
    if not kpi_path.exists():
        raise FileNotFoundError(f"KPI summary file missing at: {kpi_path}")

    films_df = pd.read_csv(films_path)
    kpis_df = pd.read_csv(kpi_path)
    return films_df, kpis_df


def chart_1_era_trends(films_df):
    """
    BLOCK: Chart 1 - Box Office Gross Over Time (1970 - 2020)
    What it does: Plots release year vs box office gross for all candidate titles,
    highlighting the post-2000 volume explosion and addressing Finance VP Yaw's concern.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    # Separate franchises from standalones
    franchises = films_df[films_df["is_franchise"]]
    standalones = films_df[~films_df["is_franchise"]]

    # Plot franchise titles in navy blue circles
    ax.scatter(
        franchises["release_year"],
        franchises["revenue"] / 1e6,
        color="#1f77b4",
        alpha=0.75,
        s=70,
        label="Franchise Title",
        edgecolors="none"
    )

    # Plot standalone titles in coral red triangles
    ax.scatter(
        standalones["release_year"],
        standalones["revenue"] / 1e6,
        color="#d62728",
        alpha=0.85,
        s=85,
        marker="^",
        label="Standalone Title",
        edgecolors="black",
        linewidths=0.5
    )

    # Highlight Finance's year 2000 cutoff boundary
    ax.axvline(x=2000, color="#2ca02c", linestyle="--", linewidth=2, label="Year 2000 Era Boundary (Finance Split)")

    # Title and labels
    ax.set_title("StreamVault Candidate Titles: Worldwide Gross Over Time (1970 - 2020)", fontsize=14, pad=15, fontweight="bold")
    ax.set_xlabel("Release Year", fontsize=11, fontweight="bold")
    ax.set_ylabel("Worldwide Box Office Gross ($ Millions USD)", fontsize=11, fontweight="bold")
    ax.set_xlim(1965, 2022)
    ax.set_ylim(-50, 3100)

    # Explanatory callout for Finance
    ax.text(
        2002, 2800,
        "Post-2000 Modern Era:\nBox office scale triples;\nFranchise dominance accelerates",
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#e8f4f8", edgecolor="#1f77b4")
    )

    ax.legend(loc="upper left", frameon=True)
    plt.tight_layout()

    out_file = DOCS_IMAGES_DIR / "era_trends_box_office.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"  [Created] {out_file.name}")


def chart_2_roi_comparison(kpis_df):
    """
    BLOCK: Chart 2 - Franchise vs. Standalone Return Multiple Comparison
    What it does: Plots side-by-side bar charts comparing median commercial returns
    for franchises vs standalones across both time windows (All-Years vs. 2000-Onward).
    """
    fig, ax = plt.subplots(figsize=(9, 5.5))

    # Parse numeric ROI values from formatted strings like '5.62x'
    kpi_clean = kpis_df.copy()
    kpi_clean["median_roi_num"] = kpi_clean["Median_Return_on_Cost"].str.replace("x", "").astype(float)
    kpi_clean["mean_roi_num"] = kpi_clean["Mean_Return_on_Cost"].str.replace("x", "").astype(float)

    # Filter to the two key windows
    all_years = kpi_clean[kpi_clean["Era_Window"] == "All-Years"].set_index("Group")
    post_2000 = kpi_clean[kpi_clean["Era_Window"] == "2000-Onward"].set_index("Group")

    x_labels = ["All-Years (Full Catalog)", "2000-Onward (Modern Era)"]
    x = np.arange(len(x_labels))
    width = 0.35

    # Franchise vs Standalone median bars
    franchise_medians = [all_years.loc["Franchise", "median_roi_num"], post_2000.loc["Franchise", "median_roi_num"]]
    standalone_medians = [all_years.loc["Standalone", "median_roi_num"], post_2000.loc["Standalone", "median_roi_num"]]

    rects1 = ax.bar(x - width/2, franchise_medians, width, label="Franchise Bundles (Median)", color="#1f77b4")
    rects2 = ax.bar(x + width/2, standalone_medians, width, label="Standalone Hits (Median)", color="#ff7f0e")

    # Annotate numeric values on top of bars
    for rect in rects1:
        h = rect.get_height()
        ax.annotate(f'{h:.2f}x',
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 4), textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold', color="#1f77b4")

    for rect in rects2:
        h = rect.get_height()
        ax.annotate(f'{h:.2f}x',
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 4), textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold', color="#d95f02")

    ax.set_title("Commercial Capital Efficiency: Franchise vs. Standalone Return Multiple", fontsize=13, pad=15, fontweight="bold")
    ax.set_ylabel("Median Return-on-Cost Multiple (Revenue / Budget)", fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontsize=11, fontweight="bold")
    ax.set_ylim(0, 7.5)
    ax.legend(loc="upper right", frameon=True)

    # Key takeaway callout banner
    ax.text(
        0.5, 6.7,
        "Recommendation Holds: Franchises lead in both eras (+1.78x All-Time, +1.21x Post-2000)",
        ha="center", fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="square,pad=0.4", facecolor="#eef8ea", edgecolor="#2ca02c")
    )

    plt.tight_layout()
    out_file = DOCS_IMAGES_DIR / "franchise_vs_standalone_roi.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"  [Created] {out_file.name}")


def chart_3_top_franchises(films_df):
    """
    BLOCK: Chart 3 - Top Franchise Ecosystems by Cumulative Box Office
    What it does: Plots horizontal bar chart showing top 10 franchise universes by total box office.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    # Group by collection name
    franchises = films_df[films_df["is_franchise"] & films_df["collection_name"].notna()]
    f_grouped = franchises.groupby("collection_name").agg(
        total_rev=("revenue", "sum"),
        film_count=("movie_id", "count"),
        median_roi=("return_on_cost", "median")
    ).reset_index().sort_values(by="total_rev", ascending=True).tail(10)

    # Strip redundant 'Collection' text for clear display
    display_names = [name.replace(" Collection", "") for name in f_grouped["collection_name"]]

    # Horizontal bar plot
    y_pos = np.arange(len(display_names))
    bars = ax.barh(y_pos, f_grouped["total_rev"] / 1e9, color="#2b5c8f", height=0.65)

    # Annotate gross, title count, and median ROI on bars
    for idx, bar in enumerate(bars):
        w = bar.get_width()
        n_films = f_grouped.iloc[idx]["film_count"]
        roi = f_grouped.iloc[idx]["median_roi"]
        ax.text(
            w + 0.1, bar.get_y() + bar.get_height()/2,
            f"${w:.2f}B ({n_films} films, {roi:.1f}x ROI)",
            va='center', fontsize=9, fontweight='bold', color="#2b5c8f"
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(display_names, fontsize=10, fontweight="bold")
    ax.set_xlabel("Total Global Box Office ($ Billions USD)", fontsize=11, fontweight="bold")
    ax.set_title("Top 10 Franchise Acquisition Candidates by Total Gross", fontsize=13, pad=15, fontweight="bold")
    ax.set_xlim(0, 9.5)

    plt.tight_layout()
    out_file = DOCS_IMAGES_DIR / "top_franchises_revenue.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"  [Created] {out_file.name}")


def chart_4_budget_vs_revenue(films_df):
    """
    BLOCK: Chart 4 - Production Budget vs. Worldwide Gross
    What it does: Plots budget vs revenue with breakeven (1x) and commercial hit (2.5x)
    threshold lines to show capital efficiency across investment tiers.
    """
    fig, ax = plt.subplots(figsize=(9.5, 6))

    # Scatter points
    franchises = films_df[films_df["is_franchise"]]
    standalones = films_df[~films_df["is_franchise"]]

    ax.scatter(franchises["budget"] / 1e6, franchises["revenue"] / 1e6, color="#1f77b4", alpha=0.7, s=65, label="Franchise Entry")
    ax.scatter(standalones["budget"] / 1e6, standalones["revenue"] / 1e6, color="#d62728", alpha=0.85, s=80, marker="^", label="Standalone Title")

    # Guide lines: 1x (Breakeven), 2.5x (Commercial Hit), 5.0x (Outsized Hit)
    max_budget = 400
    b_vals = np.linspace(0, max_budget, 100)

    ax.plot(b_vals, 1.0 * b_vals, color="gray", linestyle=":", label="1.0x (Theatrical Breakeven)")
    ax.plot(b_vals, 2.5 * b_vals, color="#2ca02c", linestyle="--", label="2.5x (Commercial Hit Line)")
    ax.plot(b_vals, 5.0 * b_vals, color="#9467bd", linestyle="-.", label="5.0x (Outsized Blockbuster Line)")

    ax.set_title("Capital Investment vs. Box Office Return: Candidate Multiples", fontsize=13, pad=15, fontweight="bold")
    ax.set_xlabel("Production Budget ($ Millions USD)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Worldwide Box Office Gross ($ Millions USD)", fontsize=11, fontweight="bold")
    ax.set_xlim(-10, 420)
    ax.set_ylim(-50, 3100)

    ax.legend(loc="upper left", frameon=True)
    plt.tight_layout()

    out_file = DOCS_IMAGES_DIR / "budget_vs_revenue_multiples.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"  [Created] {out_file.name}")


def chart_5_ratings_vs_return(films_df):
    """
    BLOCK: Chart 5 - Audience Rating vs. Return on Cost Multiple
    What it does: Plots TMDb vote average against return multiple, illustrating that
    high audience reception (>7.5) effectively protects downside capital risk.
    """
    fig, ax = plt.subplots(figsize=(9, 5.5))

    # Filter out extreme 30x outliers for clean axis scaling
    filtered = films_df[films_df["return_on_cost"] <= 18].copy()

    f_sub = filtered[filtered["is_franchise"]]
    s_sub = filtered[~filtered["is_franchise"]]

    ax.scatter(f_sub["vote_average"], f_sub["return_on_cost"], color="#1f77b4", alpha=0.75, s=60, label="Franchise (Commercial Consistency)")
    ax.scatter(s_sub["vote_average"], s_sub["return_on_cost"], color="#d62728", alpha=0.85, s=80, marker="^", label="Standalone (Prestige / High Rating)")

    # Mean rating benchmark lines
    ax.axvline(x=films_df[films_df["is_franchise"]]["vote_average"].mean(), color="#1f77b4", linestyle="--", alpha=0.6, label="Franchise Mean Rating (7.46)")
    ax.axvline(x=films_df[~films_df["is_franchise"]]["vote_average"].mean(), color="#d62728", linestyle="--", alpha=0.6, label="Standalone Mean Rating (8.37)")

    ax.set_title("Critical Reception vs. Commercial Return on Investment", fontsize=13, pad=15, fontweight="bold")
    ax.set_xlabel("Audience Rating Score (TMDb 0 - 10 scale)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Return on Cost Multiple (Revenue / Budget)", fontsize=11, fontweight="bold")
    ax.set_xlim(6.0, 9.0)
    ax.set_ylim(0, 18)

    ax.legend(loc="upper left", frameon=True)
    plt.tight_layout()

    out_file = DOCS_IMAGES_DIR / "ratings_vs_return.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"  [Created] {out_file.name}")


def main():
    # ==========================================================================
    # BLOCK: Main Execution Routine
    # What it does: Runs data loading and generates all 5 charts sequentially.
    # ==========================================================================
    print("=" * 70)
    print("GENERATING VISUAL TREND CHARTS (docs/images/)")
    print("=" * 70)

    films_df, kpis_df = load_data()

    chart_1_era_trends(films_df)
    chart_2_roi_comparison(kpis_df)
    chart_3_top_franchises(films_df)
    chart_4_budget_vs_revenue(films_df)
    chart_5_ratings_vs_return(films_df)

    print("=" * 70)
    print("All 5 trend charts successfully generated in docs/images/")
    print("=" * 70)


if __name__ == "__main__":
    main()
