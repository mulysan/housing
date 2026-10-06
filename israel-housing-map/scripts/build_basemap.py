# Street-network background for the page: road parcels from the cadastre (see
# roads.py), simplified to ~2.5 m and packed as delta-encoded integer rings.
# The page draws them on a canvas from zoom 11 up. An artifact frame cannot load
# outside map tiles, so this is the background that works everywhere.
# Inputs: parcel_geoms.tsv, h.db. Output: basemap.b64 (gzip, base64), basemap_meta.json
import json, gzip, base64, numpy as np, pandas as pd, shapely, duckdb
from roads import road_flags
LAT0 = 31.8; KX = 111320*np.cos(np.radians(LAT0)); KY = 110574
P = pd.read_csv('parcel_geoms.tsv', sep='\t', header=None, names=['gush', 'parcel', 'wkt'])
g = shapely.from_wkt(P.wkt.values)
g = np.where(shapely.is_valid(g), g, shapely.make_valid(g))
gm = shapely.transform(g, lambda c: np.c_[c[:, 0]*KX, c[:, 1]*KY])
res_set = set(map(tuple, duckdb.connect('h.db', read_only=True).sql("select gush, parcel from p").fetchall()))
road, A = road_flags(gm, P.gush.values, P.parcel.values, res_set)
r = shapely.simplify(gm[road & (A > 150)], 2.5, preserve_topology=False)
rings = []
for geom in r:
    for part in shapely.get_parts(geom):
        if part.geom_type != 'Polygon' or part.area < 100: continue
        c = np.asarray(part.exterior.coords)[:-1]
        if len(c) < 3: continue
        rings.append(np.round(np.c_[c[:, 0]/KX, c[:, 1]/KY]*1e5).astype(np.int64))
n = np.array([len(q) for q in rings], dtype='<u2')
first = np.vstack([q[0] for q in rings]).astype('<i4')
d = np.vstack([np.diff(q, axis=0) for q in rings if len(q) > 1])
assert np.abs(d).max() < 32767
d = d.astype('<i2')
buf = np.array([len(rings)], dtype='<u4').tobytes() + n.tobytes() + first.tobytes() + d.tobytes()   # header: ring count
b64 = base64.b64encode(gzip.compress(buf, 9)).decode()
open('basemap.b64', 'w').write(b64)
json.dump({'rings': len(rings), 'deltas': int(len(d))}, open('basemap_meta.json', 'w'))
print('road parcels', int(road.sum()), 'rings', len(rings), 'points', int(n.sum()), 'b64 MB', round(len(b64)/1e6, 2))
