# Road-parcel classifier shared by build_urban.py and build_basemap.py.
import numpy as np, shapely
def road_flags(gm, gush, parcel, res_set):
    """Road-like parcel: not residential, and either an elongated strip (envelope >= 3.5:1,
    short side <= 40 m), a thin curvy strip (compactness < 0.16, width < 40 m), or a branching /
    curving strip that fills under 40% of its envelope with width < 30 m, or a long
    gently curved strip (envelope >= 5:1, mean width 2A/L < 30 m) whose envelope is wider than 40 m."""
    A = shapely.area(gm); L = shapely.length(gm)
    comp = 4*np.pi*A/np.maximum(L, 1)**2; w = 2*A/np.maximum(L, 1)
    ring = shapely.get_exterior_ring(shapely.oriented_envelope(gm))   # None for degenerate envelopes
    p0, p1, p2 = (shapely.get_point(ring, k) for k in range(3))
    s1 = shapely.distance(p0, p1); s2 = shapely.distance(p1, p2)
    s1 = np.where(np.isfinite(s1), s1, np.sqrt(A)); s2 = np.where(np.isfinite(s2), s2, np.sqrt(A))
    lo, hi = np.minimum(s1, s2), np.maximum(s1, s2)
    fill = A/np.maximum(lo*hi, 1)
    isres = np.array([(a, b) in res_set for a, b in zip(gush, parcel)])
    road = ~isres & (A > 120) & (((hi/np.maximum(lo, 0.1) >= 3.5) & (lo <= 40)) | ((comp < 0.16) & (w < 40)) | ((fill < 0.4) & (w < 30)) | ((hi/np.maximum(lo, 0.1) >= 5) & (w < 30)))
    return road, A
