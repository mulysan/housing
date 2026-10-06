import json, glob, duckdb
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely import set_precision
gs=[]
for f in glob.glob('gushim/*.geojson'):
    for ft in json.load(open(f))['features']:
        try:
            g=shape(ft['geometry']); g=g if g.is_valid else g.buffer(0); gs.append(g.simplify(0.0002))
        except Exception: pass
land=unary_union([g.buffer(0.0003) for g in gs]).buffer(-0.0003).simplify(0.0008, preserve_topology=True)
land=set_precision(land,0.0001)
s=json.dumps(mapping(land),separators=(',',':')); open('land.json','w').write(s); print('land',len(s)/1e6,'MB', land.bounds)
c=duckdb.connect()
c.execute("create table g as select * from read_csv('gazetteer.csv', all_varchar=true, header=true)")
R="Type in ('דירת מגורים','דירת מגורים חדשה')"
rows=c.execute(f"""with p as (select SettlementNameHeb city, GushNum, ParcelNum, count(*) units, max(try_cast(BuildingFloors as int)) fl from g where {R} and SettlementNameHeb is not null group by 1,2,3)
select city, count(*) filter (where fl is not null) bld, sum(units)::int units, round(avg(fl),1) mean_bld, round(sum(units) filter (where fl>=9)/sum(units) filter (where fl is not null),3) s9
from p group by 1 order by units desc limit 25""").fetchall()
json.dump(rows,open('cities.json','w'),ensure_ascii=False); 
for r in rows: print(r)
