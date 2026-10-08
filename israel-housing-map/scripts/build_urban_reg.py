# Regressions of the building price premium on SA urban form (second half of build_urban.py, split off
# 2026-10-08 so it can be rerun alone). Inputs: urban_B.pkl, urban_U.pkl (build_urban.py checkpoint).
# Outputs: urban_v3.json, sa_urban.csv (with SA mean building FE).
import json, numpy as np, pandas as pd
B = pd.read_pickle('urban_B.pkl'); U = pd.read_pickle('urban_U.pkl')
codes = lambda s: pd.factorize(s)[0]

# ---------- regressions ----------
B = B.merge(U[['si', 'junc_dens', 'junc_dens_cad', 'junc_dens_walk', 'street_dens', 'deadend_share', 'fourway_share', 'orient_ent', 'road_share', 'units_dens', 'pop_dens', 'addr_dens', 'bus_dens',
               'school_dens', 'mix', 'comm_share', 'ses21', 'parcel_med', 'religion', 'yishuv', 'comm_dens', 'parking_dens',
               'parking_share', 'circuity', 'rail_1km', 'haredi', 'utj', 'arab', 'turnout']], on='si', how='left')
# MISSING VALUES (2026-10-08). The base sample is every building with >= 3 deals, a fixed effect and a
# known SA (loc_q <= 4: locality-level locations do not identify the SA). A building with a missing
# value in some regressor - e.g. no cadastral road share or parcel size (Judea and Samaria), no vote
# match, no coast distance outside the coastal band, unknown build year or floors - is dropped only
# from the regressions that use that variable (case-wise deletion inside ols()); it stays in every
# other model. So N differs across models and is reported with each one.
# ZEROS. Junctions, units, parcel size, street length: no SA in the sample has a zero (a zero would be
# treated as missing). Businesses (2% of buildings in SAs with none), bus stops (0.4%) and parking (24%)
# do have zeros: these enter as ln(x) for x > 0, set to 0 where x = 0, plus a dummy 1[x = 0] (the dummy
# absorbs the zero group, so the slope is identified from SAs with x > 0 only and does not depend on an
# arbitrary offset as ln(1 + x) would - that also depended on the unit, per km2). Distances are logged
# with an offset (rail +0.2 km, coast +0.2 km, CBD +1 km) so that the log does not explode for buildings
# next to a station or the beach; the offset flattens the curve within a short walk.
# UNITS. Variables with natural units keep them: log variables enter as logs (coefficient = elasticity
# of the price premium), shares enter per 10 percentage points. Only indices without a natural unit
# (land-use mix entropy, circuity, orientation entropy) are standardised (per weighted SD).
R = B[(B.n >= 3) & B.fe.notna() & B.si.notna() & (B.loc_q <= 4)].copy()
print('regression base sample', len(R))
lpos = lambda x: np.log(x.where(x > 0))
def l0(d, v, x):   # ln(x) with zeros set to 0 plus a zero dummy v_0 (missing x stays missing)
    d[v] = np.log(x.where(x > 0)).where(x != 0, 0.0); d[v + '_0'] = (x == 0).astype(float).where(x.notna())
