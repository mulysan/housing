"""
Part 2: Correlate urbanism quality metrics with housing prices.

Loads the 20 city XLSX files, computes median deal amount per city
(filtered to recent years 2018-2023 to capture current market), then
merges with the urbanism_metrics.csv and computes Pearson & Spearman
correlations.

Outputs
-------
  data/processed/housing_prices.csv          – city-level price summary
  data/processed/correlation_results.csv     – correlation table
  data/processed/maps/correlation_heatmap.png
  data/processed/maps/scatter_<metric>.png   – one scatter per metric

Usage
-----
  python analyze_housing_correlation.py
  python analyze_housing_correlation.py --year-min 2015 --year-max 2023
"""

import argparse
import glob
import os
import re
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats

import config

# ── Configuration ─────────────────────────────────────────────────────────────

MAPS_DIR = os.path.join(config.PROCESSED_DIR, "maps")
os.makedirs(MAPS_DIR, exist_ok=True)

METRICS_OF_INTEREST = [
    "junction_density",
    "street_density_km_km2",
    "dead_end_ratio",
    "circuity_avg",
    "amenity_density",
    "walkability_index",
]

METRIC_LABELS = {
    "junction_density":      "Junction Density\n(intersections/km²)",
    "street_density_km_km2": "Street Density\n(km/km²)",
    "dead_end_ratio":        "Dead-End Ratio\n(share)",
    "circuity_avg":          "Circuity\n(ratio)",
    "amenity_density":       "Amenity Density\n(POIs/km²)",
    "walkability_index":     "Walkability Index\n(0–100)",
}

# Mapping from XLSX city_name → metrics sa_name (handles slight name differences)
NAME_MAP = {
    "תל אביב -יפו":         "תל־אביב–יפו",
    "הרצלייה":               "הרצליה",
    "ירושלים":               "מערב ירושלים",   # best match in Overture data
}


# ── Housing price loader ───────────────────────────────────────────────────────

def _parse_amount(val) -> float:
    """Parse DEALAMOUNT which may be a comma-formatted string or numeric."""
    if pd.isna(val):
        return np.nan
    if isinstance(val, (int, float)):
        return float(val)
    # Remove commas and whitespace
    cleaned = re.sub(r"[,\s]", "", str(val))
    try:
        return float(cleaned)
    except ValueError:
        return np.nan


def _parse_year(val) -> float:
    """Extract year from DEALDATE (format DD.MM.YYYY) or DEALDATETIME."""
    if pd.isna(val):
        return np.nan
    s = str(val)
    # Try DD.MM.YYYY
    m = re.search(r"(\d{4})", s)
    if m:
        return float(m.group(1))
    return np.nan


def load_housing_prices(year_min: int = 2018, year_max: int = 2023) -> pd.DataFrame:
    """
    Read all XLSX files, filter to apartment sales in [year_min, year_max],
    and return a DataFrame with one row per city containing price statistics.
    """
    files = sorted(glob.glob(os.path.join(config.BASE_DIR, "*.xlsx")))
    if not files:
        raise FileNotFoundError(f"No XLSX files found in {config.BASE_DIR}")

    rows = []
    for path in files:
        fname = os.path.basename(path)
        muni_code = fname.split("-")[0].strip()

        try:
            df = pd.read_excel(path)
        except Exception as e:
            warnings.warn(f"Cannot read {fname}: {e}")
            continue

        if df.empty:
            continue

        city_name = df["city_name"].iloc[0] if "city_name" in df.columns else muni_code

        # Filter to apartment/dwelling sales only (exclude parking, land, etc.)
        if "DEALNATUREDESCRIPTION" in df.columns:
            df = df[df["DEALNATUREDESCRIPTION"].str.contains("דירה", na=False)]

        # Parse amounts and years
        df = df.copy()
        df["amount"] = df["DEALAMOUNT"].apply(_parse_amount)
        df["year"]   = df["DEALDATE"].apply(_parse_year)

        # Filter by year and valid amounts
        df = df[
            (df["year"] >= year_min) &
            (df["year"] <= year_max) &
            (df["amount"] > 0) &
            df["amount"].notna()
        ]

        if df.empty:
            warnings.warn(f"{city_name}: no valid deals in {year_min}–{year_max}")
            continue

        # Remove extreme outliers (1st and 99th percentile per city)
        lo, hi = df["amount"].quantile(0.01), df["amount"].quantile(0.99)
        df = df[(df["amount"] >= lo) & (df["amount"] <= hi)]

        rows.append({
            "muni_code":      muni_code,
            "city_name":      city_name,
            "n_deals":        len(df),
            "median_price":   df["amount"].median(),
            "mean_price":     df["amount"].mean(),
            "price_per_room": (df["amount"] / df["ASSETROOMNUM"].replace(0, np.nan)).median()
                              if "ASSETROOMNUM" in df.columns else np.nan,
            "year_min":       int(df["year"].min()),
            "year_max":       int(df["year"].max()),
        })

    prices = pd.DataFrame(rows)
    print(f"Loaded housing prices for {len(prices)} cities "
          f"({prices['n_deals'].sum():,} deals, {year_min}–{year_max})")
    return prices


