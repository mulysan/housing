# Parcel centroids (ST_PointOnSurface), area and locality for every parcel in over.org.il's copy of the
# Survey of Israel parcel layer. One packed row per gush (the SQL endpoint caps results at 1,000 rows).
# Batches of ~6,000 parcels sized from per-gush counts, 3 requests in flight; a batch that times out
# is split in two.
from q import *
import csv, concurrent.futures as cf
d = sql(PAR, '''select g/500 k, string_agg(g||':'||n, ';') s from (select "GUSH_NUM"::int g, count(*) n
    from append_shape_ff3176b1 group by 1) t group by 1''', tries=3)
assert not d['truncated']
cnt = {int(a): int(b) for r in d['rows'] for a, b in (it.split(':') for it in r['s'].split(';'))}
print('gushim', len(cnt), 'parcels', sum(cnt.values()), flush=True)
gs = sorted(cnt); batches = []; cur = []; n = 0
for g in gs:
    if cur and (n + cnt[g] > 6000 or len(cur) >= 900): batches.append(cur); cur, n = [], 0
    cur.append(g); n += cnt[g]
batches.append(cur)
Q = '''select "GUSH_NUM" g, string_agg("PARCEL"||':'||round(extensions.ST_Y(extensions.ST_PointOnSurface(geom))::numeric,5)||':'||
  round(extensions.ST_X(extensions.ST_PointOnSurface(geom))::numeric,5)||':'||round("SHAPE_AREA"::numeric)||':'||"LOCALITY_I", ';') s
  from append_shape_ff3176b1 where "GUSH_NUM" = any(array[{ids}]) group by 1'''   # text column with a btree index
def get(b):
    try: d = sql(PAR, Q.format(ids=",".join(f"'{g}'" for g in b)), tries=2)
    except Exception: d = None
    if d is None or d['truncated']:
        if len(b) == 1: print('FAILED gush', b[0], flush=True); return []
        m = len(b)//2; return get(b[:m]) + get(b[m:])
    return [[r['g']] + it.split(':') for r in d['rows'] for it in r['s'].split(';')]
out = csv.writer(open('parcel_centroids.csv', 'w')); out.writerow(['gush', 'parcel', 'lat', 'lon', 'area_m2', 'locality'])
done = 0
with cf.ThreadPoolExecutor(3) as ex:
    for rows in ex.map(get, batches):
        out.writerows(rows); done += 1
        if done % 20 == 0: print(done, '/', len(batches), flush=True)
print('done', len(batches))
