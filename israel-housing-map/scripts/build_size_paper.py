# "Too big to fit": dwelling size, relative supply and the price of small apartments in Israel.
# All estimates for the paper (wiki/papers/own/dwelling-size/). Output: size_paper.json
#
# SECTIONS
#  F1  composition of new construction by building year (gazetteer units, imputed size) and of new-build
#      sales (first sales, building <= 1 year old) by rooms and by m2 bins; mean m2 and rooms
#  F2  composition of the stock by year
#  F3  price per m2 by dwelling size within building: rooms and m2 bins, building x year FE, by period
#  F4  IV within building: log price on log area, rooms dummies as instruments (division bias), building FE
#      + month FE
#  F5  relative prices and relative supply of size classes over time (national; district)
#  F6  Katz-Murphy by size: national size classes; district x size with own / same-district-other-sizes /
#      same-size-other-districts; full relative cross-size matrix with district x year FE; shift-share IV
#  F7  nested-logit demand (nests = size classes) estimated from the inverse demand
#      ln P_j = c_t + mu_j + b_own ln S_j + b_nest ln S_g(j)   with   b_own = -(1-sig)/alpha_L,
#      b_nest = -sig/alpha_L  (alpha_L: log-price utility; see paper section 6)
#  F8  counterfactual construction mix 1998-2019 holding each district's new floor area fixed
#
# DATA DECISIONS are as in build_km_io.py / build_km_grid.py (stock corrections, size imputation for the
# stock, building-FE price indices). New here:
#  - First sales: deals in buildings whose building year is the sale year or the year before (Tax Authority
#    yb), i.e. new construction sold by developers.
#  - Area bins use recorded area; recorded area drifted up ~8% from 2013 (build_txn.py 5/5b), so m2 trends
#    after 2013 overstate true size growth by up to that much; rooms are not affected.
#  - Prices for the counterfactual: median nominal price of dwellings sold in 2017-2019 by district x size.
#  - Construction cost of an extra dwelling at fixed floor area (kitchen, bathrooms, services, circulation):
#    a parameter, NIS 0.15M baseline, with 0.1 and 0.3 in robustness.
import json, time, numpy as np, pandas as pd, duckdb, shapely
from scipy.optimize import minimize
c = duckdb.connect('h.db', read_only=True)
codes = lambda s: pd.factorize(s)[0]
t0 = time.time()
OUT = {}
SIZES = ['1-2', '3', '4', '5+']
def scls(r): return np.select([r < 3, r < 4, r < 5], ['1-2', '3', '4'], '5+')

# ---------------- parcels, districts ----------------
P = pd.read_parquet('parcels_v3.parquet')[['gush', 'parcel', 'units', 'city', 'lat', 'lon']]
GR = pd.read_csv('gush_region.csv').set_index('gush'); P['district'] = P.gush.map(GR.region)
_wb = shapely.from_wkb(open('wb.wkb', 'rb').read()); _m = P.district.isna() & P.lat.notna()
P.loc[_m[_m].index[shapely.contains_xy(_wb, P.lon[_m].values, P.lat[_m].values)], 'district'] = 'יהודה ושומרון'
DIST = ['ירושלים', 'הצפון', 'חיפה', 'המרכז', 'תל-אביב', 'הדרום', 'יהודה ושומרון']
DLAB = {'ירושלים': 'Jerusalem', 'הצפון': 'North', 'חיפה': 'Haifa', 'המרכז': 'Center', 'תל-אביב': 'Tel Aviv', 'הדרום': 'South', 'יהודה ושומרון': 'Judea & Samaria'}

# ---------------- deals ----------------
cx = pd.read_excel('cpi.xlsx'); cx['date'] = cx['date'].astype(str).str[:7]; cs = cx.set_index('date').cpi
A = c.sql("select gush, parcel, sub, dt, price, ppm, area, rooms, yb, y from a where y between 1998 and 2025").df()
A = A.merge(P[['gush', 'parcel', 'city', 'district']], on=['gush', 'parcel'], how='inner')
A['ym'] = pd.to_datetime(A.dt).dt.to_period('M').astype(str)
A['cpi'] = A.ym.map(cs.reindex(sorted(A.ym.unique())).ffill())
A['lp'] = np.log(A.ppm / A.cpi); A['lprice'] = np.log(A.price / A.cpi)
A['bld'] = A.gush.astype(np.int64)*100000 + A.parcel
A['s'] = np.where(A.rooms.between(1, 12), scls(A.rooms.fillna(0).values), None)
A['rc'] = np.where(A.rooms.between(1, 12), np.ceil(A.rooms.fillna(0)).clip(1, 7), np.nan)
MB = [0, 60, 80, 100, 120, 150, 1000]; MBL = ['<60', '60-80', '80-100', '100-120', '120-150', '150+']
A['mb'] = pd.cut(A.area, MB, labels=MBL, right=False)
A = A[A.lp.notna() & A.area.between(20, 400)]
print('deals', len(A), round(time.time() - t0), 's', flush=True)

# ---------------- F1/F2: composition ----------------
D = A[A.rooms.between(1, 12)][['gush', 'parcel', 'sub', 'rooms', 's', 'city']]
own = D.groupby(['gush', 'parcel', 'sub']).rooms.median()
def dist(keys):
    t = pd.crosstab([D[k_] for k_ in keys], D.s).reindex(columns=SIZES, fill_value=0); return t.div(t.sum(axis=1), axis=0)
