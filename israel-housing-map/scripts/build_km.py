# Katz-Murphy (1992) for housing: do changes in (effective) housing supply explain changes in the
# constant-quality price of housing across markets, and does an efficiency-unit ("effective") measure
# of supply explain more than a simple count of dwellings?
#
# ----------------------------------------------------------------------------------------------------
# MODEL
# Households consume housing services from J markets (cities; or groups of neighbourhoods). Services
# from different markets are imperfect substitutes, aggregated by CES:
#     H_t = [ sum_j (A_jt S_jt)^rho ]^(1/rho),    sigma = 1/(1 - rho)  (elasticity of substitution)
# S_jt = housing services supplied in market j (the stock, in efficiency units), A_jt = demand shifter
# (amenities, jobs, preferences for market j). With competitive pricing the price of a unit of services
# in market j is the marginal value of H times dH/dS_jt:
#     P_jt = lambda_t H_t^(1-rho) A_jt^rho S_jt^(rho-1)
#  => ln P_jt = theta_t + rho ln A_jt - (1/sigma) ln S_jt,      theta_t = ln(lambda_t H_t^(1-rho))
# theta_t is common to all markets (national income, interest rates, population, credit) and is
# absorbed by year fixed effects. Following Katz and Murphy, the relative demand term is a market
# effect plus a market-specific linear trend, rho ln A_jt = delta_j + gamma_j t + u_jt:
#     ln P_jt = theta_t + delta_j + gamma_j t - (1/sigma) ln S_j,t-1 + u_jt                    (KM)
# With two markets this is the classic KM relative-price regression
#     ln(P_1t/P_2t) = a + g t - (1/sigma) ln(S_1,t-1/S_2,t-1) + e_t.
# Supply enters with a one-year lag: the stock at the end of year t-1 is in place before year-t prices
# are set, which removes the mechanical within-year response of completions to prices (supply is still
# endogenous to expected prices through earlier construction decisions; see "caveats").
#
# EFFECTIVE SUPPLY. Katz and Murphy measure each group's supply in efficiency units: hours weighted by
# fixed relative wages. The housing analogue (wiki: lit-reviews/effective-housing-supply.md) weights each
# dwelling by its fixed relative value:
#     N_jt = sum_{i in j, built <= t} 1                        (simple: number of dwellings)
#     F_jt = sum_{i in j, built <= t} m2_i                     (floor space)
#     E_jt = sum_{i in j, built <= t} v_i / v_bar             (efficiency units, value-weighted)
# m2_i = median floor area of deals in the dwelling's parcel (else gush, else city; build_prices.py),
# v_i = m2_i x median real price per m2 of the dwelling's gush in 2023-26 (else city), v_bar = national
# mean. Weights are fixed over time, as in KM, so E moves only when the composition of the stock changes
# (bigger dwellings, dwellings in more valuable locations). Under the CES model the right price for E is
# the price per efficiency unit, which is what a constant-quality price index measures.
#
# PRICES ("selling-year coefficients"). For each market j and sale year t, theta_jt from
#     ln(price per m2 / CPI)_i = theta_{j(i),t(i)} + alpha_b(i) + kappa_a(i) + e_i
# b = building (gush-parcel), a = rounded m2. Building FE hold location and structure fixed, so theta_jt
# is the change in the price of constant-quality housing (normalised to 0 in 2015 in each market; the
# level is absorbed by delta_j). Deals: Tax Authority apartment sales (+ govmap where the Tax Authority
# has none), whole units, 1998-2026 (build_prices.py table a). Markets = cities with >= 12,000 registered
# dwellings (the page's city list); robustness: neighbourhood SES tiers and the two-market version
# (core = Tel Aviv and Center districts, vs the rest).
#
# ----------------------------------------------------------------------------------------------------
# DATA DECISIONS (supply)
# 1. Stock by year = dwellings in the national assets gazetteer (registered condominium units, ~2.68M)
#    by building year. The gazetteer is a 2024-25 snapshot, so the historical stock is the stock of
#    *surviving* dwellings: units demolished before the snapshot (urban renewal, ~1-2% of the stock) are
#    missing from earlier years. Units outside registered condominiums (most single-family homes,
#    unregistered Arab-locality housing) are not in the gazetteer at all.
# 2. Registration lag: units are registered as condominium units a few years after completion. The
#    count by building year falls from ~31K (2019) to 19K (2021), 12K (2022), 7K (2023), 5K (2024): the
#    recent stock is incomplete. The panel therefore uses supply up to 2019 (prices up to 2020).
# 3. Missing building year (26% of units): allocated to years in proportion to the city's known-year
#    distribution. This multiplies a city's stock by a constant, which the city effect delta_j absorbs
#    in logs; it biases growth only if missing years are concentrated in particular vintages.
# 4. Heaping: building years pile up on multiples of 5 (1990: 56K units vs ~16K in 1989/1991; 2000:
#    53K vs 31K/17K). Within each city, the excess at a multiple-of-5 year (count minus the median of
#    the two years on each side) is spread uniformly over the 5 years centred on it.
# 5. Location: dwellings are assigned to cities by the gazetteer's settlement name and to SAs by the
#    parcel location (build_prices.py: polygon centroid, or govmap deal coordinates, etc.).
#
# INSTRUMENT (shift-share / "predicted stock"). OLS estimates of -1/sigma come out near zero or positive:
# construction goes where demand grows, so supply growth and price growth move together. The
# instrument is the stock a market would have if it had kept its share of national construction from a
# pre-period before the price sample (1985-1997):
#     S^hat_jt = S_j,1997 + s_j (S_nat,t - S_nat,1997),    s_j = (S_j,1997 - S_j,1984) / (S_nat,1997 - S_nat,1984)
# and ln S^hat_j,t-1 instruments ln S_j,t-1 (2SLS, same fixed effects). National construction (S_nat)
# is driven by national demand, which the year effects absorb; identification comes from markets
# with a historically large share of construction (land reserves, planning capacity) receiving more of
# each national wave. Exclusion requires that the pre-period construction share is unrelated to later
# relative demand shocks, given market effects (and trends). The 1990s immigration wave makes this
# questionable for peripheral cities that built heavily in 1990-97; results are reported as suggestive.
#
# CAVEATS. Supply is predetermined, not exogenous: builders build where they expect prices to rise,
# which biases -1/sigma towards zero (towards a positive coefficient). Market trends absorb smooth
# demand growth; identification comes from deviations of supply growth from trend. No instrument is
# used; a natural next step is land-availability or planning-approval shocks.
#
# Inputs: h.db (tables a, g, p, cen), parcels_v3.parquet, gush_region.csv, sa2011.csv, cpi.xlsx
# Output: km_v3.json
import json, numpy as np, pandas as pd, duckdb, shapely
c = duckdb.connect('h.db', read_only=True)
codes = lambda s: pd.factorize(s)[0]
Y0, Y1 = 1998, 2020                          # price years; supply years Y0-1 .. Y1-1

