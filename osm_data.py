"""
Fetch road network and amenity data from OpenStreetMap via osmnx.

Road network → used for junction density, street density, connectivity metrics.
Amenities     → used for market-access / POI density metrics.
"""

import warnings
import osmnx as ox
import geopandas as gpd
import networkx as nx
from shapely.geometry import Polygon, MultiPolygon

import config

# Configure osmnx
ox.settings.timeout = config.OSM_TIMEOUT
ox.settings.log_console = False
ox.settings.use_cache = True
ox.settings.cache_folder = config.CACHE_DIR


# ── Road network ─────────────────────────────────────────────────────────────

def get_road_network(polygon: Polygon | MultiPolygon):
    """
    Download the walkable street network within *polygon*.

    Returns a MultiDiGraph (osmnx graph) or None if no streets found.
    """
    try:
        G = ox.graph_from_polygon(
            polygon,
            network_type=config.NETWORK_TYPE,
            retain_all=False,
            simplify=True,
        )
        return G
    except Exception as exc:
        warnings.warn(f"Road network download failed: {exc}")
        return None


# ── Amenities ────────────────────────────────────────────────────────────────

def get_amenities(polygon: Polygon | MultiPolygon) -> gpd.GeoDataFrame | None:
    """
    Download amenity POIs within *polygon* using AMENITY_TAGS from config.

    Returns a GeoDataFrame (CRS=EPSG:4326) or None if nothing found / error.
    """
    try:
        gdf = ox.features_from_polygon(polygon, tags=config.AMENITY_TAGS)
        if gdf.empty:
            return None
        return gdf
    except Exception as exc:
        warnings.warn(f"Amenity download failed: {exc}")
        return None


# ── Graph helpers ─────────────────────────────────────────────────────────────

def graph_to_projected_gdfs(
    G,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Convert an osmnx graph to projected (metric) node/edge GeoDataFrames.
    Uses the equal-area CRS defined in config.PROJECTED_CRS.
    """
    nodes, edges = ox.graph_to_gdfs(G)
    nodes = nodes.to_crs(config.PROJECTED_CRS)
    edges = edges.to_crs(config.PROJECTED_CRS)
    return nodes, edges


def count_intersections(G) -> int:
    """
    Count true intersections (nodes with street degree >= 3) in the graph.
    Degree is street-count, not edge-count, to handle one-way streets.
    """
    # street_count attribute is added by osmnx during graph creation
    return sum(
        1 for _, data in G.nodes(data=True)
        if data.get("street_count", 0) >= 3
    )


def count_dead_ends(G) -> int:
    """Count dead-end nodes (street degree == 1)."""
    return sum(
        1 for _, data in G.nodes(data=True)
        if data.get("street_count", 0) == 1
    )
