# Urban form per CBS statistical area (2011) and how much of the building
# price premium (building fixed effect) it accounts for.
#
# UNIT. CBS statistical areas of 2011 (3,187; the unit with SES and population data). Every building
# gets the values of the SA its parcel location falls in.
# DENOMINATOR. "Urban land" = total area of the SA's cadastral parcels smaller than 5 ha (streets,
# residential, commercial and public parcels; excludes farmland, forest and large open parcels, so
# that SAs with a built core and a large rural fringe are not diluted). Where the cadastre has no
# parcels (Judea and Samaria) it is the SA area within 60 m of a drivable/service OSM street, scaled
# by 1.04, the median ratio of the two in well-covered Israeli SAs. SAs with < 0.02 km2 are dropped.
#
# MEASURES (per km2 of urban land unless stated):
#  Street network - OpenStreetMap via Overture Maps (osm_streets.py, fetch_overture_roads.py;
#   overpass-api.de and Geofabrik are unreachable from the container). Main measure: drive-network
#   intersections (street count >= 3) consolidated OSMnx-style at 10 m. Also: walk-network
#   intersections, km of street, dead-end and 4-way shares, orientation entropy, circuity (curvature).
#   The earlier cadastral measure (road parcels flagged by shape, skeleton junctions; roads.py,
#   junctions.py) is kept as junc_dens_cad for comparison. (A first try with block density - merging
#   non-road parcels into blocks - failed: one missed street merges a neighbourhood.)
#  Road share - area of road parcels / urban land (cadastre; missing where there is no cadastre).
#  Parcel size - median area of non-road parcels under 5 ha (cadastre).
#  Dwelling density - registered units (gazetteer) / urban land; population 2015 (CBS) / urban land.
#  Land-use mix - normalised entropy of the CBS 2014 land-use grid (100 m cells, built-up uses);
#   commercial share = share of cells in commerce / town-centre uses.
#  Commerce - businesses with a public listing (Overture places, confidence >= 0.5, see below).
#  Parking - OSM parking lots, structures and garage entrances; share of land in mapped lots.
#  Transport - bus stops (GTFS), rail and light-rail stations within 1 km; building-level distance to
#   the nearest station, to the Tel Aviv CBD (Azrieli) and to the coast.
#  Schools - education institutions (Ministry of Education, govmap layer 18).
#  Social - CBS socio-economic cluster 2021; Knesset 25 vote shares (build_votes.py).
#
# BUILDING PREMIUM. ln(price per m2 / CPI) = building FE + month FE + rounded-m2 FE on all apartment
# deals (table a); the building FE (fe) is the price level of a building net of time and unit size.
# Regressions use buildings with >= 3 deals, weights min(deals, 50) (so a few large projects do not
# dominate), SEs clustered by SA, and variables standardised to SD units.
#
# Inputs (cwd): parcel_geoms.tsv (fetch_parcel_geoms.py), sa2011.csv,
# sa_pop2015.csv, stops.csv, lrt.csv, schools.csv, landuse_pts.csv,
# addresses.csv (fetch_urban_layers.py), ov_segments.parquet, ov_connectors.parquet
# (fetch_overture_roads.py), parcel_centroids.csv, h.db
# (build_prices.py), cpi.xlsx, land-data.json.
# Output: urban_v3.json, sa_urban.csv, bld_fe.csv
import json, numpy as np, pandas as pd, duckdb, shapely
from shapely import STRtree
LAT0 = 31.8; KX = 111320*np.cos(np.radians(LAT0)); KY = 110574
def proj(g):   # lon/lat -> local metres (equirectangular around 31.8N)
    return shapely.transform(g, lambda c: np.c_[c[:, 0]*KX, c[:, 1]*KY])

