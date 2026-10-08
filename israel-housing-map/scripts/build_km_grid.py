# Katz-Murphy over many definitions of a "market": geography x dwelling size x period length.
# Companion to build_km.py (same model, price index and supply corrections; see its header). A market is
# a cell such as "3-room dwellings in the Jerusalem district", and its price and supply are followed
# over sale periods (single years, or 5-year periods as in KM's sub-period analysis).
#
# DIMENSIONS
#   geography: IL (whole country) | district (7, incl. Judea and Samaria) | subdistrict (CBS nafa, >= 20K
#              registered dwellings) | city (>= 12K dwellings) | SES (CBS 2021 cluster of the SA, 1-10)
#   size:      all | rooms: 1-2, 3, 4, 5+ (rooms of the dwelling, rounded down: 3.5 rooms is "3")
#   period:    annual 1998-2020 (supply = stock at end of t-1, up to 2019, registration lag) |
#              5-year 1998-2002 ... 2018-22 (supply = stock at end of the year before the period)
#
# DWELLING SIZE IN THE STOCK. The gazetteer lists each registered unit (gush, parcel, sub-parcel) with its
# building year but not its size. Rooms come from the deals (table a: Tax Authority + govmap):
#   1. the unit's own sub-parcel sold at least once: median rooms of its sales (31% of units);
#   2. otherwise the rooms distribution of the units sold in its parcel (54%), else in its gush, else
#      in its city, else national: the unit is split fractionally over the four size classes.
# Rooms are reported by the seller and can change with renovations; sold units may differ from unsold
# ones in the same parcel (e.g. larger units turn over less). Both make the size split of the stock an
# approximation. Size classes are coarse to limit misclassification.
#
# PRICES. theta_m,tau = market x period FE in ln(price per m2 / CPI) = theta + building FE + rounded-m2 FE
# (build_km.price_index). With a size dimension, the market of a deal is given by its own rooms; deals
# without rooms are dropped. Cells with < 30 deals (annual) or < 50 (5-year) are dropped.
#
# MODELS (coefficient on log supply = -1/sigma; SEs clustered by market)
#   FE:     theta_m,tau = mu_tau + delta_m - (1/sigma) ln S_m,tau + u
#   TREND:  + market-specific linear trends (annual only)
#   CROSS:  geography x period FE + size x period FE + delta_m (only when both dimensions vary): the
#           KM identification - relative prices of size classes within a region and period against their
#           relative supplies, net of anything common to a region-period or a size-period
#   DIFF:   5-year first differences with period FE (KM's sub-period changes); DIFF-IV instruments the
#           change in log supply with the shift-share predicted stock (market's share of national
#           construction 1985-97, build_km.py INSTRUMENT)
# SEs: clustered by market; with few markets (IL x size: 4; districts: 7) cluster SEs are unreliable, so
# heteroskedasticity-robust unclustered SEs (se_hc) are reported alongside.
# R2 within = share of the price variation left after the fixed effects that log supply explains.
# Inputs: h.db (a, g), parcels_v3.parquet, gush_region.csv, sa2011.csv, cpi.xlsx. Output: km_grid.json
import json, itertools, time, numpy as np, pandas as pd, duckdb, shapely
c = duckdb.connect('h.db', read_only=True)
codes = lambda s: pd.factorize(s)[0]
t0 = time.time()

# ---------------- geography of each parcel ----------------
P = pd.read_parquet('parcels_v3.parquet')[['gush', 'parcel', 'units', 'city', 'lat', 'lon', 'unit_val']]
GR = pd.read_csv('gush_region.csv').set_index('gush')
P['district'] = P.gush.map(GR.region); P['subdistrict'] = P.gush.map(GR.county)
import shapely as _sh                                   # Judea and Samaria: not in gush_region (as in build_varmap)
_wb = _sh.from_wkb(open('wb.wkb', 'rb').read()); _m = P.district.isna() & P.lat.notna()
P.loc[_m[_m].index[_sh.contains_xy(_wb, P.lon[_m].values, P.lat[_m].values)], ['district', 'subdistrict']] = 'יהודה ושומרון'
sa = pd.read_csv('sa2011.csv'); sa = sa[sa.sa > 0].drop_duplicates('sa').reset_index(drop=True)
tree = shapely.STRtree(shapely.make_valid(shapely.from_wkt(sa.wkt.values)))
ok = P.lat.notna(); i, j = tree.query(shapely.points(P.lon[ok].values, P.lat[ok].values), predicate='within')
P['ses'] = None; P.loc[P.index[ok][i], 'ses'] = [f'SES {int(v)}' if v == v else None for v in sa.ses21.values[j]]
cu = P.groupby('city').units.sum(); P['city'] = P.city.where(P.city.isin(cu[cu >= 12000].index))
su = P.groupby('subdistrict').units.sum(); P['subdistrict'] = P.subdistrict.where(P.subdistrict.isin(su[su >= 20000].index))
P['IL'] = 'IL'
v_bar = np.average(P.unit_val.dropna(), weights=P.units[P.unit_val.notna()])
GEOS = ['IL', 'district', 'subdistrict', 'city', 'ses']

