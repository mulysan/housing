# Extra neighbourhood features from Overture Maps (release 2026-09-23.1), Israel bounding box:
#  places   - points of interest (businesses, services). Overture merges Meta, Microsoft, Foursquare-style
#             and OpenStreetMap sources and attaches a confidence score; used to count commercial units.
#  parking  - parking lots and structures: base/infrastructure features whose class or subtype mentions
#             parking (from OSM amenity=parking / parking_space / parking_entrance areas and points).
#             base/land_use has no parking class in this release (checked: 0 features in Israel).
# Output: ov_places.parquet (lon, lat, basic_category, primary, confidence, operating_status),
#         ov_parking.parquet (theme, subtype, class, wkb geometry)
import pyarrow.fs as pf, pyarrow.dataset as ds, pyarrow.parquet as pq, pyarrow.compute as pc, pyarrow as pa
REL = 'overturemaps-us-west-2/release/2026-09-23.1'
X0, X1, Y0, Y1 = 34.2, 35.95, 29.45, 33.35
s3 = pf.S3FileSystem(anonymous=True, region='us-west-2')
def bbox():
    b = lambda k: pc.field(('bbox', k))
    return (b('xmin') <= X1) & (b('xmax') >= X0) & (b('ymin') <= Y1) & (b('ymax') >= Y0)
pl = ds.dataset(f'{REL}/theme=places/type=place', filesystem=s3, format='parquet').to_table(
    columns=['bbox', 'basic_category', 'taxonomy', 'confidence', 'operating_status'], filter=bbox())
tax = pl['taxonomy'].combine_chunks()
out = pa.table({'lon': pl['bbox'].combine_chunks().field('xmin'), 'lat': pl['bbox'].combine_chunks().field('ymin'),
                'basic_category': pl['basic_category'], 'primary': tax.field('primary'),
                'confidence': pl['confidence'], 'operating_status': pl['operating_status']})
pq.write_table(out, 'ov_places.parquet'); print('places', out.num_rows)
parts = []
for typ in ['land_use', 'infrastructure']:
    t = ds.dataset(f'{REL}/theme=base/type={typ}', filesystem=s3, format='parquet').to_table(
        columns=['subtype', 'class', 'geometry'], filter=bbox())
    m = pc.or_(pc.match_substring(pc.fill_null(t['class'], ''), 'parking'), pc.match_substring(pc.fill_null(t['subtype'], ''), 'parking'))
    t = t.filter(m)
    if t.num_rows: parts.append(t.append_column('theme', pa.array([typ]*t.num_rows)))
    print(typ, 'parking features', t.num_rows, pc.value_counts(t['class']).to_pylist()[:10])
pq.write_table(pa.concat_tables(parts), 'ov_parking.parquet')
