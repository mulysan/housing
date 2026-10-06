# OSM street network for Israel via Overture Maps (transportation theme, built
# from OpenStreetMap ways). Used because overpass-api.de and
# download.geofabrik.de are unreachable from the container while Overture's
# public S3 bucket is. Reads anonymously with pyarrow, filtering on the bbox
# column (row-group statistics push down).
# Output: ov_segments.parquet (id, class, subclass, connectors, wkb geometry, name),
#         ov_connectors.parquet (id, lon, lat)
import pyarrow.fs as pf, pyarrow.dataset as ds, pyarrow.parquet as pq, pyarrow.compute as pc
REL = 'overturemaps-us-west-2/release/2026-09-23.1/theme=transportation'
X0, X1, Y0, Y1 = 34.2, 35.95, 29.45, 33.35            # Israel (+ the West Bank, cut later by SA polygons)
s3 = pf.S3FileSystem(anonymous=True, region='us-west-2')
def get(typ, cols, extra=None):
    d = ds.dataset(f'{REL}/type={typ}', filesystem=s3, format='parquet')
    b = lambda k: pc.field(('bbox', k))
    f = (b('xmin') <= X1) & (b('xmax') >= X0) & (b('ymin') <= Y1) & (b('ymax') >= Y0)
    if extra is not None: f = f & extra
    return d.to_table(columns=cols, filter=f)
seg = get('segment', ['id', 'class', 'subclass', 'connectors', 'geometry', 'bbox', 'names'], pc.field('subtype') == 'road')
seg = seg.append_column('name', seg['names'].combine_chunks().field('primary')).drop(['names'])   # Hebrew in Israel
print('segments', seg.num_rows, flush=True)
pq.write_table(seg, 'ov_segments.parquet')
con = get('connector', ['id', 'bbox'])
con = con.append_column('lon', con['bbox'].combine_chunks().field('xmin')).append_column(
    'lat', con['bbox'].combine_chunks().field('ymin')).drop(['bbox'])
print('connectors', con.num_rows)
pq.write_table(con, 'ov_connectors.parquet')
