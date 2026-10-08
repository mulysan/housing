# OSM street-network measures from Overture's transportation theme
# (fetch_overture_roads.py; Overture road segments are OSM highway ways).
#
# Intersections follow OSMnx: node street count = number of segment ends at a
# connector (an interior connector counts 2, a self-loop 2); intersections are
# nodes with street count >= 3 (dead ends and pass-through nodes dropped), then
# consolidated like ox.consolidate_intersections(tolerance=t): nodes whose
# t-metre buffers overlap (distance <= 2t) merge into one. Networks mirror the
# OSMnx network_type filters:
#   drive: motorway..tertiary (+links), residential, living_street,
#          unclassified, unknown (no service, track, path, footway, ...)
#   walk:  everything but motorway(+link) and cycleway / bridleway
#          (incl. footway, sidewalk, crossing, path, steps, service, track)
import numpy as np, pandas as pd, pyarrow.parquet as pq, shapely
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
LAT0 = 31.8; KX = 111320*np.cos(np.radians(LAT0)); KY = 110574

DRIVE = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'residential', 'living_street', 'unclassified', 'unknown'}
NOT_WALK = {'motorway', 'cycleway', 'bridleway'}

def load():
    S = pq.read_table('ov_segments.parquet', columns=['id', 'class', 'subclass', 'connectors', 'geometry']).to_pandas()
    C = pq.read_table('ov_connectors.parquet').to_pandas()
    S['drive'] = S['class'].isin(DRIVE)
    S['walk'] = ~S['class'].isin(NOT_WALK)
    return S, C

def nodes(S, C, mask):
    """street count per connector for segments in mask -> DataFrame(x, y, k) in metres"""
    sub = S.loc[mask, 'connectors']
    lens = sub.map(len).values
    cid = np.concatenate([[c['connector_id'] for c in cs] for cs in sub.values])
    at = np.concatenate([[c['at'] for c in cs] for cs in sub.values])
    w = np.where((at <= 1e-9) | (at >= 1 - 1e-9), 1, 2)
    k = pd.Series(w).groupby(cid).sum()
    xy = C.set_index('id').reindex(k.index)
    return pd.DataFrame({'x': xy.lon.values*KX, 'y': xy.lat.values*KY, 'k': k.values}).dropna()

def consolidate(x, y, tol):
    """OSMnx-style: merge nodes within 2*tol (overlapping buffers); centroid per cluster"""
    xy = np.c_[x, y]
    p = cKDTree(xy).query_pairs(2*tol, output_type='ndarray')
    G = coo_matrix((np.ones(len(p)), (p[:, 0], p[:, 1])), shape=(len(xy),)*2)
    n, lab = connected_components(G, directed=False)
    cx = np.bincount(lab, x)/np.bincount(lab); cy = np.bincount(lab, y)/np.bincount(lab)
    return cx, cy, lab

def edges(S, mask):
    """vertex-to-vertex pieces of all segments in mask: midpoints (m), length (m), bearing (deg, 0-180)"""
    g = shapely.from_wkb(S.loc[mask, 'geometry'].values)
    co, idx = shapely.get_coordinates(g, return_index=True)
    co = co*[KX, KY]
    same = idx[1:] == idx[:-1]
    a, b = co[:-1][same], co[1:][same]
    d = b - a; L = np.hypot(d[:, 0], d[:, 1])
    brg = np.degrees(np.arctan2(d[:, 0], d[:, 1])) % 180
    m = (a + b)/2
    return m[:, 0], m[:, 1], L, brg

def orient_entropy(brg, L, nb=36):
    """Boeing (2019) street-orientation entropy, normalized to [0,1] (0 = one direction, 1 = uniform).
    Bearings are folded to 0-180 (= both directions of each edge), 36 bins of 10 degrees over 360."""
    h = np.bincount(((brg + 5) % 180 // 10).astype(int), L, minlength=18)
    p = np.r_[h, h]/(2*h.sum()); p = p[p > 0]
    return -(p*np.log(p)).sum()/np.log(nb)

def circuity_pieces(S, C, mask):
    """Street curvature after Boeing (2019, "Urban spatial order"): circuity = network length / straight-line
    (chord) length between graph nodes. Graph nodes are connectors with street count != 2 (intersections and
    dead ends), as in a simplified OSMnx graph; each segment is cut at those connectors.
    Caveat: Overture also splits segments at attribute changes, so a street piece between two
    intersections can span several segments; its chord is then measured per segment, which makes
    circuity a slight lower bound. Pieces with a chord under 10 m (and closed loops) are dropped:
    there the ratio is dominated by noise.
    Returns midpoint x, y (m), network length and chord (m) per piece."""
    sub = S.loc[mask]
    lens = sub.connectors.map(len).values
    cid = np.concatenate([[c['connector_id'] for c in cs] for cs in sub.connectors.values])
    at = np.concatenate([[c['at'] for c in cs] for cs in sub.connectors.values])
    w = np.where((at <= 1e-9) | (at >= 1 - 1e-9), 1, 2)
    k = pd.Series(w).groupby(cid).sum()
    node = pd.Series(cid).map(k).values != 2                   # cut here
    seg = np.repeat(np.arange(len(sub)), lens)
    # cut fractions per segment: 0, 1 and the node connectors in between
    F = pd.DataFrame({'seg': np.r_[seg[node], np.arange(len(sub)), np.arange(len(sub))],
                      'f': np.r_[at[node], np.zeros(len(sub)), np.ones(len(sub))]}).drop_duplicates().sort_values(['seg', 'f'])
    geo = shapely.transform(shapely.from_wkb(sub.geometry.values), lambda c: np.c_[c[:, 0]*KX, c[:, 1]*KY])
    L = shapely.length(geo)
    pt = shapely.line_interpolate_point(geo[F.seg.values], F.f.values, normalized=True)
    x, y = shapely.get_x(pt), shapely.get_y(pt)
    same = F.seg.values[1:] == F.seg.values[:-1]
    df = np.diff(F.f.values)[same]; sg = F.seg.values[1:][same]
    net = df * L[sg]
    chord = np.hypot(np.diff(x)[same], np.diff(y)[same])
    mx, my = ((x[1:] + x[:-1])/2)[same], ((y[1:] + y[:-1])/2)[same]
    ok = (chord >= 10) & (net >= chord*0.999)
    return mx[ok], my[ok], net[ok], chord[ok]

if __name__ == '__main__':      # validation against the Overpass 1 km2 boxes (osm_val/)
    S, C = load()
    V = pd.read_csv('osm_val/val_boxes.csv')
    out = []
    for net in ['drive', 'walk']:
        N = nodes(S, C, S[net].values); I = N[N.k >= 3]
        for tol in (10, 15):
            cx, cy, _ = consolidate(I.x.values, I.y.values, tol)
            for i, b in V.iterrows():
                inb = lambda X, Y: ((Y/KY > b.s) & (Y/KY < b.n) & (X/KX > b.w) & (X/KX < b.e)).sum()
                out.append([b.city, net, tol, inb(I.x.values, I.y.values), inb(cx, cy)])
    O = pd.DataFrame(out, columns=['city', 'net', 'tol', 'raw', 'consol'])
    print(O.pivot_table(index='city', columns=['net', 'tol'], values=['raw', 'consol']).to_string())
