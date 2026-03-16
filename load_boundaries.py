"""
Load Israeli CBS statistical-area (ezor statistii) boundaries from the
local GDB file (ezorim_statistiim_2022.gdb → symlink to the actual data).

The GDB typically contains a layer named something like "ezorim_statistiim"
with one polygon per statistical area and attributes such as:
  EZOR       – statistical area code
  SHEM_EZOR  – statistical area name (Hebrew)
  YISHUV     – municipality code
  SHEM_YISHUV– municipality name (Hebrew)
  MACHOZ     – district code
  SHEM_MACHOZ– district name (Hebrew)
  (attribute names may vary by edition; we normalise them below)
"""

import os
import sys
import warnings

import fiona
import geopandas as gpd

import config


# ── Column normalisation map ──────────────────────────────────────────────────
# Maps possible raw field names (uppercase) → our canonical lower_snake names.
_FIELD_MAP = {
    # Statistical area
    "EZOR":          "sa_code",
    "SEMEL_EZOR":    "sa_code",
    "KOD_EZOR":      "sa_code",
    "SHEM_EZOR":     "sa_name",
    # Municipality
    "YISHUV":        "muni_code",
    "SEMEL_YISHUV":  "muni_code",
    "KOD_YISHUV":    "muni_code",
    "SHEM_YISHUV":   "muni_name",
    # District
    "MACHOZ":        "district_code",
    "SEMEL_MACHOZ":  "district_code",
    "SHEM_MACHOZ":   "district_name",
    # Sub-district
    "NAFA":          "subdistrict_code",
    "SEMEL_NAFA":    "subdistrict_code",
    "SHEM_NAFA":     "subdistrict_name",
    # Natural region
    "EZOR_TEVA":     "natural_region_code",
    "SHEM_EZ_TEVA":  "natural_region_name",
}


def _best_layer(gdb_path: str) -> str:
    """
    Return the best layer name to open from the GDB.
    Prefers layers whose name contains 'ezor' (case-insensitive).
    """
    layers = fiona.listlayers(gdb_path)
    for layer in layers:
        if "ezor" in layer.lower():
            return layer
    # Fallback: first layer
    return layers[0]


def _normalise_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Rename raw GDB field names to canonical lower_snake names."""
    rename = {}
    for col in gdf.columns:
        canonical = _FIELD_MAP.get(col.upper())
        if canonical and canonical not in gdf.columns:
            rename[col] = canonical
    if rename:
        gdf = gdf.rename(columns=rename)

    # Ensure mandatory columns exist (fill with empty string if missing)
    for col in ["sa_code", "sa_name", "muni_code", "muni_name"]:
        if col not in gdf.columns:
            gdf[col] = ""
            warnings.warn(f"Column '{col}' not found in GDB; filled with empty string.")

    return gdf


def load_statistical_areas(
    muni_codes: list | None = None,
    layer: str | None = None,
    to_wgs84: bool = True,
) -> gpd.GeoDataFrame:
    """
    Load statistical area boundaries from the GDB symlink.

    Parameters
    ----------
    muni_codes : list, optional
        Municipality codes (SEMEL_YISHUV) to include. None = all areas.
    layer : str, optional
        GDB layer name. Auto-detected if None.
    to_wgs84 : bool
        Reproject to EPSG:4326 (WGS84) if True (default).

    Returns
    -------
    GeoDataFrame with normalised column names and geometry.
    """
    gdb = config.SA_GDB_PATH

    if not os.path.exists(gdb):
        raise FileNotFoundError(
            f"Statistical area GDB not found at: {gdb}\n"
            "Please ensure the census data directory exists at the symlink target:\n"
            f"  {os.path.realpath(gdb) if os.path.islink(gdb) else gdb}"
        )

    layer_name = layer or _best_layer(gdb)
    print(f"Loading layer '{layer_name}' from {gdb} …")

    gdf = gpd.read_file(gdb, layer=layer_name)
    print(f"  → {len(gdf):,} statistical areas loaded (CRS: {gdf.crs})")

    gdf = _normalise_columns(gdf)

    # Optional municipality filter
    if muni_codes is not None:
        gdf = gdf[gdf["muni_code"].astype(str).isin([str(c) for c in muni_codes])].copy()
        print(f"  → {len(gdf):,} areas after municipality filter.")

    # Drop areas without geometry
    n_before = len(gdf)
    gdf = gdf[~gdf.geometry.isna() & gdf.geometry.is_valid].copy()
    if len(gdf) < n_before:
        warnings.warn(f"Dropped {n_before - len(gdf)} areas with null/invalid geometry.")

    # Reproject to WGS84 for OSM queries
    if to_wgs84 and gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")
        print(f"  → Reprojected to WGS84 (EPSG:4326).")

    return gdf


def list_gdb_layers() -> list[str]:
    """Return names of all layers in the GDB (for inspection)."""
    gdb = config.SA_GDB_PATH
    if not os.path.exists(gdb):
        raise FileNotFoundError(f"GDB not found: {gdb}")
    return fiona.listlayers(gdb)


if __name__ == "__main__":
    # Quick inspection: list layers and show first few rows
    print("GDB layers:", list_gdb_layers())
    gdf = load_statistical_areas()
    print("\nSchema:")
    print(gdf.dtypes)
    print("\nSample:")
    print(gdf[["sa_code", "sa_name", "muni_code", "muni_name"]].head(10).to_string())
