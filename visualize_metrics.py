"""
Visualise urbanism-quality metrics as choropleth maps.

Loads the statistical area boundaries from the GDB and merges them with the
computed metrics CSV (data/processed/urbanism_metrics.csv).

Usage
-----
    python visualize_metrics.py              # real data (GDB + metrics CSV required)
    python visualize_metrics.py --demo       # synthetic data (no GDB needed)
    python visualize_metrics.py --metric walkability_index
"""

import argparse
import os
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.ticker import FuncFormatter

import config

# ── Metric definitions ────────────────────────────────────────────────────────

METRICS = {
    "junction_density":      dict(label="Junction Density",      unit="intersections/km²", cmap="YlOrRd",   better="high"),
    "street_density_km_km2": dict(label="Street Density",        unit="km/km²",            cmap="Blues",    better="high"),
    "dead_end_ratio":        dict(label="Dead-End Ratio",         unit="share",             cmap="RdYlGn_r", better="low"),
    "circuity_avg":          dict(label="Circuity",               unit="ratio",             cmap="RdYlGn_r", better="low"),
    "amenity_density":       dict(label="Amenity Density",        unit="POIs/km²",          cmap="Greens",   better="high"),
    "walkability_index":     dict(label="Walkability Index",      unit="0–100",             cmap="RdYlGn",   better="high"),
}

MAPS_DIR = os.path.join(config.PROCESSED_DIR, "maps")
os.makedirs(MAPS_DIR, exist_ok=True)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_merged_data() -> gpd.GeoDataFrame:
    from load_boundaries import load_statistical_areas
    gdf = load_statistical_areas(to_wgs84=False)
    metrics_path = config.METRICS_OUTPUT_FILE
    if not os.path.exists(metrics_path):
        raise FileNotFoundError(
            f"Metrics CSV not found: {metrics_path}\n"
            "Run  python main.py  first, or use  --demo  for synthetic data."
        )
    df = pd.read_csv(metrics_path, dtype={"sa_code": str})
    drop = [c for c in ["sa_name", "muni_code", "muni_name", "area_km2", "error"]
            if c in df.columns]
    merged = gdf.merge(df.drop(columns=drop), on="sa_code", how="left")
    print(f"Merged {df['sa_code'].nunique():,} metric rows onto {len(gdf):,} polygons.")
    return merged


def make_demo_data() -> gpd.GeoDataFrame:
    """Real boundaries (when available) with spatially correlated synthetic metrics."""
    rng = np.random.default_rng(42)

    try:
        from load_boundaries import load_statistical_areas
        gdf = load_statistical_areas(to_wgs84=False)
        print(f"Demo: real boundaries ({len(gdf)} areas) with synthetic metrics.")
    except Exception:
        print("Demo: synthetic grid boundaries (GDB not found).")
        from shapely.geometry import box
        # ITM bounding box roughly covering populated Israel
        cols, rows = 15, 25
        x0, x1, y0, y1 = 150_000, 250_000, 370_000, 770_000
        dx = (x1 - x0) / cols
        dy = (y1 - y0) / rows
        polys, codes = [], []
        for r in range(rows):
            for c in range(cols):
                polys.append(box(x0+c*dx, y0+r*dy, x0+(c+1)*dx, y0+(r+1)*dy))
                codes.append(f"{r*cols+c:04d}")
        gdf = gpd.GeoDataFrame({"sa_code": codes, "sa_name": codes},
                               geometry=polys, crs=config.PROJECTED_CRS)

    n = len(gdf)
    cx = gdf.geometry.centroid
    # Normalised distance from the centroid cloud centre
    mx, my = cx.x.mean(), cx.y.mean()
    sx, sy = cx.x.std() + 1, cx.y.std() + 1
    dx = (cx.x - mx) / sx
    dy = (cx.y - my) / sy
    dist = np.sqrt(dx**2 + dy**2)

    # Two "urban cores" (like Tel Aviv + Jerusalem) with noise
    core1 = np.exp(-2.5 * ((dx - 0.1)**2 + (dy + 0.3)**2))   # south-central
    core2 = np.exp(-2.5 * ((dx + 0.5)**2 + (dy - 0.2)**2))   # north-east
    urban = np.clip(core1 + 0.6 * core2 + 0.15 * rng.standard_normal(n), 0, 1)
    urban = (urban - urban.min()) / (urban.max() - urban.min() + 1e-9)

    noise = lambda s: s * rng.standard_normal(n)

    gdf["junction_density"]      = np.clip(5  + 145 * urban + noise(8),  0, None)
    gdf["street_density_km_km2"] = np.clip(1  + 29  * urban + noise(2),  0, None)
    gdf["dead_end_ratio"]        = np.clip(0.5 - 0.45* urban + noise(0.04), 0, 1)
    gdf["circuity_avg"]          = np.clip(1.9 - 0.8 * urban + noise(0.06), 1, None)
    gdf["amenity_density"]       = np.clip(0   + 60  * urban + noise(4),  0, None)
    gdf["walkability_index"]     = np.clip(5   + 88  * urban + noise(4),  0, 100)

    return gdf