R['l_junc'] = lpos(R.junc_dens); R['l_units'] = lpos(R.units_dens); l0(R, 'l_bus', R.bus_dens)
R['l_cbd'] = np.log(R.d_cbd + 1); R['l_rail'] = np.log(R.d_rail + 0.2); R['l_coast'] = np.log(R.d_coast + 0.2)
R['l_parcel'] = lpos(R.parcel_med)
l0(R, 'l_comm', R.comm_dens); l0(R, 'l_park', R.parking_dens)
R['w'] = R.n.clip(upper=50).astype(float)
# unknown build year or floor count (fl 0 = not recorded) is missing: dropped from models with these dummies
R['dec'] = (R.yr // 10 * 10).clip(1930, 2020)
R['flb'] = pd.cut(R.fl.where(R.fl > 0), [0, 2, 4, 8, 15, 100], labels=['1-2', '3-4', '5-8', '9-15', '16+'])
URB = ['l_junc', 'road_share', 'l_parcel', 'l_units', 'mix', 'comm_share', 'l_comm', 'l_park', 'circuity', 'l_bus',
       'l_rail', 'l_cbd', 'l_coast']
GRP = ['haredi', 'arab']                                # vote shares (Knesset 25), an alternative to the SES cluster
def zs(x, w):   # standardise with the weighted mean and SD of the non-missing values
    k = x.notna(); m = np.average(x[k], weights=w[k]); return (x - m) / np.sqrt(np.cov(x[k], aweights=w[k]))
SHARES = {'road_share', 'comm_share', 'haredi', 'arab', 'deadend_share', 'fourway_share'}
SDV = {'mix', 'circuity', 'orient_ent'}
UNIT = lambda v: 'log' if v.startswith('l_') else '10pp' if v in SHARES else 'sd'
def scale(d, v):   # the regressor as entered (suffix _x): log as is, share x 10, index standardised
    d[v + '_x'] = d[v] if UNIT(v) == 'log' else d[v]*10 if UNIT(v) == '10pp' else zs(d[v], d.w)
    if v + '_0' in d: d[v + '_x_0'] = d[v + '_0']
for v in URB + GRP: scale(R, v)

def wdemean(X, groups, w):
    if groups is None: return X - np.average(X, axis=0, weights=w)
    out = X.copy()
    for gcol in groups:
        gi = codes(gcol); sw = np.bincount(gi, w)
        for _ in range(1):
            m = np.vstack([np.bincount(gi, w*out[:, j])/sw for j in range(out.shape[1])]).T
            out = out - m[gi]
    return out
def ols(df, xs, absorb=(), dummies=()):
    """WLS of fe on xs (+ dummies), absorbing FE in `absorb` (alternating projections); SE clustered by SA.
    Rows with a missing value in any variable of this model are dropped (case-wise deletion)."""
    xs = list(xs) + [v + '_0' for v in xs if v + '_0' in df]     # zero dummies travel with their log
    df = df.dropna(subset=['fe', 'w', 'si'] + list(xs) + list(absorb) + list(dummies))
    X = df[xs].astype(float).values
    for d in dummies: X = np.c_[X, pd.get_dummies(df[d], drop_first=True, dtype=float).values]
    y = df.fe.values[:, None]; w = df.w.values
    sst = float((w*(df.fe.values - np.average(df.fe.values, weights=w))**2).sum())
    M = np.c_[y, X]
    gs = [df[a].values for a in absorb]
    if gs:
        for _ in range(30): M = wdemean(M, gs, w)
    else: M = M - np.average(M, axis=0, weights=w)
    y, X = M[:, 0], M[:, 1:]
    sw = np.sqrt(w); Xw, yw = X*sw[:, None], y*sw
    XtX = np.linalg.pinv(Xw.T @ Xw); b = XtX @ Xw.T @ yw; e = yw - Xw @ b
    cl = codes(df.si.values); S = np.vstack([np.bincount(cl, Xw[:, j]*e) for j in range(X.shape[1])]).T
    V = XtX @ (S.T @ S) @ XtX; G = cl.max()+1; V *= G/(G-1)
    r2 = 1 - (e**2).sum()/sst                       # total R2 (absorbed FE count as explained)
    r2w = 1 - (e**2).sum()/(yw**2).sum()             # within R2
    k = len(xs)
    return {'b': dict(zip(xs, np.round(b[:k], 4))), 'se': dict(zip(xs, np.round(np.sqrt(np.diag(V))[:k], 4))), 'r2': round(float(r2), 3), 'r2_within': round(float(r2w), 3), 'n': int(len(df))}

Z = [v + '_x' for v in URB]
res = {}
res['m1_junc'] = ols(R, ['l_junc_x'])
res['m2_urban'] = ols(R, Z)
FORM = ['l_junc_x', 'road_share_x', 'l_parcel_x', 'l_units_x', 'mix_x', 'comm_share_x', 'l_comm_x', 'l_park_x', 'circuity_x', 'l_bus_x']
LOC = ['l_rail_x', 'l_cbd_x', 'l_coast_x']
res['m_form'] = ols(R, FORM)
res['m_loc'] = ols(R, LOC)
res['m_form_city'] = ols(R, FORM, absorb=['yishuv'])
res['m3_ses'] = ols(R, Z, dummies=['ses21'])
res['m4_city'] = ols(R, Z, absorb=['yishuv'], dummies=['ses21'])
res['m5_bld'] = ols(R, Z, absorb=['yishuv'], dummies=['ses21', 'dec', 'flb'])
res['m6_junc_city'] = ols(R, ['l_junc_x'], absorb=['yishuv'])
res['m7_junc_city_ses'] = ols(R, ['l_junc_x'], absorb=['yishuv'], dummies=['ses21'])
# vote shares as the group control, alone and with SES; all within city
G = [g + '_x' for g in GRP]
res['m8_city_votes'] = ols(R, Z + G, absorb=['yishuv'])
res['m9_city_ses_votes'] = ols(R, Z + G, absorb=['yishuv'], dummies=['ses21'])
res['r2_votes'] = ols(R, G)['r2']
res['r2_ses_votes'] = ols(R, G, dummies=['ses21'])['r2']
res['sd_grp'] = {v: float(np.sqrt(np.cov(R[v], aweights=R.w))) for v in GRP}
# OSM vs cadastral, and the extra OSM network measures: one at a time (z-scored), on the sample
# where all are defined: raw, within city, within city + SES
# each measure on its own non-missing sample; the joint model on buildings with all of them
Q = R.copy()
Q['l_junc_osm'] = lpos(Q.junc_dens); Q['l_junc_cad'] = lpos(Q.junc_dens_cad); Q['l_junc_walk'] = lpos(Q.junc_dens_walk)
Q['l_street'] = lpos(Q.street_dens)
NETV = ['l_junc_osm', 'l_junc_cad', 'l_junc_walk', 'l_street', 'deadend_share', 'fourway_share', 'orient_ent']
for v in NETV: scale(Q, v)
def one(v):
    r = [ols(Q, [v + '_x']), ols(Q, [v + '_x'], absorb=['yishuv']), ols(Q, [v + '_x'], absorb=['yishuv'], dummies=['ses21'])]
    k = Q[v].notna()
    return {'b': [m['b'][v + '_x'] for m in r], 'se': [m['se'][v + '_x'] for m in r], 'n': [m['n'] for m in r],
            'sd': float(np.sqrt(np.cov(Q[v][k], aweights=Q.w[k])))}
res['net_cmp'] = {v: one(v) for v in NETV}
res['net_cmp_n'] = int(Q[NETV].notna().all(axis=1).sum())
res['net_all_city_ses'] = ols(Q, [v + '_x' for v in NETV], absorb=['yishuv'], dummies=['ses21'])
# total explained: city dummies only, SA dummies only (ceiling for any SA-level measure)
res['r2_city'] = ols(R.assign(one=0.0), ['one'], absorb=['yishuv'])['r2']
res['r2_sa'] = ols(R.assign(one=0.0), ['one'], absorb=['si'])['r2']
res['r2_ses'] = ols(R.assign(one=0.0), ['one'], dummies=['ses21'])['r2']
res['sd_fe'] = float(np.sqrt(np.cov(R.fe, aweights=R.w)))
res['sd_raw'] = {v: float(np.sqrt(np.cov(R[v].dropna(), aweights=R.w[R[v].notna()]))) for v in URB}
res['n_base'] = int(len(R))
res['units'] = {v: UNIT(v) for v in URB + GRP + NETV}

# binned scatter: FE vs log intersection density, raw and within city (both residualised on city)
def binsc(x, y, w, nb=20):
    q = np.asarray(pd.qcut(x, nb, labels=False, duplicates='drop'))
    return [[float(np.average(x[q == k], weights=w[q == k])), float(np.average(y[q == k], weights=w[q == k])), int((q == k).sum())] for k in range(q.max()+1)]
def bins2(v, nb=20):
    """Binned scatter on the actual values of x (20 weighted-count quantile bins): mean building FE ('raw'),
    and mean building FE relative to its city's weighted mean ('city'; the city mean is over all buildings
    of the city in the base sample). Showing x in its own units keeps the axis readable (demeaning x too,
    as in a strict FWL binscatter, put shares below zero); the within-city slope is reported separately
    by the regressions. Log variables with zeros: x > 0 only."""
    d = R[R[v].notna() & R.yishuv.notna()]
    if v + '_0' in d: d = d[d[v + '_0'] == 0]
    cm = (R.fe*R.w).groupby(R.yishuv).sum() / R.w.groupby(R.yishuv).sum()
    return binsc(d[v].values, d.fe.values, d.w.values, nb), binsc(d[v].values, (d.fe - d.yishuv.map(cm)).values, d.w.values, nb), int(len(d))
res['bins_raw'], res['bins_city'], _ = bins2('l_junc')
# commerce: businesses per km2 (log(1+x)) and the commerce share of land use, same binned scatter
res['bins_comm'] = {v: dict(zip(['raw', 'city', 'n'], bins2(v))) for v in ['l_comm', 'comm_share']}
res['m_comm'] = {v: [ols(R, [v + '_x']), ols(R, [v + '_x'], absorb=['yishuv']), ols(R, [v + '_x'], absorb=['yishuv'], dummies=['ses21'])]
                 for v in ['l_comm', 'comm_share']}

# SA table for the page: SA-level mean FE and measures (urban SAs with >= 20 buildings with FE)
S = R.groupby('si').apply(lambda d: pd.Series({'fe': np.average(d.fe, weights=d.w), 'nb': len(d)}))
U = U.join(S, on='si')
U.to_csv('sa_urban.csv', index=False)
top = U[(U.nb >= 20)].copy()
res['sa_corr'] = {v: round(float(np.corrcoef(top[v].astype(float), top.fe)[0, 1]), 3) for v in
                  ['junc_dens', 'road_share', 'parcel_med', 'units_dens', 'pop_dens', 'mix', 'comm_share', 'bus_dens', 'school_dens']
                  if top[v].notna().all()}
res['n_sa'] = int(len(top)); res['n_sa_all'] = int(len(U))
res['junc_dens_q'] = [round(float(x)) for x in U[U.units > 0].junc_dens.quantile([.1, .25, .5, .75, .9])]
res['junc_dens_cad_q'] = [round(float(x)) for x in U[U.units > 0].junc_dens_cad.quantile([.1, .25, .5, .75, .9])]
_k = U[(U.units > 0) & U.junc_dens_cad.notna()]
res['sa_corr_osm_cad'] = round(float(np.corrcoef(np.log1p(_k.junc_dens), np.log1p(_k.junc_dens_cad))[0, 1]), 3)
res['city_blk'] = (U[U.units > 0].groupby('name').apply(lambda d: pd.Series({
        'junc_dens': np.average(d.junc_dens, weights=d.units), 'road_share': np.average(d.road_share, weights=d.units),
        'units': d.units.sum(), 'fe': np.average(d.fe.fillna(d.fe.mean()), weights=d.units)}))
        .query('units >= 20000').sort_values('junc_dens', ascending=False).round(3).reset_index().values.tolist())
def clean(o):   # NaN is not valid JSON
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)): return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer): return int(o)
    return o
json.dump(clean(res), open('urban_v3.json', 'w'), ensure_ascii=False)
for k, v in res.items(): print(k, json.dumps(v, ensure_ascii=False, default=float)[:600])
