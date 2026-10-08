# Transaction-level analyses, after Shmuel's nadlan.do: real price indices with
# building / apartment fixed effects, deals per month, unit size and rooms by
# vintage and sale year, the within-building size gradient, recorded-area drift,
# city indices, repeat-sale returns and the new-build premium.
# Inputs: h.db (build_prices.py), cpi.xlsx (monthly CPI). Output: txn_v3.json
import duckdb, json, numpy as np, pandas as pd
c = duckdb.connect('h.db', read_only=True)

# ---- CPI: the CBS (הלמ"ס) monthly consumer price index, cpi.xlsx (columns date YYYY-MM, cpi), rebased to 2015=100.
# Months after the last CPI month carry the last value forward.
cx = pd.read_excel('cpi.xlsx'); cx['date'] = cx['date'].astype(str).str[:7]
cs = cx.set_index('date').cpi
cs = cs / cs[cs.index.str.startswith('2015')].mean() * 100
months = pd.period_range('1998-01', '2026-09', freq='M').astype(str)
cpi = cs.reindex(months).ffill().to_dict()

df = c.sql("""select gush, parcel, sub, dt, price, area, rooms, yb, ppm, y, nat, city
              from a where dt <= date '2026-09-17'""").df()
df['yb'] = df.yb.astype(float)                                  # nullable (govmap deals have no year built)
df['ym'] = pd.to_datetime(df.dt).dt.to_period('M').astype(str)
df['cpi'] = df.ym.map(cpi)
df['lp'] = np.log(df.ppm * 100 / df.cpi)                       # real log price per m2, 2015 shekels
df['bld'] = df.gush.astype(np.int64)*100000 + df.parcel
df['apt'] = df.bld*10000 + df['sub']
df['ar'] = df.area.round()
codes = lambda s: pd.factorize(s)[0]

def fe_solve(y, gs, iters=2000, tol=1e-9):
    """Backfitting for y = sum_k fe_k[g_k] + e. Returns list of FE arrays."""
    fes = [np.zeros(g.max()+1) for g in gs]; cnt = [np.bincount(g) for g in gs]
    r = y.copy()
    for it in range(iters):
        delta = 0
        for k, g in enumerate(gs):
            r += fes[k][g]
            new = np.bincount(g, r, minlength=len(cnt[k])) / np.maximum(cnt[k], 1)
            delta = max(delta, np.abs(new - fes[k]).max()); fes[k] = new; r -= new[g]
        if delta < tol: break
    return fes, it

def time_index(d, extra, tcol='ym'):
    d = d.dropna(subset=['lp'])
    t = codes(d[tcol]); labs = pd.factorize(d[tcol])[1]
    fes, it = fe_solve(d.lp.values.astype(float), [t] + [codes(d[e]) for e in extra])
    s = pd.Series(fes[0], index=labs).sort_index()
    ref = s[s.index.str.startswith('2015')].mean() if tcol == 'ym' else s.get('2015', s.mean())
    return (100*np.exp(s - ref)).round(1), it

out = {'cpi_note': 'CBS monthly CPI (cpi.xlsx) to ' + cs.index.max(), 'n': len(df)}
# 1. deals per month: all deal types (deduped) and the apartment sample
allm = c.sql("""select strftime(dt,'%Y-%m') ym, count(*) n from (select distinct gush,parcel,sub,dt,price,nat from d)
                where dt between date '1998-01-01' and date '2026-08-31' group by 1 order by 1""").fetchall()
aptm = df[df.dt <= pd.Timestamp('2026-08-31')].groupby('ym').size()
out['deals_month'] = [[m, int(n), int(aptm.get(m, 0))] for m, n in allm]

# 2. monthly real indices: raw median, building + area FE, apartment + area FE
raw = df.groupby('ym').ppm.median() * 100 / pd.Series(cpi).reindex(df.groupby('ym').ppm.median().index)
raw = (100*raw/raw[raw.index.str.startswith('2015')].mean()).round(1)
b_idx, it_b = time_index(df, ['bld', 'ar'])
rs = df[df['sub'] > 0]; rs = rs[rs.groupby('apt').apt.transform('size') >= 2]
a_idx, it_a = time_index(rs, ['apt', 'ar'])
out['idx_month'] = [[m, float(raw.get(m, np.nan)), float(b_idx.get(m, np.nan)), float(a_idx.get(m, np.nan))] for m in b_idx.index]
out['idx_meta'] = {'bld_n': int(len(df)), 'apt_n': int(len(rs)), 'apt_units': int(rs.apt.nunique()), 'iters': [it_b, it_a]}
print('indices done', it_b, it_a, len(rs))