# ---------- statistical areas ----------
sa = pd.read_csv('sa2011.csv')
sa = sa[sa.sa > 0].reset_index(drop=True)
sa_geom = proj(shapely.from_wkt(sa.wkt.values)); sa = sa.drop(columns='wkt')
sa_tree = STRtree(sa_geom)
def to_sa(x, y):
    """index into sa for metre points (x, y); -1 if none"""
    pts = shapely.points(x, y); out = np.full(len(pts), -1)
    i, j = sa_tree.query(pts, predicate='within'); out[i] = j; return out

# ---------- parcels: roads vs blocks ----------
P = pd.read_csv('parcel_geoms.tsv', sep='\t', header=None, names=['gush', 'parcel', 'wkt'])
g = proj(shapely.from_wkt(P.wkt.values)); P = P.drop(columns='wkt')
ok = ~shapely.is_empty(g) & shapely.is_valid(g)
g = np.where(ok, g, shapely.make_valid(g))
c = duckdb.connect('h.db', read_only=True)
res_set = set(map(tuple, c.sql("select gush, parcel from p").fetchall()))   # parcels with registered homes
from roads import road_flags as _rf
road_flags = lambda gm, gush, parcel: _rf(gm, gush, parcel, res_set)
P['road'], P['A'] = road_flags(g, P.gush.values, P.parcel.values)
rp = shapely.point_on_surface(g)
P['sa'] = to_sa(shapely.get_x(rp), shapely.get_y(rp))
print('parcels', len(P), 'road share of parcels', P.road.mean().round(3), 'assigned to SA', (P.sa >= 0).mean().round(3))

# Intersections: branch points (>= 3 branches) of the skeleton of the rasterised road network
# (all road parcels unioned, 2 m pixels, spurs < 24 m pruned, merged within 20 m; junctions.py,
# junctions_skel). This also finds intersections inside a single road parcel, which the earlier
# parcel-contact counts missed. Validated against OSM 3+-way nodes in 1 km2 boxes (see wiki).
from junctions import junctions_skel
jx, jy, jdeg, jkind = junctions_skel(g[P.road.values])
jsa = to_sa(jx, jy)
np.save('junctions_xy_m.npy', np.c_[jx, jy])
print('junctions', len(jx), 'in SAs', (jsa >= 0).sum())
small = P[(P.sa >= 0) & (P.A < 50000)]                   # urban land: parcels under 5 ha (incl. streets)
U = pd.DataFrame({'urb_km2': small.groupby('sa').A.sum()/1e6,
                  'road_km2': small[small.road].groupby('sa').A.sum()/1e6,
                  'n_parcels': small.groupby('sa').size(),
                  'parcel_med': small[~small.road].groupby('sa').A.median()}).fillna({'road_km2': 0})
U = U.reindex(range(len(sa))).fillna({'urb_km2': 0, 'road_km2': 0, 'n_parcels': 0})
U['n_junc'] = pd.Series(jsa[jsa >= 0]).value_counts().reindex(U.index).fillna(0)

# OSM street network (osm_streets.py: Overture's OSM-derived road segments). Main measure:
# drive-network intersections (street count >= 3), consolidated OSMnx-style at tolerance 10 m.
# The cadastral skeleton count is kept as n_junc_cad / junc_dens_cad for comparison.
import osm_streets as OS
OSS, OSC = OS.load()

# Urban land where the cadastre has no parcels (Judea and Samaria: Civil Administration land, not in
# the Survey of Israel layer): the SA area within 60 m of an OSM drive or service street, scaled by
# the median ratio of parcel-based urban land to that footprint in well-covered Israeli SAs.
cov = (P[P.sa >= 0].groupby('sa').A.sum().reindex(U.index).fillna(0) / sa.area_m2.values).clip(upper=1)
sgm = OSS[OSS.drive.values | (OSS['class'] == 'service').values]
sgeo = shapely.transform(shapely.from_wkb(sgm.geometry.values), lambda c: np.c_[c[:, 0]*KX, c[:, 1]*KY])
stree = STRtree(sgeo)
def foot(i):
    poly = sa_geom[i]; k = stree.query(poly, predicate='intersects')
    if not len(k): return 0.0
    return shapely.area(shapely.intersection(shapely.union_all(shapely.buffer(sgeo[k], 60, quad_segs=2)), poly))/1e6
