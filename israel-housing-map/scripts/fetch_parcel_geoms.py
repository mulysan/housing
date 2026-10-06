# Simplified parcel polygons (WKT, ~1 m tolerance) for parcels < 30 ha, from
# over.org.il's copy of the Survey of Israel parcel layer. One row per gush
# via string_agg (the SQL endpoint caps results at 1,000 rows). Batches are
# sized from parcel_centroids.csv and name their gushim explicitly ("GUSH_NUM"
# is text with a btree index; a cast range scans the table). 3 requests in flight.
from q import *
import csv, collections, concurrent.futures as cf
cnt = collections.Counter(int(r['gush']) for r in csv.DictReader(open('parcel_centroids.csv')))
gs = sorted(cnt); batches = []; cur = []; n = 0
for g in gs:
    if cur and (n + cnt[g] > 8000 or len(cur) >= 900): batches.append(cur); cur, n = [], 0
    cur.append(g); n += cnt[g]
batches.append(cur)
Q = '''select "GUSH_NUM" g, string_agg("PARCEL"||';'||extensions.ST_AsText(extensions.ST_SimplifyPreserveTopology(geom,0.000008),6), '|') s
 from append_shape_ff3176b1 where "GUSH_NUM" = any(array[{ids}]) and "SHAPE_AREA"::float < 300000 group by 1'''
def get(b):
    try: d = sql(PAR, Q.format(ids=",".join(f"'{g}'" for g in b)), tries=3)
    except Exception: d = None
    if d is None or d['truncated']:
        if len(b) == 1: print('FAILED gush', b[0], flush=True); return []
        m = len(b)//2; return get(b[:m]) + get(b[m:])
    return [(r['g'], it.split(';', 1)) for r in d['rows'] for it in r['s'].split('|')]
out = open('parcel_geoms.tsv', 'w'); done = 0
with cf.ThreadPoolExecutor(3) as ex:
    for rows in ex.map(get, batches):
        for g, (p, w) in rows: out.write(f'{g}\t{p}\t{w}\n')
        done += 1
        if done % 20 == 0: print(done, '/', len(batches), flush=True)
out.close(); print('done', len(batches))