# ---------------- markets ----------------
P = pd.read_parquet('parcels_v3.parquet')[['gush', 'parcel', 'units', 'city', 'lat', 'lon', 'unit_m2', 'unit_val']]
GR = pd.read_csv('gush_region.csv').set_index('gush')
P['region'] = P.gush.map(GR.region)
sa = pd.read_csv('sa2011.csv'); sa = sa[sa.sa > 0].drop_duplicates('sa').reset_index(drop=True)
tree = shapely.STRtree(shapely.make_valid(shapely.from_wkt(sa.wkt.values)))
ok = P.lat.notna()
i, j = tree.query(shapely.points(P.lon[ok].values, P.lat[ok].values), predicate='within')
P['ses'] = np.nan; P.loc[P.index[ok][i], 'ses'] = sa.ses21.values[j]
cu = P.groupby('city').units.sum()
CITIES = sorted(cu[cu >= 12000].index)
P['core'] = np.where(P.region.isin(['תל-אביב', 'המרכז']), 'core', np.where(P.region.notna(), 'rest', None))
P['tier'] = P.ses.map(lambda v: f'SES {int(v)}' if v == v else None)   # CBS socio-economic cluster 2021 of the SA (1-10)
P['ses_m'] = P.tier
v_bar = np.average(P.unit_val.dropna(), weights=P.units[P.unit_val.notna()])