# ── Merge with urbanism metrics ────────────────────────────────────────────────

def merge_data(prices: pd.DataFrame, metrics_path: str) -> pd.DataFrame:
    """
    Merge city-level housing prices with urbanism metrics.
    Uses NAME_MAP to align name variants.
    """
    metrics = pd.read_csv(metrics_path, dtype={"sa_code": str})

    # Apply name mapping to prices
    prices = prices.copy()
    prices["sa_name"] = prices["city_name"].apply(lambda n: NAME_MAP.get(n, n))

    merged = prices.merge(metrics, on="sa_name", how="inner")
    print(f"Matched {len(merged)} cities out of {len(prices)} housing-price cities")

    if len(merged) < len(prices):
        unmatched = prices[~prices["sa_name"].isin(merged["sa_name"])]["city_name"].tolist()
        print(f"  Unmatched cities: {unmatched}")

    return merged


# ── Correlation analysis ───────────────────────────────────────────────────────

def compute_correlations(merged: pd.DataFrame,
                         price_col: str = "median_price") -> pd.DataFrame:
    """Compute Pearson and Spearman correlations for each metric vs. price."""
    results = []
    for metric in METRICS_OF_INTEREST:
        subset = merged[[metric, price_col]].dropna()
        if len(subset) < 4:
            continue
        x, y = subset[metric], subset[price_col]

        pearson_r,  pearson_p  = stats.pearsonr(x, y)
        spearman_r, spearman_p = stats.spearmanr(x, y)

        results.append({
            "metric":      metric,
            "pearson_r":   round(pearson_r,  3),
            "pearson_p":   round(pearson_p,  4),
            "spearman_r":  round(spearman_r, 3),
            "spearman_p":  round(spearman_p, 4),
            "n":           len(subset),
            "significant_pearson":  pearson_p  < 0.05,
            "significant_spearman": spearman_p < 0.05,
        })

    df = pd.DataFrame(results).set_index("metric")
    return df


# ── Visualisation ─────────────────────────────────────────────────────────────

