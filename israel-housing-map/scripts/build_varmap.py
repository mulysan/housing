# Variable maps: every computed variable as a choropleth at four levels (statistical
# area 2011, city = CBS locality, subdistrict, district), static or by sale year.
# Geometry: SA polygons (CBS), dissolved upward. Aggregation is done from SA sums
# (ratios of sums, weighted means), not by averaging SA ratios.
# Inputs: sa2011.csv, sa_urban.csv, bld_fe.csv, parcels_v3.parquet, gush_region.csv,
# hed_sample.parquet. Output: varmap.b64 (gzip JSON), varmap_info.json
import json, gzip, base64, numpy as np, pandas as pd, shapely
from scipy.spatial import cKDTree
SA = pd.read_csv('sa2011.csv'); SA = SA[SA.sa > 0].drop_duplicates('sa').reset_index(drop=True)
U = pd.read_csv('sa_urban.csv').drop_duplicates('sa').set_index('sa')
B = pd.read_csv('bld_fe.csv').merge(pd.read_parquet('parcels_v3.parquet')[['gush', 'parcel', 'unit_val']], on=['gush', 'parcel'], how='left')
GR = pd.read_csv('gush_region.csv').set_index('gush')
B['region'] = B.gush.map(GR.region); B['county'] = B.gush.map(GR.county)

# Judea and Samaria: gushim missing from over_re_parcels get district = subdistrict = יהודה ושומרון
# when the building lies in the West Bank polygon (Overture division area XW; wb.wkb)
import shapely as _sh
_wb = _sh.from_wkb(open('wb.wkb', 'rb').read())
_m = B.region.isna() & B.lat.notna()
B.loc[_m[_m].index[_sh.contains_xy(_wb, B.lon[_m].values, B.lat[_m].values)], ['region', 'county']] = 'יהודה ושומרון'
# bld_fe.si indexes sa_urban rows' 'si' (= row of the SA table used in build_urban); map si -> sa code
si2sa = pd.read_csv('sa_urban.csv').set_index('si').sa
B['sa'] = B.si.map(si2sa)

# ---------- unit hierarchy ----------
g = shapely.from_wkt(SA.wkt.values); g = np.where(shapely.is_valid(g), g, shapely.make_valid(g))
SA['city'] = SA.yishuv.astype(int)
maj = lambda col: B.dropna(subset=['sa', col]).groupby(['sa', col]).units.sum().reset_index().sort_values('units').drop_duplicates('sa', keep='last').set_index('sa')[col]
SA['region'] = SA.sa.map(maj('region')); SA['county'] = SA.sa.map(maj('county'))
cen = shapely.centroid(g); cx, cy = shapely.get_x(cen), shapely.get_y(cen)
have = SA.county.notna().values
t = cKDTree(np.c_[cx[have], cy[have]]); _, j = t.query(np.c_[cx, cy])
SA.loc[~have, 'county'] = SA.county.values[have][j[~have]]; SA.loc[~have, 'region'] = SA.region.values[have][j[~have]]
# city name: CBS locality name (strip the trailing SA number style)
SA['cityname'] = SA.name.astype(str)

# ---------- SA-level sums ----------
S = pd.DataFrame(index=SA.sa)
for c in ['urb_km2', 'road_km2', 'n_junc', 'n_junc_cad', 'n_junc_walk', 'street_km_drive', 'deadend_share', 'fourway_share', 'orient_ent', 'commerce', 'parking_n', 'parking_km2', 'circuity', 'haredi', 'arab', 'turnout', 'pop2015', 'lu_n', 'bus_stops', 'schools', 'ses21', 'parcel_med', 'mix', 'comm_share']:
    S[c] = U[c].reindex(S.index)
