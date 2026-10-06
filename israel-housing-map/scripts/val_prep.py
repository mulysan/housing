import pandas as pd, numpy as np, shapely, duckdb, json
from junctions import junctions, junctions_clean
from roads import road_flags
LAT0=31.8; KX=111320*np.cos(np.radians(LAT0)); KY=110574
res=set(map(tuple,duckdb.connect('h.db',read_only=True).sql("select gush,parcel from p").fetchall()))
P=pd.read_parquet('parcel_geoms_xy.parquet')
g=shapely.from_wkt(P.wkt.values); g=np.where(shapely.is_valid(g),g,shapely.make_valid(g))
gm=shapely.transform(g, lambda c: np.c_[c[:,0]*KX, c[:,1]*KY])
road,_=road_flags(gm, P.gush.values, P.parcel.values, res)
nx,ny,deg,kind=junctions_clean(gm[road])
np.save('junctions_clean_xy_m.npy', np.c_[nx,ny,deg,kind])
old=np.load('junctions_xy_m.npy')
print('old',len(old),'clean',len(nx))
# validation boxes: ~1x1 km around the units-weighted median location of each large city
B=pd.read_csv('bld_fe.csv'); cu=B.groupby('city').units.sum(); big=cu[cu>=20000].index
boxes=[]
for c in big:
    d=B[B.city==c].dropna(subset=['lat','lon'])
    w=d.units.values; o=np.argsort(d.lat.values); cl=np.cumsum(w[o]); lat=d.lat.values[o][np.searchsorted(cl,cl[-1]/2)]
    o=np.argsort(d.lon.values); cl=np.cumsum(w[o]); lon=d.lon.values[o][np.searchsorted(cl,cl[-1]/2)]
    boxes.append([c, round(lat-0.0045,5), round(lon-0.0053,5), round(lat+0.0045,5), round(lon+0.0053,5)])
def cnt(xy, b):
    X,Y=xy[:,0]/KX, xy[:,1]/KY
    return int(((Y>b[1])&(Y<b[3])&(X>b[2])&(X<b[4])).sum())
J=np.c_[nx,ny]
rows=[]
for b in boxes:
    area=(b[4]-b[2])*KX*(b[3]-b[1])*KY/1e6
    rows.append(b+[round(area,3), cnt(old,b), cnt(J,b)])
pd.DataFrame(rows,columns=['city','s','w','n','e','km2','old','clean']).to_csv('val_boxes.csv',index=False)
print(pd.read_csv('val_boxes.csv').to_string())
