import numpy as np, shapely
from shapely import STRtree
def junctions(road_geoms_m, merge=25.0, touch=2.0):
    """Points where distinct road parcels meet (contact areas within `touch` m), merged within `merge` m.
    Returns (x, y) arrays of junction points."""
    gb = shapely.buffer(road_geoms_m, touch/2, quad_segs=1)
    t = STRtree(gb)
    i, j = t.query(gb, predicate='intersects')
    m = i < j; i, j = i[m], j[m]
    cp = shapely.centroid(shapely.intersection(gb[i], gb[j]))
    x, y = shapely.get_x(cp), shapely.get_y(cp)
    ok = np.isfinite(x); x, y = x[ok], y[ok]
    # merge contact points within `merge` m: grid snapping + union-find on neighbouring cells
    key = np.floor(x/merge).astype(np.int64)*1_000_003 + np.floor(y/merge).astype(np.int64)
    uk, inv = np.unique(key, return_inverse=True)
    cx = np.bincount(inv, x)/np.bincount(inv); cy = np.bincount(inv, y)/np.bincount(inv)
    # second pass: collapse cell-centres closer than merge (neighbouring cells)
    tree = STRtree(shapely.points(cx, cy))
    a, b = tree.query(shapely.buffer(shapely.points(cx, cy), merge), predicate='intersects')
    parent = np.arange(len(cx))
    def find(u):
        while parent[u] != u: parent[u] = parent[parent[u]]; u = parent[u]
        return u
    for u, v in zip(a, b):
        ru, rv = find(u), find(v)
        if ru != rv: parent[max(ru, rv)] = min(ru, rv)
    root = np.array([find(u) for u in range(len(cx))])
    ur, rinv = np.unique(root, return_inverse=True)
    jx = np.bincount(rinv, cx)/np.bincount(rinv); jy = np.bincount(rinv, cy)/np.bincount(rinv)
    return jx, jy


def junctions_clean(road_geoms_m, merge=25.0, touch=2.0, side_len=30.0, end_tol=15.0, straight_cos=0.87):
    """Like junctions(), with cleaning. A contact between two road parcels is dropped when
    (a) they share a long edge (> side_len m: parallel strips, e.g. a road split lengthwise), or
    (b) it is a straight continuation: the contact sits at an end of both parcels and their long
        axes are within ~30 degrees (a street cut into two parcels mid-block).
    Remaining contacts are merged within `merge` m; a junction is kept when it joins >= 3 distinct
    road parcels, or 2 parcels in a T / corner (not a continuation).
    Returns (x, y, degree, kind) with kind 0 = 3+ parcels, 1 = T/corner of 2 parcels."""
    g = road_geoms_m
    gb = shapely.buffer(g, touch/2, quad_segs=1)
    t = STRtree(gb)
    i, j = t.query(gb, predicate='intersects')
    m = i < j; i, j = i[m], j[m]
    inter = shapely.intersection(gb[i], gb[j])
    cp = shapely.centroid(inter); x, y = shapely.get_x(cp), shapely.get_y(cp)
    shared = shapely.area(inter) / touch                       # ~ length of the shared boundary
    # long axis of each parcel from its oriented envelope
    env = shapely.get_exterior_ring(shapely.oriented_envelope(g))
    p0, p1, p2 = (shapely.get_point(env, k) for k in range(3))
    ax, ay = shapely.get_x(p0), shapely.get_y(p0); bx, by = shapely.get_x(p1), shapely.get_y(p1); cx_, cy_ = shapely.get_x(p2), shapely.get_y(p2)
    s1 = np.hypot(bx - ax, by - ay); s2 = np.hypot(cx_ - bx, cy_ - by)
    long1 = s1 >= s2
    ux = np.where(long1, bx - ax, cx_ - bx); uy = np.where(long1, by - ay, cy_ - by)
    L = np.hypot(ux, uy); ux, uy = ux/np.maximum(L, 1e-9), uy/np.maximum(L, 1e-9)
    ctr = shapely.centroid(g); gx, gy = shapely.get_x(ctr), shapely.get_y(ctr)
    def at_end(k):
        tpos = (x - gx[k])*ux[k] + (y - gy[k])*uy[k]
        return np.abs(tpos) > L[k]/2 - np.maximum(end_tol, 0.15*L[k])
    cosang = np.abs(ux[i]*ux[j] + uy[i]*uy[j])
    straight = at_end(i) & at_end(j) & (cosang > straight_cos)
    parallel = shared > side_len
    ok = np.isfinite(x) & ~parallel
    keep_pair = ok & ~straight                                  # pairs that by themselves form a junction
    # cluster all non-parallel contacts (a 4-way junction can include straight pairs)
    x, y, i, j, keep_pair = x[ok], y[ok], i[ok], j[ok], keep_pair[ok]
    pts = shapely.points(x, y); tr = STRtree(pts)
    a, b = tr.query(shapely.buffer(pts, merge/2), predicate='intersects')
    parent = np.arange(len(x))
    def find(u):
        while parent[u] != u: parent[u] = parent[parent[u]]; u = parent[u]
        return u
    for u, v in zip(a, b):
        ru, rv = find(u), find(v)
        if ru != rv: parent[max(ru, rv)] = min(ru, rv)
    root = np.array([find(u) for u in range(len(x))])
    df = __import__('pandas').DataFrame({'r': root, 'x': x, 'y': y, 'i': i, 'j': j, 'k': keep_pair})
    out = []
    for r, d in df.groupby('r'):
        deg = len(set(d.i) | set(d.j))
        if deg >= 3: out.append((d.x.mean(), d.y.mean(), deg, 0))
        elif d.k.any(): out.append((d.x.mean(), d.y.mean(), deg, 1))
    o = np.array(out) if out else np.zeros((0, 4))
    return o[:, 0], o[:, 1], o[:, 2].astype(int), o[:, 3].astype(int)


