import json, glob, collections, math, duckdb
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely import set_precision
geoms=collections.defaultdict(list)
for f in glob.glob('gushim/*.geojson'):
    for ft in json.load(open(f))['features']:
        try:
            g=shape(ft['geometry']); g=g if g.is_valid else g.buffer(0)
            geoms[str(ft['properties']['Name'])].append(g)
        except Exception: pass
c=duckdb.connect()
c.execute("create table p as select * from 'parcels_gaz.parquet'")
rows=c.execute("""select gush, count(*) filter (where fl is not null) bld, count(*) parcels, sum(units)::int units,
  avg(fl) mf,
  sum(units) filter (where fl>=9)/nullif(sum(units) filter (where fl is not null),0) s9,
  median(yr) yr,
  sum(units) filter (where yr<1980 and fl<=4)/nullif(sum(units) filter (where yr is not null and fl is not null),0) rn,
  mode(city) city
 from p group by 1""").fetchall()
feats=[]; mapped=0; tot=0
for gush,bld,parcels,units,mf,s9,yr,rn,city in rows:
    tot+=units
    if gush not in geoms: continue
    G=unary_union(geoms[gush])
    lat=G.centroid.y
    area_m2=G.area*(111320**2)*math.cos(math.radians(lat))
    if area_m2>1e6*10/1 and bld<5:  # oversized registration blocks (>10 km2, <5 bldgs)
        continue
    geom=set_precision(G.simplify(0.00004, preserve_topology=True),0.00001)
    if geom.is_empty: continue
    mapped+=units
    feats.append({"type":"Feature","geometry":mapping(geom),"properties":{
      "g":int(gush),"c":city or "","b":bld,"u":units,
      "f":round(mf,1) if mf is not None else None,
      "s":round(s9,3) if s9 is not None else None,
      "y":int(yr) if yr else None,
      "r":round(rn,3) if rn is not None else None,
      "d":round(units/(area_m2/1000),2) if area_m2>0 else None}})
print(len(feats),'gushim; units mapped',mapped,'of',tot)
s=json.dumps({"type":"FeatureCollection","features":feats},separators=(',',':'),ensure_ascii=False)
open('gush_v2.json','w').write(s); print(len(s)/1e6,'MB')
ds=sorted(f['properties']['d'] for f in feats if f['properties']['d']); print('density q',[ds[int(len(ds)*q)] for q in (.1,.25,.5,.75,.9,.97)])
rs=sorted(f['properties']['r'] for f in feats if f['properties']['r'] is not None); print('renew q',[rs[int(len(rs)*q)] for q in (.1,.25,.5,.75,.9)], len(rs))
ys=sorted(f['properties']['y'] for f in feats if f['properties']['y']); print('yr q',[ys[int(len(ys)*q)] for q in (.1,.25,.5,.75,.9)], len(ys))
# decade summary (national) + renewal by city
dec=c.execute("""select (floor(yr/10)*10)::int d, count(*) bld, sum(units)::int units, round(avg(fl),2) mf,
  round(sum(units) filter (where fl>=9)/sum(units) filter (where fl is not null),3) s9
  from p where yr between 1920 and 2025 group by 1 order by 1""").fetchall()
ren=c.execute("""select city, sum(units)::int units,
  round(sum(units) filter (where yr<1980 and fl<=4)/sum(units) filter (where yr is not null and fl is not null),3) rn,
  (sum(units) filter (where yr<1980 and fl<=4))::int rn_units
  from p where city is not null group by 1 having sum(units)>=20000 order by rn desc""").fetchall()
json.dump({'decades':dec,'renewal':ren},open('summary_v2.json','w'),ensure_ascii=False)
print(dec); print(ren[:8]); print(ren[-5:])
