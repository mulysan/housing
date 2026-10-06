# Large (>= 30 ha) but thin parcels, i.e. road networks registered as one parcel,
# which fetch_parcel_geoms.py skips. Appends to parcel_geoms.tsv.
from q import *
out = open('parcel_geoms.tsv', 'a'); n = 0
for a, b in [(0, 20000), (20001, 999999)]:
    d = sql(PAR, f'''select "GUSH_NUM" g, "PARCEL" p, extensions.ST_AsText(extensions.ST_SimplifyPreserveTopology(geom,0.00001),6) w
        from append_shape_ff3176b1 where "SHAPE_AREA"::float >= 300000 and "SHAPE_LEN"::float^2 > 60*"SHAPE_AREA"::float
        and "GUSH_NUM"::int between {a} and {b}''', tries=3)
    assert not d['truncated']
    for r in d['rows']: out.write(f"{r['g']}\t{r['p']}\t{r['w']}\n"); n += 1
print('appended', n)
