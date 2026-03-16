"""
Calculate urbanism-quality metrics for a single SA2.

Metrics produced
----------------
Street-network metrics (from OSM road graph):
  junction_density          – intersections per km²   (higher → denser grid)
  street_density_km_km2     – total street km per km² (higher → denser)
  avg_street_length_m       – mean edge length in metres
  dead_end_ratio            – dead-ends / (dead-ends + intersections)
  intersection_count        – raw intersection count
  circuity_avg              – mean(network dist / straight-line dist) per edge
                              (closer to 1 → straighter, more direct streets)

Amenity / market-access metrics (from OSM POI features):
  amenity_density           – amenities per km²
  amenity_count             – raw count of amenity POIs

Composite index:
  walkability_index         – 0–100 score combining the above
                              (higher → more walkable / urban)
"""

import warnings
import numpy as np
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, MultiPolygon

import config
import osm_data


# ── Individual metric calculators ────────────────────────────────────────────

def _network_metrics(G, area_km2: float) -> dict:
    """Derive street-network metrics from an osmnx graph."""
    if G is None or area_km2 <= 0:
        return {
            "intersection_count": np.nan,
            "junction_density": np.nan,
            "street_density_km_km2": np.nan,
            "avg_street_length_m": np.nan,
            "dead_end_ratio": np.nan,
            "circuity_avg": np.nan,
        }

    nodes, edges = osm_data.graph_to_projected_gdfs(G)

    n_intersections = osm_data.count_intersections(G)
    n_dead_ends = osm_data.count_dead_ends(G)

    total_length_m = edges["length"].sum()   # 'length' in metres (from osmnx)
    total_length_km = total_length_m / 1_000

    avg_length = edges["length"].mean() if len(edges) > 0 else np.nan

    total_nodes = n_intersections + n_dead_ends
    dead_end_ratio = n_dead_ends / total_nodes if total_nodes > 0 else np.nan

    # Circuity: ratio of network distance to straight-line distance per edge
    # edges have 'length' (network) and we can compute straight-line from geometry
    circuity = _compute_circuity(edges)

    return {
        "intersection_count": n_intersections,
        "junction_density": n_intersections / area_km2,
        "street_density_km_km2": total_length_km / area_km2,
        "avg_street_length_m": avg_length,
        "dead_end_ratio": dead_end_ratio,
        "circuity_avg": circuity,
    }


def _compute_circuity(edges: gpd.GeoDataFrame) -> float:
    """
    Mean ratio of network edge length to straight-line distance.
    Uses projected geometry so distances are in metres.
    """
    try:
        # straight-line = distance from first to last coordinate of each edge
        straight = edges.geometry.apply(
            lambda g: _straight_line_length(g)
        )
        ratios = edges["length"] / straight.replace(0, np.nan)
        return float(ratios.dropna().mean())
    except Exception:
        return np.nan


def _straight_line_length(geom) -> float:
    """Euclidean distance between the start and end point of a LineString."""
    try:
        coords = list(geom.coords)
        if len(coords) < 2:
            return 0.0
        x1, y1 = coords[0][:2]
        x2, y2 = coords[-1][:2]
        return float(np.hypot(x2 - x1, y2 - y1))
    except Exception:
        return 0.0


def _amenity_metrics(amenities: gpd.GeoDataFrame | None, area_km2: float) -> dict:
    """Derive amenity/market-access metrics from OSM POI features."""
    if amenities is None or amenities.empty or area_km2 <= 0:
        return {
            "amenity_count": 0,
            "amenity_density": 0.0,
        }

    count = len(amenities)
    return {
        "amenity_count": count,
        "amenity_density": count / area_km2,
    }


# ── Composite walkability index ───────────────────────────────────────────────

# Reference ranges for normalisation (approximate Australian urban values).
# Values above the max are clipped to 1; below min to 0.
_NORM_RANGES = {
    "junction_density":      (0,   150),   # intersections / km²
    "street_density_km_km2": (0,   30),    # km streets / km²
    "dead_end_ratio":        (0.5, 0),     # (inverted: lower = better)
    "circuity_avg":          (2.0, 1.0),   # (inverted: lower = better)
    "amenity_density":       (0,   50),    # POIs / km²
}


def _norm(value: float, low: float, high: float) -> float:
    """Min-max normalise value to [0, 1]; handles inverted ranges."""
    if np.isnan(value):
        return 0.0
    if high == low:
        return 0.0
    return float(np.clip((value - low) / (high - low), 0, 1))


def walkability_index(metrics: dict) -> float:
    """
    Compute a 0–100 composite walkability index.

    Weights:
      30% junction density  (grid connectivity)
      20% street density    (network richness)
      15% dead-end ratio    (penalises cul-de-sac suburbs)
      15% circuity          (penalises winding/indirect streets)
      20% amenity density   (daily-life destinations reachable on foot)
    """
    weights = {
        "junction_density":      0.30,
        "street_density_km_km2": 0.20,
        "dead_end_ratio":        0.15,
        "circuity_avg":          0.15,
        "amenity_density":       0.20,
    }

    score = 0.0
    for key, w in weights.items():
        low, high = _NORM_RANGES[key]
        score += w * _norm(metrics.get(key, np.nan), low, high)

    return round(score * 100, 2)


# ── Per-SA pipeline ───────────────────────────────────────────────────────────

def calculate_sa_metrics(row: pd.Series) -> dict:
    """
    Download OSM data and compute all urbanism metrics for one statistical area.

    Parameters
    ----------
    row : pandas Series
        Must have a 'geometry' column (WGS84 polygon) and ideally 'sa_code',
        'sa_name', 'muni_code', 'muni_name' from load_boundaries.py.

    Returns
    -------
    dict with all metrics plus identifier fields and an 'error' field.
    """
    sa_code   = row.get("sa_code",   "unknown")
    sa_name   = row.get("sa_name",   "")
    muni_code = row.get("muni_code", "")
    muni_name = row.get("muni_name", "")

    # Project polygon to equal-area CRS to get accurate area
    poly_wgs84 = row.geometry
    poly_proj = (
        gpd.GeoSeries([poly_wgs84], crs="EPSG:4326")
        .to_crs(config.PROJECTED_CRS)
        .iloc[0]
    )
    area_km2 = poly_proj.area / 1e6  # m² → km²

    result = {
        "sa_code":   sa_code,
        "sa_name":   sa_name,
        "muni_code": muni_code,
        "muni_name": muni_name,
        "area_km2":  round(area_km2, 4),
        "error":     None,
    }

    try:
        G = osm_data.get_road_network(poly_wgs84)
        net = _network_metrics(G, area_km2)

        amenities = osm_data.get_amenities(poly_wgs84)
        ami = _amenity_metrics(amenities, area_km2)

        all_metrics = {**net, **ami}
        all_metrics["walkability_index"] = walkability_index(all_metrics)
        result.update(all_metrics)

    except Exception as exc:
        warnings.warn(f"SA {sa_code} ({sa_name}): {exc}")
        result["error"] = str(exc)

    return result


# backwards-compatible alias used in test_pipeline.py
calculate_sa2_metrics = calculate_sa_metrics
