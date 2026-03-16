"""
Full pipeline on real data using Overture Maps (S3) as data source.

Data sources:
  - Boundaries : Overture Maps divisions (localities + neighbourhoods for Israel)
                 Downloaded and cached in data/raw/israel_divisions.pkl
                 If the CBS ezorim_statistiim_2022.gdb resolves, that is used instead.
  - Roads      : Overture Maps transportation segments
                 Cached in data/raw/israel_roads.parquet
  - Places     : Overture Maps places (amenities)
                 Cached in data/raw/israel_places.parquet

Metrics per area:
  junction_density, street_density_km_km2, dead_end_ratio, circuity_avg,
  amenity_density, walkability_index

Usage:
  python run_real_data.py               # all localities
  python run_real_data.py --level neighbourhood
  python run_real_data.py --max 200
"""

import argparse, os, warnings
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box, MultiPolygon
from shapely import wkb
from tqdm import tqdm
import pyproj

import config

ITM = pyproj.CRS("EPSG:2039")    # Israeli Transverse Mercator (metric)
WGS84 = pyproj.CRS("EPSG:4326")

# ── Load cached data ──────────────────────────────────────────────────────────

def load_boundaries(level: str = "locality") -> gpd.GeoDataFrame:
    """Load Overture Maps divisions for Israel, or CBS GDB if available."""

    # Prefer the real CBS GDB when the symlink resolves
    gdb = config.SA_GDB_PATH
    if os.path.exists(gdb):
        print("Using CBS ezorim_statistiim_2022.gdb …")
        from load_boundaries import load_statistical_areas
        return load_statistical_areas(to_wgs84=True)

    pkl = os.path.join(config.RAW_DIR, "israel_division_areas.pkl")
    if not os.path.exists(pkl):
        raise FileNotFoundError(f"Divisions cache not found: {pkl}\nRun the download step first.")

    df = pd.read_pickle(pkl)
    # Keep chosen level
    level_map = {
        "locality": "locality",
        "neighbourhood": "neighborhood",
        "neighborhood": "neighborhood",
        "macrohood": "macrohood",
        "county": "county",
        "region": "region",
    }
    subtype = level_map.get(level.lower(), level.lower())
    df = df[df["subtype"] == subtype].copy()

    # Decode geometry (WKB bytes stored in pkl)
    def _decode(g):
        if isinstance(g, bytes):
            return wkb.loads(g)
        return g

    df["geometry"] = df["geometry"].apply(_decode)
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

    # Normalise name column
    def _primary_name(names):
        try:
            if isinstance(names, dict):
                return names.get("primary", "")
            return ""
        except Exception:
            return ""

    gdf["sa_name"] = gdf["names"].apply(_primary_name)
    gdf["sa_code"] = gdf["id"].astype(str)

    # Keep relevant bbox columns for filtering
    gdf["bbox_xmin"] = gdf["bbox"].apply(lambda b: b.get("xmin", np.nan))
    gdf["bbox_ymin"] = gdf["bbox"].apply(lambda b: b.get("ymin", np.nan))

    # Drop areas without geometry
    gdf = gdf[~gdf.geometry.isna() & gdf.geometry.is_valid].copy()
    print(f"Loaded {len(gdf):,} {subtype} polygons from Overture Maps.")
    return gdf


def load_roads() -> gpd.GeoDataFrame:
    path = os.path.join(config.RAW_DIR, "israel_roads.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Roads cache not found: {path}")
    roads = gpd.read_parquet(path)
    if roads.crs is None:
        roads = roads.set_crs("EPSG:4326")
    # Walkable + drivable roads only (exclude motorway ramps, steps, etc.)
    exclude = {"motorway_link", "trunk_link", "steps", "corridor", "elevator"}
    if "class" in roads.columns:
        roads = roads[~roads["class"].isin(exclude)].copy()
    print(f"Loaded {len(roads):,} road segments.")
    return roads


def load_places() -> gpd.GeoDataFrame:
    path = os.path.join(config.RAW_DIR, "israel_places.parquet")
    if not os.path.exists(path):
        warnings.warn("Places cache not found; amenity_density will be 0.")
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs="EPSG:4326")
    places = gpd.read_parquet(path)
    if places.crs is None:
        places = places.set_crs("EPSG:4326")
    print(f"Loaded {len(places):,} places.")
    return places


# ── Metric calculation ────────────────────────────────────────────────────────

