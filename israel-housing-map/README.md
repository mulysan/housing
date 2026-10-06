# Israel housing map

Code for the parcel-level housing price map and its analysis page. The working notes and all
findings are in the research wiki (`mulysan/-econ-research-wiki`,
`wiki/projects/israel-housing-map.md`); this folder holds the same scripts so they can be run on
their own.

Two published pages are built from the same data:

- **Map** (`housing_map.html`): every residential gush-parcel as a point, coloured by price per m²,
  price change, turnover, height, vintage, renewal feasibility, OSM intersection density or
  building fixed effect, with a side panel per district, subdistrict and city. The street
  background is OpenStreetMap, served as small tiles next to the page (`roads/`).
- **Analysis** (`housing_report.html`): four real price indices, the rooms-as-instrument
  (division bias) regressions, the hedonic model, floor premium, urban form vs building
  premium, the OSM junction validation, effective supply, renewal economics, choropleths of
  every variable by year and unit, and an area explorer.

## Data (none of it is committed; rebuild with the fetch scripts)

| Source | How | Script |
|---|---|---|
| Tax Authority deals (Real estate, 1998–2026) | over.org.il dataset `fd06f5ae-8a4f-4120-b275-8a514ad23499`, `/api/append/{id}/download.csv` | `curl` (see wiki) |
| National assets gazetteer (Survey of Israel, free version) | odata.org.il `gaztir` (Google Drive file) | see `raw/data/national-assets-gazetteer/README.md` in the wiki |
| Cadastral parcels | over.org.il dataset `ff3176b1-…`, SQL endpoint | `fetch_parcel_centroids.py`, `fetch_parcel_geoms.py`, `fetch_big_thin_parcels.py` |
| govmap deals (unit floor) | over.org.il `public.govmap_deals` | `fetch_govmap_deals.py` |
| District / subdistrict | over.org.il `public.over_re_parcels` | `fetch_gush_region.py` |
| CBS statistical areas 2011 + SES 2021, population, land use; GTFS stops, light rail, schools, addresses | over.org.il | `fetch_urban_layers.py` |
| OpenStreetMap streets and boundaries | Overture Maps (public S3, release 2026-09-23.1) | `fetch_overture_roads.py` |
| CPI | CBS monthly CPI (`cpi.xlsx`) | — |

## Build order

```
fetch_parcel_centroids → fetch_urban_layers → geocode_parcels → build_prices → fetch_parcel_geoms
→ fetch_big_thin_parcels → fetch_gush_region → fetch_govmap_deals → build_txn → build_hedonic
→ build_iv → build_floor → fetch_overture_roads → build_urban → val_summary → build_areas
→ build_varmap → build_basemap_osm → build_page_v4 MAP_URL REPORT_URL
```

`map_v4_template.html` is the page template (one template, two pages; `make_v4_template.py`
derived it from the earlier single-page `map_v3_template.html`).

## Notes

- **Judea and Samaria.** The Survey of Israel parcel layer does not cover Civil Administration
  gushim, so those parcels have no polygon. `geocode_parcels.py` places them by matching the
  gazetteer street to the OSM street inside the CBS locality, or else at the gush or locality
  centre (`loc_q` 2–4). Urban land there comes from an OSM street footprint.
- **Intersection density** is OSM drive-network intersections (street count ≥ 3, OSMnx-style
  consolidation at 10 m) per km² of urban land, per CBS statistical area (`osm_streets.py`).
  The earlier cadastral measure (`roads.py`, `junctions.py`) is kept for comparison.
