# Core tables for the whole project: deals, gazetteer dwellings, parcel locations; plus the first
# descriptive results (price levels and changes, turnover, height hedonic, effective supply, renewal,
# stock value).
#
# DATA DECISIONS
# Deals (table d, then a):
#  - Source: the Tax Authority (רשות המסים, nadlan.taxes.gov.il) deal archive as kept by over.org.il
#    (dataset fd06f5ae-..., 3,844,200 rows, 1998 - Sept 2026). The archive stores rows from several
#    scrapes of the same deal; a deal is identified by (gush, parcel, sub-parcel, date, price) and
#    duplicates are dropped (3.22M remain).
#  - Judea and Samaria: the archive has almost no deals there. For gushim with no Tax Authority deal at
#    all, govmap's deal layer (nadlan.gov.il) is used instead (src = 'govmap'); govmap has no "portion
#    sold" field, so these are assumed to be whole-unit sales, and has no building year.
#  - Apartment sample (table a): deal types דירה בבית קומות, ד. מגורים, דירת גן, דירת גג (flats,
#    residential units, garden and roof flats; excludes houses, commercial, land, parking, storage);
#    whole-unit sales only (portion = 1; partial sales are inheritance and divorce transfers whose
#    price is not a market price for the unit); 25-400 m2 (below: studios / data errors; above:
#    whole-building or mis-recorded areas); price >= 150,000 NIS (below: non-market transfers, in all
#    years of the sample); price per m2 between 1,500 and 150,000 NIS (outside: recording errors in
#    price or area). 1.68M Tax Authority + 51K govmap sales remain.
#  - Prices are nominal here; real prices (CPI, 2015 = 100) are computed where needed (build_txn.py,
#    build_hedonic.py, ...).
# Dwellings (table g, p):
#  - National assets gazetteer (Survey of Israel, free version, 2024-25 snapshot): asset types דירת
#    מגורים and דירת מגורים חדשה = registered residential condominium units (2.68M). Parcel table p:
#    units, highest floor count, median building year (years outside 1870-2026 treated as missing),
#    modal settlement name.
# Parcel locations (table cen):
#  - Point inside the parcel polygon (ST_PointOnSurface) from the Survey of Israel parcel layer;
#    for parcels with no polygon (Judea and Samaria, re-parcelled ones) the location from
#    geocode_parcels.py (loc_q 2-5, see there).
#
# Inputs in cwd: gazetteer.csv, deals.csv (over.org.il download.csv of dataset
# fd06f5ae-...), govmap_deals.csv (optional, fetch_govmap_deals.py), parcel_centroids.csv (fetch_parcel_centroids.py), parcel_geocoded.csv
# (geocode_parcels.py; optional).
# Outputs: h.db (duckdb), parcels_v3.parquet, gush_v3.parquet, results_v3.json
import duckdb, json, numpy as np
c = duckdb.connect('h.db')
R = lambda q: c.sql(q).fetchall()

# --- deals: typed, deduped (the archive keeps rows from several scrapes) ---
c.execute("""create or replace table d as select settlement_code::int sc, settlement city, gush::int gush,
 try_cast(chelka as int) parcel, try_cast(sub_chelka as int) sub, strptime(deal_date,'%d/%m/%Y')::date dt,
 try_cast(deal_amount as double) price, deal_nature nat, try_cast(portion as double) por,
 try_cast(year_built as int) yb, try_cast(asset_area as double) area, try_cast(room_num as double) rooms
 from read_csv('deals.csv', all_varchar=true, header=true)""")
# Judea and Samaria: the Tax Authority archive has almost no deals there (22 in Ma'ale Adumim), but
# govmap's deal layer does (7.6K). Add govmap deals for gushim with no Tax Authority deal at all
# (src = 'govmap'). govmap has no 'portion' field, so whole-unit sales are assumed; year built is unknown.
import os
c.execute("alter table d add column src varchar default 'tax'")
if os.path.exists('govmap_deals.csv'):
    c.execute("""insert into d select null, gz.city, gm.gush::int, try_cast(gm.parcel as int), try_cast(gm.sub as int),
      try_cast(gm.date as date), try_cast(gm.amount as double), gm.nature, 1.0, null, try_cast(gm.area as double),
      try_cast(gm.rooms as double), 'govmap'
      from read_csv('govmap_deals.csv', all_varchar=true, header=true) gm
      left join (select GushNum::int gush, mode(SettlementNameHeb) city from read_csv('gazetteer.csv', all_varchar=true, header=true)
                 group by 1) gz on gz.gush = gm.gush::int
      where gm.gush::int not in (select distinct gush from d)""")
    print('govmap deals added', R("select count(*) from d where src = 'govmap'")[0][0])