d_par, d_gush, d_city = dist(['gush', 'parcel']), dist(['gush']), dist(['city'])
d_nat = D.s.value_counts(normalize=True).reindex(SIZES).fillna(0)
G = c.sql("select gush, parcel, sub, yr from g").df(); G['yr'] = G.yr.where(G.yr.between(1870, 2026))
G = G.merge(P[['gush', 'parcel', 'city', 'district']], on=['gush', 'parcel'], how='left')
F = np.zeros((len(G), 4)); src = np.zeros(len(G), int)
own_s = pd.Series(scls(own.values), index=own.index).reindex(pd.MultiIndex.from_frame(G[['gush', 'parcel', 'sub']])).values
for j_, s_ in enumerate(SIZES): F[own_s == s_, j_] = 1
src[pd.notna(own_s)] = 1
for lev, tab, keys in [(2, d_par, ['gush', 'parcel']), (3, d_gush, ['gush']), (4, d_city, ['city'])]:
    need = src == 0
    idx = pd.MultiIndex.from_frame(G.loc[need, keys]) if len(keys) > 1 else pd.Index(G.loc[need, keys[0]])
    vals = tab.reindex(idx).values; got = ~np.isnan(vals).any(axis=1); rows = np.where(need)[0][got]; F[rows] = vals[got]; src[rows] = lev
F[src == 0] = d_nat.values; src[src == 0] = 5
for j_, s_ in enumerate(SIZES): G['f_' + s_] = F[:, j_]
for j_, s_ in enumerate(SIZES): G['g_' + s_] = np.where(src == 1, F[:, j_], 0.0)   # R3: directly matched units only
OUT['size_source_shares'] = {int(k_): round(float((src == k_).mean()), 3) for k_ in range(1, 6)}
# units by building year x size (corrections: missing years spread proportionally; heaping as in build_km)
def hist_stock(yr, wt):
    known = ~np.isnan(yr)
    h = pd.Series(wt[known]).groupby(yr[known].astype(int)).sum().reindex(range(1870, 2027), fill_value=0.0)
    for Y in range(1900, 2025, 5):
        ex = max(0.0, h[Y] - np.median([h.get(Y-2, 0), h.get(Y-1, 0), h.get(Y+1, 0), h.get(Y+2, 0)])); h[Y] -= ex
        for k_ in range(Y-2, Y+3): h[k_] += ex/5
    h *= 1 + wt[~known].sum() / max(wt[known].sum(), 1e-9)
    return h
yrv = G.yr.values.astype(float)
built = pd.DataFrame({s_: hist_stock(yrv, G['f_' + s_].values) for s_ in SIZES})      # completions by year x size
OUT['built_by_year'] = {'y': list(range(1950, 2020)), **{s_: built.loc[1950:2019, s_].round(0).tolist() for s_ in SIZES}}
sh = built.div(built.sum(axis=1), axis=0)
OUT['built_share'] = {'y': list(range(1950, 2020)), **{s_: sh.loc[1950:2019, s_].round(4).tolist() for s_ in SIZES}}
stock = built.cumsum()
ssh = stock.div(stock.sum(axis=1), axis=0)
OUT['stock_share'] = {'y': list(range(1960, 2020)), **{s_: ssh.loc[1960:2019, s_].round(4).tolist() for s_ in SIZES}}
# by district: completions 1998-2019 and stock 1997 / 2019 by size
SD = {}
for d_ in DIST:
    g_ = G[G.district == d_]
    SD[d_] = pd.DataFrame({s_: hist_stock(g_.yr.values.astype(float), g_['f_' + s_].values) for s_ in SIZES}).cumsum()
SDm = {}
for d_ in DIST:
    g_ = G[G.district == d_]
    SDm[d_] = pd.DataFrame({s_: hist_stock(g_.yr.values.astype(float), g_['g_' + s_].values) for s_ in SIZES}).cumsum()
OUT['stock_district'] = {DLAB[d_]: {'1997': SD[d_].loc[1997].round(0).tolist(), '2019': SD[d_].loc[2019].round(0).tolist()} for d_ in DIST}
# first sales (new construction) by sale year: rooms classes, m2 bins, mean m2 and rooms
NB = A[A.yb.notna() & (A.y - A.yb).between(0, 1)]
fs = {}
for y_, g_ in NB.groupby('y'):
    r_ = g_[g_.s.notna()]
    fs[int(y_)] = {'n': int(len(g_)), 'm2': round(float(g_.area.mean()), 1), 'm2_med': round(float(g_.area.median()), 1),
                   'rooms': round(float(np.ceil(r_.rooms).mean()), 2) if len(r_) else None,
                   'rooms_sh': r_.s.value_counts(normalize=True).reindex(SIZES).fillna(0).round(4).tolist(),
                   'm2_sh': g_.mb.value_counts(normalize=True).reindex(MBL).fillna(0).round(4).tolist()}
