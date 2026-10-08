# Two pages from map_v4_template.html (make_v4_template.py):
#   housing_map.html     the parcel map app (points embedded; OSM street tiles fetched from roads/)
#   housing_report.html  the analysis: indices, IV, hedonic, urban form, floor, variable maps, explorer
# Inputs in cwd: parcels_v3.parquet, gush_v3.parquet, bld_fe.csv, sa_urban.csv, results_v3.json,
# txn_v3.json, urban_v3.json, junc_val.json, floor_v3.json, floor_groups.json (build_floor_groups.py), km_v3.json (build_km.py), hedonic_v3.json, areas_v3.json,
# iv_v3.json, varmap.b64, land-data.json, label-data.json, leaflet.css, roads/ (build_basemap_osm.py).
# Usage: python build_page_v4.py MAP_URL REPORT_URL   (each page links to the other)
# With --from-live live.html, the data blocks not rebuilt yet are taken from a published page.
import sys, re, json, gzip, base64, os, numpy as np, pandas as pd
MAP_URL, REP_URL = (sys.argv[1:3] + ['', ''])[:2]
LIVE = sys.argv[sys.argv.index('--from-live') + 1] if '--from-live' in sys.argv else None
def live_block(i):
    s = open(LIVE).read(); a = s.index(f'id="{i}">') + len(f'id="{i}">'); return s[a:s.index('</script>', a)]

def points():
    import duckdb
    c = duckdb.connect()
    P = c.sql("""select p.gush, p.parcel, p.units, coalesce(p.fl,0) fl, p.yr, coalesce(p.city,'') city, p.lat, p.lon,
      case when p.p_n>=3 then p.p_ppm end ppm_p, case when p.g_n>=5 then p.g_ppm end ppm_g, p.loc_ppm,
      coalesce(p.p_n1525,0) nd, coalesce(p.loc_q, 1) loc_q
      from 'parcels_v3.parquet' p where p.lat is not null order by p.lat""").df()
    BF = pd.read_csv('bld_fe.csv')[['gush', 'parcel', 'si', 'fe', 'n']]
    BF = BF.merge(pd.read_csv('sa_urban.csv')[['si', 'junc_dens']], on='si', how='left')
    P = P.merge(BF, on=['gush', 'parcel'], how='left')
    G = c.sql("""select gush, case when n_15>=10 and n_25>=10 then chg end chg, case when n_1525>=10 then turn end turn
      from 'gush_v3.parquet'""").df()
    gl = sorted(set(P.gush)); gi = {g: i for i, g in enumerate(gl)}
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
      'q': P.loc_q.clip(1, 5).astype('u1'),           # location: 1 parcel polygon, 2 deal coordinates, 3 street, 4 gush, 5 locality
    }
    assert len(gl) < 65536 and len(cities) < 65536
    buf = b''; meta = {}
    for k, a in arrs.items():
        a = np.asarray(a); meta[k] = [len(buf), a.dtype.str[-2:]]; buf += a.tobytes()
    gush = {'id': [int(g) for g in gl], 'chg': [None if np.isnan(v) else round(float(v), 3) for v in Gm.chg],
            'turn': [None if np.isnan(v) else round(float(v), 4) for v in Gm.turn]}
    return ({'n': len(P), 'fields': meta, 'cities': cities}, base64.b64encode(gzip.compress(buf, 9)).decode(), gush, len(P))

if LIVE and not os.path.exists('parcels_v3.parquet'):
    meta, pts, gush, npts = json.loads(live_block('meta')), live_block('pts'), json.loads(live_block('gush')), None
else:
    meta, pts, gush, npts = points()
def data(fn, live_id):
    return open(fn).read() if os.path.exists(fn) else live_block(live_id)
R = json.loads(data('results_v3.json', 'res'))
n_par = meta['n']
SUB = (f'{round(n_par/1000)} אלף חלקות מגורים, כולל יהודה ושומרון. גזטיר הנכסים של מפ"י, עסקאות רשות המסים ו־govmap '
       '(1998 עד ספטמבר 2026), חלקות קדסטר, שכבות הלמ"ס ורשת הרחובות של OpenStreetMap.')
fill = {'/*META*/': json.dumps(meta, ensure_ascii=False), '/*PTS*/': pts, '/*GUSH*/': json.dumps(gush, separators=(',', ':')),
        '/*RES*/': json.dumps(R, ensure_ascii=False, default=float),
        '/*TXN*/': data('txn_v3.json', 'txn-data'), '/*URB*/': data('urban_v3.json', 'urb-data'), '/*JVAL*/': data('junc_val.json', 'jval-data'),
        '/*FLOOR*/': data('floor_v3.json', 'floor-data'), '/*FLOORG*/': open('floor_groups.json').read(), '/*KM*/': open('km_v3.json').read(), '/*HED*/': data('hedonic_v3.json', 'hed-data'),
        '/*AREAS*/': data('areas_v3.json', 'areas-data'), '/*IV*/': data('iv_v3.json', 'iv-data'), '/*VARMAP*/': data('varmap.b64', 'varmap'),
        '/*LAND*/': open('land-data.json').read(), '/*LABELS*/': open('label-data.json').read(),
        '/*LEAFLET_CSS*/': open('leaflet.css').read(), '/*SUB*/': SUB}
T = open('map_v4_template.html').read()
for page, keep, drop, title, other, out in [
        ('map', 'MAP', 'REPORT', 'מפת מחירי הדיור', REP_URL, 'housing_map.html'),
        ('report', 'REPORT', 'MAP', 'ניתוח מחירי הדיור', MAP_URL, 'housing_report.html')]:
    t = re.sub(rf'<!--{drop}-->.*?<!--/{drop}-->', '', T, flags=re.S)
    t = t.replace(f'<!--{keep}-->', '').replace(f'<!--/{keep}-->', '')
    for k, v in {**fill, '/*PAGE*/': page, '/*TITLE*/': title, '/*OTHER_URL*/': other or '#'}.items():
        if k in t: t = t.replace(k, v)
    t = t.replace('265 אלף חלקות', f'{round(n_par/1000)} אלף חלקות')
    open(out, 'w').write(t)
    print(out, round(len(t.encode())/1e6, 2), 'MB')