S['comm_n'] = S.comm_share*S.lu_n
b = B.dropna(subset=['sa'])
grp = b.groupby('sa')
S['units'] = grp.units.sum(); S['bld'] = grp.size()
S['fl_sum'] = b[b.fl > 0].groupby('sa').fl.sum(); S['fl_n'] = b[b.fl > 0].groupby('sa').size()
S['u9'] = b[b.fl >= 9].groupby('sa').units.sum(); S['ufl'] = b[b.fl > 0].groupby('sa').units.sum()
S['yr_u'] = b[b.yr.notna()].assign(z=lambda d: d.yr*d.units).groupby('sa').z.sum(); S['uyr'] = b[b.yr.notna()].groupby('sa').units.sum()
S['u80'] = b[b.yr < 1980].groupby('sa').units.sum()
S['uren'] = b[(b.yr < 1980) & b.fl.between(1, 4)].groupby('sa').units.sum(); S['uboth'] = b[b.yr.notna() & (b.fl > 0)].groupby('sa').units.sum()
f = b[b.n >= 3]; S['fe_n'] = f.groupby('sa').n.sum(); S['fe_sum'] = f.assign(z=lambda d: d.fe*d.n).groupby('sa').z.sum()
v = b[b.unit_val.notna()]; S['val'] = v.assign(z=lambda d: d.unit_val*d.units).groupby('sa').z.sum(); S['uval'] = v.groupby('sa').units.sum()
for c in ['d_cbd', 'd_rail', 'd_coast']:
    w = b[b[c].notna()]; S[c+'_s'] = w.assign(z=lambda d: d[c]*d.units).groupby('sa').z.sum(); S[c+'_u'] = w.groupby('sa').units.sum()
S = S.fillna({k: 0 for k in S.columns if k not in ('ses21', 'parcel_med', 'mix', 'deadend_share', 'fourway_share', 'orient_ent', 'circuity', 'haredi', 'arab', 'turnout')})
S = S.join(SA.set_index('sa')[['city', 'county', 'region', 'cityname']])

