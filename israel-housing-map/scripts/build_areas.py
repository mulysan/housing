# Everything by area: national, district (מחוז), subdistrict (נפה) and city.
# For each area: summary numbers, histograms of every computed variable (fixed
# bins shared by all areas), and the four real price indices (monthly for the
# nation and districts, quarterly below that).
# Inputs: bld_fe.csv, sa_urban.csv, parcels_v3.parquet, gush_v3.parquet,
# gush_region.csv, hed_sample.parquet, h.db. Output: areas_v3.json
import json, numpy as np, pandas as pd, duckdb
c = duckdb.connect('h.db', read_only=True)
GR = pd.read_csv('gush_region.csv').set_index('gush')
B = pd.read_csv('bld_fe.csv')
PV = pd.read_parquet('parcels_v3.parquet')[['gush', 'parcel', 'p_ppm', 'p_n', 'g_ppm', 'g_n', 'loc_ppm', 'unit_val', 'unit_m2']]
B = B.merge(PV, on=['gush', 'parcel'], how='left')
B['region'] = B.gush.map(GR.region); B['county'] = B.gush.map(GR.county)

# Judea and Samaria: gushim missing from over_re_parcels get district = subdistrict = יהודה ושומרון
# when the building lies in the West Bank polygon (Overture division area XW; wb.wkb)
import shapely as _sh
_wb = _sh.from_wkb(open('wb.wkb', 'rb').read())
_m = B.region.isna() & B.lat.notna()
B.loc[_m[_m].index[_sh.contains_xy(_wb, B.lon[_m].values, B.lat[_m].values)], ['region', 'county']] = 'יהודה ושומרון'
B['ppm'] = np.where(B.p_n >= 3, B.p_ppm, np.where(B.g_n >= 5, B.g_ppm, np.nan))
B['fe_pct'] = np.where(B.n >= 3, np.exp(B.fe) - 1, np.nan)
B['ren'] = (B.yr < 1980) & (B.fl.between(1, 4))
U = pd.read_csv('sa_urban.csv')
# SA -> city / district / subdistrict: majority of its registered units
own = B[B.si >= 0].groupby(['si', 'city']).units.sum().reset_index().sort_values('units').drop_duplicates('si', keep='last').set_index('si').city
U['city'] = U.si.map(own)
reg = B[B.si >= 0].groupby(['si', 'region']).units.sum().reset_index().sort_values('units').drop_duplicates('si', keep='last').set_index('si').region
cty = B[B.si >= 0].groupby(['si', 'county']).units.sum().reset_index().sort_values('units').drop_duplicates('si', keep='last').set_index('si').county
U['region'] = U.si.map(reg); U['county'] = U.si.map(cty)
G = pd.read_parquet('gush_v3.parquet')
G['region'] = G.gush.map(GR.region).fillna(G.gush.map(B.groupby('gush').region.first())); G['county'] = G.gush.map(GR.county).fillna(G.gush.map(B.groupby('gush').county.first()))
G['city'] = G.gush.map(B.groupby('gush').city.agg(lambda s: s.mode().iat[0] if s.notna().any() else None))
G['chg'] = np.where((G.n_15 >= 10) & (G.n_25 >= 10), G.chg, np.nan)
G['turn'] = np.where(G.n_1525 >= 10, G.turn, np.nan)

# ---- areas
cu = B.groupby('city').units.sum()
CITIES = sorted(cu[cu >= 12000].index)
REGIONS = ['ירושלים', 'הצפון', 'חיפה', 'המרכז', 'תל-אביב', 'הדרום', 'יהודה ושומרון']
COUNTIES = sorted(B.groupby('county').units.sum().pipe(lambda s: s[s >= 20000]).index)
AREAS = [('IL', 'כל הארץ', 'nation', None, None)] + [(f'r:{r}', r, 'region', 'region', r) for r in REGIONS] + \
        [(f'n:{x}', x, 'county', 'county', x) for x in COUNTIES] + [(f'c:{x}', x, 'city', 'city', x) for x in CITIES]
def sel(df, col, val): return df if col is None else df[df[col] == val]