low = np.where(cov.values < 0.3)[0]
cal = U[(cov > 0.8) & (U.urb_km2 > 0.1)].sample(300, random_state=0).index
ratio = float(np.median([U.urb_km2[i]/f for i in cal if (f := foot(i)) > 0]))
U['urb_src'] = 'parcels'
for i in low:
    f = foot(i)
    if f > 0: U.loc[i, ['urb_km2', 'urb_src']] = [ratio*f, 'osm']
print('SAs with low cadastral coverage', len(low), 'urban land from OSM footprint', int((U.urb_src == 'osm').sum()), 'ratio', round(ratio, 3))
U = U[U.urb_km2 > 0.02]
U['road_share'] = (U.road_km2 / U.urb_km2).where(U.urb_src == 'parcels')
U['n_junc_cad'] = U.n_junc.where(U.urb_src == 'parcels')
for net in ['drive', 'walk']:
    N = OS.nodes(OSS, OSC, OSS[net].values); I = N[N.k >= 3]
    cx_o, cy_o, lab = OS.consolidate(I.x.values, I.y.values, 10)
    s_o = to_sa(cx_o, cy_o)
    U[f'n_junc_{net}'] = pd.Series(s_o[s_o >= 0]).value_counts().reindex(U.index).fillna(0)
    print(f'OSM {net}: nodes {len(N)}, 3+-way {len(I)}, consolidated {len(cx_o)}, in SAs {(s_o >= 0).sum()}')
    if net == 'drive':
        np.save('junctions_osm_xy_m.npy', np.c_[cx_o, cy_o])
        ns = to_sa(N.x.values, N.y.values)
        # dead-end share: dead ends / (dead ends + intersections); 4-way share: 4+-way / 3+-way (raw nodes)
        cnt = lambda m: pd.Series(ns[m & (ns >= 0)]).value_counts().reindex(U.index).fillna(0)
        n1, n3, n4 = cnt(N.k.values == 1), cnt(N.k.values >= 3), cnt(N.k.values >= 4)
        U['deadend_share'] = (n1 / (n1 + n3)).where(n1 + n3 >= 5)
        U['fourway_share'] = (n4 / n3).where(n3 >= 5)
    ex, ey, L, brg = OS.edges(OSS, OSS[net].values)
    es = to_sa(ex, ey); k = es >= 0
    U[f'street_km_{net}'] = pd.Series(L[k]/1000).groupby(es[k]).sum().reindex(U.index).fillna(0)
    if net == 'drive':
        E = pd.DataFrame({'s': es[k], 'L': L[k], 'b': brg[k]})
        U['orient_ent'] = E.groupby('s').apply(lambda d: OS.orient_entropy(d.b.values, d.L.values) if d.L.sum() > 1000 else np.nan).reindex(U.index)
U['n_junc'] = U.n_junc_drive
U['junc_dens'] = U.n_junc / U.urb_km2                    # OSM drive intersections per km2 of urban land
U['junc_dens_cad'] = U.n_junc_cad / U.urb_km2            # cadastral skeleton
U['junc_dens_walk'] = U.n_junc_walk / U.urb_km2
U['street_dens'] = U.street_km_drive / U.urb_km2         # km of drivable street per km2
U['street_dens_walk'] = U.street_km_walk / U.urb_km2
U.index.name = 'si'; U = U.reset_index().join(sa, on='si')
print('SAs', len(U))

# ---------- other layers, counted per SA ----------
def pts(fn, **kw):
    d = pd.read_csv(fn, **kw); return d, d.lon.values*KX, d.lat.values*KY
def count_by_sa(x, y, mask=None):
    s = to_sa(x, y) if mask is None else to_sa(x[mask], y[mask])
    return pd.Series(s[s >= 0]).value_counts()