# apartment sales: whole unit, plausible area/price
c.execute("""create or replace table a as select distinct on (gush,parcel,sub,dt,price) *, price/area ppm, year(dt) y
 from d where nat in ('דירה בבית קומות','ד. מגורים','דירת גן','דירת גג') and por=1
 and area between 25 and 400 and price>=150000 and price/area between 1500 and 150000""")

# --- gazetteer units + parcel table ---
c.execute("""create or replace table g as select GushNum::int gush, ParcelNum::int parcel, SubParcelNum::int sub,
 try_cast(BuildingFloors as int) fl, try_cast(BuildingYear as int) yr, SettlementNameHeb city
 from read_csv('gazetteer.csv', all_varchar=true, header=true) where Type in ('דירת מגורים','דירת מגורים חדשה')""")
c.execute("""create or replace table cen as select gush::int gush, parcel::int parcel, avg(lat) lat, avg(lon) lon, sum(area_m2) parea
 from read_csv('parcel_centroids.csv') where try_cast(parcel as int) is not null group by 1,2""")
# parcels with no polygon (Judea and Samaria, re-parcelled ones): street / gush / locality location
# from geocode_parcels.py. loc_q: 1 own polygon, 2 govmap deal coordinates, 3 street, 4 gush, 5 locality.
c.execute("alter table cen add column loc_q int default 1")
import os
if os.path.exists('parcel_geocoded.csv'):
    c.execute("""insert into cen select g.gush::int, g.parcel::int, g.lat, g.lon, null, g.loc_q::int from read_csv('parcel_geocoded.csv') g
     anti join cen using(gush, parcel)""")
c.execute("""create or replace table p as select gush, parcel, count(*) units, max(fl) fl,
 median(yr) filter (where yr between 1870 and 2026) yr, mode(city) city from g group by 1,2""")

# parcel price stats
c.execute("""create or replace table pp as select gush, parcel,
 median(ppm) filter (where y>=2023) ppm_r, count(*) filter (where y>=2023) n_r,
 count(*) filter (where y between 2015 and 2025) n_1525, median(area) filter (where y>=2015) area_med
 from a group by 1,2""")
# gush price stats: recent level, 2014-16 vs 2023-25 change, turnover
c.execute("""create or replace table gp as select gush,
 median(ppm) filter (where y>=2023) ppm_r, count(*) filter (where y>=2023) n_r,
 median(ppm) filter (where y between 2014 and 2016) ppm_15, count(*) filter (where y between 2014 and 2016) n_15,
 median(ppm) filter (where y between 2023 and 2025) ppm_25, count(*) filter (where y between 2023 and 2025) n_25,
 count(*) filter (where y between 2015 and 2025) n_1525, median(area) filter (where y>=2015) area_med
 from a group by 1""")
c.execute("""create or replace table cp as select g.city, median(a.ppm) filter (where a.y>=2023) ppm_r,
 median(a.area) filter (where a.y>=2015) area_med from a join (select distinct gush, parcel, city from p) g using(gush,parcel) group by 1""")

# national repeat-free benchmark: median ppm by year
yearly = R("select y, count(*), round(median(ppm)) from a group by 1 order by 1")

# --- hedonic: log ppm on building height, unit attributes, gush x year FE ---
c.execute("""create or replace table h as select a.*, p.fl, ln(a.ppm) lp from a join p using(gush,parcel)
 where a.y between 2015 and 2026 and p.fl between 1 and 60 and a.yb between 1900 and 2026""")
