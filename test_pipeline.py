"""
End-to-end test of the urbanism metrics pipeline using synthetic data.

Tests both the calculation logic (using synthetic NetworkX graphs and
GeoDataFrames) and the boundary download fallback (using live GitHub data
for ACT suburbs).

Run with:  python test_pipeline.py
"""

import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx
from shapely.geometry import Polygon, LineString, Point

import config
from calculate_metrics import (
    _network_metrics,
    _amenity_metrics,
    walkability_index,
    calculate_sa2_metrics,
)
import osm_data


# ── Synthetic graph builder ───────────────────────────────────────────────────

def _make_grid_graph(rows: int = 4, cols: int = 4, spacing: float = 100.0):
    """
    Create a synthetic grid street network (MultiDiGraph) similar to an
    osmnx graph.  Nodes sit on a regular grid; edges connect all neighbours.

    Parameters
    ----------
    rows, cols : int
        Grid dimensions.
    spacing : float
        Distance between nodes in metres (approximate; nodes in WGS84 degrees).
    """
    # Convert spacing to degrees (~1 deg lat ≈ 111_000 m)
    deg = spacing / 111_000

    G = nx.MultiDiGraph()
    G.graph["crs"] = "EPSG:4326"

    # Add nodes
    for r in range(rows):
        for c in range(cols):
            node_id = r * cols + c
            lat = -33.8 + r * deg   # near Sydney
            lon = 151.2 + c * deg
            G.add_node(node_id, y=lat, x=lon, street_count=0)

    # Add bidirectional edges
    for r in range(rows):
        for c in range(cols):
            n = r * cols + c
            # right neighbour
            if c + 1 < cols:
                m = r * cols + (c + 1)
                coords = [
                    (G.nodes[n]["x"], G.nodes[n]["y"]),
                    (G.nodes[m]["x"], G.nodes[m]["y"]),
                ]
                geom = LineString(coords)
                G.add_edge(n, m, length=spacing, geometry=geom)
                G.add_edge(m, n, length=spacing, geometry=LineString(coords[::-1]))
            # down neighbour
            if r + 1 < rows:
                m = (r + 1) * cols + c
                coords = [
                    (G.nodes[n]["x"], G.nodes[n]["y"]),
                    (G.nodes[m]["x"], G.nodes[m]["y"]),
                ]
                geom = LineString(coords)
                G.add_edge(n, m, length=spacing, geometry=geom)
                G.add_edge(m, n, length=spacing, geometry=LineString(coords[::-1]))

    # Compute street_count for each node
    for node in G.nodes():
        # street_count = unique neighbouring nodes
        neighbours = set(G.predecessors(node)) | set(G.successors(node))
        G.nodes[node]["street_count"] = len(neighbours)

    return G


def _make_amenity_gdf(n: int = 30, area_polygon: Polygon = None) -> gpd.GeoDataFrame:
    """Create a synthetic GeoDataFrame of amenity points inside *area_polygon*."""
    rng = np.random.default_rng(42)
    if area_polygon is None:
        # 1km × 1km square near Sydney (in degrees)
        area_polygon = Polygon([
            (151.2, -33.9), (151.21, -33.9),
            (151.21, -33.89), (151.2, -33.89),
        ])
    minx, miny, maxx, maxy = area_polygon.bounds
    xs = rng.uniform(minx, maxx, n)
    ys = rng.uniform(miny, maxy, n)
    return gpd.GeoDataFrame(
        {"amenity": ["shop"] * n},
        geometry=[Point(x, y) for x, y in zip(xs, ys)],
        crs="EPSG:4326",
    )


# ── Unit tests ────────────────────────────────────────────────────────────────

def test_network_metrics_grid():
    """Grid graph should give high junction density and low dead-end ratio."""
    G = _make_grid_graph(4, 4, spacing=100)
    # Area: roughly 400m × 400m = 0.16 km²
    area_km2 = 0.16

    metrics = _network_metrics(G, area_km2)

    print("\n[test_network_metrics_grid]")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    assert metrics["intersection_count"] > 0, "Should have intersections"
    assert metrics["junction_density"] > 0, "Junction density should be positive"
    assert metrics["street_density_km_km2"] > 0, "Street density should be positive"
    assert 0.0 <= metrics["dead_end_ratio"] <= 1.0, "Dead-end ratio in [0, 1]"
    # Perfect grid has no dead ends
    assert metrics["dead_end_ratio"] == 0.0, "Grid should have zero dead ends"
    print("  PASSED")


def test_network_metrics_none():
    """None graph (no streets) should return NaN metrics gracefully."""
    metrics = _network_metrics(None, 1.0)
    print("\n[test_network_metrics_none]")
    assert all(np.isnan(v) for v in metrics.values()), "All metrics should be NaN"
    print("  PASSED (NaN for missing data)")