# 3. size, rooms and m2 per room by year built and by year sold
v = df[(df.yb >= 1930) & (df.yb <= 2025)]
rooms_ok = df.rooms.between(1, 7)
byb = v.groupby('yb').agg(area=('area', 'mean'), n=('area', 'size'))
byb['rooms'] = v[rooms_ok.loc[v.index]].groupby('yb').rooms.apply(lambda s: np.ceil(s).mean())
byb['m2room'] = v[rooms_ok.loc[v.index]].assign(q=lambda x: x.area/x.rooms).query('q>=5 and q<=50').groupby('yb').q.mean()
out['by_built'] = [[int(k), round(r.area, 1), round(r.rooms, 2), round(r.m2room, 1), int(r.n)] for k, r in byb.iterrows()]
bys = df.groupby('y').agg(area=('area', 'mean'), n=('area', 'size'))
bys['rooms'] = df[rooms_ok].groupby('y').rooms.apply(lambda s: np.ceil(s).mean())
bys['m2room'] = df[rooms_ok].assign(q=lambda x: x.area/x.rooms).query('q>=5 and q<=50').groupby('y').q.mean()
out['by_sold'] = [[int(k), round(r.area, 1), round(r.rooms, 2), round(r.m2room, 1), int(r.n)] for k, r in bys.iterrows()]

# 4. within-building size gradient: log ppm on area bins and on rooms, building + year FE
bins = [0, 50, 60, 70, 80, 90, 100, 110, 120, 135, 150, 175, 200, 400]
df['abin'] = pd.cut(df.area, bins, labels=False)
fes, _ = fe_solve(df.lp.values, [df.abin.values.astype(int), codes(df.bld), codes(df.y)])
g = fes[0] - fes[0][3]                                     # relative to 70-80 m2
out['size_grad'] = [[f'{bins[i]}–{bins[i+1]}', round(float(np.exp(g[i])-1), 4), int((df.abin == i).sum())] for i in range(len(bins)-1)]
rr = df[rooms_ok].copy(); rr['rc'] = np.ceil(rr.rooms).astype(int)
fes, _ = fe_solve(rr.lp.values, [rr.rc.values, codes(rr.bld), codes(rr.y)])
g = fes[0] - fes[0][3]
out['rooms_grad'] = [[int(k), round(float(np.exp(g[k])-1), 4), int((rr.rc == k).sum())] for k in range(1, 8)]

# 5. recorded-area drift within apartment (apartment FE, yearly time FE)
d5 = rs[rs.y <= 2025]
fes, _ = fe_solve(np.log(d5.area.values), [codes(d5.y), codes(d5.apt)])
labs = pd.factorize(d5.y)[1]; s = pd.Series(fes[0], index=labs).sort_index(); s = s - s.get(2015)
out['area_drift'] = [[int(k), round(float(np.exp(x)-1), 4)] for k, x in s.items()]

# 6. city indices: apartment + area FE, annual, real, 2015=100
top = df.groupby('city').size().sort_values(ascending=False).head(20).index
ci = {}
for cty in top:
    d6 = rs[rs.city == cty]
    if len(d6) < 5000: continue
    ix, _ = time_index(d6.assign(yy=d6.y.astype(str)), ['apt', 'ar'], tcol='yy')
    ci[cty] = {k: float(v) for k, v in ix.items()}
out['city_idx'] = ci

# 7. repeat-sale returns: consecutive sales of the same apartment, area within 5%
p7 = rs.sort_values(['apt', 'dt'])[['apt', 'dt', 'price', 'cpi', 'area']].copy()
nx = p7.groupby('apt').shift(-1)
m = nx.dt.notna() & ((nx.area/p7.area - 1).abs() <= 0.05)
pr = pd.DataFrame({'yrs': (pd.to_datetime(nx.dt[m]) - pd.to_datetime(p7.dt[m])).dt.days/365.25,
                   'real': np.log((nx.price[m]/nx.cpi[m]) / (p7.price[m]/p7.cpi[m])),
                   'start': pd.to_datetime(p7.dt[m]).dt.year})
pr = pr[pr.yrs >= 0.5]
pr['ann'] = np.exp(pr.real/pr.yrs) - 1
hb = pd.cut(pr.yrs, [0.5, 2, 4, 7, 10, 15, 30], labels=['½–2', '2–4', '4–7', '7–10', '10–15', '15+'])
out['repeat_hold'] = [[str(k), round(float(g.ann.median()), 4), round(float((g.real < 0).mean()), 3), int(len(g))]
                      for k, g in pr.groupby(hb, observed=True)]
out['repeat_start'] = [[int(k), round(float(g.ann.median()), 4), round(float((g.real < 0).mean()), 3), int(len(g))]
                       for k, g in pr.groupby('start') if len(g) >= 500]
out['repeat_all'] = [int(len(pr)), round(float(pr.ann.median()), 4), round(float((pr.real < 0).mean()), 3), round(float(pr.yrs.median()), 1)]

# 8. new-build premium within building: first-hand sale (built in sale year or the year before)
df['new'] = ((df.y - df.yb).between(-1, 1)).astype(float)
X = df.new.values; Y = df.lp.values
gs = [codes(df.bld), codes(df.y), codes(df.ar)]
_, _ = None, None
def resid(v):
    fes, _ = fe_solve(v.astype(float).copy(), gs, iters=300, tol=1e-7)
    return v - sum(f[g] for f, g in zip(fes, gs))
xr, yr_ = resid(X), resid(Y)
b = float((xr*yr_).sum()/(xr*xr).sum())
out['new_premium'] = [round(float(np.exp(b)-1), 4), int(df.new.sum())]

json.dump(out, open('txn_v3.json', 'w'), ensure_ascii=False, default=float)
for k, v in out.items():
    print(k, json.dumps(v, ensure_ascii=False, default=float)[:700])
