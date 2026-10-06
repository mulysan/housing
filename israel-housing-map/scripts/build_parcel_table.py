import duckdb, json
c=duckdb.connect()
c.execute("create table g as select * from read_csv('gazetteer.csv', all_varchar=true, header=true)")
R="Type in ('דירת מגורים','דירת מגורים חדשה')"
c.execute(f"""create table p as select GushNum gush, ParcelNum parcel, count(*) units,
  max(try_cast(BuildingFloors as int)) fl,
  median(try_cast(BuildingYear as int)) filter (where try_cast(BuildingYear as int) between 1870 and 2026) yr,
  avg((Type='דירת מגורים חדשה')::int) newreg, mode(SettlementNameHeb) city, mode(StreetNameHeb) street
  from g where {R} group by 1,2""")
print(c.execute("select count(*), count(fl), count(yr) from p").fetchall())
# renewal candidates: built <1980, <=4 floors
print('renewal cand parcels/units', c.execute("select count(*), sum(units) from p where yr<1980 and fl<=4").fetchall())
print('by decade bld', c.execute("select (yr//10)*10, count(*), round(avg(fl),1) from p where yr is not null group by 1 order by 1").fetchall())
c.execute("copy p to 'parcels_gaz.parquet'")
