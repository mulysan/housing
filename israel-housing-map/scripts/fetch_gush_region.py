# District (מחוז) and subdistrict (נפה) per gush: the most common value over its
# parcels in over.org.il's parcel table (public.over_re_parcels).
from q import *
import csv
import os
gs = {int(r['gush']) for r in csv.DictReader(open('parcel_centroids.csv'))}
if os.path.exists('parcel_geocoded.csv'): gs |= {int(r['gush']) for r in csv.DictReader(open('parcel_geocoded.csv'))}   # J&S etc.
gs = sorted(gs)
w = csv.writer(open('gush_region.csv', 'w')); w.writerow(['gush', 'region', 'county']); n = 0
for k in range(0, len(gs), 900):
    a, b = gs[k], gs[min(k+899, len(gs)-1)]
    d = sql(PAR, f"""select gush g, mode() within group (order by nullif(region_name,'')) r,
        mode() within group (order by nullif(county_name,'')) c from public.over_re_parcels
        where gush between {a} and {b} group by 1""", tries=3)
    assert not d['truncated']
    for r in d['rows']: w.writerow([r['g'], r['r'], r['c']]); n += 1
print('gushim', n)