df = c.sql("select gush, y, lp, area, rooms, fl, yb, nat, dt from h").df()
df['age'] = (df.y - df.yb).clip(lower=0)
def bins(s, edges, labels):
    import pandas as pd
    return pd.cut(s, edges, labels=labels, right=True)
import pandas as pd
df['flb'] = bins(df.fl, [0,2,4,6,8,10,15,20,30,60], ['1-2','3-4','5-6','7-8','9-10','11-15','16-20','21-30','31+'])
df['ageb'] = bins(df.age, [-1,2,10,20,30,40,50,60,200], ['0-2','3-10','11-20','21-30','31-40','41-50','51-60','60+'])
df['rb'] = bins(df.rooms.where(df.rooms > 0, np.nan), [0,2,3,4,5,6,20], ['<=2','2.5-3','3.5-4','4.5-5','5.5-6','6.5+']).cat.add_categories('na').fillna('na')
df['larea'] = np.log(df.area)
df['q'] = df.dt.astype('datetime64[ns]').dt.quarter
X = pd.concat([df[['larea']],
               pd.get_dummies(df.flb, prefix='fl', drop_first=True, dtype=float),
               pd.get_dummies(df.ageb, prefix='age', drop_first=True, dtype=float),
               pd.get_dummies(df.rb, prefix='r', drop_first=True, dtype=float),
               pd.get_dummies(df.nat, prefix='t', drop_first=True, dtype=float),
               pd.get_dummies(df.q, prefix='q', drop_first=True, dtype=float)], axis=1)
fe = df.gush.astype(str) + '_' + df.y.astype(str)
keep = fe.map(fe.value_counts()) >= 2
X, yv, fe, cl = X[keep], df.lp[keep], fe[keep], df.gush[keep]
Xd = X - X.groupby(fe.values).transform('mean'); yd = yv - yv.groupby(fe.values).transform('mean')
Xm, ym = Xd.values, yd.values
XtX_inv = np.linalg.pinv(Xm.T @ Xm); b = XtX_inv @ Xm.T @ ym; e = ym - Xm @ b
# cluster-robust (gush) SE
S = pd.DataFrame(Xm * e[:, None]).groupby(cl.values).sum().values
V = XtX_inv @ (S.T @ S) @ XtX_inv
G = len(np.unique(cl)); N, K = Xm.shape; V *= G/(G-1) * (N-1)/(N-K)
se = np.sqrt(np.diag(V))
hed = {k: [round(float(bi),4), round(float(si),4)] for k, bi, si in zip(X.columns, b, se)}
hed_meta = {'N': int(N), 'cells': int(fe.nunique()), 'gush': int(G),
            'r2_within': round(float(1 - (e**2).sum()/(ym**2).sum()), 3)}
# same with no FE (raw gradient) for contrast, height bins only + area
Xr = pd.concat([df[['larea']], pd.get_dummies(df.flb, prefix='fl', drop_first=True, dtype=float),
                pd.get_dummies(df.y, prefix='y', drop_first=True, dtype=float)], axis=1)
Xr.insert(0, 'const', 1.0)
br = np.linalg.lstsq(Xr.values, df.lp.values, rcond=None)[0]
hed_raw = {k: round(float(v),4) for k, v in zip(Xr.columns, br) if k.startswith('fl_')}

# --- parcel master: units, location, value per unit ---
c.execute("""create or replace table pm as select p.*, cen.lat, cen.lon, cen.parea, cen.loc_q,
 pp.ppm_r p_ppm, pp.n_r p_n, pp.n_1525 p_n1525, gp.ppm_r g_ppm, gp.n_r g_n, cp.ppm_r c_ppm,
 coalesce(pp.area_med, gp.area_med, cp.area_med, 90) unit_m2,
 coalesce(case when gp.n_r>=5 then gp.ppm_r end, cp.ppm_r) loc_ppm
 from p left join cen using(gush,parcel) left join pp using(gush,parcel) left join gp using(gush)
 left join cp using(city)""")
c.execute("alter table pm add column unit_val double; update pm set unit_val = loc_ppm*unit_m2")
c.execute("copy pm to 'parcels_v3.parquet'")
c.execute("""create or replace table gm as select gp.*, (ppm_25/ppm_15-1) chg,
 n_1525/nullif(u.units,0)/11.0 turn, u.units, u.city from gp left join
 (select gush, sum(units) units, mode(city) city from p group by 1) u using(gush)""")
