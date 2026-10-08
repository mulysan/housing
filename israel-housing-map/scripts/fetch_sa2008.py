# CBS census 2008 statistical areas (over.org.il copies of the CBS "שכבת אזורים סטטיסטיים 2008" files):
# share whose last school was a yeshiva (education layer), mean household size (households layer)
# and main religion (population layer), with simplified polygons. Used to classify areas as Haredi.
# Also the SA-2011 religion field from the 2015 population table (for Arab areas).
# Output: sa2008.csv (sa08, yeshiva, hh_size, religion, religion_pct, wkt), sa2011_religion.csv
from q import *
import csv
X = 'extensions.'
EDU, HH, POP = 'append_cbs_pub_file_5a6408c5_305595c0', 'append_cbs_pub_file_32102bdc_d2dc2f24', 'append_cbs_pub_file_53f5b704_347c354c'
num = lambda c: f'''nullif("{c}"::text,'')::float'''
rows = {}
for off in range(0, 4000, 1000):
    for r in sql(PAR, f'''select "YISHUV_STAT08"::text k, {num('yeshiva_pcnt')} y,
            {X}ST_AsText({X}ST_SimplifyPreserveTopology(geom, 0.00002), 6) w from {EDU} order by 1 limit 1000 offset {off}''')['rows']:
        rows[r['k']] = {'yeshiva': r['y'], 'wkt': r['w']}
for off in range(0, 4000, 1000):
    for r in sql(PAR, f'''select "YISHUV_STAT08"::text k, {num('size_avg')} s from {HH} order by 1 limit 1000 offset {off}''')['rows']:
        rows.setdefault(r['k'], {})['hh_size'] = r['s']
for off in range(0, 4000, 1000):
    for r in sql(PAR, f'''select "YISHUV_STAT08"::text k, "ReligionHeb" rl, {num('religion_pcnt')} p from {POP} order by 1 limit 1000 offset {off}''')['rows']:
        rows.setdefault(r['k'], {}).update(religion=r['rl'], religion_pct=r['p'])
w = csv.writer(open('sa2008.csv', 'w')); w.writerow(['sa08', 'yeshiva', 'hh_size', 'religion', 'religion_pct', 'wkt'])
for k, v in rows.items():
    if v.get('wkt'): w.writerow([k, v.get('yeshiva'), v.get('hh_size'), v.get('religion'), v.get('religion_pct'), v['wkt']])
print('sa2008', len(rows))
w = csv.writer(open('sa2011_religion.csv', 'w')); w.writerow(['sa', 'religion_sa', 'religion_yishuv'])
for off in range(0, 4000, 1000):
    for r in sql(PAR, f'''select "YISHUV_STAT11" sa, "Religion_Stat_Txt" a, "Religion_yishuv_Txt" b
            from public.append_cbs_pub_file_ec613cd1_fe7b492e order by 1 limit 1000 offset {off}''')['rows']:
        w.writerow([r['sa'], r['a'], r['b']])
