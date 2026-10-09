# SA-level table for the report's X/Y explorer: every variable of the variable dictionary that can be
# expressed per statistical area (SA), plus the mean building effect. Output: sa_xy.json
#  - SA variables: from sa_urban.csv as they are.
#  - Building-level variables (floors, building year, distances, units per building, building effect):
#    mean over the SA's buildings (bld_fe.csv; parcels located by polygon/coordinates, loc_q <= 4).
#  - Transaction-level variables (price per m2, area, rooms, age at sale, new-build share, deals):
#    over the SA's apartment sales 2015-2025; price per m2 in 2015 NIS (CPI), median.
#  - Weight: number of buildings with an estimated building effect (nb); SAs without it get the number
#    of buildings with any data. City = locality code (yishuv).
import json, numpy as np, pandas as pd, duckdb
import var_dict
U = pd.read_csv('sa_urban.csv').set_index('si')
B = pd.read_csv('bld_fe.csv'); B = B[(B.loc_q <= 4) & B.si.notna()]; B['si'] = B.si.astype(int)
g = B.groupby('si')
X = pd.DataFrame(index=U.index)
for v in ['junc_dens', 'junc_dens_walk', 'junc_dens_cad', 'street_dens', 'deadend_share', 'fourway_share', 'orient_ent', 'circuity',
          'road_share', 'parcel_med', 'units_dens', 'pop_dens', 'mix', 'comm_share', 'comm_dens', 'parking_dens', 'parking_share',
          'bus_dens', 'school_dens', 'ses21', 'haredi', 'arab', 'turnout', 'fl_mean', 'pre1980']:
    X[v] = U[v]
X['fe'] = U.fe
X['units'] = g.units.mean(); X['yr'] = g.yr.mean()
for d in ['d_cbd', 'd_rail', 'd_coast']: X[d] = g[d].mean()
c = duckdb.connect('h.db', read_only=True)
A = c.sql("select gush, parcel, dt, ppm, area, rooms, cast(yb as double) yb, cast(y as double) y from a where y between 2015 and 2025").df()
A = A.merge(B[['gush', 'parcel', 'si']], on=['gush', 'parcel'], how='inner')
cx = pd.read_excel('cpi.xlsx'); cx['date'] = cx['date'].astype(str).str[:7]; cs = cx.set_index('date').cpi
ym = pd.to_datetime(A.dt).dt.to_period('M').astype(str); cpi = ym.map(cs.reindex(sorted(ym.unique())).ffill())
A['rppm'] = A.ppm / cpi * cs[cs.index.str.startswith('2015')].mean()
A['age'] = (A.y - A.yb).where(A.yb.between(1870, 2026)); A['new'] = (A.age <= 1).astype(float).where(A.age.notna())
A['rooms'] = A.rooms.where(A.rooms.between(1, 12)); A['area'] = A.area.where(A.area.between(20, 400))
ga = A.groupby('si')
X['ppm'] = ga.rppm.median(); X['area'] = ga.area.mean(); X['rooms'] = ga.rooms.mean(); X['age'] = ga.age.mean()
X['new'] = ga.new.mean(); X['deals'] = ga.size()
X = X.replace([np.inf, -np.inf], np.nan)
w = U.nb.fillna(0); w = w.where(w > 0, g.size().reindex(U.index).fillna(0))
keep = w > 0
X, w, city = X[keep], w[keep], U.yishuv[keep]
V = var_dict.V
LOG = {'junc_dens', 'junc_dens_walk', 'junc_dens_cad', 'street_dens', 'parcel_med', 'units_dens', 'pop_dens', 'comm_dens', 'parking_dens',
       'bus_dens', 'school_dens', 'd_cbd', 'd_rail', 'd_coast', 'units', 'ppm', 'deals'}
lab = json.load(open('varmap_info.json')).get('labels', {})
OVR = {'fe': ('אפקט הבניין (ממוצע הבניינים באזור, לוג)', 'נקודות לוג'), 'units': ('דירות לבניין (ממוצע)', 'דירות'),
       'yr': ('שנת בנייה (ממוצע הבניינים)', 'שנה'), 'd_cbd': ('מרחק למרכז תל אביב (ק"מ, ממוצע הבניינים)', 'ק"מ'),
       'd_rail': ('מרחק לתחנת רכבת או רק"ל (ק"מ, ממוצע הבניינים)', 'ק"מ'), 'd_coast': ('מרחק לחוף (ק"מ, ממוצע הבניינים)', 'ק"מ'),
       'ppm': ('מחיר למ"ר ריאלי (₪ של 2015, חציון העסקאות 2015–2025)', '₪ למ"ר'), 'area': ('שטח דירה שנמכרה (מ"ר, ממוצע 2015–2025)', 'מ"ר'),
       'rooms': ('חדרים בדירה שנמכרה (ממוצע 2015–2025)', 'חדרים'), 'age': ('גיל הבניין בעסקה (שנים, ממוצע 2015–2025)', 'שנים'),
       'new': ('שיעור מכירות בבניין חדש (2015–2025)', 'שיעור'), 'deals': ('עסקאות דירה (2015–2025)', 'עסקאות')}
SHARE = {'deadend_share', 'fourway_share', 'road_share', 'comm_share', 'parking_share', 'haredi', 'arab', 'turnout', 'pre1980', 'new'}
sig = lambda x: None if pd.isna(x) else float(f'{x:.4g}')
vars_ = []
for k in X.columns:
    d = V.get(k, {})
    lb, un = OVR.get(k, (lab.get(k) or d.get('d', k), d.get('u', '')))
    vars_.append({'k': k, 'lab': lb, 'u': un, 'share': k in SHARE, 'g': d.get('g', ''), 'lg': k in LOG,
                  'lv': d.get('lv', ''), 'n': int(X[k].notna().sum()), 'x': [sig(v) for v in X[k].values]})
cities = sorted(city.astype(int).unique().tolist()); ci = {c_: i for i, c_ in enumerate(cities)}
out = {'n': int(len(X)), 'w': w.astype(int).tolist(), 'city': [ci[int(c_)] for c_ in city], 'vars': vars_,
       'note': {'fe': 'ממוצע אפקט הבניין באזור (לוג), משוקלל במספר הבניינים'}}
json.dump(out, open('sa_xy.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(X), 'SAs', len(vars_), 'vars', round(len(json.dumps(out))/1e6, 2), 'MB')
print({v['k']: v['n'] for v in vars_})
