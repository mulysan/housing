# Floor premium within building, from govmap deals (nadlan.gov.il feed), which -
# unlike the Tax Authority archive - records the unit's floor.
# log real price per m2 = floor effect + building FE + month FE + rounded-area FE
# (all absorbed by backfitting; floor effects are read off as one more FE).
# Inputs: govmap_deals.csv (fetch_govmap_deals.py), cpi.xlsx, h.db (gazetteer
# parcels for building height). Output: floor_v3.json
import re, json, numpy as np, pandas as pd, duckdb
from floor_data import load
D = load()
codes = lambda s: pd.factorize(s)[0]
def fe_solve(y, gs, iters=1000, tol=1e-8):
    fes = [np.zeros(gg.max()+1) for gg in gs]; cnt = [np.bincount(gg) for gg in gs]; r = y.copy()
    for it in range(iters):
        delta = 0
        for k, gg in enumerate(gs):
            r += fes[k][gg]; new = np.bincount(gg, r, minlength=len(cnt[k]))/np.maximum(cnt[k], 1)
            delta = max(delta, np.abs(new - fes[k]).max()); fes[k] = new; r -= new[gg]
        if delta < tol: break
    return fes
def effect(d, cat, base):
    """FE of `cat` relative to `base`, absorbing building, month and rounded area."""
    ci, labs = pd.factorize(d[cat])
    f = fe_solve(d.lp.values.astype(float), [ci, codes(d.bld), codes(d.ym), codes(d.area.round())])[0]
    s = pd.Series(f, index=labs); s = s - s[base]
    n = d[cat].value_counts()
    return {str(k): [round(float(np.exp(v) - 1), 4), int(n[k])] for k, v in s.sort_index().items()}
out = {'n': int(len(D)), 'buildings': int(D.bld.nunique())}
D['flc'] = D.fl.clip(upper=25)
out['floor'] = effect(D, 'flc', 1)                          # relative to 1st floor
# by building height: position in the building
D['hb'] = pd.cut(D.height, [0, 4, 8, 15, 100], labels=['עד 4', '5–8', '9–15', '16+'])
fl_, h_ = D.fl.values.astype(float), D.height.values.astype(float)
D['pos'] = np.select([fl_ == 0, fl_ == h_, fl_/h_ <= 1/3, fl_/h_ <= 2/3], ['קרקע', 'עליונה', 'שליש תחתון', 'שליש אמצעי'], 'שליש עליון')
out['pos_by_height'] = {str(h): effect(d, 'pos', 'שליש תחתון') for h, d in D.groupby('hb', observed=True) if len(d) > 20000}
# floor gradient by period, floors 0-10
D['per'] = pd.cut(D.dt.dt.year, [1997, 2009, 2019, 2026], labels=['1998–2009', '2010–2019', '2020–2026'])
out['floor_by_period'] = {str(p): effect(d.assign(flc=d.fl.clip(upper=10)), 'flc', 1) for p, d in D.groupby('per', observed=True)}
# top-floor (not penthouse) premium vs the floor below, buildings 5+ floors
t = D[(D.height >= 5) & (D.fl >= D.height - 1) & (D.fl >= 1)].assign(top=lambda d: (d.fl == d.height).map({True: 'top', False: 'below'}))
out['top_vs_below'] = effect(t, 'top', 'below')
json.dump(out, open('floor_v3.json', 'w'), ensure_ascii=False)
for k, v in out.items(): print(k, json.dumps(v, ensure_ascii=False)[:900])