# ---------------- size of each unit in the stock ----------------
SIZES = ['1-2', '3', '4', '5+']
def scls(r): return np.select([r < 3, r < 4, r < 5], ['1-2', '3', '4'], '5+')
D = c.sql("select gush, parcel, sub, rooms from a where rooms between 1 and 12").df()
D['s'] = scls(D.rooms.values)
own = D.groupby(['gush', 'parcel', 'sub']).rooms.median().pipe(lambda r: pd.Series(scls(r.values), index=r.index))
def dist(keys):
    t = pd.crosstab([D[k] for k in keys], D.s).reindex(columns=SIZES, fill_value=0); return t.div(t.sum(axis=1), axis=0)
d_par, d_gush = dist(['gush', 'parcel']), dist(['gush'])
D = D.merge(P[['gush', 'parcel', 'city']], on=['gush', 'parcel'], how='left')
d_city = dist(['city']); d_nat = D.s.value_counts(normalize=True).reindex(SIZES).fillna(0)
G = c.sql("select gush, parcel, sub, yr from g").df()
G['yr'] = G.yr.where(G.yr.between(1870, 2026))
G = G.merge(P[['gush', 'parcel', 'unit_val'] + GEOS], on=['gush', 'parcel'], how='left')
F = np.zeros((len(G), 4)); src = np.zeros(len(G), int)
own_s = pd.Series(own.values, index=pd.MultiIndex.from_tuples(own.index)).reindex(pd.MultiIndex.from_frame(G[['gush', 'parcel', 'sub']])).values
for k, s_ in enumerate(SIZES): F[own_s == s_, k] = 1
src[pd.notna(own_s)] = 1
for lev, tab, keys in [(2, d_par, ['gush', 'parcel']), (3, d_gush, ['gush']), (4, d_city, ['city'])]:
    need = src == 0
    idx = pd.MultiIndex.from_frame(G.loc[need, keys]) if len(keys) > 1 else pd.Index(G.loc[need, keys[0]])
    vals = tab.reindex(idx).values; got = ~np.isnan(vals).any(axis=1)
    rows = np.where(need)[0][got]; F[rows] = vals[got]; src[rows] = lev
F[src == 0] = d_nat.values; src[src == 0] = 5
print('size source shares', {k: round(float((src == k).mean()), 3) for k in range(1, 6)}, round(time.time() - t0), 's')
G['w_val'] = (G.unit_val / v_bar).fillna((G.unit_val / v_bar).median())
for k, s_ in enumerate(SIZES): G['f_' + s_] = F[:, k]

def stock(geo, by_size, yrs):
    """end-of-year stock by market (geo[|size]) in units (n) and efficiency units (val); build_km corrections:
    heaping at multiples of 5 spread over 5 years; missing building year scaled in proportionally"""
    out = {}
    parts = [(s_, G['f_' + s_].values) for s_ in SIZES] if by_size else [(None, np.ones(len(G)))]
    for s_, f in parts:
        for mk, d in G[G[geo].notna() & (f > 0)].groupby(geo):
            fw = f[d.index]; known = d.yr.notna().values; res = {}
            for w in ['n', 'val']:
                wt = fw * (1.0 if w == 'n' else d.w_val.values)
                h = pd.Series(wt[known]).groupby(d.yr.values[known].astype(int)).sum().reindex(range(1870, 2027), fill_value=0.0)
                for Y in range(1900, 2025, 5):
                    ex = max(0.0, h[Y] - np.median([h.get(Y-2, 0), h.get(Y-1, 0), h.get(Y+1, 0), h.get(Y+2, 0)])); h[Y] -= ex
                    for k in range(Y-2, Y+3): h[k] += ex/5
                h *= 1 + wt[~known].sum() / max(wt[known].sum(), 1e-9)
                res[w] = h.cumsum().reindex(list(yrs))
            out[mk if s_ is None else f'{mk}|{s_}'] = pd.DataFrame(res)
    return out