c.execute("copy gm to 'gush_v3.parquet'")

# --- stock value + effective supply by city ---
tot_units, tot_val, pbar = R("select sum(units), sum(units*unit_val), sum(units*unit_val)/sum(units) from pm where unit_val is not null")[0]
city = R(f"""select city, sum(units)::int u, round(sum(units*unit_val)/1e9,1) val_bn,
 round(sum(units*unit_val)/{pbar})::int eff_u, round(sum(units*unit_val)/sum(units)/{pbar},3) q,
 round(median(loc_ppm)) ppm from pm where unit_val is not null and city is not null
 group by 1 having sum(units)>=15000 order by val_bn desc""")
dec = R(f"""select (floor(yr/10)*10)::int dcd, sum(units)::int u, round(sum(units*unit_val)/{pbar})::int eff,
 round(sum(units*unit_val)/sum(units)/{pbar},3) q, round(median(unit_m2)) m2, round(median(loc_ppm)) ppm
 from pm where yr between 1940 and 2025 and unit_val is not null group by 1 order by 1""")
citydec = R(f"""select city, (floor(yr/10)*10)::int dcd, sum(units)::int u, round(sum(units*unit_val)/{pbar})::int eff
 from pm where yr between 1940 and 2025 and unit_val is not null and city in
 (select city from pm group by 1 having sum(units)>=40000) group by 1,2 order by 1,2""")

# --- renewal economics ---
# Per existing unit: build m units of S m2, return one to the owner, sell (m-1).
# Feasible iff (m-1)*P >= m*C*(1+margin). C = all-in cost per sellable m2.
# A parcel is a renewal candidate if built before 1980 with <=4 floors.
ren_units = R("select sum(units) from pm where yr<1980 and fl<=4")[0][0]
scen = []
for C in (8000, 10000, 12000):
    for m in (2.5, 3, 4):
        thr = m*C*1.15/(m-1)
        u, surplus = R(f"""select sum(units), sum(units*unit_m2*(({m}-1)*loc_ppm - {m}*{C}*1.15))/1e9
          from pm where yr<1980 and fl<=4 and loc_ppm >= {thr}""")[0]
        scen.append([C, m, round(thr), int(u or 0), round((u or 0)/ren_units, 3), round(surplus or 0, 1)])
ren_city = R(f"""select city, sum(units)::int ru, round(median(loc_ppm)) ppm,
 round(sum(units) filter (where loc_ppm >= 3*10000*1.15/2)/sum(units),3) feas3,
 round(sum(units) filter (where loc_ppm >= 4*10000*1.15/3)/sum(units),3) feas4,
 round(sum(units*unit_m2*greatest(2*loc_ppm - 3*10000*1.15,0))/1e9,1) surplus3_bn
 from pm where yr<1980 and fl<=4 and loc_ppm is not null and city is not null
 group by 1 having sum(units)>=3000 order by surplus3_bn desc""")

# --- price change and turnover by city ---
chg_city = R("""select city, round(median(chg),3) chg, round(sum(n_1525)/sum(units)/11.0,4) turn, sum(units)::int u
 from gm where n_15>=10 and n_25>=10 and city is not null group by 1 having sum(units)>=15000 order by chg desc""")
nat_chg = R("select round(median(chg),3), count(*), round(sum(n_1525)/sum(units)/11.0,4) from gm where n_15>=10 and n_25>=10")[0]

out = dict(yearly=yearly, hedonic=hed, hedonic_meta=hed_meta, hedonic_raw=hed_raw,
           stock=dict(units=int(tot_units), value_bn=round(tot_val/1e9), mean_unit_val=round(pbar)),
           city=city, decades=dec, citydec=citydec, renewal_units=int(ren_units), renewal_scen=scen,
           renewal_city=ren_city, chg_city=chg_city, nat_chg=nat_chg)
json.dump(out, open('results_v3.json','w'), ensure_ascii=False, default=float)
for k, v in out.items():
    print(k, json.dumps(v, ensure_ascii=False, default=float)[:1500])