# ---------------- supply: units by city x building year, corrected ----------------
G = c.sql("select gush, parcel, yr from g").df()
G = G.merge(P[['gush', 'parcel', 'city', 'core', 'tier', 'unit_m2', 'unit_val']], on=['gush', 'parcel'], how='left')
G['yr'] = G.yr.where(G.yr.between(1870, 2026))
G['w_m2'] = G.unit_m2; G['w_val'] = G.unit_val / v_bar
def stock(G, key, yrs=range(1870, Y1)):
    """end-of-year stock by market for t in yrs, in units, m2 and efficiency units, with corrections 3-4"""
    out = {}
    for mk, d in G[G[key].notna()].groupby(key):
        res = {}
        for w in ['n', 'm2', 'val']:
            wt = np.ones(len(d)) if w == 'n' else d['w_' + w].fillna(d['w_' + w].median()).values
            known = d.yr.notna().values
            h = pd.Series(wt[known]).groupby(d.yr.values[known].astype(int)).sum().reindex(range(1870, 2027), fill_value=0.0)
            # heaping (decision 4): excess at multiples of 5 spread over the 5 years centred on them
            for Y in range(1900, 2025, 5):
                nb = [h.get(Y-2, 0), h.get(Y-1, 0), h.get(Y+1, 0), h.get(Y+2, 0)]
                ex = max(0.0, h[Y] - np.median(nb))
                h[Y] -= ex
                for k in range(Y-2, Y+3): h[k] += ex/5
            # missing year (decision 3): scale up by the missing share
            h *= 1 + wt[~known].sum() / max(wt[known].sum(), 1e-9)
            res[w] = h.cumsum().reindex(list(yrs))
        out[mk] = pd.DataFrame(res)
    return out
S_city = stock(G[G.city.isin(CITIES)], 'city'); S_core = stock(G, 'core'); S_tier = stock(G, 'tier')
S_nat = stock(G.assign(all='IL'), 'all')['IL']
def predicted(S):
    """shift-share predicted stock per market and weight (see INSTRUMENT)"""
    P_ = {}
    for m, d in S.items():
        P_[m] = pd.DataFrame({w: d[w][1997] + (d[w][1997] - d[w][1984]) / (S_nat[w][1997] - S_nat[w][1984]) * (S_nat[w] - S_nat[w][1997])
                              for w in ['n', 'm2', 'val']})
    return P_
Z_city, Z_tier = predicted(S_city), predicted(S_tier)

# ---------------- prices: market x sale-year coefficients (building FE) ----------------
cx = pd.read_excel('cpi.xlsx'); cx['date'] = cx['date'].astype(str).str[:7]; cs = cx.set_index('date').cpi
A = c.sql(f"select gush, parcel, dt, ppm, area, y from a where y between {Y0} and {Y1}").df()
A = A.merge(P[['gush', 'parcel', 'city', 'core', 'tier']], on=['gush', 'parcel'], how='inner').rename(columns={'tier': 'ses'})
A['ym'] = pd.to_datetime(A.dt).dt.to_period('M').astype(str)
A['lp'] = np.log(A.ppm / A.ym.map(cs.reindex(sorted(A.ym.unique())).ffill()))
A['bld'] = A.gush.astype(np.int64)*100000 + A.parcel
def fe_solve(y, gs, iters=2000, tol=1e-9):
    fes = [np.zeros(g.max()+1) for g in gs]; cnt = [np.bincount(g) for g in gs]; r = y.copy()
    for _ in range(iters):
        dmax = 0
        for k, g in enumerate(gs):
            r += fes[k][g]; new = np.bincount(g, r, minlength=len(cnt[k]))/np.maximum(cnt[k], 1)
            dmax = max(dmax, np.abs(new - fes[k]).max()); fes[k] = new; r -= new[g]
        if dmax < tol: break
    return fes
def price_index(A, key, min_n=30):
    """theta_{market, year}: market x year FE with building and rounded-area FE; 2015 = 0 per market.
    Cells with fewer than min_n deals are dropped (noisy)."""
    d = A[A[key].notna()]
    d = d[d.groupby('bld').bld.transform('size') >= 2]               # single-sale buildings identify nothing
    cell = d[key].astype(str) + '|' + d.y.astype(str)
    ci, labs = pd.factorize(cell)
    f = fe_solve(d.lp.values.astype(float), [ci, codes(d.bld), codes(d.area.round())])[0]
    T = pd.DataFrame({'mk': [l.split('|')[0] for l in labs], 'y': [int(l.split('|')[1]) for l in labs], 'theta': f,
                      'n': np.bincount(ci)})
    T = T[T.n >= min_n]
    base = T[T.y == 2015].set_index('mk').theta
    T['theta'] = T.theta - T.mk.map(base)
    return T.dropna(subset=['theta'])

