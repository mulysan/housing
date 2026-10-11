# Residual variance of the building fixed-effect regression (same specification as build_urban.py:
# ln(ppm/CPI) = building + month + rounded area), used to net estimation noise out of the within-unit variance
# of building effects in the variable map: Var(fe_hat_b) ~ sigma2 / n_b. Output: fe_noise.json
import json, numpy as np, pandas as pd, duckdb
c = duckdb.connect('h.db', read_only=True)
cx_ = pd.read_excel('cpi.xlsx'); cx_['date'] = cx_['date'].astype(str).str[:7]; cs = cx_.set_index('date').cpi
D = c.sql("select gush, parcel, dt, ppm, area from a").df()
D['ym'] = pd.to_datetime(D.dt).dt.to_period('M').astype(str)
D['lp'] = np.log(D.ppm / D.ym.map(cs.reindex(sorted(D.ym.unique())).ffill()))
D = D[np.isfinite(D.lp)]
D['bld'] = D.gush.astype(np.int64)*100000 + D.parcel
D = D[D.groupby('bld').bld.transform('size') >= 2]
codes = lambda s: pd.factorize(s)[0]
gs = [codes(D.bld), codes(D.ym), codes(D.area.round())]
fes = [np.zeros(g.max()+1) for g in gs]; cnt = [np.bincount(g) for g in gs]; r = D.lp.values.astype(float).copy()
for it in range(500):
    delta = 0
    for k, g in enumerate(gs):
        r += fes[k][g]; new = np.bincount(g, r, minlength=len(cnt[k]))/np.maximum(cnt[k], 1)
        delta = max(delta, np.abs(new - fes[k]).max()); fes[k] = new; r -= new[g]
    if delta < 1e-8: break
dof = len(D) - sum(g.max() + 1 for g in gs)
s2 = float((r**2).sum() / dof)
json.dump({'sigma2': round(s2, 5), 'n': int(len(D)), 'dof': int(dof)}, open('fe_noise.json', 'w'))
print('sigma2', round(s2, 5), 'sd', round(s2**0.5, 4), 'n', len(D))
