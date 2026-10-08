# Vote shares by statistical area (SA 2011), as a second, more recent and finer measure of Haredi and
# Arab neighbourhoods than the 2008 census (build_floor_groups.py).
#
# 1. Unit of observation: the polling place ("ריכוז קלפיות", usually a school), not the ballot box.
#    Ballot-box numbers are re-assigned between elections (Knesset 25 uses codes like "2.1".."2.6"
#    that do not correspond to the Knesset 26 box numbers), but polling-place codes within a locality
#    are stable: in Tel Aviv, boxes 1, 3, 4, 8, 9, 10, 12, 13 have the same polling place in both.
#    Votes are summed over the boxes of a polling place.
# 2. Location: Knesset 25 results have no coordinates. Polling places are located with govmap's
#    Knesset 26 official list ("קלפיות טופס א' כנסת 26"): median coordinate of its boxes.
#    Validation: 94% of Knesset 25 polling places (88% of valid votes) match a Knesset 26 polling
#    place, and the eligible-voter count agrees within 25% for 82% of matches (median ratio 1.04).
#    A match is kept only when eligible voters are within a factor 1.5 in either direction;
#    larger gaps mean the polling place was re-drawn. Unmatched: double-envelope votes (soldiers,
#    diplomats, prisoners, hospitals), which have no residence, and re-drawn polling places.
# 3. From polling places to SAs: voters are assigned to the polling place near their address, so
#    an SA's voters are those of the nearby polling places, not only of polling places inside it (most
#    residential SAs host none). Each SA gets the inverse-distance-squared average (weights also
#    proportional to valid votes) of the 3 nearest matched polling places in the same locality,
#    measured from the SA's residential centre (units-weighted centroid of its gazetteer parcels;
#    polygon point-on-surface if it has no units). Distances are floored at 100 m so a polling place
#    inside the SA does not get infinite weight. SAs in localities with no matched polling place
#    are left missing.
# 4. Shares (of valid votes, Knesset 25):
#      haredi = (United Torah Judaism + Shas) / valid. Shas also draws traditional, non-Haredi Mizrahi
#               voters, so utj = UTJ / valid is kept as a stricter measure.
#      arab   = (Ra'am + Hadash-Ta'al + Balad) / valid. Druze and many Bedouin vote for other parties,
#               so Druze villages are not "Arab" by this measure (they are in the census measure).
#      turnout = voters / eligible.
#    Groups: Haredi SA if haredi >= 0.5; Arab SA if arab >= 0.5; else other. The 0.5 cut-offs mean
#    a majority of valid votes; the census and vote classifications are compared in the log.
#    Knesset 24 and 23 shares are computed the same way, for a stability check (correlation across
#    elections).
# Inputs: votes_k25.csv, votes_k24.csv, votes_k23.csv, boxes_k26a.csv (fetch_votes.py), sa2011.csv, h.db
# Output: sa_votes.csv (sa, haredi, utj, arab, turnout, valid_near, vgroup, haredi_k24, arab_k24, ...)
import numpy as np, pandas as pd, duckdb, shapely
from scipy.spatial import cKDTree
LAT0 = 31.8; KX = 111320*np.cos(np.radians(LAT0)); KY = 110574
B = pd.read_csv('boxes_k26a.csv').dropna(subset=['lon', 'lat'])
place = B.groupby(['locality', 'cluster']).agg(e26=('eligible', 'sum'), lon=('lon', 'median'), lat=('lat', 'median')).reset_index()

PARTIES = {'k25': (['p_ג', 'p_שס'], ['p_ג'], ['p_עם', 'p_ום', 'p_ד']),
           'k24': (['p_ג', 'p_שס'], ['p_ג'], ['p_עם', 'p_ודעם']),
           'k23': (['p_ג', 'p_שס'], ['p_ג'], ['p_ודעם'])}
