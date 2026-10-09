# Two pages from map_v4_template.html (make_v4_template.py):
#   housing_map.html     the parcel map app (points embedded; OSM street tiles fetched from roads/)
#   housing_report.html  the analysis: indices, IV, hedonic, urban form, floor, variable maps, explorer
# Inputs in cwd: parcels_v3.parquet, gush_v3.parquet, bld_fe.csv, sa_urban.csv, results_v3.json,
# txn_v3.json, urban_v3.json, junc_val.json, floor_v3.json, floor_groups.json (build_floor_groups.py), km_v3.json (build_km.py), km_grid.json (build_km_grid.py), size_paper.json (build_size_paper.py), sa_xy.json (build_sa_xy.py), hedonic_v3.json, areas_v3.json,
# iv_v3.json, varmap.b64, varmap_info.json, var_dict.py, land-data.json, label-data.json, leaflet.css, roads/ (build_basemap_osm.py).
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
    BF = pd.read_csv('bld_fe.csv')[['gush', 'parcel', 'si', 'fe', 'n', 'd_cbd', 'd_rail', 'd_coast']]
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
      'bf': np.where((P.n >= 3) & P.fe.notna(), np.round((P.fe.fillna(0).clip(-2.9, 3) + 3)*1000), 0).astype('<u2'),
      'f': P.fl.clip(0, 255).astype('u1'),
      'd': np.nan_to_num((P.yr//10 - 180).where(P.yr.between(1870, 2026)), nan=0).astype('u1'),
      'q': P.loc_q.clip(1, 5).astype('u1'),
      # SA row (index into the SA table + 1; 0 = no SA). Distances as 1-byte log codes:
      # code = round(25*(ln km + 3)) + 1, i.e. 4% steps from 50 m to 400 km; 0 = missing
      's': np.nan_to_num(P.si.where(P.loc_q <= 4) + 1, nan=0).clip(0, 65535).astype('<u2'),
      **{f: np.nan_to_num(np.round(25*(np.log(P[c].clip(lower=0.05)) + 3)) + 1, nan=0).clip(0, 255).astype('u1')
         for f, c in [('dc', 'd_cbd'), ('dr', 'd_rail'), ('ds', 'd_coast')]},           # location: 1 parcel polygon, 2 deal coordinates, 3 street, 4 gush, 5 locality
    }
    assert len(gl) < 65536 and len(cities) < 65536
    buf = b''; meta = {}
    # 2-byte fields first: a Uint16Array view needs an even byte offset
    arrs = dict(sorted(arrs.items(), key=lambda kv: np.asarray(kv[1]).dtype.itemsize, reverse=True))
    for k, a in arrs.items():
        a = np.asarray(a); meta[k] = [len(buf), a.dtype.str[-2:]]; buf += a.tobytes()
    gush = {'id': [int(g) for g in gl], 'chg': [None if np.isnan(v) else round(float(v), 3) for v in Gm.chg],
            'turn': [None if np.isnan(v) else round(float(v), 4) for v in Gm.turn]}
    return ({'n': len(P), 'fields': meta, 'cities': cities, 'sa': sa_table(P)}, base64.b64encode(gzip.compress(buf, 9)).decode(), gush, len(P))

# SA variables for the parcel map: every SA-level variable of the variable dictionary, by SA row (si).
# Colour bounds: 2nd and 98th percentiles over parcels with a value (so the scale reflects where
# housing is); log scale for the variables the variable map draws on a log scale.
SA_VARS = ['junc_dens', 'units_dens', 'pop_dens', 'junc_dens_walk', 'junc_dens_cad', 'street_dens', 'deadend_share', 'fourway_share',
           'orient_ent', 'circuity', 'road_share', 'parcel_med', 'mix', 'comm_share', 'comm_dens', 'parking_dens',
           'parking_share', 'bus_dens', 'school_dens', 'ses21', 'haredi', 'arab', 'turnout']
SHARE = {'deadend_share', 'fourway_share', 'road_share', 'comm_share', 'parking_share', 'haredi', 'arab', 'turnout'}
LOGV = {'units_dens', 'pop_dens', 'junc_dens_walk', 'junc_dens_cad', 'street_dens', 'parcel_med', 'comm_dens', 'parking_dens', 'bus_dens', 'school_dens'}
def sig(x, k=4):
    return None if x is None or not np.isfinite(x) else float(f'{x:.{k}g}')
def sa_table(P):
    U = pd.read_csv('sa_urban.csv').set_index('si')
    nsi = int(U.index.max()) + 1
    lab = json.load(open('varmap_info.json')).get('labels', {})
    out = {'vars': []}
    for v in SA_VARS:
        col = U[v].reindex(range(nsi))
        pv = P.si.where(P.loc_q <= 4).map(U[v]).dropna()
        lg = v in LOGV
        if lg: pv = pv[pv > 0]
        lo, hi = (float(pv.quantile(.02)), float(pv.quantile(.98))) if len(pv) else (0, 1)
        out['vars'].append({'k': v, 'lab': lab.get(v, v), 'share': v in SHARE, 'lg': lg, 'lo': sig(lo, 3), 'hi': sig(hi, 3),
                            'x': [sig(x) for x in col.values]})
    return out

if LIVE and not os.path.exists('parcels_v3.parquet'):
    meta, pts, gush, npts = json.loads(live_block('meta')), live_block('pts'), json.loads(live_block('gush')), None
else:
    meta, pts, gush, npts = points()
def data(fn, live_id):
    return open(fn).read() if os.path.exists(fn) else live_block(live_id)
R = json.loads(data('results_v3.json', 'res'))
def vardict():   # var_dict.py + labels from the variable map (varmap_info.json)
    import var_dict
    lab = json.load(open('varmap_info.json')).get('labels', {}) if os.path.exists('varmap_info.json') else {}
    return json.dumps({'v': var_dict.V, 'src': var_dict.SRC, 'lab': lab}, ensure_ascii=False).replace('</', '<\\/')
n_par = meta['n']
def sizep():   # dwelling-size paper figures 1, 4 and 5 (build_size_paper.py)
    O = json.load(open('size_paper.json'))
    return json.dumps({'built_share': O['built_share'], 'national_series': O['national_series'],
                       'b': O['km']['own_dt']['b'][0], 'se': O['km']['own_dt']['se'][0],
                       'km_fig': {'resid': O['km']['fig_resid'], 'longdiff': O['km']['fig_longdiff']}}, separators=(',', ':'))
SUB = (f'{round(n_par/1000)} אלף חלקות מגורים, כולל יהודה ושומרון. גזטיר הנכסים של מפ"י, עסקאות רשות המסים ו־govmap '
       '(1998 עד ספטמבר 2026), חלקות קדסטר, שכבות הלמ"ס ורשת הרחובות של OpenStreetMap.')
fill = {'/*META*/': json.dumps(meta, ensure_ascii=False), '/*PTS*/': pts, '/*GUSH*/': json.dumps(gush, separators=(',', ':')),
        '/*RES*/': json.dumps(R, ensure_ascii=False, default=float),
        '/*TXN*/': data('txn_v3.json', 'txn-data'), '/*URB*/': data('urban_v3.json', 'urb-data'), '/*JVAL*/': data('junc_val.json', 'jval-data'),
        '/*FLOOR*/': data('floor_v3.json', 'floor-data'), '/*FLOORG*/': open('floor_groups.json').read(), '/*KM*/': open('km_v3.json').read(), '/*KMG*/': open('km_grid.json').read(), '/*SIZEP*/': sizep(), '/*SAXY*/': open('sa_xy.json').read(), '/*HED*/': data('hedonic_v3.json', 'hed-data'),
        '/*AREAS*/': data('areas_v3.json', 'areas-data'), '/*IV*/': data('iv_v3.json', 'iv-data'), '/*VARMAP*/': data('varmap.b64', 'varmap'),
        '/*VARDICT*/': vardict(),
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
