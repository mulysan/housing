# Street background for the map page: OpenStreetMap streets from Overture (fetch_overture_roads.py),
# clipped to Israel + Judea and Samaria (land_full.wkb, from Overture division areas IL + XW + XZ and
# the earlier land outline for the Golan). Replaces the cadastral road-parcel background, which had
# no streets in Judea and Samaria and weighed 7 MB inside the page.
#   roads/major.txt       motorway, trunk, primary (+links), whole country, simplified ~30 m (zoom 8 to 11)
#   roads/t_{i}_{j}.txt   every street in 0.2-degree tiles, simplified ~2 m (zoom 12 up; the page
#                         fetches only the tiles in view)
# Files are gzip'd binary (see pack()) in base64, since artifacts serve text but not octet-stream.
# Class codes: 0 motorway/trunk, 1 primary, 2 secondary/tertiary, 3 residential/unclassified/living,
#              4 service, 5 pedestrian/footway/path/steps (not drawn below zoom 15).
import os, json, numpy as np, pandas as pd, shapely, pyarrow.parquet as pq
S = pq.read_table('ov_segments.parquet', columns=['class', 'subclass', 'geometry']).to_pandas()
K = {'motorway': 0, 'trunk': 0, 'primary': 1, 'secondary': 2, 'tertiary': 2, 'residential': 3, 'unclassified': 3,
     'living_street': 3, 'unknown': 3, 'service': 4, 'pedestrian': 5, 'footway': 5, 'path': 5, 'steps': 5}
S['k'] = S['class'].map(K)
S = S[S.k.notna() & ~S.subclass.isin(['driveway', 'parking_aisle'])].reset_index(drop=True)
land = shapely.buffer(shapely.from_wkb(open('land_full.wkb', 'rb').read()), 0.003)
shapely.prepare(land)
g = shapely.from_wkb(S.geometry.values)
keep = shapely.intersects(land, g)
S, g = S[keep].reset_index(drop=True), g[keep]
print('segments kept', len(S))
def pack(geoms, ks, tol):
    """binary, gzip: uint32 n | uint8 class[n] | uint16 npts[n] | int32 first xy[2n] | int16 deltas (lon/lat x 1e5)"""
    K_, N_, F_, D_ = [], [], [], []
    for geom, k in zip(shapely.simplify(geoms, tol), ks):
        for part in shapely.get_parts(geom):
            c = np.round(np.asarray(part.coords)*1e5).astype(np.int64)
            if len(c) < 2: continue
            d = np.diff(c, axis=0)
            if np.abs(d).max() >= 32767:                      # split very long straight pieces
                steps = np.maximum(1, np.ceil(np.abs(d).max(1)/30000)).astype(int)
                c = np.vstack([c[:1]] + [c[t] + np.outer(np.arange(1, s_+1)/s_, c[t+1]-c[t]).round().astype(np.int64) for t, s_ in enumerate(steps)])
                d = np.diff(c, axis=0)
            for st in range(0, len(c) - 1, 60000):
                cc = c[st:st+60001]; K_.append(k); N_.append(len(cc)); F_.append(cc[0]); D_.append(np.diff(cc, axis=0))
    n = len(K_)
    buf = (np.array([n], '<u4').tobytes() + np.array(K_, 'u1').tobytes() + np.array(N_, '<u2').tobytes()
           + (np.array(F_, '<i4').tobytes() if n else b'') + (np.vstack(D_).astype('<i2').tobytes() if n else b''))
    return base64.b64encode(gzip.compress(buf, 9))
import gzip, shutil, base64
shutil.rmtree('roads', ignore_errors=True); os.makedirs('roads')
maj = (S.k <= 1).values
open('roads/major.txt', 'wb').write(pack(g[maj], S.k.values[maj], 3e-4))
mid = shapely.line_interpolate_point(g, 0.5, normalized=True)
ti = np.floor(shapely.get_x(mid)*5).astype(int); tj = np.floor(shapely.get_y(mid)*5).astype(int)   # 0.2-degree tiles
idx = []
for (i, j), d in pd.DataFrame({'i': ti, 'j': tj}).groupby(['i', 'j']):
    open(f'roads/t_{i}_{j}.txt', 'wb').write(pack(g[d.index], S.k.values[d.index], 2e-5))
    idx.append([int(i), int(j)])
json.dump(idx, open('roads/index.json', 'w'))
sz = [os.path.getsize('roads/' + f) for f in os.listdir('roads')]
print('files', len(sz), 'total MB', round(sum(sz)/1e6, 1), 'max KB', max(sz)//1000, 'major KB', os.path.getsize('roads/major.txt')//1000)
