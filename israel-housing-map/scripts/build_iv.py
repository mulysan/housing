# Apartment size, rooms and the division bias in log price per m2.
#
# Recorded area is noisy (and its definition shifted after 2012). With
# y = log price, regressing log(price/area) on log(area) puts the same error on
# both sides (division bias); dropping log area from a per-m2 regression imposes
# an elasticity of 1. Here the number of rooms (dummies for rooms rounded up, 1..8+)
# instruments log area. All models absorb statistical-area and month FE and
# control for floor, building age and apartment type. SEs clustered by SA.
# Input: hed_sample.parquet (build_hedonic.py), hedonic_v3.json. Output: iv_v3.json
import json, numpy as np, pandas as pd
H = pd.read_parquet('hed_sample.parquet')
H = H[H.rooms.between(1, 12)].reset_index(drop=True)
H['R'] = np.ceil(H.rooms).clip(1, 8).astype(int)
codes = lambda s: pd.factorize(s)[0]
cat = lambda col, base: pd.get_dummies(H[col], prefix=col, dtype=float).drop(columns=f'{col}_{base}')
Z = pd.get_dummies(H.R, prefix='R', dtype=float).drop(columns='R_3')            # instruments (base: 3 rooms)
W = pd.concat([cat('flb', '1'), cat('ageb', '21-30'), cat('typ', 'regular')], axis=1)
y1 = H.lpr.values; x = H.larea.values; y2 = y1 - x
gi = [codes(H.ym), codes(H.sa)]; cl = codes(H.sa)

def demean(M, gs, iters=300, tol=1e-9):
    M = M.copy(); cnt = [np.bincount(g) for g in gs]
    for _ in range(iters):
        mx = 0
        for g, n in zip(gs, cnt):
            mean = np.vstack([np.bincount(g, M[:, k])/n for k in range(M.shape[1])]).T
            M -= mean[g]; mx = max(mx, np.abs(mean).max())
        if mx < tol: break
    return M
def fe_solve(v, gs, iters=2000, tol=1e-10):
    fes = [np.zeros(g.max()+1) for g in gs]; cnt = [np.bincount(g) for g in gs]; r = v.copy()
    for _ in range(iters):
        d = 0
        for k, g in enumerate(gs):
            r += fes[k][g]; new = np.bincount(g, r, minlength=len(cnt[k]))/np.maximum(cnt[k], 1)
            d = max(d, np.abs(new - fes[k]).max()); fes[k] = new; r -= new[g]
        if d < tol: break
    return fes

def fit(Yd, Xd, names, Xhat=None, cluster=cl, n_abs=None):
    """OLS (Xhat None) or 2SLS (Xhat = first-stage fitted regressors) on demeaned data, cluster-robust SE."""
    A = Xd if Xhat is None else Xhat
    AtA = np.linalg.pinv(A.T @ A); b = AtA @ A.T @ Yd
    u = Yd - Xd @ b
    S = np.vstack([np.bincount(cluster, A[:, j]*u) for j in range(A.shape[1])]).T
    G = cluster.max() + 1; V = AtA @ (S.T @ S) @ AtA * G/(G-1)
    se = np.sqrt(np.diag(V)); r2w = 1 - (u**2).sum()/((Yd - Yd.mean())**2).sum()
    return {'b': {k: round(float(v), 4) for k, v in zip(names, b)}, 'se': {k: round(float(v), 4) for k, v in zip(names, se)},
            'r2_within': round(float(r2w), 3), 'n': int(len(Yd))}, b

def run(mask):
    m = np.asarray(mask)
    zz, ww = Z.values[m], W.values[m]
    gs = [codes(H.ym[m]), codes(H.sa[m])]; c_ = codes(H.sa[m])
    M = demean(np.c_[y1[m], y2[m], x[m], zz, ww], gs)
    Y1, Y2, X1 = M[:, 0], M[:, 1], M[:, 2]
    Zd = M[:, 3:3+zz.shape[1]]; Wd = M[:, 3+zz.shape[1]:]
    Wn, Zn = list(W.columns), list(Z.columns)
    out = {}
    out['ols_logp'], b_ols = fit(Y1, np.c_[X1, Wd], ['larea'] + Wn, cluster=c_)
    out['ols_logppm'], _ = fit(Y2, np.c_[X1, Wd], ['larea'] + Wn, cluster=c_)
    out['ols_logppm_noarea'], _ = fit(Y2, Wd, Wn, cluster=c_)
    out['ols_logp_area_rooms'], _ = fit(Y1, np.c_[X1, Zd, Wd], ['larea'] + Zn + Wn, cluster=c_)
    out['ols_logppm_area_rooms'], _ = fit(Y2, np.c_[X1, Zd, Wd], ['larea'] + Zn + Wn, cluster=c_)
    fs, gfs = fit(X1, np.c_[Zd, Wd], Zn + Wn, cluster=c_)
    # first-stage F on the excluded instruments (cluster-robust Wald / q)
    A = np.c_[Zd, Wd]; AtA = np.linalg.pinv(A.T @ A); u = X1 - A @ gfs
    S = np.vstack([np.bincount(c_, A[:, j]*u) for j in range(A.shape[1])]).T
    V = AtA @ (S.T @ S) @ AtA; q = Zd.shape[1]; bz = gfs[:q]
    fs['F_excl'] = round(float(bz @ np.linalg.solve(V[:q, :q], bz) / q), 1)
    out['first_stage'] = fs
    out['reduced_form'], _ = fit(Y1, np.c_[Zd, Wd], Zn + Wn, cluster=c_)
    Xhat = np.c_[A @ gfs, Wd]
    out['iv_logp'], b_iv = fit(Y1, np.c_[X1, Wd], ['larea'] + Wn, Xhat=Xhat, cluster=c_)
    out['iv_logppm'], _ = fit(Y2, np.c_[X1, Wd], ['larea'] + Wn, Xhat=Xhat, cluster=c_)
    return out, M, b_ols, b_iv, Wd, Zd