OUT['first_sales'] = fs
# all sales by building decade (rooms classes; mean m2)
A['dec'] = (A.yb // 10 * 10).where(A.yb.between(1940, 2025))
bd = {}
for d_, g_ in A[A.dec.notna()].groupby('dec'):
    r_ = g_[g_.s.notna()]
    bd[int(d_)] = {'n': int(len(g_)), 'm2': round(float(g_.area.mean()), 1), 'rooms': round(float(np.ceil(r_.rooms).mean()), 2),
                   'rooms_sh': r_.s.value_counts(normalize=True).reindex(SIZES).fillna(0).round(4).tolist(),
                   'm2_sh': g_.mb.value_counts(normalize=True).reindex(MBL).fillna(0).round(4).tolist()}
OUT['by_building_decade'] = bd
print('F1/F2 done', round(time.time() - t0), 's', flush=True)

# ---------------- F3: size gradients within building ----------------
def fe_solve(y, gs, iters=1000, tol=1e-8):
    fes = [np.zeros(g.max()+1) for g in gs]; cnt = [np.bincount(g) for g in gs]; r = y.copy()
    for _ in range(iters):
        dmax = 0
        for k_, g in enumerate(gs):
            r += fes[k_][g]; new = np.bincount(g, r, minlength=len(cnt[k_]))/np.maximum(cnt[k_], 1)
            dmax = max(dmax, np.abs(new - fes[k_]).max()); fes[k_] = new; r -= new[g]
        if dmax < tol: break
    return fes, r
PER = {'1998-2005': (1998, 2005), '2006-2012': (2006, 2012), '2013-2019': (2013, 2019), '2020-2025': (2020, 2025), 'all': (1998, 2025)}
grad = {}
for pn, (a_, b_) in PER.items():
    d = A[A.y.between(a_, b_) & A.rc.notna()]
    d = d[d.groupby('bld').bld.transform('size') >= 2]
    by = codes(d.bld.astype(str) + '#' + d.y.astype(str))                # building x year
    fes, _ = fe_solve(d.lp.values, [d.rc.values.astype(int), by])
    g_ = fes[0] - fes[0][4]                                                # vs 4 rooms
    fesm, _ = fe_solve(d.lp.values, [codes(d.mb.astype(str)), by])
    labs = pd.factorize(d.mb.astype(str))[1]; gm = pd.Series(fesm[0], index=labs); gm = gm - gm.get('80-100')
    grad[pn] = {'rooms': {int(k_): round(float(np.exp(g_[k_]) - 1), 4) for k_ in range(1, 8) if (d.rc == k_).sum() > 100},
                'm2': {k_: round(float(np.exp(gm.get(k_, np.nan)) - 1), 4) for k_ in MBL}, 'n': int(len(d))}
    print('  gradient', pn, grad[pn]['rooms'], flush=True)
OUT['gradient_within_building_year'] = grad
# district-specific within building x year rooms gradients (2013-2019), size classes 1-2/3/4/5+ (vs 4)
gd_ = {}
d = A[A.y.between(2013, 2019) & A.s.notna() & A.district.isin(DIST)]
d = d[d.groupby('bld').bld.transform('size') >= 2]
for d_, g_ in d.groupby('district'):
    by = codes(g_.bld.astype(str) + '#' + g_.y.astype(str)); sc = pd.Categorical(g_.s, categories=SIZES).codes.astype(int)   # category order (factorize would use order of appearance)
    fes, _ = fe_solve(g_.lp.values, [sc, by]); f_ = fes[0] - fes[0][2]
    gd_[d_] = [round(float(np.exp(v) - 1), 4) for v in f_]
OUT['gradient_district_2013_19'] = {DLAB[k_]: v for k_, v in gd_.items()}
print('  district gradients (1-2,3,4,5+ vs 4)', OUT['gradient_district_2013_19'], flush=True)

# ---------------- F4: IV within building ----------------
d = A[A.rc.notna() & A.y.between(1998, 2025)]
d = d[d.groupby('bld').bld.transform('size') >= 3]
gB, gM = codes(d.bld), codes(d.ym)
def wd(v):  # within building and month (alternating projections)
    return fe_solve(v.astype(float), [gB, gM], iters=300, tol=1e-7)[1]
y_ = wd(d.lprice.values); x_ = wd(np.log(d.area.values))
Z = np.column_stack([wd((d.rc == k_).astype(float).values) for k_ in [1, 2, 3, 5, 6, 7]])
b_ols = (x_ @ y_) / (x_ @ x_)
pi = np.linalg.lstsq(Z, x_, rcond=None)[0]; xh = Z @ pi; b_iv = (xh @ y_) / (xh @ x_)
e_ = y_ - b_iv * x_
cl = gB; S_ = np.bincount(cl, xh * e_); se_iv = np.sqrt((S_**2).sum()) / (xh @ x_)
eo = y_ - b_ols * x_; So = np.bincount(cl, x_ * eo); se_ols = np.sqrt((So**2).sum()) / (x_ @ x_)
r2f = 1 - ((x_ - xh)**2).sum() / (x_**2).sum()
OUT['iv_within_building'] = {'ols': [round(float(b_ols), 4), round(float(se_ols), 4)], 'iv': [round(float(b_iv), 4), round(float(se_iv), 4)],
                             'first_stage_partial_r2': round(float(r2f), 3), 'n': int(len(d)), 'buildings': int(d.bld.nunique())}
print('  IV within building', OUT['iv_within_building'], flush=True)

# ---------------- F5/F6/F7: relative prices and supply by size ----------------
def prices(d, mk, min_n=30):
    mk = pd.Series(mk, index=mk.index).reindex(d.index); ok_ = mk.notna(); d = d[ok_]; mk = mk[ok_]
    keep = d.groupby('bld').bld.transform('size') >= 2; d = d[keep]; mk = mk[keep]
    ci, labs = pd.factorize(mk.astype(str) + '#' + d.y.astype(str))
    f = fe_solve(d.lp.values.astype(float), [ci, codes(d.bld), codes(d.area.round())], iters=800, tol=1e-7)[0][0]
    T = pd.DataFrame({'mk': [l.split('#')[0] for l in labs], 't': [int(l.split('#')[1]) for l in labs], 'theta': f, 'n': np.bincount(ci)})
    T = T[T.n >= min_n]; base = T[T.t == 2015].set_index('mk').theta; T['theta'] = T.theta - T.mk.map(base)
    return T.dropna(subset=['theta']).reset_index(drop=True)
A20 = A[A.y <= 2020]
Tn = prices(A20, A20.s); Tn = Tn[Tn.t.between(1998, 2020)]
Sn = stock[SIZES]
OUT['national_series'] = {s_: {'t': g_.sort_values('t').t.tolist(), 'theta': g_.sort_values('t').theta.round(4).tolist(),
                                'lS': [round(float(np.log(Sn.at[t - 1, s_])), 4) for t in g_.sort_values('t').t]} for s_, g_ in Tn.groupby('mk')}
A20d = A20[A20.district.isin(DIST) & A20.s.notna()]
Td = prices(A20d, A20d.district + '|' + A20d.s.astype(str)); Td = Td[Td.t.between(1998, 2020)]
Td['dist'] = Td.mk.str.split('|').str[0]; Td['sz'] = Td.mk.str.split('|').str[1]
Td['lS'] = [np.log(SD[d_].at[t - 1, s_]) for d_, s_, t in zip(Td.dist, Td.sz, Td.t)]
Td['lS_dist_other'] = [np.log(SD[d_].loc[t - 1].drop(s_).sum()) for d_, s_, t in zip(Td.dist, Td.sz, Td.t)]
Td['lS_size_other'] = [np.log(sum(SD[o_].at[t - 1, s_] for o_ in DIST if o_ != d_)) for d_, s_, t in zip(Td.dist, Td.sz, Td.t)]
Td['lS_size_nat'] = [np.log(sum(SD[o_].at[t - 1, s_] for o_ in DIST)) for d_, s_, t in zip(Td.dist, Td.sz, Td.t)]
for k_ in SIZES: Td['lS_' + k_] = [np.log(SD[d_].at[t - 1, k_]) for d_, t in zip(Td.dist, Td.t)]
# shift-share instruments: district x size predicted stock from its 1985-97 share of national size-s construction
nat_s = {s_: sum(SD[o_][s_] for o_ in DIST) for s_ in SIZES}
def zpred(d_, s_, t):
    sh_ = (SD[d_].at[1997, s_] - SD[d_].at[1984, s_]) / max(nat_s[s_][1997] - nat_s[s_][1984], 1)
    return max(SD[d_].at[1997, s_] + sh_ * (nat_s[s_][t] - nat_s[s_][1997]), 1)
Td['z_own'] = [np.log(zpred(d_, s_, t - 1)) for d_, s_, t in zip(Td.dist, Td.sz, Td.t)]
Td['z_size_other'] = [np.log(sum(zpred(o_, s_, t - 1) for o_ in DIST if o_ != d_)) for d_, s_, t in zip(Td.dist, Td.sz, Td.t)]
Td['z_dist_other'] = [np.log(sum(zpred(d_, k_, t - 1) for k_ in SIZES if k_ != s_)) for d_, s_, t in zip(Td.dist, Td.sz, Td.t)]
Td['z_size_nat'] = [np.log(sum(zpred(o_, s_, t - 1) for o_ in DIST)) for d_, s_, t in zip(Td.dist, Td.sz, Td.t)]
Td['dt'] = Td.dist + '#' + Td.t.astype(str); Td['st'] = Td['sz'] + '#' + Td.t.astype(str)
Td = Td.replace([np.inf, -np.inf], np.nan).dropna(subset=['lS', 'lS_dist_other', 'lS_size_other']).reset_index(drop=True)
def fit(D, xs, fes, iv=None, cl='mk', trend=False):
    W = [pd.get_dummies(D[f_], prefix=f_, dtype=float) for f_ in fes]
    if trend: W.append(pd.get_dummies(D.mk, prefix='tr', dtype=float).mul(D.t - D.t.mean(), axis=0))
    Wm = pd.concat(W, axis=1).values; proj = lambda v: v - Wm @ np.linalg.lstsq(Wm, v, rcond=None)[0]
    y = proj(D.theta.values.astype(float)); X = np.column_stack([proj(D[x].values.astype(float)) for x in xs]); out = {}
    if iv:
        Zm = np.column_stack([proj(D[z].values.astype(float)) for z in iv]); Pi = np.linalg.lstsq(Zm, X, rcond=None)[0]; Xh = Zm @ Pi
        fs_ = []
        for j_ in range(X.shape[1]):
            oth = np.delete(Xh, j_, axis=1); xr = X[:, j_] - (oth @ np.linalg.lstsq(oth, X[:, j_], rcond=None)[0] if oth.shape[1] else 0)
            zr = Zm - (oth @ np.linalg.lstsq(oth, Zm, rcond=None)[0] if oth.shape[1] else 0); e1 = xr - zr @ np.linalg.lstsq(zr, xr, rcond=None)[0]
            r2 = 1 - (e1**2).sum()/(xr**2).sum(); kz = Zm.shape[1] - X.shape[1] + 1; fs_.append(round(float(r2/kz/((1 - r2)/max(len(D) - Zm.shape[1], 1))), 1))
        out['F'] = fs_; b = np.linalg.lstsq(Xh, y, rcond=None)[0]; e = y - X @ b; Xs = Xh
    else:
        b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b; Xs = X
    XtX = np.linalg.pinv(Xs.T @ Xs); g = codes(D[cl]); Gn = g.max() + 1
    Sg = np.vstack([np.bincount(g, Xs[:, k_]*e, minlength=Gn) for k_ in range(Xs.shape[1])]).T; V = XtX @ (Sg.T @ Sg) @ XtX * Gn/max(Gn - 1, 1)
    Vh = XtX @ ((Xs.T * e**2) @ Xs) @ XtX
    out.update({'x': xs, 'b': [round(float(v), 4) for v in b], 'se': [round(float(v), 4) for v in np.sqrt(np.diag(V))],
                'se_hc': [round(float(v), 4) for v in np.sqrt(np.diag(Vh))], 'r2w': round(float(1 - (e**2).sum()/max((y**2).sum(), 1e-12)), 4),
                'n': int(len(D)), 'nm': int(D.mk.nunique())})
    return out
def show(tag, r):
    print(f"  {tag:34s}", ' '.join(f"{x}={b:+.3f}({s:.3f}|{h:.3f})" for x, b, s, h in zip(r['x'], r['b'], r['se'], r['se_hc'])), f"R2w={r['r2w']:.3f}", f"F={r.get('F')}" if 'F' in r else '', flush=True)
KM = {}
# national size classes (4 markets)
Tn['lS'] = [np.log(Sn.at[t - 1, m]) for m, t in zip(Tn.mk, Tn.t)]
KM['nat_fe'] = fit(Tn, ['lS'], ['t', 'mk'])
# district x size
KM['own'] = fit(Td, ['lS'], ['t', 'mk'])
KM['own_dt'] = fit(Td, ['lS'], ['dt', 'mk'])
KM['own_dt_iv'] = fit(Td, ['lS'], ['dt', 'mk'], iv=['z_own'])
Td['lS_m'] = [np.log(max(SDm[d_].at[t - 1, s_], 1)) for d_, s_, t in zip(Td.dist, Td.sz, Td.t)]
KM['own_dt_matched'] = fit(Td.assign(lS=Td.lS_m), ['lS'], ['dt', 'mk'])
KM['own_dt_trend'] = fit(Td, ['lS'], ['dt', 'mk'], trend=True)
KM['nest3'] = fit(Td, ['lS', 'lS_dist_other', 'lS_size_other'], ['t', 'mk'])
KM['nest3_iv'] = fit(Td, ['lS', 'lS_dist_other', 'lS_size_other'], ['t', 'mk'], iv=['z_own', 'z_dist_other', 'z_size_other'])
KM['size_nest_dt'] = fit(Td, ['lS', 'lS_size_other'], ['dt', 'mk'])
KM['size_nest_dt_iv'] = fit(Td, ['lS', 'lS_size_other'], ['dt', 'mk'], iv=['z_own', 'z_size_other'])
KM['cross_dt_st'] = fit(Td, ['lS'], ['dt', 'st', 'mk'])
KM['cross_dt_st_iv'] = fit(Td, ['lS'], ['dt', 'st', 'mk'], iv=['z_own'])
# nested logit form: own and national size-nest total (includes own)
KM['nlogit_t'] = fit(Td, ['lS', 'lS_size_nat'], ['t', 'mk'])
KM['nlogit_dt'] = fit(Td, ['lS', 'lS_size_nat'], ['dt', 'mk'])
KM['nlogit_dt_iv'] = fit(Td, ['lS', 'lS_size_nat'], ['dt', 'mk'], iv=['z_own', 'z_size_nat'])
KM['nlogit_dt_trend'] = fit(Td, ['lS', 'lS_size_nat'], ['dt', 'mk'], trend=True)
for k_, v in KM.items(): show(k_, v)
# relative cross-size matrix: for own size s, effect of district stock of each size k, district x year FE
M_ = {}
for s_ in SIZES:
    for k_ in SIZES: Td[f'x_{s_}_{k_}'] = Td['lS_' + k_] * (Td['sz'] == s_)
xs = [f'x_{s_}_{k_}' for s_ in SIZES for k_ in SIZES]
rM = fit(Td, xs, ['dt', 'mk'])
B = np.array(rM['b']).reshape(4, 4); SE = np.array(rM['se']).reshape(4, 4)
Brel = B - B.mean(axis=0, keepdims=True)                                  # identified: relative to the mean over own sizes
KM['matrix_dt'] = {'b': B.round(4).tolist(), 'se': SE.round(4).tolist(), 'b_rel': Brel.round(4).tolist(), 'r2w': rM['r2w'], 'n': rM['n']}
print('  cross-size matrix (rows: price of size s; cols: stock of size k), relative to column mean:\n', np.round(Brel, 3), flush=True)
# KM figure data: (a) FWL partial residual plot for own_dt; (b) long differences 1998->2019 within district
def fwl(D, x, fes):
    Wm = pd.concat([pd.get_dummies(D[f_], prefix=f_, dtype=float) for f_ in fes], axis=1).values
    proj = lambda v: v - Wm @ np.linalg.lstsq(Wm, v, rcond=None)[0]
    return proj(D[x].values.astype(float)), proj(D.theta.values.astype(float))
rx, ry = fwl(Td, 'lS', ['dt', 'mk']); o_ = np.argsort(rx); nb = 20; bins_ = np.array_split(o_, nb)
KM['fig_resid'] = {'pts': {'x': rx.round(4).tolist(), 'y': ry.round(4).tolist(), 'sz': Td.sz.tolist(), 'dist': Td.dist.map(DLAB).tolist(), 't': Td.t.tolist()},
                   'bins': {'x': [round(float(rx[b_].mean()), 4) for b_ in bins_], 'y': [round(float(ry[b_].mean()), 4) for b_ in bins_]},
                   'slope': KM['own_dt']['b'][0], 'se': KM['own_dt']['se'][0]}
L0, L1 = 1998, 2019
ld = Td[Td.t.isin([L0, L1])].pivot_table(index=['dist', 'sz'], columns='t', values=['theta', 'lS']).dropna()
ld = pd.DataFrame({'dS': ld[('lS', L1)] - ld[('lS', L0)], 'dP': ld[('theta', L1)] - ld[('theta', L0)]}).reset_index()
ld['dS_rel'] = ld.dS - ld.groupby('dist').dS.transform('mean'); ld['dP_rel'] = ld.dP - ld.groupby('dist').dP.transform('mean')
ld['S19'] = [float(SD[d_].at[L1 - 1, s_]) for d_, s_ in zip(ld.dist, ld.sz)]
bl = np.polyfit(ld.dS_rel, ld.dP_rel, 1, w=np.sqrt(ld.S19))
KM['fig_longdiff'] = {'dist': ld.dist.map(DLAB).tolist(), 'sz': ld.sz.tolist(), 'dS': ld.dS_rel.round(4).tolist(), 'dP': ld.dP_rel.round(4).tolist(),
                      'S': ld.S19.round(0).tolist(), 'slope': round(float(bl[0]), 4), 'years': [L0, L1]}
print('  KM figure: long-difference slope', round(float(bl[0]), 3), 'markets', len(ld), flush=True)
OUT['km'] = KM
print('F6/F7 done', round(time.time() - t0), 's', flush=True)

# ---------------- F8: counterfactual ----------------
# Baseline: end-2019 stock by district x size; prices: median nominal 2017-2019 dwelling price; floor area
# per unit by district x size: median recorded m2 of 2017-2019 sales (scaled by 1/1.05 for the drift).
base = A[A.y.between(2017, 2019) & A.s.notna() & A.district.isin(DIST)]
PRC = base.groupby(['district', 's']).price.median().unstack().reindex(index=DIST, columns=SIZES) / 1e6     # NIS million
M2 = (base.groupby(['district', 's']).area.median().unstack().reindex(index=DIST, columns=SIZES) / 1.05)
PRC_raw = PRC.copy()
# Counterfactual prices hold location fixed: a dwelling of size s is valued as if built in the same building as
# the district's typical 4-room unit: P_ds = P_d4 x (m2_ds / m2_d4) x (1 + g_ds), g_ds = within building x year
# price-per-m2 gradient of size s vs 4 rooms in district d (2013-2019). Raw medians (PRC_raw) mix locations
# within the district (small units are more central) and are kept as robustness.
for i_, d_ in enumerate(DIST):
    g_ = OUT['gradient_district_2013_19'][DLAB[d_]]
    PRC.loc[d_] = [PRC_raw.loc[d_, '4'] * (M2.loc[d_, s_] / M2.loc[d_, '4']) * (1 + g_[k_]) for k_, s_ in enumerate(SIZES)]
OUT['cf_prices_same_building'] = PRC.round(3).values.tolist()
# Break-even per-unit cost c*: the extra cost of a dwelling (at fixed floor area) at which developers are
# indifferent between building size s and 4-room units in the same building:
#   (P_s - c)/m2_s = (P_4 - c)/m2_4   =>   c* = (P_s m2_4 - P_4 m2_s) / (m2_4 - m2_s)
cstar = {}
for i_, d_ in enumerate(DIST):
    p4, a4 = PRC.loc[d_, '4'], M2.loc[d_, '4']
    cstar[DLAB[d_]] = {s_: round(float((PRC.loc[d_, s_]*a4 - p4*M2.loc[d_, s_]) / (a4 - M2.loc[d_, s_])), 4) for s_ in ['1-2', '3', '5+']}
OUT['c_star'] = cstar
print('  break-even per-unit cost c* (NIS m) vs 4 rooms', cstar, flush=True)
S19 = pd.DataFrame({d_: SD[d_].loc[2019] for d_ in DIST}).T[SIZES]
S97 = pd.DataFrame({d_: SD[d_].loc[1997] for d_ in DIST}).T[SIZES]
NEW = S19 - S97
FA = (NEW * M2).sum(axis=1)                                                 # new floor area 1998-2019 by district (m2)
OUT['cf_inputs'] = {'price_musd': PRC.round(3).values.tolist(), 'm2': M2.round(1).values.tolist(), 'S19': S19.round(0).values.tolist(),
                    'new': NEW.round(0).values.tolist(), 'floor_area_new_km2': (FA/1e6).round(3).tolist(), 'districts': [DLAB[d_] for d_ in DIST], 'sizes': SIZES}
# MODEL (paper section 6). Households choose a dwelling type j = (district d, size s) or the outside option 0
# (no separate registered dwelling: living with parents or sharing, non-registered housing, leaving).
#   u_ij = xi_j - aP P_j + zeta_ig(j) + (1 - sig) eps_ij,   nests g = size classes (national)
# xi_j: fixed (mean) preference for type j (e.g. large units in Beersheba), zeta + eps: idiosyncratic.
# Stocks S_j are fixed in the short run; prices clear: s_j(P) = S_j / M, M = potential households.
# Inverse demand: aP P_j = xi_j - ln s_j + ln s0 + sig ln s_j|g.
# Mapping to the Katz-Murphy estimates (year effects absorb ln s0): at the average price Pbar,
#   d ln P_j / d ln S_j (own, holding the nest) = -(1-sig)/(aP Pbar),  d ln P_j / d ln S_g = -sig/(aP Pbar)
# so aP = 1/(Pbar |b_tot|), b_tot = b_own + b_nest = the price response of a size class to its own national
# supply (the KM inverse elasticity -1/sigma_size), and sig = b_nest / b_tot. The data put sig at the upper
# bound (district x size own effect >= 0: within a size class, districts are close substitutes), so sig is
# set to 0.9 (0.75 and 0.95 as robustness). s0 is NOT identified by regressions with year effects (it is in
# them); it governs household formation: the elasticity of the number of occupied dwellings with respect to
# a uniform price change is -aP Pbar s0 = -s0/|b_tot|. It is calibrated (0.1 / 0.2 / 0.3).
# WELFARE (NIS million, utility linear in price): CS = (M/aP) ln(1/s0)  [the nested-logit log-sum equals
# -ln s0 in equilibrium]; owners' asset value PS = sum P_j S_j; extra construction cost c per added dwelling
# (floor area held fixed): kitchen, bathrooms, safe room (mamad), services. dW = dCS + dPS - c dN.
def run_cf(b_size, s0_base, c_unit, label, search=True):
    """District-separable logit. In district d, potential households M_d choose a size class s (dwelling type
    j = (d,s)) or the outside option:  u_ij = xi_j - aP_d P_j + eps_ij  (eps iid type-1 EV).
    Location is held fixed (households do not move between districts in the counterfactual), which is the
    conservative choice: location preferences are strong and the data do not identify cross-district
    substitution. aP_d = 1/(Pbar_d |b_size|) maps the within-district relative-supply elasticity b_size
    (KM, district x year FE) into the logit price coefficient at the district's average price.
    Inverse demand: aP_d P_j = xi_j - ln s_j + ln s0_d.  CS_d = (M_d/aP_d) ln(1/s0_d)."""
    m2 = M2.values; new = NEW.values.astype(float); S97v = S97.values.astype(float); fa = FA.values; Pv = PRC.values
    S = S19.values.astype(float)
    res = {'b_size': b_size, 's0': s0_base, 'c': c_unit, 'hh_formation_elasticity': round(s0_base / abs(b_size), 3), 'district': {}}
    tot = {'simple': {q: {'dN': 0, 'dCS': 0, 'dPS': 0, 'dCost': 0, 'dW': 0} for q in (0.1, 0.25, 0.5)}, 'optimal': {'dN': 0, 'dCS': 0, 'dPS': 0, 'dCost': 0, 'dW': 0}}
    for i, d_ in enumerate(DIST):
        Pbar = float(np.average(Pv[i], weights=S[i])); aP = 1.0 / (Pbar * abs(b_size))
        Md = S[i].sum() / (1 - s0_base)
        xi = aP * Pv[i] + np.log(S[i] / Md) - np.log(s0_base)
        def eq(Sx):
            s0x = 1 - Sx.sum() / Md
            if s0x <= 1e-4 or (Sx <= 0).any(): return None, None
            return (xi - np.log(Sx / Md) + np.log(s0x)) / aP, s0x
        P0, s00 = eq(S[i]); CS0 = Md * (-np.log(s00)) / aP; PS0 = (P0 * S[i]).sum()
        def outcome(nm):
            S1 = S97v[i] + nm; P1, s01 = eq(S1)
            if P1 is None: return None
            CS1 = Md * (-np.log(s01)) / aP; PS1 = (P1 * S1).sum(); dN = S1.sum() - S[i].sum()
            return {'dN': dN, 'dCS': CS1 - CS0, 'dPS': PS1 - PS0, 'dCost': c_unit * dN, 'dW': CS1 - CS0 + PS1 - PS0 - c_unit * dN,
                    'dlnP': np.log(np.maximum(P1, 1e-6)) - np.log(P0), 'P1': P1, 'S1': S1, 's0': s01}
        rd = {'aP': round(aP, 4), 'Pbar': round(Pbar, 3), 'M': round(Md), 'simple': {}}
        for q in (0.1, 0.25, 0.5):
            nm = new[i].copy(); fa_move = q * (nm[2]*m2[i, 2] + nm[3]*m2[i, 3]); nm[2] *= (1 - q); nm[3] *= (1 - q)
            nm[0] += 0.5*fa_move / m2[i, 0]; nm[1] += 0.5*fa_move / m2[i, 1]
            o = outcome(nm); rd['simple'][q] = None if o is None else {k_: (round(float(v), 4) if np.isscalar(v) else np.round(v, 4).tolist()) for k_, v in o.items() if k_ not in ('S1',)}
            if o is not None:
                for k_ in tot['simple'][q]: tot['simple'][q][k_] += o[k_]
        if search:
            sh0 = new[i] * m2[i] / fa[i]
            def unpack(x):
                sh_ = np.abs(x) + 1e-9; sh_ = sh_ / sh_.sum(); return sh_ * fa[i] / m2[i]
            def obj(x):
                o = outcome(unpack(x)); return 1e12 if o is None else -o['dW']
            best = minimize(obj, np.sqrt(sh0), method='Nelder-Mead', options={'maxiter': 20000, 'xatol': 1e-8, 'fatol': 1e-6})
            for _ in range(3): best = minimize(obj, best.x, method='Nelder-Mead', options={'maxiter': 20000, 'xatol': 1e-9, 'fatol': 1e-7})
            nmo = unpack(best.x); o = outcome(nmo)
            # first-order check: (P_s - c)/m2_s should be equalised across sizes with positive construction
            wedge = (o['P1'] - c_unit) / m2[i]
            rd['optimal'] = {'floor_share': (nmo * m2[i] / fa[i]).round(4).tolist(), 'actual_floor_share': sh0.round(4).tolist(),
                             'net_value_per_m2_k': (wedge * 1000).round(3).tolist(),
                             'baseline_net_value_per_m2_k': ((P0 - c_unit) / m2[i] * 1000).round(3).tolist(),
                             **{k_: (round(float(v), 4) if np.isscalar(v) else np.round(v, 4).tolist()) for k_, v in o.items() if k_ not in ('S1', 'P1')}}
            for k_ in tot['optimal']: tot['optimal'][k_] += o[k_]
        res['district'][DLAB[d_]] = rd
    res['total'] = tot
    so = tot['simple'][0.25]; op = tot['optimal']
    print(f"  CF {label}: q=.25 dN={so['dN']:.0f} dCS={so['dCS']:.0f} dPS={so['dPS']:.0f} dW={so['dW']:.0f} | optimal dN={op['dN']:.0f} dCS={op['dCS']:.0f} dPS={op['dPS']:.0f} dW={op['dW']:.0f} (NIS m)", flush=True)
    return res
# sufficient statistic (paper section 7.1): value of splitting one 4-room dwelling into two smaller ones at the
# same floor area, from the within-building rooms gradient (2013-2019) and median m2/prices by size.
gr_ = OUT['gradient_within_building_year']['2013-2019']['rooms']
OUT['split_value'] = {}
for d_i, d_ in enumerate(DIST):
    p4, m4 = PRC.values[d_i, 2], M2.values[d_i, 2]; m2r = M2.values[d_i, 0]
    v_m2_4 = p4 / m4; v_m2_2 = v_m2_4 * (1 + gr_[2]) / (1 + gr_[4])
    n2 = m4 / m2r                                                       # number of 1-2 room units in a 4-room floor area
    OUT['split_value'][DLAB[d_]] = {'value_4room': round(p4, 3), 'value_as_small': round(n2 * m2r * v_m2_2, 3), 'n_small': round(n2, 2),
                                    'gain_before_cost': round(n2 * m2r * v_m2_2 - p4, 3)}
print('  split value', OUT['split_value'], flush=True)
OUT['cf'] = {}
# CONSTRUCTION COST (user's assumption, 2026-10-09): construction cost per m2 is the same in every district
# (a national construction-cost index by year, to be added), and a small unit costs slightly more per m2.
# With floor area held fixed, only the per-unit difference matters: c_true = delta x kappa x m2_small, with
# kappa ~ NIS 6,000 per m2 (placeholder until the CBS construction-input index is in) and delta ~ 5-8%,
# i.e. NIS 15-25K per extra dwelling. Baseline c_true = NIS 20K; 0 and 50K as bounds.
C_TRUE = 0.02
B_SIZE = {'district_x_year': KM['own_dt']['b'][0], 'national': KM['nat_fe']['b'][0]}
B_LOW = {'b=-0.5': -0.5, 'b=-1.09 (market trends)': KM['own_dt_trend']['b'][0]}
for bl, bt in B_SIZE.items():
    for s0_ in (0.1, 0.2, 0.3):
        for c_ in (0.0, C_TRUE, 0.05, 0.10, 0.15, 0.30):
            OUT['cf'][f'{bl}|s0={s0_}|c={c_}'] = run_cf(bt, s0_, c_, f'{bl} s0={s0_} c={c_}', search=True)
for bl, bt in B_LOW.items():
    for c_ in (0.0, C_TRUE, 0.05, 0.10, 0.15, 0.30):
        OUT['cf'][f'{bl}|s0=0.2|c={c_}'] = run_cf(bt, 0.2, c_, f'{bl} s0=0.2 c={c_}', search=True)
json.dump(OUT, open('size_paper.json', 'w'), ensure_ascii=False, default=lambda o: o.tolist() if hasattr(o, 'tolist') else float(o))
print('done', round(time.time() - t0), 's')
