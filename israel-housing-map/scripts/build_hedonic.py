# Hedonic price indices vs fixed-effects indices, on one common sample.
#
# Sample: Tax Authority apartment sales (table `a` in h.db: whole units, 25-400 m2,
# 1998-2026), real prices (cpi.xlsx). Floor added from govmap deals where the
# deal matches on (gush, parcel, sub-parcel, date); otherwise floor = unknown.
# Location: CBS statistical area (2011) of the parcel centroid.
#
# Characteristics X: log area, rooms (rounded up, 1..6+, unknown), floor (0,1,2,
# 3-4, 5-8, 9-15, 16+, unknown), building age at sale (bins), type (regular /
# garden / roof), first-hand sale (built in the sale year or the one before).
#
# Indices (monthly, 2015 = 100):
#  hed_pool  pooled time-dummy hedonic: log price = X b + SA FE + month FE
#  hed_cbs   CBS-style: the same regression run on each pair of adjacent months
#            (t-1, t) with a dummy for t, and the month-on-month changes chained
#  fe_bld    building FE + month FE + rounded-area FE (log price per m2)
#  fe_apt    apartment FE + month FE + rounded-area FE (repeat sales)
# Output: hedonic_v3.json, hed_sample.parquet
import json, numpy as np, pandas as pd, duckdb, shapely
from shapely import STRtree
# govmap deals with the unit's floor (text), matched to Tax Authority deals on gush, parcel, sub-parcel and date
_w = duckdb.connect('h.db')
_w.execute("""create or replace table gd as select try_cast(gush as int) gush, try_cast(parcel as int) parcel,
  try_cast(sub as int) sub, try_cast(date as date) dt, floor from read_csv('govmap_deals.csv', all_varchar=true, header=true)""")
_w.close()
c = duckdb.connect('h.db', read_only=True)
D = c.sql("""
  select a.gush, a.parcel, a.sub, a.dt, a.price, a.area, a.rooms, a.yb, a.nat, a.y, cen.lat, cen.lon, f.floor
  from a left join cen using (gush, parcel)
  left join (select distinct on (gush, parcel, sub, dt) gush, parcel, sub, dt, floor from gd) f using (gush, parcel, sub, dt)
  where a.dt <= date '2026-08-31'""").df()
print('sample', len(D), 'floor matched', D.floor.notna().mean().round(3))
D['yb'] = D.yb.astype(float)                                   # nullable (govmap deals have no year built)

# CPI-deflated log price, 2015 prices
cx = pd.read_excel('cpi.xlsx'); cx['date'] = cx['date'].astype(str).str[:7]
cs = cx.set_index('date').cpi; cs = cs/cs[cs.index.str.startswith('2015')].mean()
D['ym'] = pd.to_datetime(D.dt).dt.to_period('M').astype(str)
D['lpr'] = np.log(D.price / D.ym.map(cs.reindex(sorted(D.ym.unique())).ffill()))

# floor parsing (same rules as build_floor.py)
import re
ORD = {'קרקע': 0, 'ראשונה': 1, 'שניה': 2, 'שנייה': 2, 'שלישית': 3, 'רביעית': 4, 'חמישית': 5, 'שישית': 6, 'שביעית': 7,
       'שמינית': 8, 'תשיעית': 9, 'עשירית': 10}
UNITS = {'אחת': 1, 'אחד': 1, 'שתים': 2, 'שתיים': 2, 'שלוש': 3, 'ארבע': 4, 'חמש': 5, 'שש': 6, 'שבע': 7, 'שמונה': 8, 'תשע': 9}
TENS = {'עשרים': 20, 'שלושים': 30, 'ארבעים': 40}
def parse_floor(s):
    s = re.sub(r'[‎‏]', '', s or '').strip()
    if not s: return np.nan
    m = re.fullmatch(r'קומה\s*(-?\d+)', s) or re.fullmatch(r'(-?\d+)', s)
    if m: return int(m.group(1))
    if s in ORD: return ORD[s]
    m = re.fullmatch(r'(\S+) עשרה', s)
    if m and m.group(1) in UNITS: return 10 + UNITS[m.group(1)]
    if s in TENS: return TENS[s]
    m = re.fullmatch(r'(\S+) ו(\S+)', s)
    if m and m.group(1) in TENS and m.group(2) in UNITS: return TENS[m.group(1)] + UNITS[m.group(2)]
    return np.nan