res = {'n': int(len(H)), 'rooms_dist': H.R.value_counts().sort_index().to_dict()}
full, M, b_ols, b_iv, Wd, Zd = run(np.ones(len(H), bool))
res['models'] = full

# visual IV: means of (FE- and control-residualised) log area / log price / log ppm by room category
Y1, Y2, X1 = M[:, 0], M[:, 1], M[:, 2]
def resid_on(v, A):
    g = np.linalg.lstsq(A, v, rcond=None)[0]; return v - A @ g
rx, r1, r2 = resid_on(X1, Wd), resid_on(Y1, Wd), resid_on(Y2, Wd)
vis = []
for k in range(1, 9):
    s = H.R.values == k
    vis.append([k, int(s.sum()), round(float(rx[s].mean()), 4), round(float(r1[s].mean()), 4), round(float(r2[s].mean()), 4),
                round(float(H.area[s].median()), 1)])
res['visual'] = vis
# within-category binned scatter of log ppm on log area (the raw division-bias picture)
q = pd.qcut(rx, 20, labels=False)
res['bins_ppm'] = [[round(float(rx[q == j].mean()), 4), round(float(r2[q == j].mean()), 4)] for j in range(20)]

# by period: OLS vs IV elasticity
per = pd.cut(H.y, [1997, 2007, 2012, 2019, 2026], labels=['1998–2007', '2008–2012', '2013–2019', '2020–2026'])
res['by_period'] = {}
for p in per.cat.categories:
    o, *_ = run(per == p)
    res['by_period'][p] = {k: [o[k]['b']['larea'], o[k]['se']['larea']] for k in ['ols_logp', 'iv_logp']} | {'F': o['first_stage']['F_excl'], 'n': o['ols_logp']['n']}
    print(p, res['by_period'][p], flush=True)

# indices: (a) log ppm without area (elasticity 1 imposed), (b) log price with OLS area, (c) log price with IV area
ym_i, ym_l = pd.factorize(H.ym); sa_i = codes(H.sa)
Wv = W.values
def idx_from(resid):
    f = fe_solve(resid, [ym_i, sa_i])[0]
    s = pd.Series(f, index=ym_l).sort_index(); return 100*np.exp(s - s[s.index.str.startswith('2015')].mean())
b_noarea = np.array([full['ols_logppm_noarea']['b'][k] for k in W.columns])
I = pd.DataFrame({
    'ppm_noarea': idx_from(y2 - Wv @ b_noarea),
    'logp_ols': idx_from(y1 - x*b_ols[0] - Wv @ b_ols[1:]),
    'logp_iv': idx_from(y1 - x*b_iv[0] - Wv @ b_iv[1:]),
})
hv = json.load(open('hedonic_v3.json'))
apt = pd.Series({r[0]: r[4] for r in hv['idx']})
I['fe_apt'] = apt.reindex(I.index)
res['idx'] = [[m] + [None if not np.isfinite(v) else round(float(v), 2) for v in I.loc[m]] for m in I.index]
yr = np.log(I).groupby(I.index.str[:4]).mean()
res['cum'] = {f'{a}–{b}': {k: round(float(np.exp(yr.loc[b, k] - yr.loc[a, k]) - 1), 3) for k in I.columns}
              for a, b in [('1998', '2008'), ('2008', '2015'), ('2012', '2024'), ('2015', '2025'), ('2008', '2025')]}
json.dump(res, open('iv_v3.json', 'w'), ensure_ascii=False)
for k in ['ols_logp', 'ols_logppm', 'ols_logp_area_rooms', 'iv_logp', 'iv_logppm']:
    print(k, full[k]['b']['larea'], full[k]['se']['larea'], full[k]['r2_within'])
print('F', full['first_stage']['F_excl'], 'FS', {k: v for k, v in full['first_stage']['b'].items() if k.startswith('R_')})
print('visual', vis); print('cum', res['cum'])