# ---- histogram variables: (key, label, frame, column, bins, log?, unit)
LG = lambda a, b, n: list(np.round(np.geomspace(a, b, n+1), 6))
HV = [
  ('ppm', 'מחיר למ"ר, 2023–2026 (₪)', 'B', 'ppm', LG(5000, 80000, 20), True, '₪'),
  ('fe_pct', 'אפקט קבוע של בניין (מול הממוצע)', 'B', 'fe_pct', list(np.round(np.exp(np.linspace(np.log(0.35), np.log(3.0), 21)) - 1, 4)), True, '%'),
  ('fl', 'קומות בבניין', 'B', 'fl', [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 10.5, 12.5, 15.5, 20.5, 30.5, 60.5], False, ''),
  ('yr', 'שנת בנייה', 'B', 'yr', list(range(1920, 2031, 5)), False, ''),
  ('units', 'דירות בבניין', 'B', 'units', LG(1, 300, 16), True, ''),
  ('d_rail', 'מרחק לתחנת רכבת או רק"ל (ק"מ)', 'B', 'd_rail', LG(0.1, 60, 18), True, 'ק"מ'),
  ('d_cbd', 'מרחק למרכז תל אביב (ק"מ)', 'B', 'd_cbd', LG(0.5, 300, 18), True, 'ק"מ'),
  ('d_coast', 'מרחק לחוף (ק"מ)', 'B', 'd_coast', LG(0.1, 60, 18), True, 'ק"מ'),
  ('junc_dens', 'צמתים לקמ"ר (OSM, אזור סטטיסטי)', 'U', 'junc_dens', LG(5, 400, 20), True, ''),
  ('junc_dens_walk', 'צמתים לקמ"ר (OSM, רשת הליכה)', 'U', 'junc_dens_walk', LG(5, 1000, 20), True, ''),
  ('junc_dens_cad', 'צמתים לקמ"ר (קדסטר, השיטה הקודמת)', 'U', 'junc_dens_cad', LG(5, 400, 20), True, ''),
  ('street_dens', 'ק"מ רחוב לקמ"ר (OSM)', 'U', 'street_dens', LG(2, 60, 20), True, ''),
  ('deadend_share', 'שיעור רחובות ללא מוצא (OSM)', 'U', 'deadend_share', list(np.round(np.linspace(0, 0.8, 17), 3)), False, '%'),
  ('fourway_share', 'שיעור צמתים של 4 רחובות ומעלה (OSM)', 'U', 'fourway_share', list(np.round(np.linspace(0, 0.8, 17), 3)), False, '%'),
  ('orient_ent', 'אנטרופיית כיווני רחובות (OSM)', 'U', 'orient_ent', list(np.round(np.linspace(0.5, 1, 21), 3)), False, ''),
  ('comm_dens', 'עסקים לקמ"ר (Overture)', 'U', 'comm_dens', LG(5, 5000, 20), True, ''),
  ('parking_dens', 'חניונים לקמ"ר (OSM)', 'U', 'parking_dens', LG(0.5, 200, 16), True, ''),
  ('parking_share', 'שיעור השטח בחניונים ממופים', 'U', 'parking_share', list(np.round(np.linspace(0, 0.2, 21), 3)), False, '%'),
  ('circuity', 'עקמומיות רחובות', 'U', 'circuity', list(np.round(np.linspace(1.0, 1.3, 16), 3)), False, ''),
  ('haredi', 'קולות לחרדים (כנסת 25)', 'U', 'haredi', list(np.round(np.linspace(0, 1, 21), 3)), False, '%'),
  ('arab', 'קולות למפלגות ערביות (כנסת 25)', 'U', 'arab', list(np.round(np.linspace(0, 1, 21), 3)), False, '%'),
  ('turnout', 'אחוז הצבעה (כנסת 25)', 'U', 'turnout', list(np.round(np.linspace(0.3, 1, 15), 3)), False, '%'),
  ('road_share', 'שיעור שטח דרכים (אזור סטטיסטי)', 'U', 'road_share', list(np.round(np.linspace(0, 0.5, 21), 3)), False, '%'),
  ('parcel_med', 'גודל חלקה חציוני (מ"ר)', 'U', 'parcel_med', LG(100, 20000, 20), True, 'מ"ר'),
  ('units_dens', 'דירות לקמ"ר (אזור סטטיסטי)', 'U', 'units_dens', LG(50, 50000, 20), True, ''),
  ('pop_dens', 'תושבים לקמ"ר (2015)', 'U', 'pop_dens', LG(100, 100000, 20), True, ''),
  ('mix', 'עירוב שימושים (אנטרופיה, 0–1)', 'U', 'mix', list(np.round(np.linspace(0, 0.8, 17), 3)), False, ''),
  ('comm_share', 'שיעור מסחר ומשרדים', 'U', 'comm_share', list(np.round(np.linspace(0, 0.6, 13), 3)), False, '%'),
  ('bus_dens', 'תחנות אוטובוס לקמ"ר', 'U', 'bus_dens', LG(1, 300, 18), True, ''),
  ('school_dens', 'מוסדות חינוך לקמ"ר', 'U', 'school_dens', LG(0.5, 200, 18), True, ''),
  ('ses21', 'אשכול חברתי־כלכלי 2021', 'U', 'ses21', [0.5 + k for k in range(11)], False, ''),
  ('chg', 'שינוי מחיר בגוש, 2015 עד 2025', 'G', 'chg', list(np.round(np.linspace(-0.2, 1.4, 17), 3)), False, '%'),
  ('turn', 'עסקאות ל־100 דירות בשנה (גוש)', 'G', 'turn', LG(0.004, 0.15, 16), True, ''),
]
import var_dict; _miss = [h[0] for h in HV if h[0] not in var_dict.V and h[0].replace('_pct', '') not in var_dict.V]; assert not _miss, _miss   # dictionary coverage
FR = {'B': B, 'U': U, 'G': G}
def hist(df, col, bins):
    v = df[col].astype(float).dropna().values
    h = np.histogram(np.clip(v, bins[0], bins[-1] - 1e-9), bins=bins)[0]
    return h.tolist(), float(np.median(v)) if len(v) else None, int(len(v))

