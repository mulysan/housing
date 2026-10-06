# Pack parcel points + results into map_v3_template.html -> housing_v3.html
# Inputs in cwd: parcels_v3.parquet, gush_v3.parquet, results_v3.json, txn_v3.json, and
# land-data.json / label-data.json (extracted from the v2 page), leaflet.css.
import duckdb, json, gzip, base64, numpy as np, pandas as pd
c = duckdb.connect()
P = c.sql("""select p.gush, p.parcel, p.units, coalesce(p.fl,0) fl, p.yr, coalesce(p.city,'') city, p.lat, p.lon,
  case when p.p_n>=3 then p.p_ppm end ppm_p, case when p.g_n>=5 then p.g_ppm end ppm_g, p.loc_ppm,
  coalesce(p.p_n1525,0) nd
  from 'parcels_v3.parquet' p where p.lat is not null order by p.lat""").df()
BF = pd.read_csv('bld_fe.csv')[['gush', 'parcel', 'si', 'fe', 'n']]
SU = pd.read_csv('sa_urban.csv')[['si', 'junc_dens']]
BF = BF.merge(SU, on='si', how='left')
P = P.merge(BF, on=['gush', 'parcel'], how='left')
G = c.sql("""select gush, case when n_15>=10 and n_25>=10 then chg end chg, case when n_1525>=10 then turn end turn
  from 'gush_v3.parquet'""").df()
gl = sorted(set(P.gush))
gi = {g: i for i, g in enumerate(gl)}
Gm = G.set_index('gush').reindex(gl)
cities = sorted(set(P.city)); ci = {x: i for i, x in enumerate(cities)}
h = lambda s: np.nan_to_num(np.round(s.astype(float)/100), nan=0).clip(0, 65535).astype('<u2')
arrs = {
  'y': np.round((P.lat - 29.4)*1e4).astype('<u2'), 'x': np.round((P.lon - 34.2)*1e4).astype('<u2'),
  'u': P.units.clip(upper=65535).astype('<u2'), 'p': P.parcel.clip(0, 65535).astype('<u2'),
  'g': P.gush.map(gi).astype('<u2'), 'c': P.city.map(ci).astype('<u2'),
  'pp': h(P.ppm_p), 'pg': h(P.ppm_g), 'pl': h(P.loc_ppm), 'nd': P.nd.clip(upper=65535).astype('<u2'),
  'j': np.nan_to_num(P.junc_dens.round() + 1, nan=0).clip(0, 65535).astype('<u2'),
  'bf': np.where((P.n >= 3) & P.fe.notna(), np.round((P.fe.fillna(0).clip(-2.9, 3) + 3)*1000), 0).astype('<u2'),
  'f': P.fl.clip(0, 255).astype('u1'),
  'd': np.nan_to_num((P.yr//10 - 180).where(P.yr.between(1870, 2026)), nan=0).astype('u1'),
}
assert len(gl) < 65536 and len(cities) < 65536
buf = b''; meta = {}
for k, a in arrs.items():
    a = np.asarray(a); meta[k] = [len(buf), a.dtype.str[-2:]]; buf += a.tobytes()
pts = base64.b64encode(gzip.compress(buf, 9)).decode()
gush = {'id': [int(g) for g in gl],
        'chg': [None if np.isnan(v) else round(float(v), 3) for v in Gm.chg],
        'turn': [None if np.isnan(v) else round(float(v), 4) for v in Gm.turn]}
meta = {'n': len(P), 'fields': meta, 'cities': cities}
R = json.load(open('results_v3.json'))
t = open('map_v3_template.html').read()
for k, v in {'/*META*/': json.dumps(meta, ensure_ascii=False), '/*PTS*/': pts,
             '/*GUSH*/': json.dumps(gush, separators=(',', ':')), '/*RES*/': json.dumps(R, ensure_ascii=False, default=float),
             '/*TXN*/': open('txn_v3.json').read(), '/*URB*/': open('urban_v3.json').read(), '/*JVAL*/': open('junc_val.json').read(), '/*FLOOR*/': open('floor_v3.json').read(), '/*HED*/': open('hedonic_v3.json').read(), '/*AREAS*/': open('areas_v3.json').read(), '/*IV*/': open('iv_v3.json').read(), '/*VARMAP*/': open('varmap.b64').read(),
             '/*ROADS*/': open('basemap.b64').read(),
             '/*LAND*/': open('land-data.json').read(), '/*LABELS*/': open('label-data.json').read(),
             '/*LEAFLET_CSS*/': open('leaflet.css').read()}.items():
    t = t.replace(k, v)
open('housing_v3.html', 'w').write(t)
print(len(P), 'points;', len(pts)/1e6, 'MB b64;', len(t)/1e6, 'MB page')