# ---------------- regressions ----------------
def panel(T, S, label, Z=None):
    D = T.copy()
    for w in ['n', 'm2', 'val']:
        D['lS_' + w] = [np.log(S[m][w].get(y - 1, np.nan)) if m in S else np.nan for m, y in zip(D.mk, D.y)]
        if Z is not None:
            D['lZ_' + w] = [np.log(max(Z[m][w].get(y - 1, np.nan), 1)) if m in Z else np.nan for m, y in zip(D.mk, D.y)]
    D = D.dropna().reset_index(drop=True)
    D['t'] = D.y - 2009
    out = {'label': label, 'n_obs': int(len(D)), 'n_mk': int(D.mk.nunique()), 'years': [int(D.y.min()), int(D.y.max())], 'models': {}}
    def fit(xs, trend, iv=None):
        # FWL: absorb year FE and market FE (and market trends) by regression on dummies
        Xfe = [pd.get_dummies(D.y, prefix='y', dtype=float), pd.get_dummies(D.mk, prefix='m', dtype=float)]
        if trend: Xfe.append(pd.get_dummies(D.mk, prefix='tr', dtype=float).mul(D.t, axis=0))
        Wfe = pd.concat(Xfe, axis=1).values
        proj = lambda v: v - Wfe @ np.linalg.lstsq(Wfe, v, rcond=None)[0]
        y = proj(D.theta.values); X = np.column_stack([proj(D[x].values) for x in xs])
        F = None
        if iv is not None:                                             # 2SLS with one instrument per regressor
            Zm = np.column_stack([proj(D[z].values) for z in iv])
            pi = np.linalg.lstsq(Zm, X, rcond=None)[0]; Xh = Zm @ pi; u = X - Xh
            cl0 = codes(D.mk); ZtZ = np.linalg.pinv(Zm.T @ Zm)        # cluster-robust first-stage F (one instrument)
            Sz = np.vstack([np.bincount(cl0, Zm[:, 0]*u[:, 0])]).T; Vp = ZtZ @ (Sz.T @ Sz) @ ZtZ * (cl0.max()+1)/cl0.max()
            F = round(float(pi[0, 0]**2 / Vp[0, 0]), 1)
            b = np.linalg.lstsq(Xh, y, rcond=None)[0]; e = y - X @ b
            Xs = Xh                                                    # sandwich uses fitted regressors
        else:
            b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b; Xs = X
        XtX = np.linalg.pinv(Xs.T @ Xs); cl = codes(D.mk)
        Sg = np.vstack([np.bincount(cl, Xs[:, k]*e) for k in range(Xs.shape[1])]).T
        G_ = cl.max() + 1; V = XtX @ (Sg.T @ Sg) @ XtX * G_/(G_ - 1)
        r2_within = 1 - (e**2).sum()/(y**2).sum()                      # share of the residual price variation explained
        tot = D.theta.values - D.theta.mean(); r2 = 1 - (e**2).sum()/(tot**2).sum()
        return {'b': [round(float(v), 4) for v in b], 'se': [round(float(v), 4) for v in np.sqrt(np.diag(V))],
                'sigma': [round(float(-1/v), 2) if v < 0 else None for v in b], 'r2_within': round(float(r2_within), 4),
                'r2': round(float(r2), 4), 'first_stage_F': F,
                'resid': [np.round(y, 4).tolist(), np.round(X[:, 0], 4).tolist()] if len(xs) == 1 and iv is None else None}
    for trend in [False, True]:
        for w in ['n', 'm2', 'val']:
            out['models'][f'{w}_{"trend" if trend else "fe"}'] = fit(['lS_' + w], trend)
        out['models'][f'horse_{"trend" if trend else "fe"}'] = fit(['lS_n', 'lS_val'], trend)
        if Z is not None:
            for w in ['n', 'm2', 'val']:
                out['models'][f'{w}_{"trend" if trend else "fe"}_iv'] = fit(['lS_' + w], trend, iv=['lZ_' + w])
    # how similar are the three supply measures? correlation of their year-on-year growth
    D_ = D.sort_values(['mk', 'y']); gr = D_.groupby('mk')[['lS_n', 'lS_m2', 'lS_val']].diff().dropna()
    out['growth_corr'] = {'n_m2': round(float(gr.lS_n.corr(gr.lS_m2)), 3), 'n_val': round(float(gr.lS_n.corr(gr.lS_val)), 3),
                          'sd_growth': {k: round(float(gr[k].std()), 4) for k in gr.columns}}
    # long difference (cross-section): change 2008 -> Y1 in theta vs change in log supply 2007 -> Y1-1
    L = D[D.y.isin([2008, Y1])].pivot(index='mk', columns='y')
    if 2008 in L.theta.columns and Y1 in L.theta.columns and len(L) >= 10:   # cross-section needs enough markets
        ld = {}
        dy = (L.theta[Y1] - L.theta[2008]).dropna()
        for w in ['n', 'm2', 'val']:
            dx = (L['lS_' + w][Y1] - L['lS_' + w][2008]).reindex(dy.index)
            Xc = np.c_[np.ones(len(dx)), dx.values]; b = np.linalg.lstsq(Xc, dy.values, rcond=None)[0]; e = dy.values - Xc @ b
            V = np.linalg.inv(Xc.T @ Xc) @ (Xc.T * e**2) @ Xc @ np.linalg.inv(Xc.T @ Xc)   # HC0
            ld[w] = {'b': round(float(b[1]), 4), 'se': round(float(np.sqrt(V[1, 1])), 4),
                     'r2': round(float(1 - (e**2).sum()/((dy - dy.mean())**2).sum()), 4),
                     'pts': [[m, round(float(a_), 4), round(float(b_), 4)] for m, a_, b_ in zip(dy.index, dx.values, dy.values)]}
        out['long_diff'] = ld
    D = D.sort_values(['mk', 'y'])
    out['series'] = {m: {'y': g.y.tolist(), 'theta': g.theta.round(4).tolist(), 'lS_n': g.lS_n.round(4).tolist(),
                         'lS_val': g.lS_val.round(4).tolist(), 'lS_m2': g.lS_m2.round(4).tolist()} for m, g in D.groupby('mk')}
    return out