# ---- index machinery (same definitions as build_hedonic.py)
H = pd.read_parquet('hed_sample.parquet')
H['region'] = H.gush.map(GR.region); H['county'] = H.gush.map(GR.county)
H['region'] = H.region.fillna(H.gush.map(B.groupby('gush').region.first())); H['county'] = H.county.fillna(H.gush.map(B.groupby('gush').county.first()))   # J&S
gc = B.drop_duplicates(['gush', 'parcel']).set_index(['gush', 'parcel']).city
H['city'] = pd.MultiIndex.from_arrays([H.gush, H.parcel]).map(gc)
H['q'] = H.ym.str[:4] + 'Q' + ((H.ym.str[5:7].astype(int) - 1)//3 + 1).astype(str)
codes = lambda s: pd.factorize(s)[0]
def fe_solve(v, gs, iters=1000, tol=1e-9):
    fes = [np.zeros(g.max()+1) for g in gs]; cnt = [np.bincount(g) for g in gs]; r = v.copy()
    for _ in range(iters):
        d = 0
        for k, g in enumerate(gs):
            r += fes[k][g]; new = np.bincount(g, r, minlength=len(cnt[k]))/np.maximum(cnt[k], 1)
            d = max(d, np.abs(new - fes[k]).max()); fes[k] = new; r -= new[g]
        if d < tol: break
    return fes
def demean(M, gs, iters=200, tol=1e-9):
    M = M.copy(); cnt = [np.bincount(g) for g in gs]
    for _ in range(iters):
        mx = 0
        for g, n in zip(gs, cnt):
            mean = np.vstack([np.bincount(g, M[:, k])/n for k in range(M.shape[1])]).T
            M -= mean[g]; mx = max(mx, np.abs(mean).max())
        if mx < tol: break
    return M
def xmat(d):
    parts = [d[['larea']].values]
    for col, base in [('rb', '3'), ('flb', '1'), ('ageb', '21-30'), ('typ', 'regular')]:
        dm = pd.get_dummies(d[col], dtype=float)
        parts.append(dm.drop(columns=[base], errors='ignore').values)
    X = np.hstack(parts)
    return X[:, X.std(0) > 0]
def indices(d, per):
    d = d.reset_index(drop=True)
    pi, pl = pd.factorize(d[per]); si = codes(d.sa); y = d.lpr.values; X = xmat(d)
    out = {}
    M = demean(np.c_[y, X], [pi, si]); b = np.linalg.lstsq(M[:, 1:], M[:, 0], rcond=None)[0]
    out['hed_pool'] = pd.Series(fe_solve(y - X @ b, [pi, si])[0], index=pl)
    ps = sorted(pl); pos = {p: k for k, p in enumerate(ps)}; mi = d[per].map(pos).values
    order = np.argsort(mi, kind='stable'); st = np.searchsorted(mi[order], np.arange(len(ps)+1)); ch = [0.0]
    for t in range(1, len(ps)):
        rows = order[st[t-1]:st[t+1]]; g = codes(d.sa.values[rows]); keep = np.bincount(g)[g] >= 2
        Mw = np.c_[y[rows], (mi[rows] == t).astype(float), X[rows]][keep]; g = codes(g[keep])
        if len(Mw) < 30: ch.append(ch[-1]); continue
        n = np.bincount(g); Mw = Mw - np.vstack([np.bincount(g, Mw[:, k])/n for k in range(Mw.shape[1])]).T[g]
        Mw = Mw[:, np.r_[True, True, Mw[:, 2:].std(0) > 0]]
        ch.append(ch[-1] + np.linalg.lstsq(Mw[:, 1:], Mw[:, 0], rcond=None)[0][0])
    out['hed_cbs'] = pd.Series(ch, index=ps)
    lpm = y - d.larea.values; bld = d.gush.astype(np.int64)*100000 + d.parcel; ar = codes(d.area.round())
    out['fe_bld'] = pd.Series(fe_solve(lpm, [pi, codes(bld), ar])[0], index=pl)
    apt = bld*10000 + d['sub']; rs = ((d['sub'] > 0) & (apt.map(apt.value_counts()) >= 2)).values
    ri, rl = pd.factorize(d[per][rs])
    out['fe_apt'] = pd.Series(fe_solve(lpm[rs], [ri, codes(apt[rs]), codes(d.area[rs].round())])[0], index=rl)
    I = pd.DataFrame(out).sort_index()[['hed_cbs', 'hed_pool', 'fe_bld', 'fe_apt']]
    base = I[I.index.str.startswith('2015')].mean()
    I = 100*np.exp(I - base)
    n_per = d.groupby(per).size()
    return [[p] + [None if not np.isfinite(v) else round(float(v), 1) for v in I.loc[p]] + [int(n_per.get(p, 0))] for p in I.index]

res = {'hist_vars': [[k, lab, fr, bins, lg, unit] for k, lab, fr, col, bins, lg, unit in HV], 'areas': []}
for key, name, level, col, val in AREAS:
    b, u, g, h = sel(B, col, val), sel(U, col, val), sel(G, col, val), sel(H, col, val)
    if len(b) == 0: continue
    a = {'key': key, 'name': name, 'level': level}
    bu = b[b.unit_val.notna()]
    rc = b[b.ren]
    a['sum'] = {
        'units': int(b.units.sum()), 'bld': int(len(b)), 'deals': int(len(h)),
        'value_bn': round(float((bu.units*bu.unit_val).sum()/1e9), 1),
        'ppm_med': None if b.ppm.notna().sum() == 0 else round(float(np.average(b.ppm.dropna(), weights=b.units[b.ppm.notna()]))),
        'fe_mean': None if b.fe_pct.notna().sum() < 10 else round(float(np.exp(np.average(np.log1p(b.fe_pct.dropna()), weights=b.n[b.fe_pct.notna()])) - 1), 3),
        'ren_units': int(rc.units.sum()), 'ren_share': round(float(rc.units.sum()/max(b.units.sum(), 1)), 3),
        'ren_feasible': round(float(rc.units[rc.loc_ppm >= 17250].sum()/max(rc.units.sum(), 1)), 3) if len(rc) else None,
        'junc': None if u.junc_dens.notna().sum() == 0 else round(float(np.average(u.junc_dens.fillna(0), weights=u.units.fillna(0) + 1e-9))),
        'ses': None if u.ses21.notna().sum() == 0 else round(float(np.average(u.ses21.dropna(), weights=u.units[u.ses21.notna()].fillna(0) + 1e-9)), 1),
        'fl_mean': round(float(b.fl.dropna().mean()), 1) if b.fl.notna().any() else None,
        'n_sa': int(len(u)),
    }
    a['hist'] = {k: hist(FR[fr] if fr != 'B' else b, colname, bins) if fr == 'B' else hist({'U': u, 'G': g}[fr], colname, bins)
                 for k, lab, fr, colname, bins, lg, unit in HV}
    per = 'ym' if level in ('nation', 'region') else 'q'
    if len(h) >= 3000:
        try: a['idx'] = {'per': per, 'rows': indices(h, per)}
        except Exception as e: print('index failed', key, e)
    res['areas'].append(a); print(key, len(b), len(h), flush=True)
json.dump(res, open('areas_v3.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('areas', len(res['areas']))