def _project(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf.to_crs(ITM)


def metrics_for_polygon(poly_wgs84, roads_proj: gpd.GeoDataFrame,
                         places_wgs84: gpd.GeoDataFrame, area_km2: float) -> dict:
    """Compute all urbanism metrics for a single polygon."""

    if area_km2 <= 0:
        return _empty_metrics()

    # ── Road network metrics ─────────────────────────────────────────────────
    # Clip roads to polygon
    try:
        poly_proj = gpd.GeoSeries([poly_wgs84], crs=WGS84).to_crs(ITM).iloc[0]
        local_roads = roads_proj[roads_proj.intersects(poly_proj)].copy()
    except Exception:
        local_roads = gpd.GeoDataFrame(columns=roads_proj.columns, crs=roads_proj.crs)

    n_segs = len(local_roads)
    if n_segs == 0:
        net = _empty_network_metrics()
    else:
        # Total road length
        total_length_m = local_roads.geometry.length.sum()
        total_length_km = total_length_m / 1000

        # Junction density: approximate via connector endpoints
        # Each road segment's endpoints that appear in 3+ segments = intersection
        # Use bounding-box centroid approach as proxy
        endpoint_counts = {}
        for geom in local_roads.geometry:
            try:
                coords = list(geom.coords)
                for pt in [coords[0], coords[-1]]:
                    key = (round(pt[0], 1), round(pt[1], 1))   # ~10cm grid
                    endpoint_counts[key] = endpoint_counts.get(key, 0) + 1
            except Exception:
                pass

        n_intersections = sum(1 for v in endpoint_counts.values() if v >= 3)
        n_dead_ends = sum(1 for v in endpoint_counts.values() if v == 1)
        total_nodes = n_intersections + n_dead_ends

        # Circuity: ratio of road length to straight-line length per segment
        def _circuity(geom):
            try:
                coords = list(geom.coords)
                sl = np.hypot(coords[-1][0]-coords[0][0], coords[-1][1]-coords[0][1])
                return geom.length / sl if sl > 0 else np.nan
            except Exception:
                return np.nan

        circuities = local_roads.geometry.apply(_circuity).dropna()

        net = {
            "intersection_count":    n_intersections,
            "junction_density":      n_intersections / area_km2,
            "street_density_km_km2": total_length_km / area_km2,
            "avg_street_length_m":   total_length_m / n_segs,
            "dead_end_ratio":        n_dead_ends / total_nodes if total_nodes > 0 else np.nan,
            "circuity_avg":          float(circuities.mean()) if len(circuities) else np.nan,
        }

    # ── Amenity metrics ──────────────────────────────────────────────────────
    try:
        local_places = places_wgs84[places_wgs84.within(poly_wgs84)]
        n_places = len(local_places)
    except Exception:
        n_places = 0

    ami = {
        "amenity_count":   n_places,
        "amenity_density": n_places / area_km2,
    }

    all_m = {**net, **ami}
    all_m["walkability_index"] = _walkability(all_m)
    return all_m


def _empty_network_metrics():
    return {k: np.nan for k in [
        "intersection_count", "junction_density", "street_density_km_km2",
        "avg_street_length_m", "dead_end_ratio", "circuity_avg"]}


def _empty_metrics():
    return {**_empty_network_metrics(),
            "amenity_count": 0, "amenity_density": 0.0, "walkability_index": 0.0}


_NORM = {
    "junction_density":      (0,   150),
    "street_density_km_km2": (0,   30),
    "dead_end_ratio":        (0.5, 0),
    "circuity_avg":          (2.0, 1.0),
    "amenity_density":       (0,   50),
}

def _norm(v, lo, hi):
    if np.isnan(v): return 0.0
    return float(np.clip((v - lo) / (hi - lo + 1e-9), 0, 1))

def _walkability(m: dict) -> float:
    weights = {"junction_density": 0.30, "street_density_km_km2": 0.20,
               "dead_end_ratio": 0.15, "circuity_avg": 0.15, "amenity_density": 0.20}
    score = sum(w * _norm(m.get(k, np.nan), *_NORM[k]) for k, w in weights.items())
    return round(score * 100, 2)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--level", default="locality",
                   help="Overture division level: locality, neighborhood, macrohood, county")
    p.add_argument("--max", type=int, default=None, dest="max_areas")
    return p.parse_args()


def main():
    args = parse_args()

    # 1. Load data
    boundaries = load_boundaries(level=args.level)
    roads_wgs84 = load_roads()
    places = load_places()

    # Project roads to ITM once (for spatial operations)
    roads_proj = _project(roads_wgs84)

    # 2. Restrict by bounding box to populated Israel
    # (exclude Negev/Arava desert where no housing data exists)
    boundaries = boundaries[
        boundaries.geometry.centroid.y > 29.5
    ].copy()

    if args.max_areas:
        boundaries = boundaries.head(args.max_areas)

    print(f"\nCalculating metrics for {len(boundaries):,} areas …\n")

    results = []
    for _, row in tqdm(boundaries.iterrows(), total=len(boundaries), unit="area"):
        poly = row.geometry
        try:
            poly_proj = gpd.GeoSeries([poly], crs=WGS84).to_crs(ITM).iloc[0]
            area_km2 = poly_proj.area / 1e6
        except Exception:
            area_km2 = 0.0

        m = metrics_for_polygon(poly, roads_proj, places, area_km2)
        results.append({
            "sa_code":   row.get("sa_code", row.get("id", "")),
            "sa_name":   row.get("sa_name", ""),
            "subtype":   row.get("subtype", args.level),
            "area_km2":  round(area_km2, 4),
            **m,
        })

    df = pd.DataFrame(results)
    out = config.METRICS_OUTPUT_FILE
    df.to_csv(out, index=False)
    print(f"\nSaved {len(df):,} rows to {out}")
    print(df[["sa_name", "area_km2", "junction_density",
               "street_density_km_km2", "walkability_index"]].head(10).to_string(index=False))
    return df


if __name__ == "__main__":
    main()
