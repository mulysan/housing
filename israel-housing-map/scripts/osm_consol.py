import numpy as np, sys
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
LAT0=31.8; KX=111320*np.cos(np.radians(LAT0)); KY=110574
def consol(lat, lon, r):
    xy=np.c_[lon*KX, lat*KY]; p=cKDTree(xy).query_pairs(r, output_type='ndarray')
    G=coo_matrix((np.ones(len(p)),(p[:,0],p[:,1])),shape=(len(xy),)*2)
    return connected_components(G,directed=False)[0]
if __name__=='__main__':
    d=np.loadtxt(sys.argv[1], usecols=(0,1))
    print(sys.argv[1], 'raw', len(d), {r: consol(d[:,0], d[:,1], r) for r in (10,15,20,25)})
