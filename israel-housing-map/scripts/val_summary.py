# Junction validation vs OpenStreetMap -> junc_val.json (for the page)
# Overpass: nodes shared by >= 3 way segments of driveable highways (motorway..residential, living_street,
# pedestrian), fetched per 1 km2 box from overpass-api.de (osm_val/box*.txt, 7 boxes, 2026-10-05),
# merged within 20 m. Overture (fetch_overture_roads.py, all 31 boxes): the measure now used on the page,
# OSMnx-style drive intersections consolidated at tolerance 10 m (= merged within 20 m), osm_streets.py.
import json, glob, numpy as np, pandas as pd
from osm_consol import consol
import osm_streets as OS
KX, KY = OS.KX, OS.KY
V = pd.read_csv('osm_val/val_boxes.csv')
S, C = OS.load()
ov = {}
for net in ['drive', 'walk']:
    N = OS.nodes(S, C, S[net].values); I = N[N.k >= 3]
    cx, cy, _ = OS.consolidate(I.x.values, I.y.values, 10)
    ov[net] = (I.x.values, I.y.values, cx, cy)
def inbox(X, Y, b): return int(((Y/KY > b.s) & (Y/KY < b.n) & (X/KX > b.w) & (X/KX < b.e)).sum())
for net in ['drive', 'walk']:
    x, y, cx, cy = ov[net]
    V[f'ov_{net}_raw'] = [inbox(x, y, b) for _, b in V.iterrows()]
    V[f'ov_{net}'] = [inbox(cx, cy, b) for _, b in V.iterrows()]
rows = []
for f in sorted(glob.glob('osm_val/box*.txt'), key=lambda s: int(s.split('box')[1][:-4])):
    i = int(f.split('box')[1][:-4]); d = np.loadtxt(f, usecols=(0, 1)); b = V.iloc[i]
    rows.append({'city': b.city, 'osm_raw': len(d), 'osm20': int(consol(d[:, 0], d[:, 1], 20)), 'ov_raw': int(b.ov_drive_raw),
                 'ov': int(b.ov_drive), 'contact': int(b.old), 'contact_clean': int(b.clean), 'skel': int(b.skel0)})
R = pd.DataFrame(rows)
st = {c: {'ratio': round(float((R[c]/R.osm20).mean()), 2), 'mape': round(float((abs(R[c]-R.osm20)/R.osm20).mean()), 2),
          'corr': round(float(np.corrcoef(R[c], R.osm20)[0, 1]), 2)} for c in ['ov', 'contact', 'contact_clean', 'skel']}
# all 31 boxes: cadastral skeleton vs Overture drive
st31 = {'ratio': round(float((V.skel0/V.ov_drive).mean()), 2), 'mape': round(float((abs(V.skel0-V.ov_drive)/V.ov_drive).mean()), 2),
        'corr': round(float(np.corrcoef(V.skel0, V.ov_drive)[0, 1]), 2), 'n': int(len(V))}
out = {'boxes': rows, 'stats': st, 'stats31': st31,
       'all_boxes': V[['city', 'old', 'clean', 'skel0', 'ov_drive', 'ov_walk']].rename(
           columns={'old': 'contact', 'clean': 'contact_clean', 'skel0': 'skel'}).to_dict('records')}
json.dump(out, open('junc_val.json', 'w'), ensure_ascii=False)
print(R.to_string()); print(st); print(st31)
print(V[['city', 'skel0', 'ov_drive', 'ov_walk']].to_string())
