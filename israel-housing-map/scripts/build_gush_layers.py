import duckdb, json
from shapely.geometry import shape
c=duckdb.connect()
c.execute("create table p as select * from 'parcels_gaz.parquet'")
c.execute("""create table gl as select gush,
  count(*) parcels, sum(units)::int units,
  count(fl) bld_f, avg(fl) mean_f,
  sum(units) filter (where fl>=9)/nullif(sum(units) filter (where fl is not null),0) s9,
  median(yr) yr,
  sum(units) filter (where yr<1980 and fl<=4)/nullif(sum(units) filter (where yr is not null and fl is not null),0) renew,
  mode(city) city
 from p group by 1""")
rows=c.execute("select * from gl").fetchall()
cols=[d[0] for d in c.description]
json.dump({'cols':cols,'rows':rows},open('gushlayers.json','w'),ensure_ascii=False,default=float)
print(len(rows)); print(rows[:3])
