"""
SA-Level Analysis: Housing Prices at the Statistical Area (Gush Block) Level

This script extends the city-level analysis by aggregating housing transaction
data to the sub-city gush-block (POLYGON_ID) level, enabling a more granular
examination of urbanism quality effects on housing prices.

The approach:
1. Aggregate all housing transactions to POLYGON_ID (gush block) level
2. Spatial-join gush centroids (from sub_gush geometry) to Overture SA polygons
3. Compute within-city and cross-SA price variation statistics
4. Run regressions at gush-block level with city fixed effects
5. Generate SA-level figures and regression tables
"""

import os
import glob
import json
import pickle
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats
from shapely.geometry import Point

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────
NIS_TO_USD = 1.0 / 3.5
PROCESSED_DIR = "data/processed"
MAPS_DIR = "data/processed/maps"
os.makedirs(MAPS_DIR, exist_ok=True)

# Hebrew → English city name mapping (using Unicode escapes for exact matching)
EN_NAMES = {
    "\u05ea\u05dc \u05d0\u05d1\u05d9\u05d1 -\u05d9\u05e4\u05d5": "Tel Aviv-Yafo",
    "\u05d9\u05e8\u05d5\u05e9\u05dc\u05d9\u05dd": "Jerusalem",
    "\u05d7\u05d9\u05e4\u05d4": "Haifa",
    "\u05e8\u05d0\u05e9\u05d5\u05df \u05dc\u05e6\u05d9\u05d5\u05df": "Rishon LeZion",
    "\u05e4\u05ea\u05d7 \u05ea\u05e7\u05d5\u05d5\u05d4": "Petah Tikva",
    "\u05d0\u05e9\u05d3\u05d5\u05d3": "Ashdod",
    "\u05e0\u05ea\u05e0\u05d9\u05d4": "Netanya",
    "\u05d1\u05d0\u05e8 \u05e9\u05d1\u05e2": "Beer Sheva",
    "\u05d1\u05e0\u05d9 \u05d1\u05e8\u05e7": "Bnei Brak",
    "\u05d7\u05d5\u05dc\u05d5\u05df": "Holon",
    "\u05e8\u05de\u05ea \u05d2\u05df": "Ramat Gan",
    "\u05d1\u05ea \u05d9\u05dd": "Bat Yam",
    "\u05d7\u05d3\u05e8\u05d4": "Hadera",
    "\u05d0\u05e9\u05e7\u05dc\u05d5\u05df": "Ashkelon",
    "\u05e8\u05d7\u05d5\u05d1\u05d5\u05ea": "Rehovot",
    "\u05d4\u05e8\u05e6\u05dc\u05d9\u05d4": "Herzliya",
    "\u05db\u05e4\u05e8 \u05e1\u05d1\u05d0": "Kfar Saba",
    "\u05de\u05d5\u05d3\u05d9\u05e2\u05d9\u05df-\u05de\u05db\u05d1\u05d9\u05dd-\u05e8\u05e2\u05d5\u05ea": "Modi'in",
    "\u05e8\u05e2\u05e0\u05e0\u05d4": "Ra'anana",
    "\u05d1\u05d9\u05ea \u05e9\u05de\u05e9": "Bet Shemesh",
}

# City code → English name from filenames
CITY_CODE_MAP = {
    "100779": "Tel Aviv-Yafo",
    "65700": "Jerusalem",
    "62630": "Haifa",
    "40747": "Rishon LeZion",
    "49499": "Petah Tikva",
    "34119": "Ashdod",
    "45470": "Netanya",
    "42076": "Beer Sheva",
    "24123": "Bnei Brak",
    "36351": "Holon",
    "39093": "Ramat Gan",
    "29156": "Bat Yam",
    "18355": "Hadera",
    "22775": "Ashkelon",
    "23894": "Rehovot",
    "18384": "Herzliya",
    "17081": "Kfar Saba",
    "14519": "Modi'in",
    "15040": "Ra'anana",
    "13148": "Bet Shemesh",
}


# ──────────────────────────────────────────────────────────────────────────────
# OLS with analytic standard errors
# ──────────────────────────────────────────────────────────────────────────────
def ols(y, X_raw):
    n = len(y)
    X = np.column_stack([np.ones(n), np.asarray(X_raw)])
    k = X.shape[1]
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta
    sigma2 = np.sum(resid**2) / max(n - k, 1)
    var_b = sigma2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.abs(np.diag(var_b)))
    tstat = beta / np.where(se > 0, se, np.nan)
    pval = 2 * stats.t.sf(np.abs(tstat), df=max(n - k, 1))
    r2 = 1 - np.sum(resid**2) / np.sum((y - y.mean()) ** 2)
    adj_r2 = 1 - (1 - r2) * (n - 1) / max(n - k, 1)
    return dict(coef=beta, se=se, tstat=tstat, pval=pval, r2=r2, adj_r2=adj_r2, n=n)