S_nat = stock('IL', False, range(1870, 2021))['IL']

# ---------------- prices ----------------
cx = pd.read_excel('cpi.xlsx'); cx['date'] = cx['date'].astype(str).str[:7]; cs = cx.set_index('date').cpi
A = c.sql("select gush, parcel, dt, ppm, area, rooms, y from a where y between 1998 and 2022").df()
A = A.merge(P[['gush', 'parcel'] + GEOS], on=['gush', 'parcel'], how='inner')
A['ym'] = pd.to_datetime(A.dt).dt.to_period('M').astype(str)
A['lp'] = np.log(A.ppm / A.ym.map(cs.reindex(sorted(A.ym.unique())).ffill()))
A['bld'] = A.gush.astype(np.int64)*100000 + A.parcel
A['s'] = np.where(A.rooms.between(1, 12), scls(A.rooms.fillna(0).values), None)
PER = [(1998, 2002), (2003, 2007), (2008, 2012), (2013, 2017), (2018, 2022)]
A['p5'] = A.y.map(lambda v: next(k for k, (a, b) in enumerate(PER) if a <= v <= b))
def fe_solve(y, gs, iters=800, tol=1e-7):
    fes = [np.zeros(g.max()+1) for g in gs]; cnt = [np.bincount(g) for g in gs]; r = y.copy()
    for _ in range(iters):
        dmax = 0
        for k, g in enumerate(gs):
            r += fes[k][g]; new = np.bincount(g, r, minlength=len(cnt[k]))/np.maximum(cnt[k], 1)
            dmax = max(dmax, np.abs(new - fes[k]).max()); fes[k] = new; r -= new[g]
        if dmax < tol: break
    return fes
def prices(geo, by_size, per):
    d = A[A[geo].notna() & (A.s.notna() if by_size else True)]
    if per == 'annual': d = d[d.y <= 2020]
    d = d[d.groupby('bld').bld.transform('size') >= 2]
    mk = d[geo].astype(str) + (('|' + d.s.astype(str)) if by_size else '')
    tcol = d.y if per == 'annual' else d.p5
    ci, labs = pd.factorize(mk + '#' + tcol.astype(str))
    f = fe_solve(d.lp.values.astype(float), [ci, codes(d.bld), codes(d.area.round())])[0]
    T = pd.DataFrame({'mk': [l.split('#')[0] for l in labs], 't': [int(l.split('#')[1]) for l in labs], 'theta': f, 'n': np.bincount(ci)})
    T = T[T.n >= (30 if per == 'annual' else 50)]
    base = T[T.t == (2015 if per == 'annual' else 3)].set_index('mk').theta
    T['theta'] = T.theta - T.mk.map(base)
    return T.dropna(subset=['theta'])

# ---------------- regressions ----------------
def fit(D, xs, fes, trend=False, iv=None):
    W = [pd.get_dummies(D[f_], prefix=f_, dtype=float) for f_ in fes]
    if trend: W.append(pd.get_dummies(D.mk, prefix='tr', dtype=float).mul(D.t - D.t.mean(), axis=0))
    Wm = pd.concat(W, axis=1).values
    proj = lambda v: v - Wm @ np.linalg.lstsq(Wm, v, rcond=None)[0]
    y = proj(D.theta.values); X = np.column_stack([proj(D[x].values) for x in xs]); Fs = None
    if iv:
        Zm = np.column_stack([proj(D[z].values) for z in iv]); pi = np.linalg.lstsq(Zm, X, rcond=None)[0]; Xh = Zm @ pi
        cl0 = codes(D.mk); u = X - Xh; ZtZ = np.linalg.pinv(Zm.T @ Zm); Sz = np.c_[np.bincount(cl0, Zm[:, 0]*u[:, 0])]
        Vp = ZtZ @ (Sz.T @ Sz) @ ZtZ * (cl0.max()+1)/max(cl0.max(), 1); Fs = round(float(pi[0, 0]**2 / Vp[0, 0]), 1) if Vp[0, 0] > 0 else None
        b = np.linalg.lstsq(Xh, y, rcond=None)[0]; e = y - X @ b; Xs = Xh
    else:
        b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b; Xs = X
    XtX = np.linalg.pinv(Xs.T @ Xs); cl = codes(D.mk); G_ = cl.max() + 1
    Sg = np.vstack([np.bincount(cl, Xs[:, k]*e) for k in range(Xs.shape[1])]).T; V = XtX @ (Sg.T @ Sg) @ XtX * G_/max(G_ - 1, 1)
    Hh = (Xs.T * e**2) @ Xs; Vh = XtX @ Hh @ XtX                                  # heteroskedasticity-robust, unclustered
    return {'b': round(float(b[0]), 4), 'se': round(float(np.sqrt(V[0, 0])), 4), 'se_hc': round(float(np.sqrt(Vh[0, 0])), 4), 'r2w': round(float(1 - (e**2).sum()/max((y**2).sum(), 1e-12)), 4),
            'F': Fs, 'n': int(len(D)), 'nm': int(D.mk.nunique())}