def agg(df):
    """Static variables for one group of SA rows (ratios of sums)."""
    sd = lambda a, b: a/b if b > 0 else np.nan
    u, km = df.units.sum(), df.urb_km2.sum()
    ses_w = df.pop2015.fillna(0); pm_w = df.units
    return {
        'units': u, 'units_dens': sd(u, km), 'pop_dens': sd(df.pop2015.fillna(0).sum(), km), 'junc_dens': sd(df.n_junc.sum(), km),
        'junc_dens_walk': sd(df.n_junc_walk.sum(), km), 'junc_dens_cad': sd(df.n_junc_cad.sum(), km), 'street_dens': sd(df.street_km_drive.sum(), km),
        'comm_dens': sd(df.commerce.sum(), km), 'parking_dens': sd(df.parking_n.sum(), km), 'parking_share': sd(df.parking_km2.sum(), km),
        # SA-level ratios aggregated with the natural weights: circuity by street length, vote shares by population (2015)
        'circuity': np.average(df.circuity[df.circuity.notna()], weights=df.street_km_drive[df.circuity.notna()] + 1e-9) if df.circuity.notna().any() else np.nan,
        'haredi': np.average(df.haredi[df.haredi.notna()], weights=df.pop2015.fillna(0)[df.haredi.notna()] + 1e-9) if df.haredi.notna().any() else np.nan,
        'arab': np.average(df.arab[df.arab.notna()], weights=df.pop2015.fillna(0)[df.arab.notna()] + 1e-9) if df.arab.notna().any() else np.nan,
        'turnout': np.average(df.turnout[df.turnout.notna()], weights=df.pop2015.fillna(0)[df.turnout.notna()] + 1e-9) if df.turnout.notna().any() else np.nan,
        'deadend_share': np.average(df.deadend_share[df.deadend_share.notna()], weights=df.urb_km2[df.deadend_share.notna()]) if df.deadend_share.notna().any() else np.nan,
        'fourway_share': np.average(df.fourway_share[df.fourway_share.notna()], weights=df.urb_km2[df.fourway_share.notna()]) if df.fourway_share.notna().any() else np.nan,
        'orient_ent': np.average(df.orient_ent[df.orient_ent.notna()], weights=df.street_km_drive[df.orient_ent.notna()] + 1e-9) if df.orient_ent.notna().any() else np.nan,
        'road_share': sd(df.road_km2.sum(), km), 'bus_dens': sd(df.bus_stops.sum(), km), 'school_dens': sd(df.schools.sum(), km),
        'parcel_med': np.average(df.parcel_med[df.parcel_med.notna()], weights=pm_w[df.parcel_med.notna()] + 1e-9) if df.parcel_med.notna().any() else np.nan,
        'mix': np.average(df.mix.fillna(0), weights=df.lu_n + 1e-9) if df.lu_n.sum() > 0 else np.nan,
        'comm_share': sd(df.comm_n.sum(), df.lu_n.sum()),
        'ses21': np.average(df.ses21[df.ses21.notna()], weights=ses_w[df.ses21.notna()] + 1e-9) if df.ses21.notna().any() else np.nan,
        'fl_mean': sd(df.fl_sum.sum(), df.fl_n.sum()), 'share_9': sd(df.u9.sum(), df.ufl.sum()),
        'yr_mean': sd(df.yr_u.sum(), df.uyr.sum()), 'pre1980': sd(df.u80.sum(), df.uyr.sum()), 'renewal': sd(df.uren.sum(), df.uboth.sum()),
        'fe': np.exp(sd(df.fe_sum.sum(), df.fe_n.sum())) - 1 if df.fe_n.sum() >= 3 else np.nan,
        'unit_val': sd(df.val.sum(), df.uval.sum()), 'value_bn': df.val.sum()/1e9,
        'd_cbd': sd(df.d_cbd_s.sum(), df.d_cbd_u.sum()), 'd_rail': sd(df.d_rail_s.sum(), df.d_rail_u.sum()), 'd_coast': sd(df.d_coast_s.sum(), df.d_coast_u.sum()),
    }
STATIC = [  # key, label, unit, log scale for bins
  ('units', 'דירות רשומות', '', True), ('units_dens', 'דירות לקמ"ר', '', True), ('pop_dens', 'תושבים לקמ"ר (2015)', '', True),
  ('junc_dens', 'צמתים לקמ"ר (OSM, רשת נסיעה)', '', True), ('junc_dens_walk', 'צמתים לקמ"ר (OSM, רשת הליכה)', '', True),
  ('junc_dens_cad', 'צמתים לקמ"ר (קדסטר, השיטה הקודמת)', '', True), ('street_dens', 'ק"מ רחוב לקמ"ר (OSM)', '', True),
  ('deadend_share', 'שיעור רחובות ללא מוצא (OSM)', '%', False), ('fourway_share', 'שיעור צמתים של 4 רחובות ומעלה (OSM)', '%', False),
  ('comm_dens', 'עסקים לקמ"ר (Overture)', '', True), ('parking_dens', 'חניונים וכניסות לחניון לקמ"ר (OSM)', '', True),
  ('parking_share', 'שיעור השטח בחניונים ממופים', '%', False), ('circuity', 'עקמומיות רחובות (אורך / מרחק ישר)', '', False),
  ('haredi', 'קולות ליהדות התורה וש"ס (כנסת 25)', '%', False), ('arab', 'קולות למפלגות ערביות (כנסת 25)', '%', False), ('turnout', 'אחוז הצבעה (כנסת 25)', '%', False), ('orient_ent', 'אנטרופיית כיווני רחובות (0 = רשת, 1 = אקראי)', '', False), ('road_share', 'שיעור שטח דרכים', '%', False), ('bus_dens', 'תחנות אוטובוס לקמ"ר', '', True),
  ('school_dens', 'מוסדות חינוך לקמ"ר', '', True), ('parcel_med', 'גודל חלקה חציוני (מ"ר)', '', True), ('mix', 'עירוב שימושים (0–1)', '', False),
  ('comm_share', 'שיעור מסחר ומשרדים', '%', False), ('ses21', 'אשכול חברתי־כלכלי 2021', '', False), ('fl_mean', 'קומות בבניין (ממוצע)', '', False),
  ('share_9', 'דירות בבניינים של 9+ קומות', '%', False), ('yr_mean', 'שנת בנייה (ממוצע משוקלל)', '', False), ('pre1980', 'דירות בבניינים מלפני 1980', '%', False),
  ('renewal', 'דירות ישנות ונמוכות (פוטנציאל התחדשות)', '%', False), ('fe', 'אפקט קבוע של בניין (ממוצע)', '%', False),
  ('unit_val', 'שווי דירה ממוצע (₪)', '₪', True), ('value_bn', 'שווי מלאי הדירות (מיליארד ₪)', '', True),
  ('d_cbd', 'מרחק למרכז תל אביב (ק"מ)', '', True), ('d_rail', 'מרחק לתחנת רכבת או רק"ל (ק"מ)', '', True), ('d_coast', 'מרחק לחוף (ק"מ)', '', True)]