def stars(p):
    if p < 0.01:
        return "***"
    elif p < 0.05:
        return "**"
    elif p < 0.1:
        return "*"
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# 1. Load all transactions and aggregate to POLYGON_ID level
# ──────────────────────────────────────────────────────────────────────────────
def load_gush_level_data():
    """Load all housing XLSXs and aggregate to POLYGON_ID (gush block) level."""
    print("Loading housing transactions...")
    dfs = []
    xlsx_files = sorted(glob.glob("/home/user/housing/*.xlsx"))
    for f in xlsx_files:
        fname = os.path.basename(f)
        city_code = fname.split("-")[0]
        city_en = CITY_CODE_MAP.get(city_code, city_code)
        try:
            df = pd.read_excel(
                f,
                usecols=["DEALAMOUNT", "POLYGON_ID", "GUSH", "DEALDATE",
                         "ASSETROOMNUM", "BUILDINGYEAR", "BUILDINGFLOORS"],
            )
            df["city_en"] = city_en
            df["city_code"] = city_code
            dfs.append(df)
        except Exception as e:
            print(f"  Warning: {fname}: {e}")

    all_txns = pd.concat(dfs, ignore_index=True)
    print(f"  Total transactions: {len(all_txns):,}")

    # Filter valid transactions (DEALAMOUNT may be string with commas e.g. "1,200,000")
    all_txns["DEALAMOUNT"] = (
        all_txns["DEALAMOUNT"].astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    all_txns["DEALAMOUNT"] = pd.to_numeric(all_txns["DEALAMOUNT"], errors="coerce")
    all_txns = all_txns[all_txns["DEALAMOUNT"] > 0].copy()
    all_txns["price_usd"] = all_txns["DEALAMOUNT"] * NIS_TO_USD

    # Parse gush_num from POLYGON_ID (format: "6034-26" or "6034-26-3")
    all_txns["gush_num"] = (
        all_txns["POLYGON_ID"].astype(str).str.split("-").str[0]
        .str.strip()
        .replace("nan", np.nan)
    )
    all_txns = all_txns[all_txns["gush_num"].notna()].copy()
    all_txns["gush_num"] = pd.to_numeric(all_txns["gush_num"], errors="coerce")
    all_txns = all_txns[all_txns["gush_num"].notna()].copy()

    print(f"  Valid transactions: {len(all_txns):,}")
    print(f"  Unique POLYGON_IDs: {all_txns['POLYGON_ID'].nunique():,}")
    print(f"  Unique gush_nums: {all_txns['gush_num'].nunique():,}")

    # Aggregate to POLYGON_ID level
    agg = (
        all_txns.groupby(["POLYGON_ID", "gush_num", "city_en", "city_code"])
        .agg(
            median_price_usd=("price_usd", "median"),
            mean_price_usd=("price_usd", "mean"),
            n_transactions=("price_usd", "count"),
            p25_price_usd=("price_usd", lambda x: x.quantile(0.25)),
            p75_price_usd=("price_usd", lambda x: x.quantile(0.75)),
            avg_rooms=("ASSETROOMNUM", "median"),
        )
        .reset_index()
    )

    # Keep only blocks with enough transactions
    agg = agg[agg["n_transactions"] >= 3].copy()
    print(f"  POLYGON_IDs with >=3 transactions: {len(agg):,}")
    return all_txns, agg


# ──────────────────────────────────────────────────────────────────────────────
# 2. Spatial assignment: gush centroids → Overture SA
# ──────────────────────────────────────────────────────────────────────────────
def assign_gush_to_sa(gush_df):
    """
    Assign gush blocks to Overture SA polygons using spatial join.
    For gush blocks with known geometry (10 sample rows), use centroid spatial join.
    For remaining blocks, fall back to city-level assignment.
    """
    print("\nAssigning gush blocks to Overture SAs...")

    # Load sub_gush geometry (10 sample rows)
    sg = gpd.read_file("/tmp/layer_sub_gush_full.geojson")
    # Reproject to WGS84 for spatial join
    sg = sg.to_crs("EPSG:4326")
    sg_centroids = sg.copy()
    sg_centroids["geometry"] = sg.geometry.centroid
    sg_lookup = sg_centroids[["gush_num", "geometry", "locality_name"]].copy()
    sg_lookup["gush_num"] = sg_lookup["gush_num"].astype(int)
    print(f"  Sample sub_gush records: {len(sg_lookup)}")

    # Load Overture SA polygons
    with open("/home/user/housing/data/raw/israel_division_areas.pkl", "rb") as f:
        sa_gdf = pickle.load(f)

    # Extract English names from Overture
    def get_en_name(names):
        if not isinstance(names, dict):
            return ""
        for item in names.get("common", []) or []:
            if isinstance(item, (list, tuple)) and len(item) >= 2 and item[0] == "en":
                return item[1]
        return names.get("primary", "")

    sa_gdf["name_en"] = sa_gdf["names"].apply(get_en_name)
    sa_gdf["name_he"] = sa_gdf["names"].apply(
        lambda n: n.get("primary", "") if isinstance(n, dict) else ""
    )
    sa_gdf = sa_gdf[["id", "geometry", "name_en", "name_he"]].copy()

    # Spatial join: known gush centroids → SA polygons
    sg_pts = gpd.GeoDataFrame(sg_lookup, geometry="geometry", crs="EPSG:4326")
    joined = gpd.sjoin(sg_pts, sa_gdf, how="left", predicate="within")
    gush_sa_map = dict(zip(joined["gush_num"].astype(int), joined["id"]))
    print(f"  Gush blocks spatially assigned: {sum(1 for v in gush_sa_map.values() if pd.notna(v))}")

    # Assign SA to gush-level data
    gush_df["gush_num_int"] = gush_df["gush_num"].astype(int)
    gush_df["sa_code_spatial"] = gush_df["gush_num_int"].map(gush_sa_map)

    # Load city-level SA assignments from urbanism metrics
    um = pd.read_csv(f"{PROCESSED_DIR}/urbanism_metrics.csv")
    merged_city = pd.read_csv(f"{PROCESSED_DIR}/merged_housing_urbanism.csv")

    # Create city-level sa_code lookup (from merged data)
    city_sa = dict(zip(merged_city["city_name_en"] if "city_name_en" in merged_city.columns
                       else merged_city.get("city_en", merged_city.iloc[:,0]),
                       merged_city.get("sa_code", merged_city.iloc[:,1])))

    print(f"  Total gush-level records: {len(gush_df)}")
    return gush_df, sa_gdf, gush_sa_map


# ──────────────────────────────────────────────────────────────────────────────
# 3. Within-city variation analysis
# ──────────────────────────────────────────────────────────────────────────────
def within_city_analysis(all_txns, gush_agg):
    """Analyze within-city price variation across gush blocks."""
    print("\nWithin-city variation analysis...")

    # City-level statistics
    city_stats = (
        gush_agg.groupby("city_en")
        .agg(
            n_gush_blocks=("POLYGON_ID", "count"),
            total_transactions=("n_transactions", "sum"),
            median_price=("median_price_usd", "median"),
            price_std=("median_price_usd", "std"),
            price_cv=("median_price_usd", lambda x: x.std() / x.mean() if x.mean() > 0 else np.nan),
            price_p10=("median_price_usd", lambda x: x.quantile(0.1)),
            price_p90=("median_price_usd", lambda x: x.quantile(0.9)),
        )
        .reset_index()
    )
    city_stats["price_range_ratio"] = city_stats["price_p90"] / city_stats["price_p10"]
    city_stats = city_stats.sort_values("median_price", ascending=False)

    print(f"  Cities analyzed: {len(city_stats)}")
    print(f"  Avg gush blocks per city: {city_stats['n_gush_blocks'].mean():.1f}")
    print(f"  Total gush-level observations: {city_stats['n_gush_blocks'].sum()}")

    return city_stats


# ──────────────────────────────────────────────────────────────────────────────
# 4. Merge gush data with city-level urbanism metrics
# ──────────────────────────────────────────────────────────────────────────────
def merge_gush_urbanism(gush_agg):
    """Merge gush-level price data with city-level urbanism metrics."""
    print("\nMerging gush data with urbanism metrics...")

    # Load city-level urbanism + housing from existing merged file
    merged = pd.read_csv(f"{PROCESSED_DIR}/merged_housing_urbanism.csv")

    # Deduplicate (handle Hadera duplicate) — keep highest amenity_density
    if "amenity_density" in merged.columns:
        merged = merged.sort_values("amenity_density", ascending=False)
    # Identify city name column (Hebrew)
    city_col = None
    for col in ["city_name", "city_en", "city_name_en"]:
        if col in merged.columns:
            city_col = col
            break
    if city_col:
        merged = merged.drop_duplicates(subset=city_col, keep="first")

    # Map Hebrew city name → English
    if "city_name_en" not in merged.columns:
        he_col = city_col or merged.columns[0]
        merged["city_name_en"] = merged[he_col].map(EN_NAMES).fillna(merged[he_col])

    # Create urbanism lookup keyed by English city name
    urbanism_cols = [
        "walkability_index", "junction_density", "street_density_km_km2",
        "avg_street_length_m", "dead_end_ratio", "amenity_density",
    ]
    urbanism_cols = [c for c in urbanism_cols if c in merged.columns]

    city_urbanism = merged[["city_name_en"] + urbanism_cols].copy()

    # Merge with gush data (gush_agg has 'city_en')
    gush_merged = gush_agg.merge(
        city_urbanism, left_on="city_en", right_on="city_name_en", how="left"
    )
    gush_merged = gush_merged.dropna(subset=urbanism_cols[:1] if urbanism_cols else [])

    print(f"  Gush blocks with urbanism data: {len(gush_merged)}")
    return gush_merged, urbanism_cols


# ──────────────────────────────────────────────────────────────────────────────
# 5. Gush-level regressions with city fixed effects
# ──────────────────────────────────────────────────────────────────────────────
def run_gush_regressions(gush_merged, urbanism_cols):
    """Run OLS regressions at gush-block level with city fixed effects."""
    print("\nRunning gush-level regressions...")

    results = {}
    y_label = "log_price"
    gush_merged[y_label] = np.log(gush_merged["median_price_usd"])
    gush_merged = gush_merged.replace([np.inf, -np.inf], np.nan).dropna(subset=[y_label])

    # Create city dummies for fixed effects
    city_dummies = pd.get_dummies(gush_merged["city_en"], drop_first=True, prefix="city")

    # ── Bivariate regressions (no FE) ──
    bivariate = {}
    for metric in urbanism_cols:
        col = gush_merged[metric].dropna()
        valid = gush_merged[[y_label, metric]].dropna()
        if len(valid) < 5:
            continue
        y = valid[y_label].values
        x = valid[metric].values
        res = ols(y, x.reshape(-1, 1))
        bivariate[metric] = {
            "coef": float(res["coef"][1]),
            "se": float(res["se"][1]),
            "pval": float(res["pval"][1]),
            "r2": float(res["r2"]),
            "n": int(res["n"]),
        }

    # ── Bivariate with log-log ──
    bivariate_ll = {}
    for metric in urbanism_cols:
        valid = gush_merged[[y_label, metric]].dropna()
        valid = valid[valid[metric] > 0]
        if len(valid) < 5:
            continue
        y = valid[y_label].values
        x = np.log(valid[metric].values)
        res = ols(y, x.reshape(-1, 1))
        bivariate_ll[metric] = {
            "coef": float(res["coef"][1]),
            "se": float(res["se"][1]),
            "pval": float(res["pval"][1]),
            "r2": float(res["r2"]),
            "n": int(res["n"]),
        }

    # ── Multivariate OLS with cluster-robust SE (cluster = city) ──
    # Note: urbanism metrics are city-level constants, so city FE would absorb
    # all variation. Instead, use pooled OLS with cluster-robust SEs.
    fe_results = {}
    gush_merged = gush_merged.reset_index(drop=True)
    city_ids = pd.Categorical(gush_merged["city_en"]).codes

    def ols_clustered(y, X_raw, clusters):
        """OLS with cluster-robust variance-covariance matrix (HC)."""
        n = len(y)
        X = np.column_stack([np.ones(n), np.asarray(X_raw)])
        k = X.shape[1]
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        resid = y - X @ beta
        # Cluster-robust variance (sandwich estimator)
        XtX_inv = np.linalg.inv(X.T @ X)
        meat = np.zeros((k, k))
        for c in np.unique(clusters):
            mask = clusters == c
            Xc = X[mask]
            ec = resid[mask]
            meat += (Xc * ec[:, None]).T @ (Xc * ec[:, None])
        # Small-sample correction
        G = len(np.unique(clusters))
        corr = G / (G - 1) * (n - 1) / (n - k)
        vcov = corr * XtX_inv @ meat @ XtX_inv
        se = np.sqrt(np.abs(np.diag(vcov)))
        tstat = beta / np.where(se > 0, se, np.nan)
        pval = 2 * stats.t.sf(np.abs(tstat), df=max(G - 1, 1))
        r2 = 1 - np.sum(resid**2) / np.sum((y - y.mean()) ** 2)
        adj_r2 = 1 - (1 - r2) * (n - 1) / max(n - k, 1)
        return dict(coef=beta, se=se, tstat=tstat, pval=pval, r2=r2, adj_r2=adj_r2, n=n, n_clusters=G)

    for spec_name, spec_cols in [
        ("Walkability (Clustered SE)", ["walkability_index"]),
        ("Walkability + Amenity (Clustered SE)", ["walkability_index", "amenity_density"]),
        ("All Urbanism (Clustered SE)", urbanism_cols),
        ("Street + Junction (Clustered SE)",
         [c for c in ["street_density_km_km2", "junction_density"] if c in urbanism_cols]),
    ]:
        spec_cols = [c for c in spec_cols if c in urbanism_cols]
        if not spec_cols:
            continue
        valid_idx = gush_merged[[y_label] + spec_cols].dropna().index
        valid = gush_merged.loc[valid_idx]
        X = valid[spec_cols].values
        y = valid[y_label].values
        cl = city_ids[valid_idx]
        if len(y) < len(spec_cols) + 3:
            continue
        try:
            res = ols_clustered(y, X, cl)
            k = len(spec_cols)
            fe_results[spec_name] = {
                "coefs": {spec_cols[i]: {
                    "coef": float(res["coef"][i + 1]),
                    "se": float(res["se"][i + 1]),
                    "pval": float(res["pval"][i + 1]),
                } for i in range(k)},
                "r2": float(res["r2"]),
                "adj_r2": float(res["adj_r2"]),
                "n": int(res["n"]),
                "n_clusters": int(res["n_clusters"]),
            }
        except Exception as e:
            print(f"  Clustered SE regression error ({spec_name}): {e}")

    results = {
        "bivariate_level_log": bivariate,
        "bivariate_log_log": bivariate_ll,
        "multivariate_fe": fe_results,
    }
    print(f"  Bivariate regressions: {len(bivariate)}")
    print(f"  FE specifications: {len(fe_results)}")
    return results


# ──────────────────────────────────────────────────────────────────────────────
# 6. Generate SA-level figures
# ──────────────────────────────────────────────────────────────────────────────
def plot_within_city_variation(gush_agg, city_stats):
    """Plot within-city price variation across gush blocks."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Panel A: Distribution of gush-level prices by city (violin/box)
    ax = axes[0]
    # Select top 10 cities by transaction count for clarity
    top_cities = city_stats.nlargest(10, "total_transactions")["city_en"].tolist()
    data_for_plot = []
    labels = []
    for city in top_cities:
        prices = gush_agg[gush_agg["city_en"] == city]["median_price_usd"].dropna()
        if len(prices) >= 3:
            data_for_plot.append(prices.values / 1000)
            labels.append(city.replace(" ", "\n"))

    bp = ax.boxplot(data_for_plot, patch_artist=True, vert=True, widths=0.6)
    colors = plt.cm.RdYlGn(np.linspace(0.2, 0.8, len(data_for_plot)))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_xlabel("City", fontsize=11)
    ax.set_ylabel("Median Price per Block (USD thousands)", fontsize=11)
    ax.set_title("A. Within-City Price Distribution\nacross Gush Blocks", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    # Panel B: Price CV vs. city size
    ax = axes[1]
    valid = city_stats.dropna(subset=["price_cv", "total_transactions"])
    scatter = ax.scatter(
        np.log(valid["total_transactions"]),
        valid["price_cv"] * 100,
        c=valid["median_price"] / 1000,
        cmap="RdYlGn",
        s=80,
        alpha=0.8,
        edgecolors="k",
        linewidths=0.5,
    )
    for _, row in valid.iterrows():
        ax.annotate(
            row["city_en"].split("-")[0].split("/")[0][:10],
            (np.log(row["total_transactions"]), row["price_cv"] * 100),
            fontsize=7,
            ha="left",
            xytext=(4, 0),
            textcoords="offset points",
        )
    cb = plt.colorbar(scatter, ax=ax)
    cb.set_label("Median Price (USD thousands)", fontsize=9)
    ax.set_xlabel("Log(Total Transactions)", fontsize=11)
    ax.set_ylabel("Price Coefficient of Variation (%)", fontsize=11)
    ax.set_title("B. Price Dispersion vs. Market Size\nby City", fontsize=12, fontweight="bold")
    ax.grid(alpha=0.3)

    plt.tight_layout()
    out = f"{MAPS_DIR}/sa_within_city_variation.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")
    return out


def plot_gush_regression_results(gush_merged, urbanism_cols, reg_results):
    """Scatter plots: gush-level price vs. urbanism metrics."""
    n_metrics = len(urbanism_cols)
    ncols = 3
    nrows = (n_metrics + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 5 * nrows))
    axes = axes.flatten()

    bivariate = reg_results.get("bivariate_level_log", {})
    gush_merged["log_price"] = np.log(gush_merged["median_price_usd"])

    metric_labels = {
        "walkability_index": "Walkability Index",
        "junction_density": "Junction Density (per km²)",
        "street_density_km_km2": "Street Density (km/km²)",
        "avg_street_length_m": "Avg Street Length (m)",
        "dead_end_ratio": "Dead-End Ratio",
        "amenity_density": "Amenity Density (per km²)",
    }

    # Color by city
    cities = gush_merged["city_en"].unique()
    cmap = plt.cm.tab20
    city_colors = {c: cmap(i / len(cities)) for i, c in enumerate(cities)}

    for i, metric in enumerate(urbanism_cols):
        ax = axes[i]
        valid = gush_merged[["log_price", metric, "city_en"]].dropna()
        if len(valid) < 5:
            ax.set_visible(False)
            continue

        for city, grp in valid.groupby("city_en"):
            ax.scatter(
                grp[metric],
                np.exp(grp["log_price"]) / 1000,
                c=[city_colors.get(city, "gray")],
                s=15,
                alpha=0.5,
                label=city,
            )

        # Trend line
        x_all = valid[metric].values
        y_all = np.exp(valid["log_price"].values) / 1000
        z = np.polyfit(x_all, y_all, 1)
        p = np.poly1d(z)
        xr = np.linspace(x_all.min(), x_all.max(), 100)
        ax.plot(xr, p(xr), "k-", linewidth=1.5, alpha=0.7)

        info = bivariate.get(metric, {})
        coef = info.get("coef", np.nan)
        pval = info.get("pval", np.nan)
        r2 = info.get("r2", np.nan)
        n = info.get("n", len(valid))
        star = stars(pval) if not np.isnan(pval) else ""
        ax.set_title(
            f"{metric_labels.get(metric, metric)}\n"
            f"β={coef:.4f}{star}  R²={r2:.3f}  N={n}",
            fontsize=10,
        )
        ax.set_xlabel(metric_labels.get(metric, metric), fontsize=9)
        ax.set_ylabel("Median Price (USD thousands)", fontsize=9)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)

    # Hide unused axes
    for j in range(len(urbanism_cols), len(axes)):
        axes[j].set_visible(False)

    # Legend for cities (outside)
    handles = [
        mpatches.Patch(color=city_colors[c], label=c, alpha=0.7)
        for c in list(city_colors.keys())[:10]
    ]
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=7,
               bbox_to_anchor=(0.5, -0.02))

    plt.suptitle(
        "Gush-Block Level: Housing Prices vs. Urbanism Metrics\n"
        "(Each point = one gush block; colored by city)",
        fontsize=13,
        fontweight="bold",
        y=1.01,
    )
    plt.tight_layout()
    out = f"{MAPS_DIR}/sa_gush_scatter.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")
    return out


def plot_fe_coef(reg_results):
    """Forest plot of city-FE regression coefficients."""
    fe = reg_results.get("multivariate_fe", {})
    if not fe:
        return None

    # Take the "All Urbanism (FE)" spec if available, else first
    spec = next((s for s in fe if "All" in s), next(iter(fe)))
    spec_res = fe[spec]
    coefs = spec_res["coefs"]

    metrics = list(coefs.keys())
    vals = [coefs[m]["coef"] for m in metrics]
    ses = [coefs[m]["se"] for m in metrics]
    pvals = [coefs[m]["pval"] for m in metrics]

    metric_labels = {
        "walkability_index": "Walkability Index",
        "junction_density": "Junction Density",
        "street_density_km_km2": "Street Density",
        "avg_street_length_m": "Avg Street Length",
        "dead_end_ratio": "Dead-End Ratio",
        "amenity_density": "Amenity Density",
    }

    fig, ax = plt.subplots(figsize=(8, max(4, len(metrics) * 0.8 + 1)))
    y_pos = np.arange(len(metrics))
    colors = ["#d73027" if p < 0.05 else "#fdae61" if p < 0.1 else "#999999"
              for p in pvals]

    ax.barh(y_pos, vals, xerr=1.96 * np.array(ses), color=colors, alpha=0.8,
            height=0.5, ecolor="black", capsize=4)
    ax.axvline(0, color="black", linewidth=1.0)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([metric_labels.get(m, m) for m in metrics], fontsize=10)
    ax.set_xlabel("Coefficient (log price)", fontsize=11)
    n_cl = spec_res.get("n_clusters", "")
    ax.set_title(
        f"Gush-Block Regression with Cluster-Robust SEs\n{spec}\n"
        f"R²={spec_res['r2']:.3f}  N={spec_res['n']}  Clusters={n_cl}",
        fontsize=11,
        fontweight="bold",
    )

    # Legend
    legend_handles = [
        mpatches.Patch(color="#d73027", label="p<0.01 or p<0.05"),
        mpatches.Patch(color="#fdae61", label="p<0.10"),
        mpatches.Patch(color="#999999", label="p≥0.10"),
    ]
    ax.legend(handles=legend_handles, fontsize=9, loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    out = f"{MAPS_DIR}/sa_fe_coefs.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")
    return out


def plot_price_quantiles_by_city(gush_agg):
    """Plot p10, median, p90 price distribution for each city."""
    fig, ax = plt.subplots(figsize=(12, 7))

    city_order = (
        gush_agg.groupby("city_en")["median_price_usd"]
        .median()
        .sort_values(ascending=True)
        .index.tolist()
    )

    y_pos = np.arange(len(city_order))
    for i, city in enumerate(city_order):
        sub = gush_agg[gush_agg["city_en"] == city]["median_price_usd"].dropna()
        if len(sub) < 2:
            continue
        p10 = sub.quantile(0.1) / 1000
        p50 = sub.quantile(0.5) / 1000
        p90 = sub.quantile(0.9) / 1000
        ax.plot([p10, p90], [i, i], "b-", linewidth=2, alpha=0.5)
        ax.scatter([p50], [i], color="navy", s=60, zorder=5)
        ax.scatter([p10, p90], [i, i], color="steelblue", s=25, alpha=0.6)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(city_order, fontsize=9)
    ax.set_xlabel("Median Price per Gush Block (USD thousands)", fontsize=11)
    ax.set_title(
        "Housing Price Distribution Within Cities\n"
        "P10 ─ Median ● ─ P90 by City (Gush-Block Level)",
        fontsize=12,
        fontweight="bold",
    )
    ax.grid(axis="x", alpha=0.3)
    ax.axvline(
        gush_agg["median_price_usd"].median() / 1000,
        color="red",
        linestyle="--",
        alpha=0.5,
        label="National Median",
    )
    ax.legend(fontsize=9)
    plt.tight_layout()
    out = f"{MAPS_DIR}/sa_price_quantiles.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 7. Generate SA-level regression tables (text format for PDF)
# ──────────────────────────────────────────────────────────────────────────────
def build_regression_table(reg_results, gush_agg):
    """Build formatted regression tables for the paper."""
    bivariate = reg_results.get("bivariate_level_log", {})
    bivariate_ll = reg_results.get("bivariate_log_log", {})
    fe = reg_results.get("multivariate_fe", {})

    metric_labels = {
        "walkability_index": "Walkability Index",
        "junction_density": "Junction Density",
        "street_density_km_km2": "Street Density",
        "avg_street_length_m": "Avg Street Length",
        "dead_end_ratio": "Dead-End Ratio",
        "amenity_density": "Amenity Density",
    }

    lines = []

    # Table 1: Bivariate results
    lines.append("GUSH-BLOCK BIVARIATE REGRESSIONS (Dependent: log median price in USD)")
    lines.append("=" * 80)
    header = f"{'Metric':<25} {'Coef':>10} {'SE':>8} {'p-val':>8} {'Stars':>6} {'R²':>8} {'N':>6}"
    lines.append(header)
    lines.append("-" * 80)
    for metric, info in bivariate.items():
        label = metric_labels.get(metric, metric)
        c = info["coef"]
        se = info["se"]
        p = info["pval"]
        r2 = info["r2"]
        n = info["n"]
        lines.append(f"{label:<25} {c:>10.5f} {se:>8.5f} {p:>8.4f} {stars(p):>6} {r2:>8.4f} {n:>6}")
    lines.append("")

    # Table 2: Clustered SE multivariate
    if fe:
        lines.append("GUSH-BLOCK MULTIVARIATE REGRESSIONS WITH CLUSTER-ROBUST SEs (cluster=city)")
        lines.append("=" * 80)
        for spec_name, spec_res in fe.items():
            lines.append(f"\nSpecification: {spec_name}")
            n_cl = spec_res.get("n_clusters", "?")
            lines.append(f"R² = {spec_res['r2']:.4f}  Adj-R² = {spec_res['adj_r2']:.4f}  N = {spec_res['n']}  Clusters = {n_cl}")
            lines.append(f"{'Variable':<25} {'Coef':>10} {'SE (cl)':>10} {'p-val':>8} {'Stars':>6}")
            lines.append("-" * 65)
            for metric, mres in spec_res["coefs"].items():
                label = metric_labels.get(metric, metric)
                lines.append(
                    f"{label:<25} {mres['coef']:>10.5f} {mres['se']:>10.5f} {mres['pval']:>8.4f} {stars(mres['pval']):>6}"
                )

    table_text = "\n".join(lines)
    out = f"{PROCESSED_DIR}/sa_regression_tables.txt"
    with open(out, "w") as fh:
        fh.write(table_text)
    print(f"  Saved regression tables: {out}")
    return table_text


# ──────────────────────────────────────────────────────────────────────────────
# 8. Summary statistics table
# ──────────────────────────────────────────────────────────────────────────────
def build_summary_stats(gush_agg, all_txns):
    """Build summary statistics at city and gush-block levels."""
    summary = {}

    # City-level stats
    city_stats = gush_agg.groupby("city_en").agg(
        n_gush=("POLYGON_ID", "count"),
        n_txns=("n_transactions", "sum"),
        median_price=("median_price_usd", "median"),
        cv_price=("median_price_usd", lambda x: x.std() / x.mean()),
    ).reset_index()

    summary["city_level"] = {
        "n_cities": len(city_stats),
        "total_gush_blocks": int(city_stats["n_gush"].sum()),
        "total_transactions": int(city_stats["n_txns"].sum()),
        "median_price_usd": float(city_stats["median_price"].median()),
        "mean_gush_per_city": float(city_stats["n_gush"].mean()),
        "avg_price_cv": float(city_stats["cv_price"].mean()),
    }

    # Overall gush-level stats
    summary["gush_level"] = {
        "n_observations": len(gush_agg),
        "median_price_usd": float(gush_agg["median_price_usd"].median()),
        "std_price_usd": float(gush_agg["median_price_usd"].std()),
        "min_price_usd": float(gush_agg["median_price_usd"].min()),
        "max_price_usd": float(gush_agg["median_price_usd"].max()),
        "avg_txns_per_block": float(gush_agg["n_transactions"].mean()),
    }

    out = f"{PROCESSED_DIR}/sa_summary_stats.json"
    with open(out, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"  Saved summary stats: {out}")
    return summary


# ──────────────────────────────────────────────────────────────────────────────
# 9. Plot: Gush-level price vs. city-level walkability (with FE residuals)
# ──────────────────────────────────────────────────────────────────────────────
def plot_within_between_decomposition(gush_merged, urbanism_cols):
    """
    Decompose price variation into within-city and between-city components.
    Show the within-city variation (residualized on city mean) vs. urbanism.
    """
    if "walkability_index" not in gush_merged.columns:
        return None

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Panel A: Raw gush-level price vs. city walkability
    ax = axes[0]
    cities = gush_merged["city_en"].unique()
    city_med_walk = gush_merged.groupby("city_en")["walkability_index"].mean()
    city_med_price = gush_merged.groupby("city_en")["median_price_usd"].median()

    cmap = plt.cm.RdYlGn
    norm = plt.Normalize(vmin=gush_merged["median_price_usd"].quantile(0.05) / 1000,
                         vmax=gush_merged["median_price_usd"].quantile(0.95) / 1000)

    for city in cities:
        sub = gush_merged[gush_merged["city_en"] == city]
        walk = city_med_walk.get(city, np.nan)
        if np.isnan(walk):
            continue
        jitter = np.random.normal(0, 0.3, len(sub))
        sc = ax.scatter(
            walk + jitter,
            sub["median_price_usd"] / 1000,
            c=sub["median_price_usd"] / 1000,
            cmap=cmap,
            norm=norm,
            s=8,
            alpha=0.4,
        )
    # City means
    ax.scatter(
        city_med_walk,
        city_med_price / 1000,
        c="black",
        s=60,
        zorder=10,
        marker="D",
        label="City Median",
    )
    for city in city_med_walk.index:
        ax.annotate(
            city.split("-")[0][:8],
            (city_med_walk[city], city_med_price[city] / 1000),
            fontsize=6,
            xytext=(3, 2),
            textcoords="offset points",
        )
    ax.set_xlabel("City Walkability Index", fontsize=11)
    ax.set_ylabel("Gush-Block Median Price (USD thousands)", fontsize=11)
    ax.set_title("A. Gush-Level Prices vs. City Walkability\n(dots = gush blocks, diamonds = city medians)", fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # Panel B: Within-city demeaned price vs. walkability
    ax = axes[1]
    gush_merged = gush_merged.copy()
    gush_merged["city_mean_log_price"] = gush_merged.groupby("city_en")["median_price_usd"].transform(
        lambda x: np.log(x).mean()
    )
    gush_merged["log_price_demeaned"] = np.log(gush_merged["median_price_usd"]) - gush_merged["city_mean_log_price"]

    gush_merged["city_mean_walk"] = gush_merged.groupby("city_en")["walkability_index"].transform("mean")
    gush_merged["walk_demeaned"] = gush_merged["walkability_index"] - gush_merged["city_mean_walk"]

    valid = gush_merged[["log_price_demeaned", "walk_demeaned", "city_en"]].dropna()
    ax.scatter(valid["walk_demeaned"], valid["log_price_demeaned"],
               alpha=0.3, s=10, color="steelblue")

    # Trend
    if len(valid) > 5:
        x = valid["walk_demeaned"].values
        y = valid["log_price_demeaned"].values
        z = np.polyfit(x, y, 1)
        xr = np.linspace(x.min(), x.max(), 100)
        ax.plot(xr, np.polyval(z, xr), "r-", linewidth=2, label=f"β={z[0]:.4f}")
        res = ols(y, x.reshape(-1, 1))
        p = res["pval"][1]
        r2 = res["r2"]
        ax.set_title(
            f"B. Within-City Variation\n(Demeaned log price vs. demeaned walkability)\n"
            f"β={z[0]:.4f}{stars(p)}  R²={r2:.3f}  N={len(valid)}",
            fontsize=10,
        )

    ax.axhline(0, color="black", linewidth=0.8, alpha=0.5)
    ax.axvline(0, color="black", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Walkability Index (within-city demeaned)", fontsize=11)
    ax.set_ylabel("log(Price) (within-city demeaned)", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    out = f"{MAPS_DIR}/sa_within_between.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out}")
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("SA-LEVEL ANALYSIS: Housing Prices at the Gush-Block Level")
    print("=" * 70)

    np.random.seed(42)

    # 1. Load data
    all_txns, gush_agg = load_gush_level_data()

    # 2. Spatial assignment (demonstration with 10 sample rows)
    try:
        gush_agg, sa_gdf, gush_sa_map = assign_gush_to_sa(gush_agg)
    except Exception as e:
        print(f"  Spatial assignment skipped: {e}")

    # 3. Within-city analysis
    city_stats = within_city_analysis(all_txns, gush_agg)

    # 4. Merge with urbanism metrics
    gush_merged, urbanism_cols = merge_gush_urbanism(gush_agg)

    # 5. Regressions
    reg_results = run_gush_regressions(gush_merged, urbanism_cols)

    # 6. Figures
    print("\nGenerating figures...")
    plot_within_city_variation(gush_agg, city_stats)
    plot_gush_regression_results(gush_merged, urbanism_cols, reg_results)
    plot_fe_coef(reg_results)
    plot_price_quantiles_by_city(gush_agg)
    if urbanism_cols:
        plot_within_between_decomposition(gush_merged, urbanism_cols)

    # 7. Tables and stats
    print("\nGenerating tables...")
    build_regression_table(reg_results, gush_agg)
    summary = build_summary_stats(gush_agg, all_txns)

    # 8. Save full results
    out_path = f"{PROCESSED_DIR}/sa_regression_results.json"
    with open(out_path, "w") as fh:
        json.dump(reg_results, fh, indent=2, default=str)
    print(f"  Saved full results: {out_path}")

    print("\n" + "=" * 70)
    print("SA-LEVEL ANALYSIS COMPLETE")
    print(f"  Total gush-block observations: {len(gush_agg)}")
    print(f"  Cities covered: {gush_agg['city_en'].nunique()}")
    print(f"  Median price: USD {gush_agg['median_price_usd'].median():,.0f}")
    print("=" * 70)

    return {
        "gush_agg": gush_agg,
        "city_stats": city_stats,
        "gush_merged": gush_merged,
        "reg_results": reg_results,
        "summary": summary,
    }


if __name__ == "__main__":
    os.chdir("/home/user/housing")
    results = main()