stops, sx, sy = pts('stops.csv')
U['bus_stops'] = U.si.map(count_by_sa(sx, sy, (stops.kind == 'bus').values)).fillna(0)
addr, ax, ay = pts('addresses.csv')
U['addresses'] = U.si.map(count_by_sa(ax, ay)).fillna(0)
sch, cx, cy = pts('schools.csv')
U['schools'] = U.si.map(count_by_sa(cx, cy)).fillna(0)
lu, lx, ly = pts('landuse_pts.csv')
lu['si'] = to_sa(lx, ly)
grpmap = {21: 'res', 9: 'center', 11: 'comm', 12: 'ind', 1: 'edu', 2: 'health', 3: 'relig', 7: 'culture', 5: 'public',
          20: 'public', 4: 'public', 8: 'hotel', 33: 'park', 10: 'comm', 25: 'transport', 29: 'roads'}
lu['cat'] = lu.code.map(grpmap)
lu = lu[(lu.si >= 0) & lu.cat.notna() & (lu.cat != 'roads')]
ct = pd.crosstab(lu.si, lu.cat)
sh = ct.div(ct.sum(axis=1), axis=0)
U['lu_n'] = U.si.map(ct.sum(axis=1)).fillna(0)
U['mix'] = U.si.map(-(sh*np.log(sh.where(sh > 0))).sum(axis=1) / np.log(sh.shape[1])).fillna(0)   # normalized entropy
U['comm_share'] = U.si.map(sh[['center', 'comm']].sum(axis=1)).fillna(0)
pop = pd.read_csv('sa_pop2015.csv'); pop = pop[pop['sa'] > 0].drop_duplicates('sa').set_index('sa')
U['pop2015'] = U.sa.map(pd.to_numeric(pop['pop'], errors='coerce'))
U['religion'] = U.sa.map(pop['religion'])

# ---------- added 2026-10-08: commerce, parking, street curvature, rail stations, votes ----------
# Commercial units: Overture places (fetch_overture_extra.py). Overture recommends a confidence filter;
# 0.5 drops the long tail of stale or duplicated listings (median confidence in Israel is 0.60).
# "Commercial" = every category except public, civic, religious, educational, health-system, natural
# and transport ones (a keyword list on Overture's basic_category). Clinics, pharmacies, hotels,
# offices and all shops, restaurants and services count. The result is a count of businesses with a
# public listing, a proxy for the number of commercial units (no open registry of non-residential
# units exists; the gazetteer has residential assets only).
PL = pd.read_parquet('ov_places.parquet')
NONCOM = ['school', 'learning', 'education', 'preschool', 'college', 'university', 'hospital', 'religio', 'worship',
          'church', 'mosque', 'synagogue', 'park', 'historic', 'monument', 'government', 'public_service', 'community',
          'social', 'cemetery', 'military', 'landmark', 'nature', 'beach', 'mountain', 'structure', 'bus', 'train',
          'station', 'airport', 'parking', 'police', 'fire', 'library', 'museum', 'embassy', 'courthouse', 'post_office',
          'playground', 'garden', 'forest', 'river', 'lake', 'island', 'bridge', 'road', 'street']
