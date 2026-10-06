# Urban-form inputs from over.org.il (append SQL endpoint; PostGIS in schema
# `extensions`). Writes small CSVs into cwd.
from q import *
import csv
X = 'extensions.'
def rows(q): return sql(PAR, q, tries=3)['rows']
def packed(q, fn, header):
    """q returns rows (k, s) with s = 'a,b,..;a,b,..'; explode into fn."""
    w = csv.writer(open(fn, 'w')); w.writerow(header); n = 0
    for r in rows(q):
        for it in (r['s'] or '').split(';'):
            if it: w.writerow([r['k']] + it.split(',')); n += 1
    print(fn, n)

import os
if not os.path.exists('sa2011.csv'):
  pass
# 1. Statistical areas 2011 with the 2021 socio-economic cluster (CBS), simplified
w = csv.writer(open('sa2011.csv', 'w')); w.writerow(['sa', 'yishuv', 'name', 'stat', 'func', 'ses21', 'area_m2', 'wkt'])
for off in range(0, 4000, 1000):
    for r in rows(f'''select "YISHUV_STAT11" sa, "SEMEL_YISHUV" y, "SHEM_YISHUV" n, "STAT11" s, "Main_Function_Txt" f, "eshkol_madad2021" e,
        round({X}ST_Area(geom::{X}geography)) a, {X}ST_AsText({X}ST_SimplifyPreserveTopology(geom, 0.00002), 6) wkt
        from public.append_cbs_pub_file_afb48290_5fa5cab4 order by 1 limit 1000 offset {off}'''):
        w.writerow([r['sa'], r['y'], r['n'], r['s'], r['f'], r['e'], r['a'], r['wkt']])
# 2. SA 2011 population 2015
w = csv.writer(open('sa_pop2015.csv', 'w')); w.writerow(['sa', 'pop', 'religion'])
for off in range(0, 4000, 1000):
    for r in rows(f'''select "YISHUV_STAT11" sa, "Pop_Total" p, "Religion_yishuv_Txt" rl from public.append_cbs_pub_file_ec613cd1_fe7b492e order by 1 limit 1000 offset {off}'''):
        w.writerow([r['sa'], r['p'], r['rl']])
# 3. Bus / rail stops (GTFS via govmap layer 20)
packed(f'''select case when stop_name like 'ת. רכבת%' then 'rail' else 'bus' end k,
  string_agg(round(x::numeric,5)||','||round(y::numeric,5), ';') s
  from idx.govmap_20_42de706b_41734d96 where location_type='0' group by 1''', 'stops.csv', ['kind', 'lon', 'lat'])
# 4. Light rail / metro stations in operation (entrances)
packed(f'''select 'lrt' k, string_agg(round({X}ST_X(p)::numeric,5)||','||round({X}ST_Y(p)::numeric,5), ';') s from
  (select {X}ST_Transform({X}ST_SetSRID({X}ST_MakePoint("X"::float,"Y"::float),2039),4326) p
   from public.append_lrt_stat_b4aacea3_b2ca8ac5 where "STATUS"='קיימת') t''', 'lrt.csv', ['kind', 'lon', 'lat'])
# 5. Schools and kindergartens (govmap layer 18)
packed(f'''select coalesce(shlav_chinuch,'') k, string_agg(round({X}ST_X({X}ST_Centroid(geom))::numeric,5)||','||round({X}ST_Y({X}ST_Centroid(geom))::numeric,5), ';') s
  from idx.govmap_18_5e512807_af3fceaf group by 1''', 'schools.csv', ['level', 'lon', 'lat'])
# 6. CBS land-use grid points, built-up categories only (codes 1-29 and parks 33)
packed(f'''select "LANDUSE_CO" k, string_agg(round({X}ST_X({X}ST_Centroid(geom))::numeric,5)||','||round({X}ST_Y({X}ST_Centroid(geom))::numeric,5), ';') s
  from public.append_cbs_pub_file_4f9baf1a_462c2349 where "LANDUSE_CO"::int <= 29 or "LANDUSE_CO"::int = 33 group by 1''',
  'landuse_pts.csv', ['code', 'lon', 'lat'])
# 7. Geocoded address points (population-authority address list, over.org.il build)
w = csv.writer(open('addresses.csv', 'w')); w.writerow(['settlement', 'lon', 'lat']); n = 0
codes = [r['c'] for r in rows("select distinct settlement_code c from public.over_re_addresses where lat is not null")]
for i in range(0, len(codes), 40):
    cs = ','.join(str(c) for c in codes[i:i+40])
    for r in rows(f'''select settlement_code k, string_agg(round(lon::numeric,5)||','||round(lat::numeric,5), ';') s
        from public.over_re_addresses where lat is not null and settlement_code in ({cs}) group by 1'''):
        for it in r['s'].split(';'): w.writerow([r['k']] + it.split(',')); n += 1
print('addresses.csv', n)
