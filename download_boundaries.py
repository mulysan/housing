"""
Download SA2 (Statistical Area Level 2) digital boundaries from ABS.

Primary source  : ABS ASGS Edition 3 (2021) via ABS ArcGIS REST API.
Fallback source : GitHub-hosted PSMA suburb polygons (tonywr71/GeoJson-Data).
                  These are suburb-level boundaries — a close proxy for SA2.

Boundaries returned in WGS84 (EPSG:4326).
"""

import os
import warnings
import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from tqdm import tqdm

import config

# ── GitHub fallback: PSMA suburb polygons ────────────────────────────────────
# Maps ABS state code → (GitHub raw URL, name-field suffix for that state)
_GITHUB_SUBURB_URLS = {
    1: ("https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/suburb-10-nsw.geojson", "nsw"),
    2: ("https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/suburb-10-vic.geojson", "vic"),
    3: ("https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/suburb-10-qld.geojson", "qld"),
    4: ("https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/suburb-10-sa.geojson",  "sa"),
    5: ("https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/suburb-10-wa.geojson",  "wa"),
    6: ("https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/suburb-10-tas.geojson", "tas"),
    7: ("https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/suburb-10-nt.geojson",  "nt"),
    8: ("https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/suburb-10-act.geojson", "act"),
}


# ── ABS ArcGIS REST API ───────────────────────────────────────────────────────

def _fetch_abs_page(offset: int, where_clause: str, page_size: int) -> dict:
    """Fetch one page of SA2 features from the ABS ArcGIS REST API."""
    params = {
        "where": where_clause,
        "outFields": (
            "SA2_CODE21,SA2_NAME21,SA3_CODE21,SA3_NAME21,"
            "SA4_CODE21,SA4_NAME21,GCC_CODE21,GCC_NAME21,"
            "STE_CODE21,STE_NAME21,AREASQKM21"
        ),
        "outSR": "4326",
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": page_size,
        "geometryPrecision": 6,
    }
    r = requests.get(config.ABS_SA2_API, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def _download_from_abs(state_codes: list[int] | None) -> gpd.GeoDataFrame:
    """Download SA2 boundaries from the ABS ArcGIS REST API."""
    if state_codes:
        quoted = ",".join(f"'{c}'" for c in state_codes)
        where_clause = f"STE_CODE21 IN ({quoted})"
    else:
        where_clause = "1=1"

    features = []
    offset = 0
    page_size = config.ABS_REQUEST_SIZE

    print(f"Fetching SA2 boundaries from ABS API (filter: {where_clause}) …")
    with tqdm(unit=" features") as pbar:
        while True:
            data = _fetch_abs_page(offset, where_clause, page_size)
            batch = data.get("features", [])
            if not batch:
                break
            features.extend(batch)
            pbar.update(len(batch))
            offset += len(batch)
            if len(batch) < page_size:
                break

    if not features:
        raise RuntimeError("No features returned from ABS API.")

    rows = []
    for f in features:
        props = f["properties"]
        geom = shape(f["geometry"]) if f.get("geometry") else None
        rows.append({**props, "geometry": geom})

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    gdf.columns = [c.lower().rstrip("21") for c in gdf.columns]
    print(f"  → {len(gdf):,} SA2s downloaded from ABS.")
    return gdf


# ── GitHub / PSMA suburb fallback ────────────────────────────────────────────

def _download_from_github(state_codes: list[int] | None) -> gpd.GeoDataFrame:
    """
    Download suburb-level boundaries from GitHub (PSMA data via tonywr71/GeoJson-Data).

    Note: these are suburb polygons, used as a proxy for SA2 when the ABS API
    is unreachable.  They carry a 'source=psma_suburb' attribute.
    """
    states = state_codes if state_codes else list(_GITHUB_SUBURB_URLS.keys())
    all_frames = []

    for state_code in states:
        if state_code not in _GITHUB_SUBURB_URLS:
            continue
        url, prefix = _GITHUB_SUBURB_URLS[state_code]
        print(f"  Downloading {config.STATE_CODES.get(state_code, state_code)} suburbs from GitHub …")

        r = requests.get(url, timeout=90)
        r.raise_for_status()
        data = r.json()

        rows = []
        for feat in data.get("features", []):
            props = feat["properties"]
            geom = shape(feat["geometry"]) if feat.get("geometry") else None

            # The name field pattern is "{state_prefix}_loca_2" (all-caps suburb name)
            name_field = f"{prefix}_loca_2"
            suburb_name = props.get(name_field, "")
            loc_pid = props.get("loc_pid", "")
            state_field = f"{prefix}_loca_7"
            state_code_val = props.get(state_field, str(state_code))

            rows.append({
                "sa2_code": loc_pid,
                "sa2_name": suburb_name or loc_pid,
                "ste_code": str(state_code),
                "ste_name": config.STATE_CODES.get(state_code, ""),
                "geometry": geom,
                "source": "psma_suburb",
            })

        frame = gpd.GeoDataFrame(rows, crs="EPSG:4326")
        all_frames.append(frame)
        print(f"    → {len(frame):,} suburbs")

    if not all_frames:
        raise RuntimeError("No suburb data retrieved from GitHub.")

    gdf = gpd.GeoDataFrame(pd.concat(all_frames, ignore_index=True), crs="EPSG:4326")
    print(f"  → {len(gdf):,} suburb polygons total (proxy for SA2).")
    warnings.warn(
        "Using PSMA suburb boundaries as a proxy for ABS SA2 boundaries. "
        "SA2 codes will be PSMA locality IDs, not official ABS codes.",
        UserWarning,
        stacklevel=2,
    )
    return gdf


# ── Public API ────────────────────────────────────────────────────────────────

def download_sa2_boundaries(state_codes: list[int] | None = None) -> gpd.GeoDataFrame:
    """
    Download SA2 (or suburb proxy) boundaries.

    Tries the ABS ArcGIS REST API first; falls back to GitHub-hosted PSMA
    suburb polygons if the ABS API is unreachable.

    Parameters
    ----------
    state_codes : list of int, optional
        ABS state codes (see config.STATE_CODES). None = all states.

    Returns
    -------
    GeoDataFrame (CRS = EPSG:4326)
    """
    try:
        return _download_from_abs(state_codes)
    except Exception as abs_err:
        warnings.warn(
            f"ABS API unavailable ({abs_err}). Falling back to GitHub suburb data.",
            UserWarning,
            stacklevel=2,
        )
        return _download_from_github(state_codes)


def load_or_download_boundaries(
    state_codes: list[int] | None = None,
    force_download: bool = False,
) -> gpd.GeoDataFrame:
    """
    Load boundaries from local cache if available, otherwise download.

    Parameters
    ----------
    state_codes : list of int, optional
    force_download : bool
        Re-download even if a cached file exists.
    """
    path = config.SA2_BOUNDARIES_FILE

    if os.path.exists(path) and not force_download:
        print(f"Loading boundaries from cache: {path}")
        gdf = gpd.read_file(path)
        if state_codes:
            gdf = gdf[gdf["ste_code"].astype(str).isin([str(c) for c in state_codes])].copy()
        print(f"  → {len(gdf):,} areas loaded.")
        return gdf

    gdf = download_sa2_boundaries(state_codes=state_codes)
    gdf.to_file(path, driver="GPKG")
    print(f"  Saved to {path}")
    return gdf


if __name__ == "__main__":
    gdf = load_or_download_boundaries(state_codes=config.FILTER_STATES)
    print(gdf[["sa2_code", "sa2_name", "ste_name"]].head(10))