def two_group(T, S, a, b_):
    """classic KM: ln(P_a/P_b)_t = c + g t - (1/sigma) ln(S_a/S_b)_{t-1}; Newey-West (2 lags) SEs"""
    W = T.pivot(index='y', columns='mk', values='theta')[[a, b_]].dropna()
    res = {}
    for w in ['n', 'm2', 'val']:
        rel = np.log(S[a][w] / S[b_][w])
        d = pd.DataFrame({'rp': W[a] - W[b_], 'rs': [rel.get(y - 1, np.nan) for y in W.index], 't': W.index - 2009.0}).dropna()
        X = np.c_[np.ones(len(d)), d.t, d.rs]; yv = d.rp.values
        bb = np.linalg.lstsq(X, yv, rcond=None)[0]; e = yv - X @ bb
        XtXi = np.linalg.inv(X.T @ X); Sx = (X.T * e**2) @ X
        for L_ in (1, 2):
            wl = 1 - L_/3; G_ = (X[L_:].T * (e[L_:]*e[:-L_])) @ X[:-L_]; Sx += wl*(G_ + G_.T)
        V = XtXi @ Sx @ XtXi
        X0 = np.c_[np.ones(len(d)), d.t]; e0 = yv - X0 @ np.linalg.lstsq(X0, yv, rcond=None)[0]
        res[w] = {'b': round(float(bb[2]), 4), 'se': round(float(np.sqrt(V[2, 2])), 4), 'g': round(float(bb[1]), 4),
                  'sigma': round(float(-1/bb[2]), 2) if bb[2] < 0 else None,
                  'r2': round(float(1 - (e**2).sum()/((yv - yv.mean())**2).sum()), 4),
                  'r2_trend_only': round(float(1 - (e0**2).sum()/((yv - yv.mean())**2).sum()), 4),
                  'y': d.index.tolist(), 'rp': d.rp.round(4).tolist(), 'rs': d.rs.round(4).tolist(), 'fit': (X @ bb).round(4).tolist()}
    return res

