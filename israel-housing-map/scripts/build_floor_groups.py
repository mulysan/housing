# (1) Floor premium within building, separately for Arab, Haredi and other statistical areas.
# (2) Building height: the price effect of the number of floors in the building, holding the unit's
#     own floor and everything else fixed.
#
# Groups (by the parcel's location):
#   Arab   = 2008 census statistical area whose main religion is not Jewish (Muslim, Christian, Druze);
#            outside 2008 SAs (newer neighbourhoods), the locality's religion (SA 2011 file, 2015 population).
#   Haredi = Jewish 2008 SA where >= 40% of those 15+ last studied in a yeshiva (CBS census 2008,
#            education layer, yeshiva_pcnt). Bnei Brak median 72%, Modi'in Illit 94%, Tel Aviv 1.4%.
#   Other  = everything else.
#
# Model 1 (per group):  ln p_ibt = sum_f gamma_f 1[floor_i = f] + alpha_b + tau_t + kappa_a + e
#   p = real price per m2 (CPI, 2015 shekels), b = building (gush-parcel), t = month, a = rounded m2.
#   gamma_f relative to the 1st floor; floors 25+ pooled. SEs clustered by building.
# Model 2 (pooled and per group):
#   ln p_igt = sum_h beta_h 1[height_b in h] + sum_f gamma_f 1[floor_i = f] + delta ln m2_i
#              + rooms_i + age_b + mu_{g x year} + e
#   h = building-height bins (gazetteer max floors; 3-4 floors is the base), g x year = gush-by-year FE,
#   so beta_h compares taller and shorter buildings in the same gush and year, at the same unit floor.
#   SEs clustered by gush.
# Inputs: govmap_deals.csv, cpi.xlsx, h.db, sa2008.csv, sa2011.csv, sa2011_religion.csv. Output: floor_groups.json
import json, numpy as np, pandas as pd, duckdb, shapely
from shapely import STRtree
from floor_data import load
D = load()
c = duckdb.connect('h.db', read_only=True)
loc = c.sql("select p.gush, p.parcel, p.yr, cen.lat, cen.lon from p join cen using(gush, parcel)").df()
D = D.drop(columns=['lat', 'lon'], errors='ignore').merge(loc, on=['gush', 'parcel'], how='left')   # parcel location (cen), not the deal's
D = D[D.lat.notna()].reset_index(drop=True)
pts = shapely.points(D.lon.values, D.lat.values)

S8 = pd.read_csv('sa2008.csv').dropna(subset=['wkt']).reset_index(drop=True)
t8 = STRtree(shapely.make_valid(shapely.from_wkt(S8.wkt.values)))
i, j = t8.query(pts, predicate='within'); k8 = np.full(len(D), -1); k8[i] = j
S11 = pd.read_csv('sa2011.csv'); S11 = S11[S11.sa > 0].reset_index(drop=True)
t11 = STRtree(shapely.make_valid(shapely.from_wkt(S11.wkt.values)))
i, j = t11.query(pts, predicate='within'); k11 = np.full(len(D), -1); k11[i] = j
REL = pd.read_csv('sa2011_religion.csv').drop_duplicates('sa').set_index('sa')
rel8 = np.where(k8 >= 0, S8.religion.values[np.maximum(k8, 0)], None)
yes8 = np.where(k8 >= 0, S8.yeshiva.values[np.maximum(k8, 0)], np.nan)
sa11 = np.where(k11 >= 0, S11.sa.values[np.maximum(k11, 0)], -1)
rely = pd.Series(sa11).map(REL.religion_yishuv).values
arab = np.where(k8 >= 0, pd.notna(rel8) & (rel8 != 'יהודים'),
                pd.Series(rely).isin(['ערבי', 'לא יהודי', 'מעורב-ערבי']).values)   # values checked below
D['grp'] = np.where(arab, 'ערבי', np.where(np.nan_to_num(yes8) >= 40, 'חרדי', 'אחר'))
print('religion_yishuv values', pd.Series(rely).value_counts().to_dict())
print('groups', D.grp.value_counts().to_dict(), 'in 2008 SA', (k8 >= 0).mean().round(3))

codes = lambda s: pd.factorize(s)[0]
def demean(M, gs, iters=40):
    M = M.copy()
    for _ in range(iters):
        for g in gs:
            cnt = np.bincount(g); M -= (np.vstack([np.bincount(g, M[:, k]) for k in range(M.shape[1])]).T / cnt[:, None])[g]
    return M
