"""
Two-Stage Hedonic Regression for Israeli Housing Prices
=======================================================

Stage 1  (transaction level)
    log(price_usd) ~ log(rooms) + building_age + building_age² + year_FE
                   + POLYGON_ID fixed effects

    Estimation via within-group (demeaning) transformation – no need to
    invert a 50 k-column dummy matrix.
    Output: one FE coefficient α̂_j per gush block j.

Stage 2  (gush-block / city level)
    α̂_j ~ urbanism_metrics_city(j) + ε_j
    (cluster-robust SE by city; also city-aggregated N=20 version)

The key improvement over the current approach:  α̂_j is the PURE LOCATION
premium – stripped of room count, building age, and macro time effects –
so Stage 2 identifies the urbanism–location-quality relationship free of
housing-stock composition bias.
"""

import os
import glob
import json
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

warnings.filterwarnings("ignore")

# ── Constants ────────────────────────────────────────────────────────────────
NIS_TO_USD   = 1.0 / 3.5
PROCESSED_DIR = "data/processed"
MAPS_DIR      = "data/processed/maps"
os.makedirs(MAPS_DIR, exist_ok=True)

MIN_TXN_PER_BLOCK = 5      # minimum transactions to keep a gush block
REF_YEAR          = 2018   # reference year for year FEs

CITY_CODE_MAP = {
    "100779": "Tel Aviv-Jaffa",
    "65700":  "Jerusalem",
    "62630":  "Haifa",
    "40747":  "Rishon LeZion",
    "49499":  "Petah Tikva",
    "34119":  "Ashdod",
    "45470":  "Netanya",
    "42076":  "Be'er Sheva",
    "24123":  "Bnei Brak",
    "36351":  "Holon",
    "39093":  "Ramat Gan",
    "29156":  "Bat Yam",
    "18355":  "Hadera",
    "22775":  "Ashkelon",
    "23894":  "Rehovot",
    "18384":  "Herzliya",
    "17081":  "Kfar Sava",
    "14519":  "Modi'in",
    "15040":  "Ra'anana",
    "13148":  "Beit Shemesh",
}

URBANISM_METRICS = [
    "walkability_index",
    "junction_density",
    "street_density_km_km2",
    "amenity_density",
    "dead_end_ratio",
    "circuity_avg",
]

METRIC_LABELS = {
    "walkability_index":       "Walkability Index (0–100)",
    "junction_density":        "Junction Density (int./km²)",
    "street_density_km_km2":   "Street Density (km/km²)",
    "amenity_density":         "Amenity Density (POIs/km²)",
    "dead_end_ratio":          "Dead-End Ratio",
    "circuity_avg":            "Circuity (ratio)",
}


# ── OLS helpers ───────────────────────────────────────────────────────────────

def ols_plain(y, X_raw):
    """OLS with homoskedastic SEs.  Returns dict."""
    n  = len(y)
    X  = np.column_stack([np.ones(n), np.asarray(X_raw)])
    k  = X.shape[1]
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid  = y - X @ b
    sigma2 = np.sum(resid**2) / max(n - k, 1)
    var_b  = sigma2 * np.linalg.inv(X.T @ X)
    se     = np.sqrt(np.maximum(np.diag(var_b), 0))
    tstat  = b / np.where(se > 0, se, np.nan)
    pval   = 2 * stats.t.sf(np.abs(tstat), df=max(n - k, 1))
    r2     = 1 - np.sum(resid**2) / np.sum((y - y.mean())**2)
    adj_r2 = 1 - (1 - r2) * (n - 1) / max(n - k, 1)
    return dict(b=b, se=se, tstat=tstat, pval=pval,
                r2=r2, adj_r2=adj_r2, n=n, resid=resid)


