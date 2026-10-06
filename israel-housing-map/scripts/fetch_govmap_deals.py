# govmap real-estate deals (nadlan.gov.il feed, archived by over.org.il as
# public.govmap_deals): unlike the Tax Authority archive it has the unit's
# floor. Nulls are written as '' (concat_ws would drop them and shift columns).
# One packed row per gush (the SQL endpoint caps results at 1,000 rows).
from q import *
import csv, duckdb, concurrent.futures as cf
cnt = dict(duckdb.connect('h.db', read_only=True).sql("select gush, count(*) from d group by 1").fetchall())
# ranges tile the whole gush number line, so gushim with no Tax Authority deal (Judea and Samaria) are included
gs = sorted(cnt); batches = []; cur = []; n = 0; lo = 0
for g in gs:
    if cur and (n + cnt[g] > 30000 or len(cur) >= 900): batches.append((lo, cur[-1])); lo = cur[-1] + 1; cur, n = [], 0
    cur.append(g); n += cnt[g]
batches.append((lo, cur[-1])); batches.append((cur[-1] + 1, 10**7))
Q = '''select gush g, string_agg(concat_ws('|', coalesce(parcel::text,''), coalesce(sub_parcel::text,''), coalesce(deal_date::text,''),
       coalesce(deal_amount::text,''), replace(replace(coalesce(floor,''),'|',' '),'~',' '), coalesce(asset_area::text,''),
       coalesce(rooms::text,''), replace(coalesce(deal_nature,''),'|',' '), coalesce(round(lon::numeric,5)::text,''),
       coalesce(round(lat::numeric,5)::text,'')), '~') s
       from public.govmap_deals where gush between {a} and {b} group by 1'''
def get(ab):
    a, b = ab
    try: d = sql(PAR, Q.format(a=a, b=b), tries=3)
    except Exception: d = None
    if d is None or d['truncated']:
        if a >= b: return []
        m = (a + b)//2; return get((a, m)) + get((m+1, b))
    return [[r['g']] + it.split('|') for r in d['rows'] for it in r['s'].split('~')]
w = csv.writer(open('govmap_deals.csv', 'w'))
w.writerow(['gush', 'parcel', 'sub', 'date', 'amount', 'floor', 'area', 'rooms', 'nature', 'lon', 'lat'])
done = 0
with cf.ThreadPoolExecutor(3) as ex:
    for rows in ex.map(get, batches):
        w.writerows(rows); done += 1
        if done % 10 == 0: print(done, '/', len(batches), flush=True)
print('done')