out = {'years': [Y0, Y1]}
T_city = price_index(A[A.city.isin(CITIES)], 'city')
out['city'] = panel(T_city, S_city, 'ערים', Z_city)
T_tier = price_index(A, 'ses', min_n=100)
out['tier'] = panel(T_tier, S_tier, 'אשכולות SES', Z_tier)
T_core = price_index(A, 'core', min_n=100)
out['core'] = two_group(T_core, S_core, 'core', 'rest')
# ---------------- five-year periods (KM's sub-period changes) ----------------
# Katz and Murphy fit the two-group model on annual data, and analyse the 64 detailed groups through
# changes over three sub-periods (1963-71, 1971-79, 1979-87). The analogue here: sale years in 5-year
# periods tau = 1998-2002, 2003-07, 2008-12, 2013-17, 2018-22. Price theta_j,tau = market x period FE
# from the same building-FE regression (normalised to 0 in 2013-17 per market). Supply = log stock at
# the end of the year before the period starts (1997, 2002, 2007, 2012, 2017): predetermined for the
# period's prices, and all before the registration-lag cut-off (decision 2), which lets the price
# sample run to 2022. Two estimators:
#   levels:      theta_j,tau = mu_tau + delta_j [+ gamma_j tau] - (1/sigma) ln S_j,tau + u      (5 periods)
#   differences: D theta_j,tau = D mu_tau [+ gamma_j] - (1/sigma) D ln S_j,tau + D u             (4 changes)
# The difference form is KM's: price changes across sub-periods against supply changes, with common
# period effects; market effects in the difference form are market-specific trends in levels.
PER = [(1998, 2002), (2003, 2007), (2008, 2012), (2013, 2017), (2018, 2022)]
PLAB = [f'{a}-{b % 100:02d}' for a, b in PER]
A5 = c.sql("select gush, parcel, dt, ppm, area, y from a where y between 1998 and 2022").df()
A5 = A5.merge(P[['gush', 'parcel', 'city', 'core', 'tier']], on=['gush', 'parcel'], how='inner').rename(columns={'tier': 'ses'})
A5['ym'] = pd.to_datetime(A5.dt).dt.to_period('M').astype(str)
A5['lp'] = np.log(A5.ppm / A5.ym.map(cs.reindex(sorted(A5.ym.unique())).ffill()))
A5['bld'] = A5.gush.astype(np.int64)*100000 + A5.parcel
A5['y_real'] = A5.y; A5['y'] = A5.y_real.map(lambda v: next(k for k, (a, b) in enumerate(PER) if a <= v <= b))   # period index 0..4
S_city5 = stock(G[G.city.isin(CITIES)], 'city', yrs=range(1870, 2018)); S_tier5 = stock(G, 'tier', yrs=range(1870, 2018))
S_nat5 = stock(G.assign(all='IL'), 'all', yrs=range(1870, 2018))['IL']
def predicted5(S):
    return {m: pd.DataFrame({w: d[w][1997] + (d[w][1997] - d[w][1984]) / (S_nat5[w][1997] - S_nat5[w][1984]) * (S_nat5[w] - S_nat5[w][1997])
                             for w in ['n', 'm2', 'val']}) for m, d in S.items()}
