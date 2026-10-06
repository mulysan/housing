import pandas as pd, numpy as np, shapely, duckdb, sys
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from roads import road_flags
LAT0=31.8; KX=111320*np.cos(np.radians(LAT0)); KY=110574
V=pd.read_csv('val_boxes.csv')
P=pd.read_parquet('parcel_geoms_xy.parquet')
res=set(map(tuple,duckdb.connect('h.db',read_only=True).sql("select gush,parcel from p").fetchall()))
J=np.load('junctions_clean_xy_m.npy')
for i in map(int,sys.argv[1:]):
    b=V.iloc[i]; x0,x1,y0,y1=b.w*KX,b.e*KX,b.s*KY,b.n*KY; pad=300
    m=((P.x0*KX).between(x0-pad-800,x1+pad+800))&((P.y0*KY).between(y0-pad-800,y1+pad+800)); S=P[m]
    g=shapely.from_wkt(S.wkt.values); g=np.where(shapely.is_valid(g),g,shapely.make_valid(g))
    gm=shapely.transform(g, lambda c: np.c_[c[:,0]*KX, c[:,1]*KY])
    road,_=road_flags(gm,S.gush.values.astype(np.int64),S.parcel.values.astype(np.int64),res)
    box=shapely.box(x0,y0,x1,y1); cov=shapely.area(shapely.intersection(shapely.union_all(gm),box))/shapely.area(box)
    fig,ax=plt.subplots(figsize=(11,11))
    for gg,r in zip(gm,road):
        for p in getattr(gg,'geoms',[gg]):
            if p.geom_type!='Polygon': continue
            xy=np.asarray(p.exterior.coords); ax.fill(xy[:,0],xy[:,1],fc='#555' if r else '#eee',ec='#999',lw=.3)
    jj=J[(J[:,0]>x0)&(J[:,0]<x1)&(J[:,1]>y0)&(J[:,1]<y1)]
    ax.scatter(jj[:,0],jj[:,1],c=np.where(jj[:,3]==0,'red','orange'),s=25,zorder=5)
    ax.plot([x0,x1,x1,x0,x0],[y0,y0,y1,y1,y0],'b-'); ax.set_aspect('equal'); ax.set_xlim(x0-pad,x1+pad); ax.set_ylim(y0-pad,y1+pad)
    ax.set_title(f'{i} parcels {len(S)} road {road.sum()} cover {cov:.2f} junc {len(jj)}')
    plt.savefig(f'aud_box{i}.png',dpi=70,bbox_inches='tight'); print(i, len(S), road.sum(), round(cov,2), len(jj))