def ols_clustered(y, X_raw, cluster_ids):
    """OLS with cluster-robust (sandwich) SEs.  Returns dict."""
    n  = len(y)
    X  = np.column_stack([np.ones(n), np.asarray(X_raw)])
    k  = X.shape[1]
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid  = y - X @ b
    r2     = 1 - np.sum(resid**2) / np.sum((y - y.mean())**2)

    # Sandwich: Σ_g (X_g' e_g e_g' X_g)
    clusters = np.unique(cluster_ids)
    G = len(clusters)
    meat = np.zeros((k, k))
    for g in clusters:
        idx = cluster_ids == g
        Xg  = X[idx]
        eg  = resid[idx]
        score = Xg.T @ eg
        meat += np.outer(score, score)

    bread  = np.linalg.inv(X.T @ X)
    # small-sample correction
    correction = G / (G - 1) * (n - 1) / (n - k)
    var_b  = correction * bread @ meat @ bread
    se     = np.sqrt(np.maximum(np.diag(var_b), 0))
    tstat  = b / np.where(se > 0, se, np.nan)
    pval   = 2 * stats.t.sf(np.abs(tstat), df=G - 1)
    return dict(b=b, se=se, tstat=tstat, pval=pval,
                r2=r2, n=n, G=G, resid=resid)


# ── Hebrew floor-number parser ────────────────────────────────────────────────

# Maps Hebrew ordinal words → integer floor numbers (ground = 0, basement = -1)
_HEB_FLOOR = {
    # ground / basement / special
    "קרקע": 0, "קרקע ": 0,
    "מרתף": -1, "מרתף ": -1,
    "גג": 99,         # penthouse flag
    "גלריה": 99,
    "ביניים": 0, "בניים": 0, "בנים": 0, "יציע": 0, "עמודים": 0,
    # single-letter abbreviations (alef=1, bet=2, etc.)
    "א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5,
    "ו": 6, "ז": 7, "ח": 8, "ט": 9, "י": 10,
    # feminine ordinals 1–10
    "ראשונה": 1, "ראשון": 1,
    "שניה": 2,  "שנייה": 2, "שני": 2,
    "שלישית": 3, "שלישי": 3,
    "רביעית": 4, "רביעי": 4,
    "חמישית": 5, "חמישי": 5,
    "שישית": 6,  "שישי": 6,
    "שביעית": 7, "שביעי": 7,
    "שמינית": 8, "שמיני": 8,
    "תשיעית": 9, "תשיעי": 9,
    "עשירית": 10, "עשירי": 10,
    # teens
    "אחת עשרה": 11, "אחד עשר": 11,
    "שתים עשרה": 12, "שתיים עשרה": 12, "שניים עשר": 12,
    "שלוש עשרה": 13, "שלושה עשר": 13,
    "ארבע עשרה": 14, "ארבעה עשר": 14,
    "חמש עשרה": 15,  "חמישה עשר": 15,
    "שש עשרה": 16,   "שישה עשר": 16,
    "שבע עשרה": 17,  "שבעה עשר": 17,
    "שמונה עשרה": 18,
    "תשע עשרה": 19,  "תשעה עשר": 19,
    # tens
    "עשרים": 20,
    "שלושים": 30,
    "ארבעים": 40,
    "חמישים": 50,
}

import re as _re

def _parse_floor(raw) -> tuple:
    """
    Return (floor_num, is_penthouse).
    floor_num: integer floor (ground=0, basement=-1) or NaN
    is_penthouse: 1 if גג/penthouse, else 0
    For multi-floor entries take the first (lowest) floor.
    """
    if pd.isna(raw):
        return np.nan, 0
    s = str(raw).strip()
    # strip RTL marks
    s_clean = _re.sub(r'[\u200e\u200f]', '', s)

    # 1. try embedded Arabic numerals first (handles קומה ‎2‏ pattern)
    nums = _re.findall(r'-?\d+', s_clean)
    if nums:
        n = int(nums[0])
        return n, int(n >= 15)   # treat very high floors as penthouse-ish

    # 2. try Hebrew ordinal map – longest match first
    for key in sorted(_HEB_FLOOR, key=len, reverse=True):
        if key in s:
            val = _HEB_FLOOR[key]
            if val == 99:
                return np.nan, 1   # penthouse – don't assign numeric floor
            return val, 0

    return np.nan, 0


def stars(p):
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.10: return "*"
    return ""


# ── Stage 1: load transactions ────────────────────────────────────────────────

_RAW_CACHE = f"{PROCESSED_DIR}/transactions_raw.parquet"