cat = PL.basic_category.fillna('').str.lower()
is_com = (PL.confidence >= 0.5) & (cat != '') & ~cat.apply(lambda c: any(k in c for k in NONCOM))
U['commerce'] = U.si.map(count_by_sa(PL.lon.values*KX, PL.lat.values*KY, is_com.values)).fillna(0)
U['comm_dens'] = U.commerce / U.urb_km2
print('commercial places', int(is_com.sum()), 'of', len(PL))
# Parking: Overture base/infrastructure features with class "parking" (OSM amenity=parking: surface lots
# and multi-storey structures) and "parking_entrance" (mostly entrances to underground garages).
# Two measures: facilities per km2 of urban land, and the share of urban land covered by mapped parking
# polygons. OSM mapping of parking is uneven across cities and private building parking is not mapped,
# so this is a measure of visible public parking supply, not of residents' parking.
PK = pd.read_parquet('ov_parking.parquet')
PK = PK[PK['class'].isin(['parking', 'parking_entrance'])]
pg = proj(shapely.from_wkb(PK.geometry.values))
pp = shapely.point_on_surface(pg)
U['parking_n'] = U.si.map(count_by_sa(shapely.get_x(pp), shapely.get_y(pp))).fillna(0)
U['parking_dens'] = U.parking_n / U.urb_km2
poly = shapely.get_type_id(pg) >= 3
U['parking_km2'] = U.si.map(pd.Series(shapely.area(pg[poly])/1e6).groupby(to_sa(shapely.get_x(pp[poly]), shapely.get_y(pp[poly]))).sum()).fillna(0)
U['parking_share'] = (U.parking_km2 / U.urb_km2).clip(upper=1)
# Street curvature: circuity of the drive network (osm_streets.circuity_pieces): network length / chord
# between intersections and dead ends, length-weighted over pieces whose midpoint is in the SA
# (= sum of lengths / sum of chords, Boeing's "average circuity"). Missing if under 1 km of street.
cxm, cym, cnet, cch = OS.circuity_pieces(OSS, OSC, OSS.drive.values)
csa = to_sa(cxm, cym); k_ = csa >= 0
cn = pd.Series(cnet[k_]).groupby(csa[k_]).sum(); cc = pd.Series(cch[k_]).groupby(csa[k_]).sum()
U['circuity'] = U.si.map((cn/cc).where(cn >= 1000))
# Rail and light-rail stations: stations (GTFS rail stops + light-rail entrances) within 1 km of the SA
# polygon. Complements the building-level distance to the nearest station (d_rail below).
_st = pd.concat([stops[stops.kind == 'rail'][['lon', 'lat']], pd.read_csv('lrt.csv')[['lon', 'lat']]])
_sp = shapely.points(_st.lon.values*KX, _st.lat.values*KY)
_i, _j = STRtree(sa_geom).query(_sp, predicate='dwithin', distance=1000)
U['rail_1km'] = U.si.map(pd.Series(_j).value_counts()).fillna(0)
# Vote shares, Knesset 25 (build_votes.py): Haredi parties (UTJ + Shas), UTJ alone, Arab parties, turnout.
VT = pd.read_csv('sa_votes.csv').set_index('sa')
for v in ['haredi', 'utj', 'arab', 'turnout', 'vgroup']: U[v] = U.sa.map(VT[v])