def fwl(d, X, absorb, cluster):
    """OLS of d.lp on X (DataFrame), absorbing FE in `absorb`; SEs clustered by `cluster`."""
    gs = [codes(d[a]) if isinstance(a, str) else codes(pd.Series(list(zip(*[d[x] for x in a])))) for a in absorb]
    M = demean(np.c_[d.lp.values, X.values.astype(float)], gs)
    y, Z = M[:, 0], M[:, 1:]
    ZtZ = np.linalg.pinv(Z.T @ Z); b = ZtZ @ Z.T @ y; e = y - Z @ b
    cl = codes(d[cluster]); Sg = np.vstack([np.bincount(cl, Z[:, k]*e) for k in range(Z.shape[1])]).T
    G = cl.max() + 1; V = ZtZ @ (Sg.T @ Sg) @ ZtZ * G/(G-1)
    return pd.DataFrame({'b': b, 'se': np.sqrt(np.diag(V))}, index=X.columns)

D['flc'] = D.fl.clip(upper=25).astype(int)
D['ar'] = D.area.round()
out = {'n': int(len(D)), 'groups': {}, 'height': {}}
for gname, d in [('הכול', D)] + list(D.groupby('grp')):
    d = d[d.groupby('bld').bld.transform('size') >= 2]
    X = pd.get_dummies(d.flc, prefix='f', dtype=float).drop(columns='f_1')
    r = fwl(d, X, ['bld', 'ym', 'ar'], 'bld')
    fl = {int(k[2:]): [round(float(np.exp(v.b) - 1), 4), round(float(v.se), 4), int((d.flc == int(k[2:])).sum())] for k, v in r.iterrows()}
    fl[1] = [0.0, 0.0, int((d.flc == 1).sum())]
    # per-floor gradient above the 4th floor: slope of gamma_f on f for f = 5..20 (weighted by deals)
    ff = np.array([f for f in range(5, 21) if f in fl and fl[f][2] >= 200]); gg = np.log1p([fl[f][0] for f in ff])
    slope = float(np.polyfit(ff, gg, 1, w=np.sqrt([fl[f][2] for f in ff]))[0]) if len(ff) > 3 else None
    out['groups'][gname] = {'floor': {str(k): fl[k] for k in sorted(fl)}, 'n': int(len(d)), 'buildings': int(d.bld.nunique()),
                            'slope_5_20': None if slope is None else round(np.exp(slope) - 1, 4)}
    print(gname, len(d), 'slope', out['groups'][gname]['slope_5_20'], {k: fl[k][0] for k in (0, 2, 5, 10, 15, 20) if k in fl})

# ---- (2) building height, holding unit floor fixed
H = D[D.bfl.notna() & (D.bfl > 0)].copy()
H['hb'] = pd.cut(H.bfl.astype(float), [0, 2, 4, 8, 12, 20, 30, 200], labels=['1–2', '3–4', '5–8', '9–12', '13–20', '21–30', '31+']).astype(str)
H['y'] = H.dt.dt.year
H['age'] = (H.y - H.yr).where(H.yr.between(1900, 2027))
H['ageb'] = pd.cut(H.age, [-5, 2, 10, 20, 30, 40, 50, 60, 200], labels=['0-2', '3-10', '11-20', '21-30', '31-40', '41-50', '51-60', '60+']).astype(str)
H['rb'] = np.ceil(H.rooms.clip(1, 7)).fillna(0).astype(int)
H['lar'] = np.log(H.area)
for gname, d in [('הכול', H)] + list(H.groupby('grp')):
    X = pd.concat([pd.get_dummies(d.hb, prefix='h', dtype=float).drop(columns='h_3–4'),
                   pd.get_dummies(d.flc, prefix='f', dtype=float).drop(columns='f_1'),
                   pd.get_dummies(d.ageb, prefix='a', dtype=float).drop(columns='a_21-30'),
                   pd.get_dummies(d.rb, prefix='r', dtype=float).drop(columns='r_3', errors='ignore'), d[['lar']]], axis=1)
    X = X.loc[:, X.std() > 0]
    r = fwl(d, X, [('gush', 'y'), 'ym'], 'gush')
    hh = {k[2:]: [round(float(np.exp(v.b) - 1), 4), round(float(v.se), 4), int((d.hb == k[2:]).sum())] for k, v in r.iterrows() if k.startswith('h_')}
    hh['3–4'] = [0.0, 0.0, int((d.hb == '3–4').sum())]
    # same without the unit-floor dummies: how much of the tower premium is the unit's own floor
    r0 = fwl(d, X[[c for c in X.columns if not c.startswith('f_')]], [('gush', 'y'), 'ym'], 'gush')
    h0 = {k[2:]: round(float(np.exp(v.b) - 1), 4) for k, v in r0.iterrows() if k.startswith('h_')}
    h0['3–4'] = 0.0
    out['height'][gname] = {'with_floor': hh, 'no_floor': h0, 'n': int(len(d)), 'gush': int(d.gush.nunique()),
                            'larea': round(float(r.loc['lar', 'b']), 3)}
    print('height', gname, len(d), {k: hh[k][0] for k in hh}, 'no floor', h0)
json.dump(out, open('floor_groups.json', 'w'), ensure_ascii=False)