def load_transactions():
    """Load all XLSX files; return cleaned transaction-level DataFrame.

    On first run, all XLSX files are parsed and the raw data is written to
    a parquet cache so that subsequent runs skip the slow Excel reading.
    """
    print("Stage 1 – loading transactions …")

    if os.path.exists(_RAW_CACHE):
        print(f"  reading from cache: {_RAW_CACHE}")
        df = pd.read_parquet(_RAW_CACHE)
        # always re-apply the map so name fixes take effect without rebuilding
        df["city_en"] = df["city_code"].astype(str).map(CITY_CODE_MAP).fillna(df["city_code"])
        print(f"  raw rows: {len(df):,}")
    else:
        dfs = []
        xlsx_files = sorted(glob.glob("/home/user/housing/*.xlsx"))
        for i, f in enumerate(xlsx_files, 1):
            city_code = os.path.basename(f).split("-")[0]
            city_en   = CITY_CODE_MAP.get(city_code, city_code)
            try:
                print(f"  [{i}/{len(xlsx_files)}] {os.path.basename(f)} …", end="\r")
                tmp = pd.read_excel(
                    f,
                    usecols=["DEALAMOUNT", "POLYGON_ID", "DEALDATE",
                             "ASSETROOMNUM", "BUILDINGYEAR", "BUILDINGFLOORS",
                             "FLOORNO", "NEWPROJECTTEXT"],
                )
                tmp["city_en"]   = city_en
                tmp["city_code"] = city_code
                dfs.append(tmp)
            except Exception as e:
                print(f"\n  warning {os.path.basename(f)}: {e}")

        df = pd.concat(dfs, ignore_index=True)
        print(f"\n  raw rows: {len(df):,}")
        df.to_parquet(_RAW_CACHE, index=False)
        print(f"  cache written → {_RAW_CACHE}")

    # ── parse price ──────────────────────────────────────────────────────────
    df["DEALAMOUNT"] = (
        df["DEALAMOUNT"].astype(str)
        .str.replace(",", "", regex=False).str.strip()
    )
    df["DEALAMOUNT"] = pd.to_numeric(df["DEALAMOUNT"], errors="coerce")
    df = df[df["DEALAMOUNT"] > 50_000].copy()          # remove implausible values
    df["log_price"] = np.log(df["DEALAMOUNT"] * NIS_TO_USD)

    # ── parse deal year ───────────────────────────────────────────────────────
    def parse_year(s):
        try:
            parts = str(s).strip().split(".")
            if len(parts) == 3:
                return int(parts[2])
        except Exception:
            pass
        return np.nan

    df["deal_year"] = df["DEALDATE"].apply(parse_year)
    df = df[df["deal_year"].between(2018, 2023)].copy()

    # ── parse rooms ───────────────────────────────────────────────────────────
    df["rooms"] = pd.to_numeric(df["ASSETROOMNUM"], errors="coerce")
    df = df[df["rooms"].between(1, 15)].copy()
    df["log_rooms"] = np.log(df["rooms"])

    # ── parse building year / age ─────────────────────────────────────────────
    df["build_year"] = pd.to_numeric(df["BUILDINGYEAR"], errors="coerce")
    df = df[df["build_year"].between(1920, 2024)].copy()
    df["building_age"]    = df["deal_year"] - df["build_year"]
    df["building_age_sq"] = df["building_age"] ** 2 / 1_000   # scale for numerics
    # building decade dummies (captures nonlinear vintage effects)
    df["decade"] = (df["build_year"] // 10 * 10).clip(1930, 2020)

    # ── number of floors in building ──────────────────────────────────────────
    df["bldg_floors"] = pd.to_numeric(df["BUILDINGFLOORS"], errors="coerce")
    df["bldg_floors"] = df["bldg_floors"].where(df["bldg_floors"].between(1, 60))
    # log(floors): proxy for building height / type (low-rise vs high-rise)
    df["log_bldg_floors"] = np.log(df["bldg_floors"].fillna(df["bldg_floors"].median()))

    # ── apartment floor number ────────────────────────────────────────────────
    parsed = df["FLOORNO"].apply(_parse_floor)
    df["floor_num"]     = [x[0] for x in parsed]
    df["is_penthouse"]  = [x[1] for x in parsed]
    # clip implausible floors
    df["floor_num"] = df["floor_num"].where(df["floor_num"].between(-2, 60))
    # relative floor position = floor / building_floors (0-1), if both available
    df["floor_pos"] = np.where(
        df["floor_num"].notna() & df["bldg_floors"].notna() & (df["bldg_floors"] > 0),
        df["floor_num"] / df["bldg_floors"],
        np.nan,
    )
    # impute missing floor_num with block-level median for FE demeaning
    block_floor_med = df.groupby("POLYGON_ID")["floor_num"].transform("median")
    df["floor_num_imp"] = df["floor_num"].fillna(block_floor_med)
    df["floor_pos_imp"] = df["floor_pos"].fillna(
        df.groupby("POLYGON_ID")["floor_pos"].transform("median")
    )
    floor_known = df["floor_num"].notna().mean()
    print(f"  floor number parsed: {floor_known*100:.1f}% of rows")

    # ── new project dummy ─────────────────────────────────────────────────────
    df["is_new_project"] = (df["NEWPROJECTTEXT"] == 1).astype(float)

    # ── parse POLYGON_ID ──────────────────────────────────────────────────────
    df["POLYGON_ID"] = df["POLYGON_ID"].astype(str).str.strip()
    df = df[df["POLYGON_ID"].notna() & (df["POLYGON_ID"] != "nan")].copy()

    # ── year dummies (2019–2023; 2018 = reference) ───────────────────────────
    for yr in range(2019, 2024):
        df[f"yr_{yr}"] = (df["deal_year"] == yr).astype(float)

    print(f"  clean rows:  {len(df):,}")
    print(f"  unique gush: {df['POLYGON_ID'].nunique():,}")
    return df


# ── Stage 1: within-group FE estimation ──────────────────────────────────────

def estimate_stage1(df):
    """
    Within-group (POLYGON_ID) estimation.

    Returns
    -------
    beta_house : array of shape (k,) – coefficients on house characteristics
    fe_df      : DataFrame with columns [POLYGON_ID, city_en, fe, fe_se, n_txn]
    stage1_info: dict with regression diagnostics
    """
    print("\nStage 1 – within-group FE estimation …")

    YEAR_DUMMIES = [f"yr_{y}" for y in range(2019, 2024)]
    HOUSE_VARS   = [
        # dwelling characteristics
        "log_rooms",
        # building age & vintage
        "building_age", "building_age_sq",
        # building height / type
        "log_bldg_floors",
        # apartment floor (imputed medians for missing; relative position)
        "floor_num_imp", "floor_pos_imp",
        # new-project premium
        "is_new_project",
        # penthouse
        "is_penthouse",
        # year macro controls
    ] + YEAR_DUMMIES

    # ── keep only blocks with >= MIN_TXN_PER_BLOCK observations ──────────────
    block_n = df.groupby("POLYGON_ID").size()
    good_blocks = block_n[block_n >= MIN_TXN_PER_BLOCK].index
    df2 = df[df["POLYGON_ID"].isin(good_blocks)].copy()
    print(f"  gush blocks with >= {MIN_TXN_PER_BLOCK} txns: {len(good_blocks):,}")
    print(f"  transactions used: {len(df2):,}")

    # ── within-group demeaning ────────────────────────────────────────────────
    all_vars = ["log_price"] + HOUSE_VARS
    # fill any remaining NaN with column-level median before demeaning
    for v in HOUSE_VARS:
        med = df2[v].median()
        df2[v] = df2[v].fillna(med)

    group_means = df2.groupby("POLYGON_ID")[all_vars].transform("mean")
    df_within = df2[all_vars].subtract(group_means)   # demeaned

    y_w = df_within["log_price"].values
    X_raw = df_within[HOUSE_VARS].values

    # Drop columns with near-zero within-group variance (would be singular)
    col_std = X_raw.std(axis=0)
    active = col_std > 1e-10
    HOUSE_VARS_ACTIVE = [v for v, a in zip(HOUSE_VARS, active) if a]
    dropped = [v for v, a in zip(HOUSE_VARS, active) if not a]
    if dropped:
        print(f"  dropping zero-variance columns: {dropped}")
    X_w = X_raw[:, active]

    # OLS on demeaned data (no intercept needed after demeaning)
    b_w, *_ = np.linalg.lstsq(X_w, y_w, rcond=None)

    # R² of the within regression
    resid_w = y_w - X_w @ b_w
    r2_w = 1 - np.sum(resid_w**2) / np.sum((y_w - y_w.mean())**2)
    print(f"  Stage 1 within-R²: {r2_w:.4f}")
    print(f"  Active regressors: {len(HOUSE_VARS_ACTIVE)}")
    for nm, bv in zip(HOUSE_VARS_ACTIVE[:4], b_w[:4]):
        print(f"    {nm}: {bv:.5f}")

    # ── recover FEs: α̂_j = ȳ_j – β̂' x̄_j ─────────────────────────────────
    # group means
    grp = df2.groupby(["POLYGON_ID", "city_en"])[all_vars].mean()
    grp = grp.reset_index()

    Xbar = grp[HOUSE_VARS_ACTIVE].values
    ybar = grp["log_price"].values
    fe   = ybar - Xbar @ b_w

    # ── SE of FE: based on within-group variance / n_j ───────────────────────
    sigma2_w = np.sum(resid_w**2) / max(len(y_w) - len(b_w) - len(good_blocks), 1)
    k_active = len(b_w)
    n_j = df2.groupby("POLYGON_ID").size().reindex(grp["POLYGON_ID"]).values
    fe_se = np.sqrt(sigma2_w / n_j)

    fe_df = grp[["POLYGON_ID", "city_en"]].copy()
    fe_df["fe"]    = fe
    fe_df["fe_se"] = fe_se
    fe_df["n_txn"] = n_j

    # ── full-model R² (including FE) – approximate via explained variance ─────
    # predicted = city-mean + X β̂; compare with residual variance
    df2["fitted_house"] = X_w @ b_w + group_means["log_price"].values
    total_ss  = np.sum((df2["log_price"] - df2["log_price"].mean())**2)
    resid_full = (df2["log_price"] - df2["fitted_house"] - resid_w).values  # ≈ 0 by construction
    # simpler: use within-R² + between-R²
    resid_total = df2["log_price"].values - (df2["fitted_house"].values)
    r2_full = 1 - np.sum(resid_total**2) / total_ss

    stage1_info = dict(
        b_w=b_w.tolist(),
        house_vars=HOUSE_VARS_ACTIVE,
        r2_within=r2_w,
        n_txn=len(df2),
        n_blocks=len(good_blocks),
        sigma2=sigma2_w,
    )

    print(f"  FE estimates: {len(fe_df):,} gush blocks")
    print(f"  FE range: [{fe.min():.3f}, {fe.max():.3f}]  "
          f"median={np.median(fe):.3f}  std={fe.std():.3f}")
    return b_w, HOUSE_VARS, fe_df, stage1_info


# ── Stage 2 helper ────────────────────────────────────────────────────────────

def merge_with_urbanism(fe_df):
    """Merge gush-block FEs with city-level urbanism metrics."""
    urban = pd.read_csv(f"{PROCESSED_DIR}/analysis_data.csv")
    # normalise city name column
    name_col = None
    for c in ["en_name", "city_name_en", "city_en", "en name"]:
        if c in urban.columns:
            name_col = c
            break
    if name_col is None:
        # try a column that contains 'Tel Aviv'
        for c in urban.columns:
            if urban[c].astype(str).str.contains("Tel Aviv", na=False).any():
                name_col = c
                break

    urban = urban.rename(columns={name_col: "city_en"})
    # keep relevant columns
    keep = ["city_en"] + [m for m in URBANISM_METRICS if m in urban.columns]
    urban = urban[keep].drop_duplicates("city_en")

    merged = fe_df.merge(urban, on="city_en", how="left")
    missing = merged[URBANISM_METRICS[0]].isna().sum()
    if missing > 0:
        print(f"  warning: {missing} gush blocks with no urbanism match")
    merged = merged.dropna(subset=URBANISM_METRICS[:4])   # keep 4 main metrics
    print(f"  merged gush blocks: {len(merged):,}  cities: {merged['city_en'].nunique()}")
    return merged


# ── Stage 2 regressions ───────────────────────────────────────────────────────

def run_stage2(merged):
    """
    Bivariate and multivariate regressions of gush FEs on urbanism metrics.
    Returns dict of results.
    """
    print("\nStage 2 – regressing FEs on urbanism metrics …")
    results = {}

    y    = merged["fe"].values
    city = merged["city_en"].values

    # ── bivariate (each metric separately, cluster by city) ──────────────────
    biv = {}
    for m in URBANISM_METRICS:
        if m not in merged.columns:
            continue
        x = merged[m].values
        ok = np.isfinite(x) & np.isfinite(y)
        res = ols_clustered(y[ok], x[ok].reshape(-1, 1), city[ok])
        biv[m] = dict(
            coef=float(res["b"][1]),
            se=float(res["se"][1]),
            tstat=float(res["tstat"][1]),
            pval=float(res["pval"][1]),
            r2=float(res["r2"]),
            n=int(res["n"]),
            G=int(res["G"]),
        )
        print(f"  {m:<32s}  coef={res['b'][1]:+.5f}  "
              f"p={res['pval'][1]:.3f} {stars(res['pval'][1])}")

    results["bivariate_gush"] = biv

    # ── multivariate: main urbanism bundle, clustered ─────────────────────────
    main_metrics = ["street_density_km_km2", "amenity_density",
                    "junction_density", "walkability_index"]
    main_metrics = [m for m in main_metrics if m in merged.columns]
    X_main = merged[main_metrics].values
    ok = np.all(np.isfinite(X_main), axis=1) & np.isfinite(y)
    res_mv = ols_clustered(y[ok], X_main[ok], city[ok])
    mv_coefs = {}
    for i, m in enumerate(main_metrics):
        mv_coefs[m] = dict(
            coef=float(res_mv["b"][i + 1]),
            se=float(res_mv["se"][i + 1]),
            pval=float(res_mv["pval"][i + 1]),
        )
    results["multivariate_gush"] = dict(
        coefs=mv_coefs,
        r2=float(res_mv["r2"]),
        n=int(res_mv["n"]),
        G=int(res_mv["G"]),
    )

    # ── city-aggregate Stage 2 (N = 20) ──────────────────────────────────────
    city_fe = (
        merged.groupby("city_en")
        .apply(lambda g: np.average(g["fe"], weights=g["n_txn"]))
        .rename("fe_city")
        .reset_index()
    )
    # re-merge urbanism
    urban = pd.read_csv(f"{PROCESSED_DIR}/analysis_data.csv")
    name_col = next(
        (c for c in ["en_name", "city_name_en", "city_en", "en name"]
         if c in urban.columns), None
    )
    urban = urban.rename(columns={name_col: "city_en"})
    city_fe = city_fe.merge(
        urban[["city_en"] + [m for m in URBANISM_METRICS if m in urban.columns]],
        on="city_en", how="left"
    ).dropna(subset=URBANISM_METRICS[:4])

    print(f"\n  City-level Stage 2 (N={len(city_fe)}):")
    biv_city = {}
    y_c = city_fe["fe_city"].values
    for m in URBANISM_METRICS:
        if m not in city_fe.columns:
            continue
        x_c = city_fe[m].values
        ok = np.isfinite(x_c) & np.isfinite(y_c)
        res = ols_plain(y_c[ok], x_c[ok].reshape(-1, 1))
        biv_city[m] = dict(
            coef=float(res["b"][1]),
            se=float(res["se"][1]),
            pval=float(res["pval"][1]),
            r2=float(res["r2"]),
            n=int(res["n"]),
        )
        print(f"  {m:<32s}  r²={res['r2']:.3f}  "
              f"p={res['pval'][1]:.3f} {stars(res['pval'][1])}")

    results["bivariate_city"] = biv_city
    results["city_fe_df"] = city_fe.to_dict(orient="records")

    return results, city_fe


# ── figures ───────────────────────────────────────────────────────────────────

def make_figures(merged, city_fe, stage1_info):
    print("\nGenerating figures …")

    # ── Fig A: Stage 1 year FE plot ──────────────────────────────────────────
    b_w      = np.array(stage1_info["b_w"])
    hv       = stage1_info["house_vars"]
    coef_map = dict(zip(hv, b_w))
    yr_labels = ["2018 (ref)", "2019", "2020", "2021", "2022", "2023"]
    yr_coefs  = [0.0] + [coef_map.get(f"yr_{y}", 0.0) for y in range(2019, 2024)]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(yr_labels, yr_coefs, color="#2C7BB6", alpha=0.8)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_title("Stage 1 – Year Fixed Effects (log price)", fontsize=12)
    ax.set_ylabel("Coefficient (log points)")
    ax.set_xlabel("Transaction year")
    plt.tight_layout()
    plt.savefig(f"{MAPS_DIR}/hedonic_year_fe.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ── Fig B: city-aggregated FE vs. walkability ─────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    metrics_to_plot = [
        ("walkability_index",     "Walkability Index"),
        ("street_density_km_km2", "Street Density (km/km²)"),
        ("amenity_density",       "Amenity Density (POIs/km²)"),
    ]
    for ax, (m, label) in zip(axes, metrics_to_plot):
        if m not in city_fe.columns:
            continue
        x = city_fe[m].values
        y = city_fe["fe_city"].values
        ok = np.isfinite(x) & np.isfinite(y)
        ax.scatter(x[ok], y[ok], color="#E04A2F", s=50, zorder=3)
        for _, row in city_fe.iterrows():
            ax.annotate(row["city_en"].split("-")[0][:8],
                        (row[m], row["fe_city"]),
                        fontsize=6.5, ha="center", va="bottom")
        # OLS line
        if ok.sum() > 2:
            z = np.polyfit(x[ok], y[ok], 1)
            xr = np.linspace(x[ok].min(), x[ok].max(), 100)
            ax.plot(xr, np.polyval(z, xr), "k--", lw=1.2, alpha=0.7)
        ax.set_xlabel(label, fontsize=9)
        ax.set_ylabel("Stage 1 FE  (log price, adj. for house chars)", fontsize=8)
        ax.set_title(label, fontsize=10)
        ax.grid(alpha=0.3)
    plt.suptitle("Stage 2: Quality-Adjusted Location Premium vs. Urbanism",
                 fontsize=12, y=1.02)
    plt.tight_layout()
    plt.savefig(f"{MAPS_DIR}/hedonic_stage2_scatter.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ── Fig C: gush-block FE distribution by city ─────────────────────────────
    top_cities = (
        merged.groupby("city_en")["n_txn"].sum()
        .nlargest(10).index.tolist()
    )
    sub = merged[merged["city_en"].isin(top_cities)].copy()
    sub_sorted = sub.groupby("city_en")["fe"].median().sort_values(ascending=False)
    ordered = sub_sorted.index.tolist()

    fig, ax = plt.subplots(figsize=(12, 5))
    data_by_city = [sub[sub["city_en"] == c]["fe"].values for c in ordered]
    bp = ax.boxplot(data_by_city, labels=[c.split("-")[0][:10] for c in ordered],
                    patch_artist=True, medianprops=dict(color="k", lw=2))
    cmap = plt.cm.RdYlGn
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(cmap(i / len(ordered)))
    ax.axhline(0, color="gray", lw=0.8, ls="--")
    ax.set_ylabel("Stage 1 Fixed Effect (log price, house-char-adjusted)", fontsize=9)
    ax.set_title("Gush-Block Location Quality Premiums by City", fontsize=12)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{MAPS_DIR}/hedonic_fe_by_city.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ── Fig D: comparison – raw median vs. FE-based measure ──────────────────
    # Load the old city median prices for comparison
    try:
        ad = pd.read_csv(f"{PROCESSED_DIR}/analysis_data.csv")
        name_col = next(
            (c for c in ["en_name", "city_name_en", "city_en"]
             if c in ad.columns), None
        )
        ad = ad.rename(columns={name_col: "city_en"})
        comp = city_fe.merge(ad[["city_en", "median_price_usd"]], on="city_en", how="inner")
        comp["log_median"] = np.log(comp["median_price_usd"])

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        for ax, (xcol, xlbl) in zip(axes, [
            ("log_median", "log(Median Price, USD)  [raw]"),
            ("fe_city",    "Stage 1 FE  [house-char adjusted]"),
        ]):
            for m, clr in [("walkability_index", "#E04A2F"),
                           ("street_density_km_km2", "#2C7BB6")]:
                if m not in comp.columns:
                    continue
                x = comp[m].values
                y = comp[xcol].values
                ok = np.isfinite(x) & np.isfinite(y)
                r, p = stats.pearsonr(x[ok], y[ok])
                ax.scatter(x[ok], y[ok], s=50, alpha=0.7, color=clr,
                           label=f"{METRIC_LABELS[m][:20]} r={r:.2f} p={p:.3f}")
            ax.legend(fontsize=8)
            ax.set_ylabel(xlbl, fontsize=9)
            ax.set_title(xlbl[:40], fontsize=9)
            ax.grid(alpha=0.3)
        plt.suptitle("Raw Median vs. Quality-Adjusted FE: Correlation with Urbanism",
                     fontsize=11)
        plt.tight_layout()
        plt.savefig(f"{MAPS_DIR}/hedonic_raw_vs_fe.png", dpi=150, bbox_inches="tight")
        plt.close()
    except Exception as e:
        print(f"  skip comparison figure: {e}")

    print("  figures saved to", MAPS_DIR)


# ── save outputs ──────────────────────────────────────────────────────────────

def save_results(b_w, house_vars, stage1_info, stage2_results):
    # ── text table for quick inspection ──────────────────────────────────────
    lines = []
    lines.append("=" * 70)
    lines.append("TWO-STAGE HEDONIC REGRESSION – RESULTS SUMMARY")
    lines.append("=" * 70)
    lines.append("\nSTAGE 1: House Characteristics (within-POLYGON_ID estimator)")
    lines.append(f"  N transactions: {stage1_info['n_txn']:,}")
    lines.append(f"  N gush blocks:  {stage1_info['n_blocks']:,}")
    lines.append(f"  Within-R²:      {stage1_info['r2_within']:.4f}")
    lines.append(f"\n  {'Variable':<25s}  {'Coef':>10s}")
    lines.append(f"  {'-'*37}")
    for nm, b in zip(stage1_info["house_vars"], b_w):
        lines.append(f"  {nm:<25s}  {b:>10.5f}")

    lines.append("\n" + "=" * 70)
    lines.append("STAGE 2: FE ~ Urbanism Metrics  (cluster-robust SE, cluster=city)")
    lines.append(f"  {'Metric':<32s}  {'Coef':>9s}  {'SE':>8s}  {'p':>6s}  {'Sig':>4s}  {'R²':>6s}")
    lines.append(f"  {'-' * 72}")
    for m, res in stage2_results["bivariate_gush"].items():
        lines.append(
            f"  {METRIC_LABELS.get(m, m):<32s}  "
            f"{res['coef']:>9.5f}  {res['se']:>8.5f}  "
            f"{res['pval']:>6.3f}  {stars(res['pval']):>4s}  {res['r2']:>6.4f}"
        )

    lines.append("\n" + "=" * 70)
    lines.append("STAGE 2 (city-level, N=20): FE ~ Urbanism Metrics")
    lines.append(f"  {'Metric':<32s}  {'Coef':>9s}  {'SE':>8s}  {'p':>6s}  {'R²':>6s}")
    lines.append(f"  {'-' * 65}")
    for m, res in stage2_results["bivariate_city"].items():
        lines.append(
            f"  {METRIC_LABELS.get(m, m):<32s}  "
            f"{res['coef']:>9.5f}  {res['se']:>8.5f}  "
            f"{res['pval']:>6.3f}  {res['r2']:>6.4f}"
        )

    txt = "\n".join(lines)
    out_txt = f"{PROCESSED_DIR}/hedonic_twostage_results.txt"
    with open(out_txt, "w") as fh:
        fh.write(txt)
    print(f"\n  Results written → {out_txt}")
    print(txt[:1200])

    # ── JSON for paper PDF ────────────────────────────────────────────────────
    out_json = f"{PROCESSED_DIR}/hedonic_twostage_results.json"
    json_payload = dict(
        stage1=dict(
            n_txn=stage1_info["n_txn"],
            n_blocks=stage1_info["n_blocks"],
            r2_within=stage1_info["r2_within"],
            house_vars=stage1_info["house_vars"],
            coefs=dict(zip(stage1_info["house_vars"], [float(x) for x in b_w])),
        ),
        stage2_gush=stage2_results["bivariate_gush"],
        stage2_multivariate_gush=stage2_results["multivariate_gush"],
        stage2_city=stage2_results["bivariate_city"],
    )
    with open(out_json, "w") as fh:
        json.dump(json_payload, fh, indent=2)
    print(f"  JSON written  → {out_json}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    df_txn = load_transactions()
    b_w, house_vars, fe_df, stage1_info = estimate_stage1(df_txn)
    merged = merge_with_urbanism(fe_df)
    stage2_results, city_fe = run_stage2(merged)
    make_figures(merged, city_fe, stage1_info)
    save_results(b_w, house_vars, stage1_info, stage2_results)
    print("\nDone.")


if __name__ == "__main__":
    main()