def junctions_skel(road_geoms_m, res=2.0, tile=4000.0, pad=150.0, prune=24.0, merge=20.0, bridge=0.0):
    """Junctions from the skeleton of the rasterised road network (all road parcels unioned).
    Unlike the parcel-contact methods this also finds intersections *inside* one road parcel
    (a whole street grid or a ring road with branches is often registered as a single parcel),
    and parcel breaks along a straight street or side-by-side strips never create a junction.
    Steps per tile (res m pixels, tile + pad overlap): rasterise, skeletonise, prune spurs
    shorter than `prune` m (iterative end-point removal; corner/width artefacts of the medial
    axis), take clusters of skeleton pixels where >= 3 segments meet, merge within `merge` m.
    Returns (x, y, degree, kind) with kind 2 (skeleton); degree = max branch count in the cluster."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from skimage.morphology import skeletonize
    K8 = np.ones((3, 3)); K8[1, 1] = 0
    b = shapely.bounds(road_geoms_m)
    tree = STRtree(road_geoms_m)
    X0, Y0 = np.floor(b[:, 0].min()/tile)*tile, np.floor(b[:, 1].min()/tile)*tile
    tx = np.floor((b[:, 0] + b[:, 2])/2/tile - X0/tile).astype(int); ty = np.floor((b[:, 1] + b[:, 3])/2/tile - Y0/tile).astype(int)
    px, py, pd_ = [], [], []
    n = int((tile + 2*pad)/res)
    for cx, cy in sorted(set(zip(tx, ty))):
        x0, y0 = X0 + cx*tile - pad, Y0 + cy*tile - pad
        idx = tree.query(shapely.box(x0, y0, x0 + tile + 2*pad, y0 + tile + 2*pad))
        if len(idx) == 0: continue
        img = Image.new('1', (n, n), 0); dr = ImageDraw.Draw(img)
        for gg in road_geoms_m[idx]:
            for p in getattr(gg, 'geoms', [gg]):
                if p.geom_type != 'Polygon' or p.is_empty: continue
                e = np.asarray(p.exterior.coords); dr.polygon([(u, v) for u, v in zip((e[:, 0]-x0)/res, (n - (e[:, 1]-y0)/res))], fill=1)
                for h in p.interiors:
                    e = np.asarray(h.coords); dr.polygon([(u, v) for u, v in zip((e[:, 0]-x0)/res, (n - (e[:, 1]-y0)/res))], fill=0)
        a = np.array(img, bool)
        a = ndimage.binary_closing(a, iterations=1)                 # seal 1-px slivers between touching parcels
        if bridge > 0:                                              # bridge short gaps between road parcels
            r_ = int(round(bridge/2/res)); yy, xx = np.mgrid[-r_:r_+1, -r_:r_+1]
            a = ndimage.binary_closing(a, structure=(xx**2 + yy**2) <= r_*r_)
        s = skeletonize(a)
        for _ in range(int(prune/res)):                             # spur pruning
            nb = ndimage.convolve(s.astype(np.uint8), K8, mode='constant')
            s &= ~(nb <= 1)
        # branch points: clusters of skeleton pixels with >= 3 neighbours, kept when >= 3 distinct
        # skeleton segments leave the cluster (a staircase pixel on a plain curve splits it into 2)
        nb = ndimage.convolve(s.astype(np.uint8), K8, mode='constant')
        J = s & (nb >= 3)
        lj, nj = ndimage.label(J, np.ones((3, 3)))
        if nj == 0: continue
        ls, _ = ndimage.label(s & ~J, np.ones((3, 3)))
        H, Wd = s.shape; pairs = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0: continue
                a_ = lj[max(0, -dy):H - max(0, dy), max(0, -dx):Wd - max(0, dx)]
                b_ = ls[max(0, dy):H - max(0, -dy) or None, max(0, dx):Wd - max(0, -dx) or None]
                m_ = (a_ > 0) & (b_ > 0); pairs.append(a_[m_].astype(np.int64)*10_000_000 + b_[m_])
        up = np.unique(np.concatenate(pairs)); nbr = np.bincount((up // 10_000_000).astype(int), minlength=nj + 1)
        com = ndimage.center_of_mass(J, lj, np.arange(1, nj + 1)); com = np.array(com).reshape(-1, 2)
        keep = nbr[1:] >= 3
        r, c = com[keep, 0], com[keep, 1]; dval = nbr[1:][keep]
        xs, ys = x0 + (c + 0.5)*res, y0 + (n - r - 0.5)*res
        core = (xs >= x0 + pad) & (xs < x0 + pad + tile) & (ys >= y0 + pad) & (ys < y0 + pad + tile)
        px.append(xs[core]); py.append(ys[core]); pd_.append(dval[core])
    x, y, d = np.concatenate(px), np.concatenate(py), np.concatenate(pd_)
    pairs = cKDTree(np.c_[x, y]).query_pairs(merge, output_type='ndarray')
    G = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(x), len(x)))
    _, lab = connected_components(G, directed=False)
    cnt = np.bincount(lab)
    jx, jy = np.bincount(lab, x)/cnt, np.bincount(lab, y)/cnt
    deg = np.zeros(len(cnt), int); np.maximum.at(deg, lab, d)
    return jx, jy, deg, np.full(len(cnt), 2)
