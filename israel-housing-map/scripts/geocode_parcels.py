# Locations for gazetteer residential parcels with no polygon in the Survey of Israel parcel
# layer. That layer does not cover Judea and Samaria (Civil Administration gushim, 6xxxx/7xxxx),
# and about 9% of parcels inside Israel were re-parcelled since the gazetteer was cut.
# In order:
#   q=2 deals: median coordinates of the parcel's govmap deals (govmap_deals.csv, fetch_govmap_deals.py),
#       when the parcel has at least one deal with coordinates.
#   q=3 street: the gazetteer street name matched to an OSM street name (Overture segments,
#       fetch_overture_roads.py) inside the parcel's CBS locality (SA 2011 polygons by yishuv,
#       buffered 500 m); point = the matched street piece nearest the gush's centre
#       (the gush centre is the median of its parcels' street matches).
#   q=4 gush: centroid of the other parcels of the same gush (parcel_centroids.csv, all parcels).
#   q=5 locality: a point inside the CBS locality, only for localities that are a single SA
#       (otherwise all its units would pile into one SA); the rest stay unlocated, as before.
# (q=1 = the parcel's own polygon, in parcel_centroids.csv; not written here.)
# Inputs: gazetteer.csv, parcel_centroids.csv, sa2011.csv, ov_segments.parquet, govmap_deals.csv (optional)
# Output: parcel_geocoded.csv (gush, parcel, lat, lon, loc_q)
import re, numpy as np, pandas as pd, shapely, pyarrow.parquet as pq
from shapely import STRtree
LAT0 = 31.8; KX = 111320*np.cos(np.radians(LAT0)); KY = 110574

g = pd.read_csv('gazetteer.csv', dtype=str, usecols=['GushNum', 'ParcelNum', 'SettlmentID', 'StreetNameHeb', 'Type'])
g = g[g.Type.isin(['דירת מגורים', 'דירת מגורים חדשה'])]
g['gush'] = g.GushNum.astype(int); g['parcel'] = g.ParcelNum.astype(int)
g['yishuv'] = pd.to_numeric(g.SettlmentID, errors='coerce')
cnt = g.groupby(['gush', 'parcel', 'yishuv', 'StreetNameHeb'], dropna=False).size().rename('n').reset_index()
cnt = cnt.sort_values('n').drop_duplicates(['gush', 'parcel'], keep='last')      # modal yishuv/street per parcel
C = pd.read_csv('parcel_centroids.csv', usecols=['gush', 'parcel', 'lat', 'lon'])
C = C[pd.to_numeric(C.parcel, errors='coerce').notna()].astype(float)
have = set(zip(C.gush.astype(int), C.parcel.astype(int)))
U = cnt[[(a, b) not in have for a, b in zip(cnt.gush, cnt.parcel)]].reset_index(drop=True)
print('residential parcels without polygon', len(U))

# localities: SA 2011 polygons dissolved by yishuv, in metres
sa = pd.read_csv('sa2011.csv'); sa = sa[sa.sa > 0]
sg = shapely.make_valid(shapely.transform(shapely.from_wkt(sa.wkt.values), lambda c: np.c_[c[:, 0]*KX, c[:, 1]*KY]))
loc = {int(y): shapely.union_all(sg[(sa.yishuv == y).values]) for y in sa.yishuv.unique()}
n_sa = sa.yishuv.value_counts()

# OSM named streets, vertex-to-vertex pieces with midpoints
S = pq.read_table('ov_segments.parquet', columns=['name', 'geometry']).to_pandas().dropna(subset=['name'])
norm = lambda s: re.sub(r'^(רחוב|רח|שדרות|שד|דרך|סמטת|סמ|כיכר)(?=.{2,})', '', re.sub(r'[\s"\'`״׳\-.,()]+', '', str(s)))
S['k'] = S.name.map(norm)
geo = shapely.transform(shapely.from_wkb(S.geometry.values), lambda c: np.c_[c[:, 0]*KX, c[:, 1]*KY])
mid = shapely.line_interpolate_point(geo, 0.5, normalized=True)
S['x'], S['y'] = shapely.get_x(mid), shapely.get_y(mid)
tree = STRtree(mid)

U['k'] = U.StreetNameHeb.map(lambda s: norm(s) if isinstance(s, str) and s.strip() else None)
U['x'] = np.nan; U['y'] = np.nan; U['q'] = 0; cands = {}
import os
if os.path.exists('govmap_deals.csv'):
    GD = pd.read_csv('govmap_deals.csv', usecols=['gush', 'parcel', 'lon', 'lat']).dropna()
    GD = GD[GD.lon.between(34, 36) & GD.lat.between(29, 34)]
    gm = GD.groupby(['gush', 'parcel'])[['lon', 'lat']].median()
    key = pd.MultiIndex.from_arrays([U.gush, U.parcel]); hit = key.isin(gm.index)
    U.loc[hit, 'x'] = gm.lon.reindex(key[hit]).values*KX; U.loc[hit, 'y'] = gm.lat.reindex(key[hit]).values*KY; U.loc[hit, 'q'] = 2
for y, d in U[U.k.notna() & (U.q == 0)].groupby('yishuv'):
    poly = loc.get(int(y)) if np.isfinite(y) else None
    if poly is None: continue
    idx = tree.query(shapely.buffer(poly, 500), predicate='intersects')
    cand = S.iloc[idx]
    for k, dk in d.groupby('k'):
        m = cand[cand.k == k]
        if not len(m):
            m = cand[cand.k.map(lambda s: k in s or (len(s) >= 3 and s in k)).astype(bool).values] if len(k) >= 3 else m
        if len(m):
            U.loc[dk.index, 'q'] = 3
            for i in dk.index: cands[i] = m[['x', 'y']].values
# pick, per parcel, the matched street piece nearest its gush centre (median of all candidate points in the gush)
st = U[U.q == 3]
gc = {gu: np.median(np.vstack([cands[i] for i in d.index]), axis=0) for gu, d in st.groupby('gush')}
for i, gu in zip(st.index, st.gush):
    c = cands[i]; j = np.argmin(((c - gc[gu])**2).sum(1)); U.loc[i, ['x', 'y']] = c[j]
# gush centre from other parcels of the gush
gcen = C.groupby('gush')[['lat', 'lon']].median()
m = (U.q == 0) & U.gush.isin(gcen.index)
U.loc[m, 'x'] = gcen.lon.reindex(U.gush[m]).values*KX; U.loc[m, 'y'] = gcen.lat.reindex(U.gush[m]).values*KY; U.loc[m, 'q'] = 4
# locality
for y, d in U[U.q == 0].groupby('yishuv'):
    poly = loc.get(int(y)) if np.isfinite(y) and n_sa.get(int(y), 0) == 1 else None
    if poly is None: continue
    p = shapely.point_on_surface(poly); U.loc[d.index, ['x', 'y']] = [p.x, p.y]; U.loc[d.index, 'q'] = 5
O = U[U.q > 0]
out = pd.DataFrame({'gush': O.gush, 'parcel': O.parcel, 'lat': (O.y/KY).round(6), 'lon': (O.x/KX).round(6), 'loc_q': O.q})
out.to_csv('parcel_geocoded.csv', index=False)
print(out.loc_q.value_counts().sort_index().to_dict(), 'unlocated', int((U.q == 0).sum()))