fm = {v: parse_floor(v) for v in D.floor.dropna().unique()}
fl = D.floor.map(fm)
def lab(x):  # categorical labels with an explicit 'na' level (pandas 3 keeps NaN through astype(str))
    x = pd.Series(x, index=D.index).astype(object)
    return x.where(x.notna(), 'na').astype(str)
D['flb'] = lab(pd.cut(fl, [-0.5, 0.5, 1.5, 2.5, 4.5, 8.5, 15.5, 99], labels=['0', '1', '2', '3-4', '5-8', '9-15', '16+']))

# statistical area of the parcel centroid
LAT0 = 31.8; KX = 111320*np.cos(np.radians(LAT0)); KY = 110574
sa = pd.read_csv('sa2011.csv'); sa = sa[sa.sa > 0].reset_index(drop=True)
geom = shapely.transform(shapely.from_wkt(sa.wkt.values), lambda q: np.c_[q[:, 0]*KX, q[:, 1]*KY])
tree = STRtree(geom); pts = shapely.points(D.lon.values*KX, D.lat.values*KY)
D['sa'] = -1; ok = D.lat.notna().values
i, j = tree.query(pts[ok], predicate='within'); idx = np.where(ok)[0]
D.loc[idx[i], 'sa'] = sa.sa.values[j]
D = D[D.sa > 0].copy()
print('with SA', len(D))

# characteristics
age = (D.y - D.yb).where(D.yb.between(1900, 2027))
D['ageb'] = lab(pd.cut(age, [-2, 1, 5, 10, 20, 30, 40, 50, 60, 200], labels=['new', '2-5', '6-10', '11-20', '21-30', '31-40', '41-50', '51-60', '60+']))
D['rb'] = lab(np.ceil(D.rooms.where(D.rooms.between(1, 12))).clip(upper=6).map(lambda v: str(int(v)) if v == v else None))
D['typ'] = D.nat.map({'דירת גן': 'garden', 'דירת גג': 'roof'}).fillna('regular')
D['larea'] = np.log(D.area)
cat = lambda col, base: pd.get_dummies(D[col], prefix=col, dtype=float).drop(columns=f'{col}_{base}')
X = pd.concat([D[['larea']], cat('rb', '3'), cat('flb', '1'), cat('ageb', '21-30'), cat('typ', 'regular')], axis=1)
XN = list(X.columns); Xv = X.values; y = D.lpr.values
D[['gush', 'parcel', 'sub', 'ym', 'y', 'lpr', 'larea', 'area', 'rooms', 'yb', 'rb', 'flb', 'ageb', 'typ', 'sa']].to_parquet('hed_sample.parquet')   # reused by build_areas.py
codes = lambda s: pd.factorize(s)[0]
ym_i, ym_l = pd.factorize(D.ym); sa_i = codes(D.sa)

def demean(M, gs, iters=200, tol=1e-9):
    """Residualise columns of M on several FE groups (alternating projections)."""
    M = M.copy(); cnt = [np.bincount(g) for g in gs]
    for it in range(iters):
        mx = 0
        for g, n in zip(gs, cnt):
            mean = np.vstack([np.bincount(g, M[:, k]) / n for k in range(M.shape[1])]).T
            M -= mean[g]; mx = max(mx, np.abs(mean).max())
        if mx < tol: break
    return M

# 1. pooled time-dummy hedonic with SA FE (FWL), then recover the month FE
Mr = demean(np.c_[y, Xv], [ym_i, sa_i])
b = np.linalg.lstsq(Mr[:, 1:], Mr[:, 0], rcond=None)[0]
r = y - Xv @ b
def fe_solve(v, gs, iters=2000, tol=1e-10):
    fes = [np.zeros(g.max()+1) for g in gs]; cnt = [np.bincount(g) for g in gs]; res = v.copy()
    for _ in range(iters):
        d = 0
        for k, g in enumerate(gs):
            res += fes[k][g]; new = np.bincount(g, res, minlength=len(cnt[k]))/np.maximum(cnt[k], 1)
            d = max(d, np.abs(new - fes[k]).max()); fes[k] = new; res -= new[g]
        if d < tol: break
    return fes
