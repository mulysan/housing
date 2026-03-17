"""
analysis_extended.py
====================
Extended analysis pipeline:
  - All prices in USD (1 USD = 3.5 NIS, 2018-2023 average)
  - English city names throughout
  - Market access (Donaldson-Hornbeck framework)
  - Bivariate OLS, multivariate OLS, and MA regression tables
  - New figures: English labels, USD prices, MA plots, coefficient forest plot

Outputs:
  data/processed/maps/scatter_all_metrics_en.png
  data/processed/maps/walkability_vs_price_en.png
  data/processed/maps/market_access_vs_price.png
  data/processed/maps/log_ma_vs_log_price.png
  data/processed/maps/market_access_bars.png
  data/processed/maps/correlation_heatmap_en.png
  data/processed/maps/coef_plot.png
  data/processed/regression_results.json
  data/processed/analysis_data.csv
"""

import os, json, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAPS_DIR = os.path.join(BASE_DIR, "data", "processed", "maps")
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
os.makedirs(MAPS_DIR, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────

NIS_TO_USD = 1.0 / 3.5   # average NIS/USD over 2018-2023

METRICS = [
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
    "walkability_index":     "Walkability Index\n(0-100)",
}

METRIC_LABELS_SHORT = {
    "junction_density":      "Junction Density",
    "street_density_km_km2": "Street Density",
    "dead_end_ratio":        "Dead-End Ratio",
    "circuity_avg":          "Circuity",
    "amenity_density":       "Amenity Density",
    "walkability_index":     "Walkability Index",
    "market_access":         "Market Access",
}

# Hebrew -> English city names (exact strings from the CSV)
EN_NAMES = {
    "\u05ea\u05dc \u05d0\u05d1\u05d9\u05d1 -\u05d9\u05e4\u05d5": "Tel Aviv-Jaffa",
    "\u05d1\u05d9\u05ea \u05e9\u05de\u05e9":                      "Beit Shemesh",
    "\u05de\u05d5\u05d3\u05d9\u05e2\u05d9\u05df-\u05de\u05db\u05d1\u05d9\u05dd-\u05e8\u05e2\u05d5\u05ea": "Modi'in",
    "\u05e8\u05e2\u05e0\u05e0\u05d4":                             "Ra'anana",
    "\u05db\u05e4\u05e8 \u05e1\u05d1\u05d0":                      "Kfar Sava",
    "\u05d7\u05d3\u05e8\u05d4":                                    "Hadera",
    "\u05d4\u05e8\u05e6\u05dc\u05d9\u05d9\u05d4":                  "Herzliya",
    "\u05d0\u05e9\u05e7\u05dc\u05d5\u05df":                        "Ashkelon",
    "\u05e8\u05d7\u05d5\u05d1\u05d5\u05ea":                        "Rehovot",
    "\u05d1\u05e0\u05d9 \u05d1\u05e8\u05e7":                       "Bnei Brak",
    "\u05d1\u05ea \u05d9\u05dd":                                    "Bat Yam",
    "\u05d0\u05e9\u05d3\u05d5\u05d3":                              "Ashdod",
    "\u05d7\u05d5\u05dc\u05d5\u05df":                              "Holon",
    "\u05e8\u05de\u05ea \u05d2\u05df":                             "Ramat Gan",
    "\u05e8\u05d0\u05e9\u05d5\u05df \u05dc\u05e6\u05d9\u05d5\u05df": "Rishon LeZion",
    "\u05d1\u05d0\u05e8 \u05e9\u05d1\u05e2":                       "Be'er Sheva",
    "\u05e0\u05ea\u05e0\u05d9\u05d4":                              "Netanya",
    "\u05e4\u05ea\u05d7 \u05ea\u05e7\u05d5\u05d5\u05d4":           "Petah Tikva",
    "\u05d7\u05d9\u05e4\u05d4":                                    "Haifa",
    "\u05d9\u05e8\u05d5\u05e9\u05dc\u05d9\u05dd":                  "Jerusalem",
}

# City coordinates (lat, lon)
CITY_COORDS = {
    "Tel Aviv-Jaffa":  (32.0853, 34.7818),
    "Beit Shemesh":    (31.7478, 34.9888),
    "Modi'in":         (31.8988, 34.9997),
    "Ra'anana":        (32.1848, 34.8708),
    "Kfar Sava":       (32.1748, 34.9077),
    "Hadera":          (32.4342, 34.9190),
    "Herzliya":        (32.1663, 34.8439),
    "Ashkelon":        (31.6688, 34.5742),
    "Rehovot":         (31.8928, 34.8113),
    "Bnei Brak":       (32.0835, 34.8338),
    "Bat Yam":         (32.0186, 34.7520),
    "Ashdod":          (31.8011, 34.6495),
    "Holon":           (32.0104, 34.7740),
    "Ramat Gan":       (32.0684, 34.8248),
    "Rishon LeZion":   (31.9730, 34.7925),
    "Be'er Sheva":     (31.2516, 34.7913),
    "Netanya":         (32.3215, 34.8532),
    "Petah Tikva":     (32.0840, 34.8878),
    "Haifa":           (32.7940, 34.9896),
    "Jerusalem":       (31.7683, 35.2137),
}

# City populations (thousands, ~2020, CBS)
CITY_POP = {
    "Tel Aviv-Jaffa":  460,
    "Beit Shemesh":    120,
    "Modi'in":         102,
    "Ra'anana":         82,
    "Kfar Sava":       101,
    "Hadera":          104,
    "Herzliya":         99,
    "Ashkelon":        145,
    "Rehovot":         150,
    "Bnei Brak":       204,
    "Bat Yam":         155,
    "Ashdod":          234,
    "Holon":           200,
    "Ramat Gan":       164,
    "Rishon LeZion":   261,
    "Be'er Sheva":     215,
    "Netanya":         232,
    "Petah Tikva":     261,
    "Haifa":           285,
    "Jerusalem":       952,
}

SELF_DIST_KM = 7.0   # approximate intra-city travel distance for MA self-term


# ── Statistics helpers ─────────────────────────────────────────────────────

def stars(p):
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return ""


def ols(y, X_raw):
    """
    OLS with analytic standard errors.
    y      : 1-D array (n,)
    X_raw  : 2-D array (n, k) WITHOUT intercept
    Returns dict: coef, se, tstat, pval, r2, adj_r2, n
    """
    n = len(y)
    X = np.column_stack([np.ones(n), np.asarray(X_raw)])
    k = X.shape[1]
    try:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
    except Exception:
        nans = np.full(k, np.nan)
        return dict(coef=nans, se=nans, tstat=nans, pval=np.ones(k),
                    r2=np.nan, adj_r2=np.nan, n=n)
    resid  = y - X @ beta
    sigma2 = np.sum(resid ** 2) / max(n - k, 1)
    try:
        var_b = sigma2 * np.linalg.inv(X.T @ X)
        se    = np.sqrt(np.abs(np.diag(var_b)))
    except np.linalg.LinAlgError:
        se = np.full(k, np.nan)
    tstat  = beta / np.where(se > 0, se, np.nan)
    pval   = 2 * stats.t.sf(np.abs(tstat), df=max(n - k, 1))
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2     = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    adj_r2 = 1 - (1 - r2) * (n - 1) / max(n - k, 1) if r2 is not np.nan else np.nan
    return dict(coef=beta, se=se, tstat=tstat, pval=pval,
                r2=r2, adj_r2=adj_r2, n=n)


# ── Geography helpers ──────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2)**2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def compute_market_access(cities, theta=1.0):
    """
    MA_i = sum_{j} Pop_j / d_{ij}^theta
    Own-city contribution uses self_dist = SELF_DIST_KM.
    Returns dict {city -> MA value}.
    """
    ma = {}
    for ci in cities:
        if ci not in CITY_COORDS:
            ma[ci] = np.nan
            continue
        lat_i, lon_i = CITY_COORDS[ci]
        acc = CITY_POP.get(ci, 0) / (SELF_DIST_KM ** theta)   # own-city
        for cj in cities:
            if cj == ci or cj not in CITY_COORDS:
                continue
            d = haversine_km(lat_i, lon_i, *CITY_COORDS[cj])
            d = max(d, 0.5)
            acc += CITY_POP.get(cj, 0) / (d ** theta)
        ma[ci] = acc
    return ma


# ── Data loading ───────────────────────────────────────────────────────────

def load_and_prepare():
    path = os.path.join(PROC_DIR, "merged_housing_urbanism.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")

    # English names
    df["en_name"] = df["city_name"].apply(
        lambda x: EN_NAMES.get(str(x).strip(), str(x).strip()))

    # USD conversion
    df["median_price_usd"] = df["median_price"] * NIS_TO_USD
    df["mean_price_usd"]   = df["mean_price"]   * NIS_TO_USD

    # Deduplicate: keep row with highest amenity_density per city
    df = (df.sort_values("amenity_density", ascending=False)
            .drop_duplicates(subset="city_name", keep="first")
            .reset_index(drop=True))

    # Market access
    ma_dict = compute_market_access(df["en_name"].tolist())
    df["market_access"] = df["en_name"].map(ma_dict)
    df["log_ma"]        = np.log(df["market_access"])

    print(f"Dataset ready: {len(df)} cities")
    return df


# ── Regression analysis ────────────────────────────────────────────────────

def run_regressions(df):
    """
    Returns a dict with:
      bivariate  : {metric -> result dict}
      multivariate: {label  -> result dict}
      ma_models  : {label  -> result dict}
    """
    price_col  = "median_price_usd"
    log_price  = np.log(df[price_col])
    results    = {}

    # ── Bivariate ────────────────────────────────────────────────────────
    bivariate = {}
    for metric in METRICS + ["market_access"]:
        sub = df[[metric, price_col]].dropna()
        if len(sub) < 5:
            continue
        x  = sub[metric].values
        y  = sub[price_col].values
        ly = np.log(y)

        r_ll  = ols(y,  x.reshape(-1, 1))          # level ~ level
        r_lp  = ols(ly, x.reshape(-1, 1))          # log   ~ level
        if x.min() > 0:
            r_ll2 = ols(ly, np.log(x).reshape(-1, 1))  # log   ~ log
        else:
            r_ll2 = dict(coef=[np.nan, np.nan], se=[np.nan, np.nan],
                         pval=[np.nan, np.nan], r2=np.nan)

        sx, sy = np.std(x, ddof=1), np.std(y, ddof=1)
        bivariate[metric] = {
            "n":         int(r_ll["n"]),
            # level-level
            "beta":      float(r_ll["coef"][1]),
            "se":        float(r_ll["se"][1]),
            "p":         float(r_ll["pval"][1]),
            "r2":        float(r_ll["r2"]),
            # log-level
            "lp_beta":   float(r_lp["coef"][1]),
            "lp_se":     float(r_lp["se"][1]),
            "lp_p":      float(r_lp["pval"][1]),
            "lp_r2":     float(r_lp["r2"]),
            # log-log
            "ll_beta":   float(r_ll2["coef"][1]),
            "ll_se":     float(r_ll2["se"][1]),
            "ll_p":      float(r_ll2["pval"][1]),
            "ll_r2":     float(r_ll2["r2"]),
            # standardised (for forest plot)
            "beta_std":  float(r_ll["coef"][1] * sx / sy) if sy > 0 else np.nan,
            "se_std":    float(r_ll["se"][1]   * sx / sy) if sy > 0 else np.nan,
        }
    results["bivariate"] = bivariate

    # ── Multivariate: log(price) on combinations ──────────────────────────
    multi_specs = [
        ("M1: Street + Amenity",
            ["street_density_km_km2", "amenity_density"]),
        ("M2: Street + Amenity + Junction",
            ["street_density_km_km2", "amenity_density", "junction_density"]),
        ("M3: Walkability only",
            ["walkability_index"]),
        ("M4: Walkability + Amenity",
            ["walkability_index", "amenity_density"]),
        ("M5: All significant",
            ["street_density_km_km2", "amenity_density",
             "junction_density", "walkability_index"]),
    ]
    multi = {}
    for label, preds in multi_specs:
        sub = df[preds + [price_col]].dropna()
        y   = np.log(sub[price_col].values)
        X   = sub[preds].values
        r   = ols(y, X)
        multi[label] = {
            "predictors": preds,
            "coef":       [float(c) for c in r["coef"]],
            "se":         [float(s) for s in r["se"]],
            "pval":       [float(p) for p in r["pval"]],
            "r2":         float(r["r2"]),
            "adj_r2":     float(r["adj_r2"]),
            "n":          int(r["n"]),
        }
    results["multivariate"] = multi

    # ── Market-access models ───────────────────────────────────────────────
    ma_specs = [
        ("MA1: log(MA) only",
            ["log_ma"]),
        ("MA2: log(MA) + Walkability",
            ["log_ma", "walkability_index"]),
        ("MA3: log(MA) + Amenity",
            ["log_ma", "amenity_density"]),
        ("MA4: log(MA) + Street",
            ["log_ma", "street_density_km_km2"]),
        ("MA5: log(MA) + Street + Amenity",
            ["log_ma", "street_density_km_km2", "amenity_density"]),
    ]
    ma_models = {}
    for label, preds in ma_specs:
        sub = df[preds + [price_col]].dropna()
        y   = np.log(sub[price_col].values)
        X   = sub[preds].values
        r   = ols(y, X)
        ma_models[label] = {
            "predictors": preds,
            "coef":       [float(c) for c in r["coef"]],
            "se":         [float(s) for s in r["se"]],
            "pval":       [float(p) for p in r["pval"]],
            "r2":         float(r["r2"]),
            "adj_r2":     float(r["adj_r2"]),
            "n":          int(r["n"]),
        }
    results["ma_models"] = ma_models
    return results


# ── Figure helpers ─────────────────────────────────────────────────────────

def _fmt_price(v, _=None):
    if v < 1e6:
        return f"${v/1e3:.0f}K"
    return f"${v/1e6:.2f}M"


def _annotate(ax, subset, xcol, ycol, fontsize=5.5):
    for _, row in subset.iterrows():
        ax.annotate(
            row["en_name"], (row[xcol], row[ycol]),
            fontsize=fontsize, ha="left", va="bottom",
            xytext=(2, 2), textcoords="offset points", alpha=0.78)


# ── Individual figures ─────────────────────────────────────────────────────

def plot_scatter_all_en(df):
    """6-panel scatter: each urbanism metric vs. USD median price."""
    price_col = "median_price_usd"
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    for ax, metric in zip(axes.flatten(), METRICS):
        sub = df[["en_name", metric, price_col]].dropna()
        x, y = sub[metric].values, sub[price_col].values
        ax.scatter(x, y, s=65, alpha=0.82, color="#1565C0",
                   edgecolors="white", linewidth=0.5)
        if len(sub) >= 3:
            slope, intercept, r, p, _ = stats.linregress(x, y)
            xfit = np.linspace(x.min(), x.max(), 100)
            ax.plot(xfit, slope * xfit + intercept, color="#C62828",
                    linewidth=1.8, linestyle="--", alpha=0.85)
            sig = stars(p)
            ax.text(0.97, 0.05, f"r = {r:.2f}{sig}",
                    transform=ax.transAxes, ha="right", fontsize=9,
                    color="#C62828" if abs(r) > 0.3 else "#757575",
                    fontweight="bold" if sig else "normal")
        _annotate(ax, sub, metric, price_col)
        ax.set_xlabel(METRIC_LABELS[metric], fontsize=9)
        if ax in axes[:, 0]:
            ax.set_ylabel("Median Apartment Price (USD)", fontsize=9)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(_fmt_price))
        ax.tick_params(labelsize=8)
        ax.grid(True, alpha=0.22, linewidth=0.5)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        "Urbanism Metrics vs. Median Apartment Price — Israeli Cities (2018–2023, USD)",
        fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out = os.path.join(MAPS_DIR, "scatter_all_metrics_en.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


def plot_walkability_en(df):
    """Walkability vs. USD price with English labels."""
    price_col = "median_price_usd"
    sub = df[["en_name", "walkability_index", price_col]].dropna()
    fig, ax = plt.subplots(figsize=(11, 7))
    sc = ax.scatter(sub["walkability_index"], sub[price_col], s=85,
                    alpha=0.87, c=sub[price_col], cmap="YlOrRd",
                    edgecolors="#333333", linewidth=0.5)
    cb = fig.colorbar(sc, ax=ax)
    cb.set_label("Median Price (USD)", fontsize=9)
    cb.ax.yaxis.set_major_formatter(plt.FuncFormatter(_fmt_price))
    x, y = sub["walkability_index"].values, sub[price_col].values
    slope, intercept, r, p, _ = stats.linregress(x, y)
    xfit = np.linspace(x.min(), x.max(), 100)
    ax.plot(xfit, slope * xfit + intercept, color="#C62828", linewidth=2,
            linestyle="--", label=f"r = {r:.2f}  (p = {p:.3f})")
    ax.legend(fontsize=10)
    _annotate(ax, sub, "walkability_index", price_col, fontsize=7.5)
    ax.set_xlabel("Walkability Index (0–100)", fontsize=11)
    ax.set_ylabel("Median Apartment Price (USD)", fontsize=11)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(_fmt_price))
    ax.set_title("Walkability Index vs. Median Apartment Price — Israeli Cities",
                 fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.22)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = os.path.join(MAPS_DIR, "walkability_vs_price_en.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


def plot_market_access(df):
    """Market access (level) vs. USD price."""
    price_col = "median_price_usd"
    sub = df[["en_name", "market_access", price_col]].dropna()
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.scatter(sub["market_access"], sub[price_col], s=75, alpha=0.85,
               color="#2E7D32", edgecolors="white", linewidth=0.5)
    x, y = sub["market_access"].values, sub[price_col].values
    slope, intercept, r, p, _ = stats.linregress(x, y)
    xfit = np.linspace(x.min(), x.max(), 100)
    ax.plot(xfit, slope * xfit + intercept, color="#C62828", linewidth=2,
            linestyle="--", label=f"r = {r:.2f}  (p = {p:.3f})")
    ax.legend(fontsize=10)
    _annotate(ax, sub, "market_access", price_col, fontsize=7.5)
    ax.set_xlabel("Market Access  MA = sum(Pop_j / d_ij)  [pop. thousands / km, theta=1]",
                  fontsize=9)
    ax.set_ylabel("Median Apartment Price (USD)", fontsize=11)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(_fmt_price))
    ax.set_title("Market Access vs. Median Apartment Price — Israeli Cities",
                 fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.22)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = os.path.join(MAPS_DIR, "market_access_vs_price.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


def plot_log_ma_vs_log_price(df):
    """Log–log: market access vs. USD price."""
    price_col = "median_price_usd"
    sub = df[["en_name", "market_access", price_col]].dropna()
    lx  = np.log(sub["market_access"].values)
    ly  = np.log(sub[price_col].values)
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.scatter(lx, ly, s=75, alpha=0.85, color="#2E7D32",
               edgecolors="white", linewidth=0.5)
    slope, intercept, r, p, _ = stats.linregress(lx, ly)
    xfit = np.linspace(lx.min(), lx.max(), 100)
    ax.plot(xfit, slope * xfit + intercept, color="#C62828", linewidth=2,
            linestyle="--",
            label=f"elasticity = {slope:.3f}  (p = {p:.3f})  r = {r:.2f}")
    ax.legend(fontsize=10)
    for i, row in sub.reset_index(drop=True).iterrows():
        ax.annotate(row["en_name"], (lx[i], ly[i]),
                    fontsize=7, alpha=0.8, xytext=(3, 2),
                    textcoords="offset points")
    ax.set_xlabel("log(Market Access)", fontsize=11)
    ax.set_ylabel("log(Median Apartment Price, USD)", fontsize=11)
    ax.set_title("Log Market Access vs. Log Apartment Price — Israeli Cities",
                 fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.22)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = os.path.join(MAPS_DIR, "log_ma_vs_log_price.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


def plot_market_access_bars(df):
    """Side-by-side bar charts: MA ranking and price ranking."""
    price_col = "median_price_usd"
    sub = df[["en_name", "market_access", price_col]].dropna()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
    # MA bars
    s1 = sub.sort_values("market_access")
    cmap = plt.cm.YlGn(np.linspace(0.25, 0.9, len(s1)))
    ax1.barh(s1["en_name"], s1["market_access"], color=cmap,
             edgecolor="white", linewidth=0.4)
    ax1.set_xlabel("Market Access  (pop. thousands / km)", fontsize=9)
    ax1.set_title("Market Access by City", fontsize=11, fontweight="bold")
    ax1.grid(True, axis="x", alpha=0.25)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.tick_params(labelsize=8)
    # Price bars
    s2 = sub.sort_values(price_col)
    cmap2 = plt.cm.YlOrRd(np.linspace(0.25, 0.9, len(s2)))
    ax2.barh(s2["en_name"], s2[price_col], color=cmap2,
             edgecolor="white", linewidth=0.4)
    ax2.xaxis.set_major_formatter(plt.FuncFormatter(_fmt_price))
    ax2.set_xlabel("Median Apartment Price (USD)", fontsize=9)
    ax2.set_title("Median Apartment Price by City", fontsize=11, fontweight="bold")
    ax2.grid(True, axis="x", alpha=0.25)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.tick_params(labelsize=8)
    fig.suptitle(
        "Market Access and Housing Prices — Israeli Cities (2018–2023)",
        fontsize=12, fontweight="bold")
    fig.tight_layout()
    out = os.path.join(MAPS_DIR, "market_access_bars.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


def plot_correlation_heatmap_en(df):
    """Updated Pearson/Spearman heatmap including market access."""
    price_col = "median_price_usd"
    all_m = METRICS + ["market_access"]
    res = {}
    for m in all_m:
        sub = df[[m, price_col]].dropna()
        if len(sub) < 5:
            continue
        rp, pp = stats.pearsonr(sub[m], sub[price_col])
        rs, ps = stats.spearmanr(sub[m], sub[price_col])
        res[m] = dict(pr=rp, pp=pp, sr=rs, sp=ps)

    labels = [METRIC_LABELS_SHORT.get(m, m) for m in res]
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, (col_r, col_p, title) in [
        (axes[0], ("pr", "pp", "Pearson r")),
        (axes[1], ("sr", "sp", "Spearman rho")),
    ]:
        metrics_list = list(res.keys())
        vals  = [res[m][col_r] for m in metrics_list]
        lbls  = [METRIC_LABELS_SHORT.get(m, m) for m in metrics_list]
        cols  = ["#C62828" if v < 0 else "#1565C0" for v in vals]
        bars  = ax.barh(lbls, vals, color=cols, edgecolor="white", linewidth=0.5)
        for bar, m in zip(bars, metrics_list):
            s = stars(res[m][col_p])
            if s:
                xv = bar.get_width()
                ax.text(xv + (0.02 if xv >= 0 else -0.02),
                        bar.get_y() + bar.get_height() / 2,
                        s, va="center",
                        ha="left" if xv >= 0 else "right",
                        fontsize=11, fontweight="bold")
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_xlim(-1, 1)
        ax.set_xlabel("Correlation coefficient", fontsize=9)
        ax.set_title(f"{title}\n(* p<0.05, ** p<0.01, *** p<0.001)", fontsize=10)
        ax.tick_params(labelsize=9)
        ax.grid(True, axis="x", alpha=0.25, linewidth=0.5)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        "Correlation with Median Apartment Price: Urbanism Metrics and Market Access",
        fontsize=11, fontweight="bold")
    fig.tight_layout()
    out = os.path.join(MAPS_DIR, "correlation_heatmap_en.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


def plot_coef_forest(bivariate_results):
    """Forest plot of standardized bivariate OLS coefficients."""
    all_m    = METRICS + ["market_access"]
    present  = [m for m in all_m if m in bivariate_results]
    labels   = [METRIC_LABELS_SHORT.get(m, m) for m in present]
    betas    = [bivariate_results[m]["beta_std"] for m in present]
    ses      = [bivariate_results[m]["se_std"]   for m in present]
    pvals    = [bivariate_results[m]["p"]         for m in present]

    fig, ax = plt.subplots(figsize=(9, 6))
    y_pos   = np.arange(len(present))
    colors  = ["#C62828" if p < 0.05 else "#BDBDBD" for p in pvals]
    ci      = 1.96 * np.array([s if not np.isnan(s) else 0 for s in ses])
    betas_a = np.array([b if not np.isnan(b) else 0 for b in betas])

    ax.barh(y_pos, betas_a, xerr=ci, color=colors, edgecolor="white",
            linewidth=0.5, error_kw=dict(ecolor="#333333", capsize=4, lw=1.2))
    ax.axvline(0, color="black", linewidth=1.0)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Standardized OLS Coefficient  (beta * std_x / std_y)", fontsize=10)
    ax.set_title(
        "Bivariate OLS: Standardized Coefficients — Urbanism Metrics vs. Apartment Price\n"
        "Red = significant at p < 0.05; error bars = 95% CI",
        fontsize=10, fontweight="bold")
    ax.grid(True, axis="x", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)

    # Legend patches
    import matplotlib.patches as mpatches
    ax.legend(handles=[
        mpatches.Patch(color="#C62828", label="p < 0.05"),
        mpatches.Patch(color="#BDBDBD", label="p >= 0.05"),
    ], fontsize=9, loc="lower right")

    fig.tight_layout()
    out = os.path.join(MAPS_DIR, "coef_plot.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    df  = load_and_prepare()
    reg = run_regressions(df)

    # Save analysis data
    df.to_csv(os.path.join(PROC_DIR, "analysis_data.csv"), index=False,
              encoding="utf-8-sig")

    # Save regression results (JSON-serialisable)
    with open(os.path.join(PROC_DIR, "regression_results.json"), "w") as f:
        json.dump(reg, f, indent=2, allow_nan=True)

    # Generate figures
    plot_scatter_all_en(df)
    plot_walkability_en(df)
    plot_market_access(df)
    plot_log_ma_vs_log_price(df)
    plot_market_access_bars(df)
    plot_correlation_heatmap_en(df)
    plot_coef_forest(reg["bivariate"])

    # Print summary
    print("\n--- Bivariate correlations (Pearson, level-level) ---")
    for m, r in reg["bivariate"].items():
        sig = stars(r["p"])
        print(f"  {m:30s}  beta={r['beta']:10.2f}  p={r['p']:.4f} {sig}  R2={r['r2']:.3f}")

    print("\n--- Market access (log-log) ---")
    biv = reg["bivariate"].get("market_access", {})
    if biv:
        print(f"  elasticity={biv['ll_beta']:.3f}  p={biv['ll_p']:.4f}  R2={biv['ll_r2']:.3f}")

    return df, reg


if __name__ == "__main__":
    main()
