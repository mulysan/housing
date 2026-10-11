import duckdb, numpy as np, pandas as pd
c = duckdb.connect('/home/user/work/h.db', read_only=True)
A = c.sql("select gush, parcel, dt, ppm, area, rooms, cast(yb as double) yb, cast(y as double) y from a where y between 1998 and 2025 and rooms between 1 and 12 and area between 20 and 400").df()
cx = pd.read_excel('/home/user/work/cpi.xlsx'); cx['date'] = cx['date'].astype(str).str[:7]; cs = cx.set_index('date').cpi
ym = pd.to_datetime(A.dt).dt.to_period('M').astype(str); A['lp'] = np.log(A.ppm / ym.map(cs.reindex(sorted(ym.unique())).ffill()))
A = A[A.lp.notna()]; A['age'] = (A.y - A.yb).where(A.yb.between(1870, 2026))
A['grp'] = np.select([A.age.between(0, 2), A.age >= 3], ['new', 'resale'], 'na')
A['bld'] = A.gush.astype(np.int64) * 100000 + A.parcel; A['rc'] = np.ceil(A.rooms).clip(1, 7).astype(int)
codes = lambda s: pd.factorize(s)[0]
def fe_solve(y, gs, iters=600, tol=1e-7):
    fes = [np.zeros(g.max() + 1) for g in gs]; cnt = [np.bincount(g) for g in gs]; r = y.copy()
    for _ in range(iters):
        dm = 0
        for k, g in enumerate(gs):
            r += fes[k][g]; new = np.bincount(g, r, minlength=len(cnt[k])) / np.maximum(cnt[k], 1); dm = max(dm, np.abs(new - fes[k]).max()); fes[k] = new; r -= new[g]
        if dm < tol: break
    return fes
def grad(d):
    d = d[d.groupby('bld').bld.transform('size') >= 2]
    by = codes(d.bld.astype(str) + '#' + d.y.astype(str)); f = fe_solve(d.lp.values, [d.rc.values, by])[0]
    return {r: round(float(np.exp(f[r] - f[4]) - 1) * 100, 1) for r in (2, 3, 5, 6) if (d.rc == r).sum() > 200}, len(d)
for grp in ('new', 'resale'):
    for a, b in ((1998, 2007), (2008, 2015), (2016, 2025)):
        d = A[(A.grp == grp) & A.y.between(a, b)]
        g, n = grad(d)
        dm = d.copy(); med = dm.groupby(['bld', 'y']).lp.transform('median'); dt_ = dm[dm.lp > med - np.log(1.25)]   # drop sales >20% below building-year median
        g2, n2 = grad(dt_)
        print(grp, a, b, 'all', g, n, '| trimmed', g2, n2, flush=True)