def five(A5, key, S, min_n):
    d = A5[A5[key].notna()]
    d = d[d.groupby('bld').bld.transform('size') >= 2]
    cell = d[key].astype(str) + '|' + d.y.astype(str); ci, labs = pd.factorize(cell)
    f = fe_solve(d.lp.values.astype(float), [ci, codes(d.bld), codes(d.area.round())])[0]
    T = pd.DataFrame({'mk': [l.split('|')[0] for l in labs], 'p': [int(l.split('|')[1]) for l in labs], 'theta': f, 'n': np.bincount(ci)})
    T = T[T.n >= min_n]; base = T[T.p == 3].set_index('mk').theta; T['theta'] = T.theta - T.mk.map(base)
    T = T.dropna(subset=['theta'])
    Z = predicted5(S)
    for w in ['n', 'm2', 'val']:
        T['lS_' + w] = [np.log(S[m][w][PER[p][0] - 1]) if m in S else np.nan for m, p in zip(T.mk, T.p)]
        T['lZ_' + w] = [np.log(max(Z[m][w][PER[p][0] - 1], 1)) if m in Z else np.nan for m, p in zip(T.mk, T.p)]
    T = T.dropna().sort_values(['mk', 'p']).reset_index(drop=True)
    T = T[T.groupby('mk').p.transform('size') == len(PER)].reset_index(drop=True)      # balanced panel
    def fit(D, xs, fe_cols, iv=None):
        W = pd.concat([pd.get_dummies(D[c_], prefix=c_, dtype=float) for c_ in fe_cols if c_ != 'trend'] +
                      ([pd.get_dummies(D.mk, prefix='tr', dtype=float).mul(D.p, axis=0)] if 'trend' in fe_cols else []), axis=1) if fe_cols else None
        proj = (lambda v: v - W.values @ np.linalg.lstsq(W.values, v, rcond=None)[0]) if W is not None else (lambda v: v - v.mean())
        y = proj(D.theta.values); X = np.column_stack([proj(D[x].values) for x in xs]); F = None
        if iv:
            Zm = np.column_stack([proj(D[z].values) for z in iv]); pi = np.linalg.lstsq(Zm, X, rcond=None)[0]; Xh = Zm @ pi
            cl0 = codes(D.mk); u = X - Xh; ZtZ = np.linalg.pinv(Zm.T @ Zm); Sz = np.c_[np.bincount(cl0, Zm[:, 0]*u[:, 0])]
            Vp = ZtZ @ (Sz.T @ Sz) @ ZtZ * (cl0.max()+1)/cl0.max(); F = round(float(pi[0, 0]**2 / Vp[0, 0]), 1)
            b = np.linalg.lstsq(Xh, y, rcond=None)[0]; e = y - X @ b; Xs = Xh
        else:
            b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b; Xs = X
        XtX = np.linalg.pinv(Xs.T @ Xs); cl = codes(D.mk); Sg = np.vstack([np.bincount(cl, Xs[:, k]*e) for k in range(Xs.shape[1])]).T
        G_ = cl.max() + 1; V = XtX @ (Sg.T @ Sg) @ XtX * G_/(G_ - 1)
        return {'b': [round(float(v), 4) for v in b], 'se': [round(float(v), 4) for v in np.sqrt(np.diag(V))],
                'sigma': [round(float(-1/v), 2) if v < 0 else None for v in b], 'r2_within': round(float(1 - (e**2).sum()/(y**2).sum()), 4),
                'first_stage_F': F, 'n': int(len(D))}
    res = {'n_mk': int(T.mk.nunique()), 'periods': PLAB, 'models': {}}
    D1 = T.copy()                                                         # first differences across periods
    for col in ['theta'] + [f'l{a}_{w}' for a in 'SZ' for w in ['n', 'm2', 'val']]:
        D1[col] = D1.groupby('mk')[col].diff()
    D1 = D1.dropna().reset_index(drop=True)
    for w in ['n', 'm2', 'val']:
        res['models'][f'lev_{w}'] = fit(T, ['lS_' + w], ['p', 'mk'])
        res['models'][f'levtr_{w}'] = fit(T, ['lS_' + w], ['p', 'mk', 'trend'])
        res['models'][f'dif_{w}'] = fit(D1, ['lS_' + w], ['p'])
        res['models'][f'diftr_{w}'] = fit(D1, ['lS_' + w], ['p', 'mk'])
        res['models'][f'dif_{w}_iv'] = fit(D1, ['lS_' + w], ['p'], iv=['lZ_' + w])
    res['models']['dif_horse'] = fit(D1, ['lS_n', 'lS_val'], ['p'])
    # the KM picture: per-period cross-market scatter of price change vs supply change (units)
    res['pts'] = [[m, int(p), round(float(a_), 4), round(float(b_), 4)] for m, p, a_, b_ in zip(D1.mk, D1.p, D1.lS_n, D1.theta)]
    res['mean_dS'] = {PLAB[p]: round(float(g.lS_n.mean()), 4) for p, g in D1.groupby('p')}
    res['mean_dP'] = {PLAB[p]: round(float(g.theta.mean()), 4) for p, g in D1.groupby('p')}
    return res
out['p5'] = {'city': five(A5, 'city', S_city5, 30), 'tier': five(A5, 'ses', S_tier5, 100)}
for k, r in out['p5'].items():
    print('5y', k, r['n_mk'])
    for m, v in r['models'].items(): print('   ', m, v['b'], v['se'], 'sigma', v['sigma'], 'R2w', v['r2_within'], 'F', v['first_stage_F'], 'n', v['n'])
