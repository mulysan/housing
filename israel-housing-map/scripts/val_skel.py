# test junctions_skel on the validation boxes (parcels within 1.5 km of each box)
import pandas as pd, numpy as np, shapely, duckdb, sys, time
from roads import road_flags
from junctions import junctions_skel
LAT0=31.8; KX=111320*np.cos(np.radians(LAT0)); KY=110574
V=pd.read_csv('val_boxes.csv'); P=pd.read_parquet('parcel_geoms_xy.parquet')
res=set(map(tuple,duckdb.connect('h.db',read_only=True).sql("select gush,parcel from p").fetchall()))
out=[]
for i,b in V.iterrows():
    x0,x1,y0,y1=b.w*KX,b.e*KX,b.s*KY,b.n*KY
    S=P[((P.x0*KX).between(x0-1500,x1+1500))&((P.y0*KY).between(y0-1500,y1+1500))]
    g=shapely.from_wkt(S.wkt.values); g=np.where(shapely.is_valid(g),g,shapely.make_valid(g))
    gm=shapely.transform(g, lambda c: np.c_[c[:,0]*KX, c[:,1]*KY])
    road,_=road_flags(gm,S.gush.values.astype(np.int64),S.parcel.values.astype(np.int64),res)
    mw=float(sys.argv[2]) if len(sys.argv)>2 else 0
    env=shapely.get_exterior_ring(shapely.oriented_envelope(gm)); p0,p1,p2=(shapely.get_point(env,k) for k in range(3))
    s1=np.nan_to_num(shapely.distance(p0,p1)); s2=np.nan_to_num(shapely.distance(p1,p2)); hi=np.maximum(s1,s2); lo=np.minimum(s1,s2)
    wd=shapely.area(gm)/np.maximum(hi,1); strip=(hi/np.maximum(lo,.1)>=3.5)&(shapely.area(gm)/np.maximum(lo*hi,1)>0.6)
    rr=road&~(strip&(wd<mw))
    jx,jy,deg,_=junctions_skel(gm[rr], bridge=float(sys.argv[1]))
    k=(jx>x0)&(jx<x1)&(jy>y0)&(jy<y1); out.append(int(k.sum()))
    np.save(f'{"_".join(sys.argv[1:])}_box{i}.npy', np.c_[jx[k],jy[k],deg[k]])
tag='skel'+sys.argv[1]+('s'+sys.argv[2] if len(sys.argv)>2 else ''); V[tag]=out; V.to_csv('val_boxes.csv',index=False); print(V.drop(columns=['s','w','n','e','km2']).to_string())