f_ym = fe_solve(r, [ym_i, sa_i])[0]
e = Mr[:, 0] - Mr[:, 1:] @ b
r2_within = 1 - (e**2).sum()/(Mr[:, 0]**2).sum()
idx = lambda s: 100*np.exp(s - s[s.index.str.startswith('2015')].mean())
hed_pool = idx(pd.Series(f_ym, index=ym_l).sort_index())
coef = {k: round(float(v), 4) for k, v in zip(XN, b)}
print('pooled done; within R2', round(r2_within, 3))

# 2. CBS-style adjacent-month hedonic, chained
months = sorted(D.ym.unique()); pos = {m: k for k, m in enumerate(months)}
mi = D.ym.map(pos).values
order = np.argsort(mi, kind='stable'); starts = np.searchsorted(mi[order], np.arange(len(months)+1))
chain = [0.0]; nwin = []
for t in range(1, len(months)):
    rows = order[starts[t-1]:starts[t+1]]
    dt_ = (mi[rows] == t).astype(float)
    g = codes(D.sa.values[rows])
    M = np.c_[y[rows], dt_, Xv[rows]]
    cnt = np.bincount(g); keep = cnt[g] >= 2                      # SA must appear twice to identify anything
    M, g = M[keep], codes(g[keep])
    n = np.bincount(g); M = M - np.vstack([np.bincount(g, M[:, k])/n for k in range(M.shape[1])]).T[g]
    bb = np.linalg.lstsq(M[:, 1:], M[:, 0], rcond=None)[0]
    chain.append(chain[-1] + bb[0]); nwin.append(int(keep.sum()))
hed_cbs = idx(pd.Series(chain, index=months))
print('cbs-style done; median window n', int(np.median(nwin)))

# 3-4. fixed-effects indices on the same sample (log price per m2, rounded-area FE)
lpm = y - D.larea.values
D['bld'] = D.gush.astype(np.int64)*100000 + D.parcel
D['apt'] = D.bld*10000 + D['sub']
ar = codes(D.area.round())
fb = fe_solve(lpm, [ym_i, codes(D.bld), ar])[0]
fe_bld = idx(pd.Series(fb, index=ym_l).sort_index())
rs = (D['sub'] > 0) & (D.groupby('apt').apt.transform('size') >= 2)
ri, rl = pd.factorize(D.ym[rs])
fa = fe_solve(lpm[rs.values], [ri, codes(D.apt[rs]), codes(D.area[rs].round())])[0]
fe_apt = idx(pd.Series(fa, index=rl).sort_index())

# ---- comparison ----
I = pd.DataFrame({'hed_cbs': hed_cbs, 'hed_pool': hed_pool, 'fe_bld': fe_bld, 'fe_apt': fe_apt}).sort_index()
L = np.log(I)
mchg = L.diff().dropna()
yoy = L.diff(12).dropna()
yr = L.groupby(L.index.str[:4]).mean()
def cum(a, b): return {k: round(float(np.exp(yr.loc[b, k] - yr.loc[a, k]) - 1), 3) for k in I.columns}
out = {
  'n': int(len(D)), 'share_na': {k: round(float((D[k] == 'na').mean()), 3) for k in ['flb', 'rb', 'ageb']}, 'n_floor': int((D.flb != 'na').sum()), 'n_sa': int(D.sa.nunique()), 'n_rs': int(rs.sum()),
  'coef': coef, 'r2_within_pool': round(float(r2_within), 3), 'cbs_window_n_median': int(np.median(nwin)),
  'idx': [[m] + [round(float(I.loc[m, k]), 2) for k in I.columns] for m in I.index],
  'cum': {f'{a}–{b}': cum(a, b) for a, b in [('1998', '2008'), ('2008', '2015'), ('2015', '2020'), ('2020', '2024'), ('2024', '2026'), ('2008', '2025'), ('1998', '2025')]},
  'sd_monthly': {k: round(float(mchg[k].std()*100), 2) for k in I.columns},
  'corr_monthly': mchg.corr().round(3).values.tolist(),
  'corr_yoy': yoy.corr().round(3).values.tolist(),
  'sd_yoy_gap_vs_apt': {k: round(float((yoy[k] - yoy.fe_apt).std()*100), 2) for k in I.columns},
  'cols': list(I.columns),
}
json.dump(out, open('hedonic_v3.json', 'w'), ensure_ascii=False)
for k, v in out.items():
    if k != 'idx': print(k, json.dumps(v, ensure_ascii=False)[:700])
