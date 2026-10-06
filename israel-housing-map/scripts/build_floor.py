# Floor premium within building, from govmap deals (nadlan.gov.il feed), which -
# unlike the Tax Authority archive - records the unit's floor.
# log real price per m2 = floor effect + building FE + month FE + rounded-area FE
# (all absorbed by backfitting; floor effects are read off as one more FE).
# Inputs: govmap_deals.csv (fetch_govmap_deals.py), cpi.xlsx, h.db (gazetteer
# parcels for building height). Output: floor_v3.json
import re, json, numpy as np, pandas as pd, duckdb
D = pd.read_csv('govmap_deals.csv', dtype={'floor': str, 'nature': str}, keep_default_na=False)
for c in ['gush', 'parcel', 'sub', 'amount', 'area', 'rooms']: D[c] = pd.to_numeric(D[c], errors='coerce')
D['dt'] = pd.to_datetime(D.date, errors='coerce')
D = D[D.dt.between('1998-01-01', '2026-09-30') & D.nature.isin(['דירה בבית קומות', 'דירה'])]
D = D[(D.area.between(25, 400)) & (D.amount >= 150000) & (D.amount/D.area).between(1500, 150000)]
D = D.drop_duplicates(['gush', 'parcel', 'sub', 'date', 'amount'])

ORD = {'קרקע': 0, 'ראשונה': 1, 'שניה': 2, 'שנייה': 2, 'שלישית': 3, 'רביעית': 4, 'חמישית': 5, 'שישית': 6, 'שביעית': 7,
       'שמינית': 8, 'תשיעית': 9, 'עשירית': 10}
UNITS = {'אחת': 1, 'אחד': 1, 'שתים': 2, 'שתיים': 2, 'שניים': 2, 'שלוש': 3, 'ארבע': 4, 'חמש': 5, 'שש': 6, 'שבע': 7, 'שמונה': 8, 'תשע': 9}
TENS = {'עשרים': 20, 'שלושים': 30, 'ארבעים': 40, 'חמישים': 50}
def parse_floor(s):
    s = re.sub(r'[‎‏]', '', s or '').strip()
    if not s: return np.nan
    m = re.fullmatch(r'קומה\s*(-?\d+)', s) or re.fullmatch(r'(-?\d+)', s)
    if m: return int(m.group(1))
    if s in ORD: return ORD[s]
    m = re.fullmatch(r'(\S+) עשרה', s)                     # 11-19: "אחת עשרה"
    if m and m.group(1) in UNITS: return 10 + UNITS[m.group(1)]
    if s in TENS: return TENS[s]
    m = re.fullmatch(r'(\S+) ו(\S+)', s)                    # 21-59: "עשרים ושלוש"
    if m and m.group(1) in TENS and m.group(2) in UNITS: return TENS[m.group(1)] + UNITS[m.group(2)]
    return np.nan                                          # duplexes, letters, basements, blanks
fl = {v: parse_floor(v) for v in D.floor.unique()}
D['fl'] = D.floor.map(fl)
print('deals', len(D), 'with parsed floor', D.fl.notna().mean().round(3))
D = D[D.fl.between(0, 60)]

cx = pd.read_excel('cpi.xlsx'); cx['date'] = cx['date'].astype(str).str[:7]
cs = cx.set_index('date').cpi
D['ym'] = D.dt.dt.to_period('M').astype(str)
D['lp'] = np.log(D.amount/D.area / D.ym.map(cs.reindex(sorted(D.ym.unique())).ffill()))
D['bld'] = D.gush.astype(np.int64)*100000 + D.parcel
g = duckdb.connect('h.db', read_only=True).sql("select gush, parcel, fl from p").df()
D = D.merge(g.rename(columns={'fl': 'bfl'}), on=['gush', 'parcel'], how='left')
D['obs_max'] = D.groupby('bld').fl.transform('max')
D['height'] = np.fmax(D.bfl.astype(float).fillna(0), D.obs_max.astype(float))          # building floors: gazetteer, or highest floor sold
D = D[D.groupby('bld').bld.transform('size') >= 2]
print('sample', len(D), 'buildings', D.bld.nunique())

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