def test_amenity_metrics():
    """Amenity density should be count / area_km2."""
    n_amenities = 20
    area_km2 = 4.0
    gdf = _make_amenity_gdf(n=n_amenities)
    metrics = _amenity_metrics(gdf, area_km2)

    print("\n[test_amenity_metrics]")
    print(f"  amenity_count: {metrics['amenity_count']}")
    print(f"  amenity_density: {metrics['amenity_density']}")

    assert metrics["amenity_count"] == n_amenities
    assert abs(metrics["amenity_density"] - n_amenities / area_km2) < 1e-9
    print("  PASSED")


def test_amenity_metrics_none():
    """None amenities should give zero count and density."""
    metrics = _amenity_metrics(None, 1.0)
    assert metrics["amenity_count"] == 0
    assert metrics["amenity_density"] == 0.0
    print("\n[test_amenity_metrics_none]  PASSED")


def test_walkability_index_bounds():
    """Walkability index should always be in [0, 100]."""
    scenarios = [
        {"junction_density": 0, "street_density_km_km2": 0,
         "dead_end_ratio": 1, "circuity_avg": 3, "amenity_density": 0},
        {"junction_density": 200, "street_density_km_km2": 50,
         "dead_end_ratio": 0, "circuity_avg": 1, "amenity_density": 100},
        {"junction_density": np.nan, "street_density_km_km2": np.nan,
         "dead_end_ratio": np.nan, "circuity_avg": np.nan, "amenity_density": np.nan},
        {"junction_density": 80, "street_density_km_km2": 15,
         "dead_end_ratio": 0.1, "circuity_avg": 1.2, "amenity_density": 25},
    ]
    print("\n[test_walkability_index_bounds]")
    for i, s in enumerate(scenarios):
        w = walkability_index(s)
        print(f"  scenario {i}: score = {w}")
        assert 0 <= w <= 100, f"Score out of range: {w}"
    print("  PASSED")


def test_full_metric_pipeline_synthetic():
    """
    Simulate a full SA2 metric calculation using a synthetic polygon and
    monkey-patching osm_data functions to avoid network calls.
    """
    import unittest.mock as mock

    # Synthetic 1km² polygon near Sydney CBD
    poly = Polygon([
        (151.200, -33.900),
        (151.209, -33.900),
        (151.209, -33.891),
        (151.200, -33.891),
    ])

    G = _make_grid_graph(5, 5, spacing=100)
    amenities = _make_amenity_gdf(n=15, area_polygon=poly)

    # Monkey-patch OSM functions to return synthetic data
    with mock.patch.object(osm_data, "get_road_network", return_value=G), \
         mock.patch.object(osm_data, "get_amenities", return_value=amenities):

        row = pd.Series({
            "sa_code":   "TEST001",
            "sa_name":   "Test Area",
            "muni_code": "5000",
            "muni_name": "Tel Aviv",
            "geometry":  poly,
        })

        result = calculate_sa2_metrics(row)

    print("\n[test_full_metric_pipeline_synthetic]")
    for k, v in result.items():
        print(f"  {k}: {v}")

    assert result["sa_code"] == "TEST001"
    assert result["error"] is None, f"Unexpected error: {result['error']}"
    assert result["area_km2"] > 0
    assert result["junction_density"] > 0
    assert result["walkability_index"] >= 0
    print("  PASSED")


def test_boundary_load_gdb():
    """
    Test loading statistical area boundaries from the GDB.
    Skips gracefully when the GDB symlink target is not present (CI / cloud env).
    """
    import os
    from load_boundaries import load_statistical_areas, list_gdb_layers

    print("\n[test_boundary_load_gdb]")

    if not os.path.exists(config.SA_GDB_PATH):
        print(f"  SKIP – GDB not found at {config.SA_GDB_PATH}")
        return

    layers = list_gdb_layers()
    print(f"  GDB layers: {layers}")
    assert len(layers) > 0, "GDB should have at least one layer"

    gdf = load_statistical_areas()
    print(f"  Loaded {len(gdf)} statistical areas")
    print(f"  Columns: {list(gdf.columns)}")
    print(f"  CRS: {gdf.crs}")
    print(f"  Sample:\n{gdf[['sa_code','sa_name','muni_code','muni_name']].head(3)}")

    assert len(gdf) > 0
    assert "sa_code" in gdf.columns
    assert "geometry" in gdf.columns
    assert gdf.crs.to_epsg() == 4326
    print("  PASSED")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        test_network_metrics_grid,
        test_network_metrics_none,
        test_amenity_metrics,
        test_amenity_metrics_none,
        test_walkability_index_bounds,
        test_full_metric_pipeline_synthetic,
        test_boundary_load_gdb,
    ]

    passed = 0
    failed = 0
    for fn in tests:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR ({type(e).__name__}): {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    run_all()