# ---------------- cross-section in levels (2015) ----------------
# Within a city over time the three supply measures grow almost identically (growth correlation ~0.995),
# so they cannot differ in explanatory power there. They do differ across cities, in levels: a city of
# large dwellings has more floor space per resident than its unit count suggests. The CES model in
# levels, with a common demand shifter, gives  ln P_j = c - (1/sigma) ln(S_j / Pop_j) + amenity_j.
# P_j = mean real price per m2 of the city's deals in 2014-16 (no building FE: the level is the point);
# Pop_j = CBS population 2015 of the city's statistical areas; S_j = units or floor space in 2015.
# The value-weighted measure is not used here: its weights are built from 2023-26 prices, so across
# cities it is mechanically correlated with the price level.
POP = pd.read_csv('sa_pop2015.csv'); POP = POP[POP.sa > 0].drop_duplicates('sa')
P['sa'] = np.nan; P.loc[P.index[ok][i], 'sa'] = sa.sa.values[j]
city_sa = P.dropna(subset=['sa']).groupby('city').sa.apply(lambda v: set(v.astype(int)))
pop_city = {cty: POP[POP.sa.isin(v)]['pop'].apply(pd.to_numeric, errors='coerce').sum() for cty, v in city_sa.items()}
lv = A[A.y.between(2014, 2016) & A.city.isin(CITIES)].groupby('city').lp.mean()
X_ = pd.DataFrame({'lp': lv, 'pop': pd.Series(pop_city).reindex(lv.index),
                   'n': [S_city[cty]['n'][2015] for cty in lv.index], 'm2': [S_city[cty]['m2'][2015] for cty in lv.index]})
X_ = X_[X_['pop'] > 0]
lev = {}
for w in ['n', 'm2']:
    x = np.log(X_[w] / X_['pop']); Xc = np.c_[np.ones(len(x)), x]; b = np.linalg.lstsq(Xc, X_.lp.values, rcond=None)[0]
    e = X_.lp.values - Xc @ b; V = np.linalg.inv(Xc.T @ Xc) @ (Xc.T * e**2) @ Xc @ np.linalg.inv(Xc.T @ Xc)
    lev[w] = {'b': round(float(b[1]), 4), 'se': round(float(np.sqrt(V[1, 1])), 4), 'r2': round(float(1 - (e**2).sum()/((X_.lp - X_.lp.mean())**2).sum()), 4),
              'pts': [[cty, round(float(a_), 4), round(float(b_), 4)] for cty, a_, b_ in zip(X_.index, x, X_.lp)]}
out['levels_2015'] = lev; out['levels_n'] = int(len(X_))
print('levels 2015', {w: (v['b'], v['se'], v['r2']) for w, v in lev.items()}, 'cities', len(X_))
# supply growth by vintage, for the popup: national units and efficiency units by building year (corrected)
nat = stock(G.assign(all='IL'), 'all', yrs=range(1950, 2027))['IL']
out['national_stock'] = {'y': list(range(1950, 2027)), 'n': nat.n.round(0).tolist(), 'val': nat.val.round(0).tolist(), 'm2': nat.m2.round(0).tolist()}
raw = G[G.yr.between(1980, 2026)].groupby('yr').size()
out['raw_by_year'] = [[int(k), int(v)] for k, v in raw.items()]
json.dump(out, open('km_v3.json', 'w'), ensure_ascii=False)
for k in ['city', 'tier']:
    o = out[k]; print(k, o['n_obs'], o['n_mk'], o['years'])
    for m, r in o['models'].items(): print('  ', m, r['b'], r['se'], 'sigma', r['sigma'], 'R2w', r['r2_within'], 'R2', r['r2'], 'F', r['first_stage_F'])
    print('   growth corr', o['growth_corr'])
    if 'long_diff' in o: print('   long diff', {w: (v['b'], v['se'], v['r2']) for w, v in o['long_diff'].items()})
for w, r in out['core'].items(): print('core/rest', w, r['b'], r['se'], 'sigma', r['sigma'], 'R2', r['r2'], 'trend only', r['r2_trend_only'])
