import json, glob, duckdb, collections
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely import set_precision
# polygons by gush
geoms=collections.defaultdict(list)
for f in glob.glob('gushim/*.geojson'):
    for ft in json.load(open(f))['features']:
        try:
            g=shape(ft['geometry'])
            if not g.is_valid: g=g.buffer(0)
            geoms[str(ft['properties']['Name'])].append(g)
        except Exception: pass
c=duckdb.connect()
c.execute("create table g as select * from read_csv('gazetteer.csv', all_varchar=true, header=true)")
R="Type in ('דירת מגורים','דירת מגורים חדשה')"
# building = gush-parcel; floors = max over units in parcel
rows=c.execute(f"""
with p as (
  select GushNum gush, ParcelNum parcel, count(*) units, max(try_cast(BuildingFloors as int)) fl,
    median(try_cast(BuildingYear as int)) filter (where try_cast(BuildingYear as int) between 1850 and 2026) yr,
    mode(SettlementNameHeb) city
  from g where {R} group by 1,2)
select gush, count(*) filter (where fl is not null) bld, sum(units) units,
  sum(units) filter (where fl is not null) units_f,
  avg(fl) mean_bld, sum(fl*units)/sum(units) filter (where fl is not null) mean_unit,
  sum(units) filter (where fl>=9)/sum(units) filter (where fl is not null) share9,
  median(yr) yr, mode(city) city
from p group by 1""").fetchall()
feats=[]; miss=0; tot_units=0; map_units=0
for gush,bld,units,units_f,mb,mu,s9,yr,city in rows:
    tot_units+=units
    if not bld or gush not in geoms: miss+=1; continue
    geom=unary_union(geoms[gush]).simplify(0.00004, preserve_topology=True)
    geom=set_precision(geom, 0.00001)
    if geom.is_empty: continue
    map_units+=units
    feats.append({"type":"Feature","geometry":mapping(geom),
      "properties":{"g":int(gush),"c":city or "","b":bld,"u":int(units),"f":round(mb,1),"s":round(s9 or 0,3),"y":int(yr) if yr else None}})
print(len(feats),'mapped gushim; missing',miss,'; units mapped',map_units,'of',tot_units)
gj={"type":"FeatureCollection","features":feats}
s=json.dumps(gj,separators=(',',':'),ensure_ascii=False)
open('gush_floors.json','w').write(s); print(len(s)/1e6,'MB')
import statistics
fs=sorted(f['properties']['f'] for f in feats); print('mean_bld quantiles',[fs[int(len(fs)*q)] for q in (.1,.25,.5,.75,.9,.97,.99)])