def polling_places(k):
    v = pd.read_csv(f'votes_{k}.csv')
    h, u, a = PARTIES[k]
    v['h'] = v[h].sum(axis=1); v['u'] = v[u].sum(axis=1); v['a'] = v[a].sum(axis=1)
    P = v.groupby(['locality', 'cluster']).agg(elig=('eligible', 'sum'), voters=('voters', 'sum'), valid=('valid', 'sum'),
                                               h=('h', 'sum'), u=('u', 'sum'), a=('a', 'sum')).reset_index()
    P = P.merge(place, on=['locality', 'cluster'], how='inner')
    r = P.e26 / P.elig
    print(k, 'polling places matched', len(P), 'kept (eligible within x1.5)', int(r.between(1/1.5, 1.5).sum()))
    return P[r.between(1/1.5, 1.5) & (P.valid > 0)].reset_index(drop=True)

# SA residential centres (units-weighted parcel centroids), else polygon point-on-surface
sa = pd.read_csv('sa2011.csv'); sa = sa[sa.sa > 0].drop_duplicates('sa').reset_index(drop=True)
g = shapely.make_valid(shapely.from_wkt(sa.wkt.values))
tree = shapely.STRtree(g)
c = duckdb.connect('h.db', read_only=True)
U = c.sql("select p.units, cen.lat, cen.lon from p join cen using(gush, parcel)").df()
i, j = tree.query(shapely.points(U.lon.values, U.lat.values), predicate='within')
U = U.iloc[i].assign(si=j)
cw = U.groupby('si').apply(lambda d: pd.Series({'lon': np.average(d.lon, weights=d.units), 'lat': np.average(d.lat, weights=d.units)}))
pos = shapely.point_on_surface(g)
sa['clon'] = cw.lon.reindex(sa.index).fillna(pd.Series(shapely.get_x(pos))).values
sa['clat'] = cw.lat.reindex(sa.index).fillna(pd.Series(shapely.get_y(pos))).values

def to_sa(P, K=3, floor_m=100):
    """IDW (1/d^2 x valid votes) average of the K nearest polling places in the same locality"""
    out = {}
    for loc, d in sa.groupby('yishuv'):
        p = P[P.locality == loc]
        if not len(p): continue
        xy = np.c_[p.lon*KX, p.lat*KY]; k = min(K, len(p))
        dist, idx = cKDTree(xy).query(np.c_[d.clon*KX, d.clat*KY], k=k)
        dist, idx = dist.reshape(len(d), k), idx.reshape(len(d), k)
        w = p.valid.values[idx] / np.maximum(dist, floor_m)**2
        for c_, num in [('h', 'h'), ('u', 'u'), ('a', 'a'), ('voters', 'voters')]:
            out.setdefault(c_, []).append(pd.Series((w*p[num].values[idx]).sum(1)/w.sum(1), index=d.sa.values))
        out.setdefault('valid', []).append(pd.Series((w*p.valid.values[idx]).sum(1)/w.sum(1), index=d.sa.values))
        out.setdefault('elig', []).append(pd.Series((w*p.elig.values[idx]).sum(1)/w.sum(1), index=d.sa.values))
        out.setdefault('dist', []).append(pd.Series(dist[:, 0], index=d.sa.values))
    o = pd.DataFrame({k: pd.concat(v) for k, v in out.items()})
    return pd.DataFrame({'haredi': o.h/o.valid, 'utj': o.u/o.valid, 'arab': o.a/o.valid, 'turnout': o.voters/o.elig,
                         'dist_near_m': o.dist.round()})

R = to_sa(polling_places('k25'))
for k in ['k24', 'k23']:
    Rk = to_sa(polling_places(k))
    R[f'haredi_{k}'] = Rk.haredi; R[f'arab_{k}'] = Rk.arab
R['vgroup'] = np.where(R.arab >= 0.5, 'ערבי', np.where(R.haredi >= 0.5, 'חרדי', 'אחר'))
R.index.name = 'sa'; R = R.reset_index()
R.to_csv('sa_votes.csv', index=False)
print('SAs with vote shares', len(R), 'of', len(sa), R.vgroup.value_counts().to_dict())
print('stability: corr(haredi k25, k24) =', round(R.haredi.corr(R.haredi_k24), 3), ' corr(arab k25, k24) =', round(R.arab.corr(R.arab_k24), 3),
      ' corr(haredi k25, k23) =', round(R.haredi.corr(R.haredi_k23), 3))
print('distance to nearest polling place (m), quantiles', R.dist_near_m.quantile([.5, .9, .99]).tolist())