def plot_scatter_grid(merged: pd.DataFrame,
                      price_col: str = "median_price",
                      corr: pd.DataFrame = None,
                      demo: bool = False) -> str:
    """6-panel scatter plot grid: each metric vs. median housing price."""
    ncols, nrows = 3, 2
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 10))

    price_label = "Median Apartment Price (₪)"

    for ax, metric in zip(axes.flatten(), METRICS_OF_INTEREST):
        subset = merged[[metric, price_col, "city_name"]].dropna()
        if subset.empty:
            ax.set_visible(False)
            continue

        x, y = subset[metric], subset[price_col]

        ax.scatter(x, y, alpha=0.75, s=60, color="#2196F3", edgecolors="white", linewidth=0.5)

        # Regression line
        if len(subset) >= 3:
            m_slope, m_intercept, *_ = stats.linregress(x, y)
            xfit = np.linspace(x.min(), x.max(), 100)
            ax.plot(xfit, m_slope * xfit + m_intercept, color="#E53935",
                    linewidth=1.5, linestyle="--", alpha=0.8)

        # Label each point with city name
        for _, row in subset.iterrows():
            ax.annotate(
                row["city_name"],
                (row[metric], row[price_col]),
                fontsize=5.5, ha="left", va="bottom",
                alpha=0.7,
                xytext=(2, 2), textcoords="offset points"
            )

        # Annotation with correlation
        if corr is not None and metric in corr.index:
            r = corr.loc[metric, "pearson_r"]
            p = corr.loc[metric, "pearson_p"]
            sig = "*" if p < 0.05 else ""
            ax.text(0.97, 0.05, f"r = {r:.2f}{sig}",
                    transform=ax.transAxes, ha="right", fontsize=8,
                    color="#E53935" if abs(r) > 0.3 else "gray")

        ax.set_xlabel(METRIC_LABELS[metric], fontsize=8)
        ax.set_ylabel(price_label if ax in axes[:, 0] else "", fontsize=8)
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"₪{v/1e6:.1f}M"))
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3, linewidth=0.5)
        ax.spines[["top", "right"]].set_visible(False)

    suptitle = "Urbanism Metrics vs. Housing Prices – Israeli Cities"
    if demo:
        suptitle += "  [DEMO: synthetic prices]"
    fig.suptitle(suptitle, fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()

    fname = os.path.join(MAPS_DIR, "scatter_all_metrics.png")
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")
    return fname


def plot_correlation_heatmap(corr: pd.DataFrame) -> str:
    """Bar chart / heatmap of Pearson and Spearman r values."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, col, title in [
        (axes[0], "pearson_r",  "Pearson  r"),
        (axes[1], "spearman_r", "Spearman ρ"),
    ]:
        values = corr[col]
        colors = ["#E53935" if v < 0 else "#1E88E5" for v in values]
        edge   = ["#B71C1C" if v < 0 else "#0D47A1" for v in values]

        bars = ax.barh(
            [METRIC_LABELS[m].replace("\n", " ") for m in values.index],
            values,
            color=colors, edgecolor=edge, linewidth=0.8
        )

        # Add significance markers
        for bar, metric in zip(bars, values.index):
            p = corr.loc[metric, col.replace("_r", "_p")]
            marker = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else ""))
            if marker:
                x = bar.get_width()
                ax.text(x + (0.01 if x >= 0 else -0.01), bar.get_y() + bar.get_height() / 2,
                        marker, va="center", ha="left" if x >= 0 else "right",
                        fontsize=10, color="black")

        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_xlim(-1, 1)
        ax.set_xlabel("Correlation coefficient", fontsize=9)
        ax.set_title(f"{title}\n(* p<0.05, ** p<0.01, *** p<0.001)", fontsize=10)
        ax.tick_params(labelsize=8)
        ax.grid(True, axis="x", alpha=0.3, linewidth=0.5)
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle("Correlation: Urbanism Metrics ↔ Median Housing Price",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()

    fname = os.path.join(MAPS_DIR, "correlation_heatmap.png")
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")
    return fname


def plot_walkability_vs_price(merged: pd.DataFrame,
                               price_col: str = "median_price") -> str:
    """Detailed scatter: walkability index vs. price with city labels."""
    subset = merged[["walkability_index", price_col, "city_name"]].dropna()

    fig, ax = plt.subplots(figsize=(10, 7))

    sc = ax.scatter(
        subset["walkability_index"], subset[price_col],
        s=80, alpha=0.85, c=subset[price_col],
        cmap="YlOrRd", edgecolors="#555555", linewidth=0.5
    )
    fig.colorbar(sc, ax=ax, label="Median Price (₪)", format=lambda v, _: f"₪{v/1e6:.1f}M")

    # Regression
    if len(subset) >= 3:
        m, b, r, p, _ = stats.linregress(subset["walkability_index"], subset[price_col])
        xfit = np.linspace(subset["walkability_index"].min(),
                           subset["walkability_index"].max(), 100)
        ax.plot(xfit, m * xfit + b, color="#E53935", linewidth=2,
                linestyle="--", label=f"r = {r:.2f}  (p = {p:.3f})")
        ax.legend(fontsize=9)

    for _, row in subset.iterrows():
        ax.annotate(row["city_name"],
                    (row["walkability_index"], row[price_col]),
                    fontsize=7, alpha=0.8,
                    xytext=(4, 2), textcoords="offset points")

    ax.set_xlabel("Walkability Index (0–100)", fontsize=11)
    ax.set_ylabel("Median Apartment Price (₪)", fontsize=11)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"₪{v/1e6:.1f}M"))
    ax.set_title("Walkability Index vs. Median Housing Price – Israeli Cities",
                 fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fname = os.path.join(MAPS_DIR, "walkability_vs_price.png")
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")
    return fname


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--year-min", type=int, default=2018)
    p.add_argument("--year-max", type=int, default=2023)
    p.add_argument("--price-col", default="median_price",
                   choices=["median_price", "mean_price", "price_per_room"])
    return p.parse_args()


def main():
    args = parse_args()

    # 1. Load housing prices
    prices = load_housing_prices(year_min=args.year_min, year_max=args.year_max)
    prices_path = os.path.join(config.PROCESSED_DIR, "housing_prices.csv")
    prices.to_csv(prices_path, index=False, encoding="utf-8-sig")
    print(f"Saved: {prices_path}")
    print(prices[["city_name", "n_deals", "median_price"]].to_string(index=False))

    # 2. Merge with urbanism metrics
    merged = merge_data(prices, config.METRICS_OUTPUT_FILE)
    if merged.empty:
        print("ERROR: No cities matched between housing data and urbanism metrics.")
        return

    merged_path = os.path.join(config.PROCESSED_DIR, "merged_housing_urbanism.csv")
    merged.to_csv(merged_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved merged data: {merged_path}  ({len(merged)} cities)")

    # 3. Compute correlations
    corr = compute_correlations(merged, price_col=args.price_col)
    corr_path = os.path.join(config.PROCESSED_DIR, "correlation_results.csv")
    corr.to_csv(corr_path, encoding="utf-8-sig")
    print(f"\nCorrelation results ({args.price_col}):")
    print(corr[["pearson_r", "pearson_p", "spearman_r", "spearman_p", "n"]].to_string())

    # 4. Visualise
    print(f"\nSaving plots to: {MAPS_DIR}")
    plot_correlation_heatmap(corr)
    plot_scatter_grid(merged, price_col=args.price_col, corr=corr)
    plot_walkability_vs_price(merged, price_col=args.price_col)

    print("\nDone.")


if __name__ == "__main__":
    main()