# ── Single-metric choropleth ──────────────────────────────────────────────────

def _choropleth(ax, gdf, metric, cfg, k=7):
    """
    Draw a quantile choropleth on *ax*.  Returns the ScalarMappable for the
    colour bar.
    """
    col = gdf[metric]
    valid = col.notna() & np.isfinite(col)

    # Quantile bin edges (used both for classification and colorbar ticks)
    bins = np.nanquantile(col[valid], np.linspace(0, 1, k + 1))
    bins = np.unique(bins)           # remove duplicate edges
    k_actual = len(bins) - 1

    cmap = plt.get_cmap(cfg["cmap"], k_actual)
    norm = mcolors.BoundaryNorm(bins, ncolors=k_actual)

    # No-data
    gdf[~valid].plot(ax=ax, color="#e0e0e0", linewidth=0)

    # Classified polygons
    gdf[valid].plot(
        column=metric, ax=ax,
        cmap=cmap, norm=norm,
        linewidth=0.05, edgecolor="#ffffff",
    )

    ax.set_aspect("equal")
    ax.set_axis_off()

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    return sm, bins


def _add_colorbar(fig, ax, sm, bins, unit):
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="4%", pad=0.06)
    cb = fig.colorbar(sm, cax=cax, ticks=bins)

    # Format tick labels
    rng_val = bins[-1] - bins[0]
    decimals = 0 if rng_val > 10 else (1 if rng_val > 1 else 2)
    cb.ax.set_yticklabels([f"{v:.{decimals}f}" for v in bins], fontsize=6)
    cb.set_label(unit, fontsize=7)
    cb.ax.tick_params(length=2)


# ── Public plot functions ─────────────────────────────────────────────────────

def plot_single(gdf, metric, save=True, demo=False):
    cfg = METRICS[metric]
    fig, ax = plt.subplots(figsize=(7, 9))

    sm, bins = _choropleth(ax, gdf, metric, cfg)
    _add_colorbar(fig, ax, sm, bins, cfg["unit"])

    title = f"{cfg['label']}  ({cfg['unit']})"
    if demo:
        title += "\n[DEMO – synthetic data]"
    ax.set_title(title, fontsize=11, pad=8)

    fig.tight_layout()
    fname = os.path.join(MAPS_DIR, f"{metric}.png")
    if save:
        fig.savefig(fname, dpi=150, bbox_inches="tight")
        print(f"  Saved: {fname}")
        plt.close(fig)
    else:
        plt.show()
    return fname


def plot_all(gdf, demo=False):
    metrics = list(METRICS.keys())
    ncols, nrows = 3, 2
    fig, axes = plt.subplots(nrows, ncols, figsize=(18, 14))

    for ax, metric in zip(axes.flatten(), metrics):
        cfg = METRICS[metric]
        sm, bins = _choropleth(ax, gdf, metric, cfg)

        # Inline colorbar
        from mpl_toolkits.axes_grid1 import make_axes_locatable
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="4%", pad=0.05)
        cb = fig.colorbar(sm, cax=cax, ticks=bins[[0, len(bins)//2, -1]])
        rng_val = bins[-1] - bins[0]
        dec = 0 if rng_val > 10 else (1 if rng_val > 1 else 2)
        cb.ax.set_yticklabels([f"{v:.{dec}f}" for v in bins[[0, len(bins)//2, -1]]], fontsize=6)
        cb.ax.tick_params(length=2)

        title = f"{cfg['label']}\n({cfg['unit']})"
        ax.set_title(title, fontsize=9, pad=5)

    suptitle = "Urbanism Quality Metrics – Israeli Statistical Areas"
    if demo:
        suptitle += "  [DEMO: synthetic data]"
    fig.suptitle(suptitle, fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()

    fname = os.path.join(MAPS_DIR, "all_metrics.png")
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)
    return fname


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true")
    p.add_argument("--metric", default=None, choices=list(METRICS))
    return p.parse_args()


def main():
    args = parse_args()
    gdf = make_demo_data() if args.demo else load_merged_data()

    if gdf.crs and gdf.crs.to_epsg() == 4326:
        gdf = gdf.to_crs(config.PROJECTED_CRS)

    print(f"\nSaving maps to: {MAPS_DIR}\n")
    if args.metric:
        plot_single(gdf, args.metric, save=True, demo=args.demo)
    else:
        plot_all(gdf, demo=args.demo)
        for m in METRICS:
            plot_single(gdf, m, save=True, demo=args.demo)
    print("Done.")


if __name__ == "__main__":
    main()