def predicted(S):
    return {m: pd.DataFrame({w: d[w][1997] + (d[w][1997] - d[w][1984]) / (S_nat[w][1997] - S_nat[w][1984]) * (S_nat[w] - S_nat[w][1997])
                             for w in ['n', 'val']}) for m, d in S.items()}
GEO_LAB = {'IL': 'כל הארץ', 'district': 'מחוז', 'subdistrict': 'נפה', 'city': 'עיר', 'ses': 'אשכול SES'}
results = []
for geo, by_size, per in itertools.product(GEOS, [False, True], ['annual', '5y']):
    if geo == 'IL' and not by_size: continue                                    # a single market
    T = prices(geo, by_size, per)
    S = stock(geo, by_size, range(1870, 2021)); Z = predicted(S)
    lag = (lambda t: t - 1) if per == 'annual' else (lambda t: PER[t][0] - 1)
    for w in ['n', 'val']:
        T['lS_' + w] = [np.log(S[m][w][lag(t)]) if m in S and S[m][w][lag(t)] > 0 else np.nan for m, t in zip(T.mk, T.t)]
        T['lZ_' + w] = [np.log(max(Z[m][w][lag(t)], 1)) if m in Z else np.nan for m, t in zip(T.mk, T.t)]
    T = T.dropna().reset_index(drop=True)
    if per == 'annual': T = T[T.t <= 2020]
    T['geo'] = T.mk.str.split('|').str[0]; T['size'] = T.mk.str.split('|').str[1] if by_size else 'all'
    T['gt'] = T.geo + '#' + T.t.astype(str); T['st'] = T['size'] + '#' + T.t.astype(str)
    r = {'geo': geo, 'geo_lab': GEO_LAB[geo], 'size': 'rooms' if by_size else 'all', 'per': per,
         'n_mk': int(T.mk.nunique()), 'n_obs': int(len(T)), 'm': {}}
    for w in ['n', 'val']:
        r['m'][f'fe_{w}'] = fit(T, ['lS_' + w], ['t', 'mk'])
        if per == 'annual': r['m'][f'tr_{w}'] = fit(T, ['lS_' + w], ['t', 'mk'], trend=True)
        if by_size and geo != 'IL': r['m'][f'cross_{w}'] = fit(T, ['lS_' + w], ['gt', 'st', 'mk'])
        if per == 'annual': r['m'][f'iv_{w}'] = fit(T, ['lS_' + w], ['t', 'mk'], iv=['lZ_' + w])
    if per == '5y':                                                                # first differences, balanced markets
        B = T[T.groupby('mk').t.transform('size') == len(PER)].sort_values(['mk', 't']).copy()
        for col in ['theta', 'lS_n', 'lS_val', 'lZ_n', 'lZ_val']: B[col] = B.groupby('mk')[col].diff()
        B = B.dropna().reset_index(drop=True)
        if B.mk.nunique() >= 3:
            for w in ['n', 'val']:
                r['m'][f'dif_{w}'] = fit(B, ['lS_' + w], ['t'])
                r['m'][f'difiv_{w}'] = fit(B, ['lS_' + w], ['t'], iv=['lZ_' + w])
                if by_size and geo != 'IL': r['m'][f'difcross_{w}'] = fit(B, ['lS_' + w], ['gt', 'st'])
    if r['n_obs'] <= 120:                                                          # small panels: keep the series for charts
        r['series'] = {m: {'t': g.t.tolist(), 'theta': g.theta.round(4).tolist(), 'lS_n': g.lS_n.round(4).tolist()} for m, g in T.sort_values('t').groupby('mk')}
    results.append(r)
    print(geo, by_size, per, r['n_mk'], r['n_obs'], {k: (v['b'], v['se'], v['r2w']) for k, v in r['m'].items() if k.endswith('_n')}, round(time.time() - t0), 's', flush=True)
json.dump({'sizes': SIZES, 'periods': [f'{a}-{b % 100:02d}' for a, b in PER], 'results': results}, open('km_grid.json', 'w'), ensure_ascii=False)