# ---------- yearly variables from deals ----------
H = pd.read_parquet('hed_sample.parquet')
H['ppm'] = np.exp(H.lpr - H.larea); H['price'] = np.exp(H.lpr)
H['age'] = (H.y - H.yb).where(H.yb.between(1900, 2027))
H['new'] = (H.age <= 1).astype(float).where(H.age.notna())
H = H.join(SA.set_index('sa')[['city', 'county', 'region']], on='sa')
YEARS = list(range(1998, 2027))
YEARLY = [('ppm', 'מחיר למ"ר ריאלי (₪ של 2015, חציון)', '₪', True), ('price', 'מחיר דירה ריאלי (₪ של 2015, חציון)', '₪', True),
          ('area', 'שטח דירה שנמכרה (מ"ר, ממוצע)', '', False), ('rooms', 'חדרים בדירה שנמכרה (ממוצע)', '', False),
          ('age', 'גיל הבניין בעסקה (שנים, ממוצע)', '', False), ('new', 'שיעור מכירות בבניין חדש', '%', False),
          ('deals', 'עסקאות דירה', '', True), ('turn', 'עסקאות ל־100 דירות רשומות', '', True)]
def yearly(level):
    key = 'sa' if level == 'sa' else level
    gb = H[H.rooms.between(1, 12) | True].groupby([key, 'y'])
    out = {}
    med = gb[['ppm', 'price']].median(); mean = gb[['area', 'rooms', 'age', 'new']].mean(); n = gb.size()
    rooms_ok = H[H.rooms.between(1, 12)].groupby([key, 'y']).rooms.mean()
    mean['rooms'] = rooms_ok
    minn = 5 if level == 'sa' else 10
    for k in ['ppm', 'price']: out[k] = med[k].where(n >= minn)
    for k in ['area', 'rooms', 'age', 'new']: out[k] = mean[k].where(n >= minn)
    out['deals'] = n.astype(float)
    return out