# ---------- buildings: gazetteer parcels with centroid, SA, distances ----------
B = c.sql("""select p.gush, p.parcel, p.units, p.fl, p.yr, p.city, cen.lat, cen.lon, cen.loc_q from p join cen using(gush, parcel)""").df()
bx, by = B.lon.values*KX, B.lat.values*KY
B['si'] = to_sa(bx, by)
rail = stops[stops.kind == 'rail']; lrt = pd.read_csv('lrt.csv')
st = np.r_[np.c_[rail.lon*KX, rail.lat*KY], np.c_[lrt.lon*KX, lrt.lat*KY]]
from scipy.spatial import cKDTree
B['d_rail'] = cKDTree(st).query(np.c_[bx, by])[0]/1000
B['d_cbd'] = np.hypot(bx - 34.7915*KX, by - 32.0745*KY)/1000            # Azrieli / Ha-Shalom, Tel Aviv
# Distance to the sea (km): straight-line distance to the nearest point of the coastline, taken from the
# outer boundary of the Overture land polygon (Israel + West Bank + Gaza, land_full.wkb, merged so internal
# borders vanish), densified to ~40 m. Coast = Mediterranean (boundary points between 31.2N and the Lebanese
# border at 33.088N, west of 35.11E - the land borders there lie further east) plus the Red Sea at Eilat
# (boundary south of 29.56N, east of 34.905E, i.e. the gulf shore between Taba and Aqaba).
# (Until 2026-10-08 this used the westmost vertex of a coarse land outline per 0.02 deg latitude band; bands
# with no coastal vertex picked up a point on the eastern border, so ~1/3 of buildings got a negative
# distance, and Eilat and the south were missing.)
_land = shapely.union_all(shapely.buffer(shapely.from_wkb(open('land_full.wkb', 'rb').read()), 0.0003))
_ext = shapely.multilinestrings([p.exterior for p in getattr(_land, 'geoms', [_land])])
_cc = shapely.get_coordinates(shapely.segmentize(_ext, 0.0004))
_cc = _cc[((_cc[:, 1] > 31.2) & (_cc[:, 1] < 33.088) & (_cc[:, 0] < 35.11)) | ((_cc[:, 1] < 29.56) & (_cc[:, 0] > 34.905))]
B['d_coast'] = cKDTree(np.c_[_cc[:, 0]*KX, _cc[:, 1]*KY]).query(np.c_[bx, by])[0]/1000
# units in SA (gazetteer) -> residential density
U['units'] = U.si.map(B.groupby('si').units.sum()).fillna(0)
U['units_dens'] = U.units / U.urb_km2
U['pop_dens'] = U.pop2015 / U.urb_km2
U['addr_dens'] = U.addresses / U.urb_km2
U['bus_dens'] = U.bus_stops / U.urb_km2
U['school_dens'] = U.schools / U.urb_km2
U['fl_mean'] = U.si.map(B[B.fl > 0].groupby('si').fl.mean())
U['pre1980'] = U.si.map(B[B.yr.notna()].assign(o=lambda d: d.yr < 1980).groupby('si').o.mean())

# ---------- building fixed effects (real log price per m2) ----------
cx_ = pd.read_excel('cpi.xlsx'); cx_['date'] = cx_['date'].astype(str).str[:7]
cs = cx_.set_index('date').cpi
D = c.sql("select gush, parcel, dt, ppm, area from a").df()
D['ym'] = pd.to_datetime(D.dt).dt.to_period('M').astype(str)
cpi = cs.reindex(sorted(D.ym.unique())).ffill()
D['lp'] = np.log(D.ppm / D.ym.map(cpi))
D['bld'] = D.gush.astype(np.int64)*100000 + D.parcel
D = D[D.groupby('bld').bld.transform('size') >= 2]
codes = lambda s: pd.factorize(s)[0]
def fe_solve(y, gs, iters=500, tol=1e-8):
    fes = [np.zeros(gg.max()+1) for gg in gs]; cnt = [np.bincount(gg) for gg in gs]; r = y.copy()
    for it in range(iters):
        delta = 0
        for k, gg in enumerate(gs):
            r += fes[k][gg]; new = np.bincount(gg, r, minlength=len(cnt[k]))/np.maximum(cnt[k], 1)
            delta = max(delta, np.abs(new - fes[k]).max()); fes[k] = new; r -= new[gg]
        if delta < tol: break
    return fes
bi, blabs = pd.factorize(D.bld)
fes = fe_solve(D.lp.values.astype(float), [bi, codes(D.ym), codes(D.area.round())])
F = pd.DataFrame({'bld': blabs, 'fe': fes[0], 'n': np.bincount(bi)})
F['gush'] = F.bld // 100000; F['parcel'] = F.bld % 100000
B = B.merge(F[['gush', 'parcel', 'fe', 'n']], on=['gush', 'parcel'], how='left')
B['fe'] = B.fe - np.average(B.fe.dropna(), weights=B.n.dropna())
B.to_csv('bld_fe.csv', index=False)
print('buildings with FE', B.fe.notna().sum())

B.to_pickle('urban_B.pkl'); U.to_pickle('urban_U.pkl')    # checkpoint: build_urban_reg.py starts here
import runpy; runpy.run_path('build_urban_reg.py', run_name='__main__')
