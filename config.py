"""
Configuration for Israeli urbanism-quality analysis.

Geographic units: Israeli CBS Statistical Areas (ezorim statistiim, עזורים סטטיסטיים).
Each statistical area represents ~2,000–5,000 residents.  The 2022 edition
contains ~3,000 areas covering all of Israel and the settlements.

Road data and amenity POIs are fetched from OpenStreetMap via osmnx.
"""

import os

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

for _d in [RAW_DIR, PROCESSED_DIR, CACHE_DIR]:
    os.makedirs(_d, exist_ok=True)

# Symlink in the repo → actual GDB directory delivered separately
SA_GDB_PATH = os.path.join(BASE_DIR, "ezorim_statistiim_2022.gdb")

# Output files
METRICS_OUTPUT_FILE = os.path.join(PROCESSED_DIR, "urbanism_metrics.csv")
CHECKPOINT_FILE = os.path.join(PROCESSED_DIR, "checkpoint.csv")

# ── Statistical area filtering ────────────────────────────────────────────────
# Set to a list of SEMEL_YISHUV (municipality codes) to restrict processing.
# None = process all statistical areas.
FILTER_MUNICIPALITIES = None

# Cap the number of SAs to process (useful for testing). None = no cap.
MAX_AREAS = None

# ── OSM / osmnx settings ─────────────────────────────────────────────────────
NETWORK_TYPE = "walk"

# Tags for amenities (daily-life POIs for market-access metric)
AMENITY_TAGS = {
    "shop": True,
    "amenity": [
        "supermarket", "marketplace", "pharmacy", "hospital",
        "clinic", "school", "kindergarten", "restaurant",
        "cafe", "bar", "bank", "post_office", "library",
    ],
    "landuse": ["retail", "commercial"],
}

OSM_TIMEOUT = 180

# ── Projected CRS for area calculations ──────────────────────────────────────
# ITM (Israeli Transverse Mercator) — official Israeli metric CRS
PROJECTED_CRS = "EPSG:2039"