LEVELS = [('region', 'מחוז', 0.0015), ('county', 'נפה', 0.0008), ('city', 'עיר', 0.0003), ('sa', 'אזור סטטיסטי', 0.00015)]
pack = {'years': YEARS, 'static': [[k, l, un, lg] for k, l, un, lg in STATIC], 'yearly': [[k, l, un, lg] for k, l, un, lg in YEARLY], 'levels': []}
for lev, lname, tol in LEVELS:
    if lev == 'sa':
        keys = list(S.index); groups = {k: S.loc[[k]] for k in keys}
        names = [f'{S.cityname[k]} · א"ס {int(k) % 10000}' for k in keys]
        geoms = {k: g[i] for i, k in enumerate(SA.sa)}
    else:
        keys = sorted(S[lev].dropna().unique(), key=str); groups = {k: S[S[lev] == k] for k in keys}
        if lev == 'city':
            nm = S.groupby('city').cityname.first(); names = [nm[k] for k in keys]
        else: names = [str(k) for k in keys]
        geoms = {}
        for k in keys:
            ids = set(groups[k].index); geoms[k] = shapely.union_all(shapely.buffer(g[SA.sa.isin(ids).values], 0.0002))
    feats = []
    for k, nmk in zip(keys, names):
        gg = shapely.simplify(geoms[k], tol, preserve_topology=True)
        rings = []
        for part in shapely.get_parts(gg):
            if part.geom_type != 'Polygon' or part.area < tol*tol*4: continue
            c = np.round(np.asarray(part.exterior.coords)[:-1]*1e4).astype(np.int64)
            if len(c) < 3: continue
            d = np.diff(c, axis=0); rings.append([int(c[0, 0]), int(c[0, 1])] + d.ravel().tolist())
        feats.append(rings)
    stat = {k: [] for k, *_ in STATIC}
    for kk in keys:
        a = agg(groups[kk])
        for k, *_ in STATIC: stat[k].append(None if a[k] is None or not np.isfinite(a[k]) else round(float(a[k]), 5))
    Y = yearly(lev)
    units_by = pd.Series({kk: groups[kk].units.sum() for kk in keys})
    yv = {}
    for k, *_ in YEARLY:
        if k == 'turn':
            dl = Y['deals'].unstack().reindex(index=keys, columns=YEARS)
            m = (dl.div(units_by.reindex(keys).replace(0, np.nan), axis=0)*100)
        else:
            m = Y[k].unstack().reindex(index=keys, columns=YEARS)
        yv[k] = [[None if not np.isfinite(x) else round(float(x), 4) for x in row] for row in m.values]
    pack['levels'].append({'key': lev, 'name': lname, 'ids': [str(k) for k in keys], 'names': names, 'geom': feats, 'static': stat, 'yearly': yv})
    print(lev, len(keys), flush=True)

# deal-level national histograms by year for the deal variables
HB = {'ppm': list(np.round(np.geomspace(2000, 100000, 26), 1)), 'price': list(np.round(np.geomspace(150000, 15e6, 26), -2)),
      'area': list(range(25, 276, 10)), 'rooms': [0.5 + k for k in range(9)], 'age': list(range(0, 101, 5))}
pack['deal_hist'] = {'bins': HB, 'by_year': {}}
for k, bins in HB.items():
    col = H[k] if k != 'rooms' else H.rooms.where(H.rooms.between(1, 12))
    pack['deal_hist']['by_year'][k] = {str(y): np.histogram(np.clip(col[H.y == y].dropna(), bins[0], bins[-1] - 1e-9), bins=bins)[0].tolist() for y in YEARS}
    pack['deal_hist']['by_year'][k]['all'] = np.histogram(np.clip(col.dropna(), bins[0], bins[-1] - 1e-9), bins=bins)[0].tolist()
txt = json.dumps(pack, ensure_ascii=False, separators=(',', ':'))
b64 = base64.b64encode(gzip.compress(txt.encode(), 9)).decode()
open('varmap.b64', 'w').write(b64)
json.dump({'json_mb': round(len(txt)/1e6, 2), 'b64_mb': round(len(b64)/1e6, 2),
           'labels': {k: l for k, l, *_ in STATIC + YEARLY}}, open('varmap_info.json', 'w'), ensure_ascii=False)
# every variable must have a dictionary entry (var_dict.py)
import var_dict; _miss = [k for k, *_ in STATIC + YEARLY if k not in var_dict.V]; assert not _miss, _miss
print('json MB', round(len(txt)/1e6, 2), 'b64 MB', round(len(b64)/1e6, 2))
