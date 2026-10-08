# Knesset election results by ballot box (Central Elections Committee, via over.org.il) and the
# locations of ballot boxes (govmap polling-station layers, via over.org.il).
#
# Results: Knesset 25 (Nov 2022) is the main measure; Knesset 24 (Mar 2021) and 23 (Mar 2020) are
#   kept for a stability check. Columns kept: locality code, ballot-box code, polling-place cluster,
#   eligible voters, valid votes, and the votes of the parties that identify the two groups:
#     Haredi parties: United Torah Judaism (letter ג) and Shas (שס).
#     Arab parties:   K25: Ra'am (עם), Hadash-Ta'al (ום), Balad (ד); K24: Ra'am (עם), Joint List (ודעם);
#                     K23: Joint List (ודעם).
# Locations: there is no location layer for the Knesset 25 boxes. govmap publishes the Knesset 26
#   ballot boxes ("טופס א'", the official list, and the final layer) with a point per box. Box
#   numbers are assigned within locality and are largely carried over between elections; the match
#   is validated in build_votes.py by comparing eligible voters per box across the two elections.
# Output: votes_k25.csv, votes_k24.csv, votes_k23.csv, boxes_k26a.csv, boxes_k26.csv
from q import *
import csv
TAB = {'k25': ('append_votes_knesset_76df52af', ['ג', 'שס', 'עם', 'ום', 'ד']),
       'k24': ('append_votes_knesset_447b5f9a', ['ג', 'שס', 'עם', 'ודעם']),
       'k23': ('append_votes_knesset_1c422fcc', ['ג', 'שס', 'ודעם'])}
def packed(q, key_cols, fn, header):
    """one row per locality (string_agg), exploded into fn; stays under the 1,000-row cap per request"""
    rows = sql(PAR, q)['rows']
    w = csv.writer(open(fn, 'w')); w.writerow(header); n = 0
    for r in rows:
        for it in r['s'].split('~'):
            w.writerow([r['y']] + it.split('|')); n += 1
    print(fn, n)
for k, (t, parties) in TAB.items():
    cols = ['"קלפי"', '"ריכוז"', '"בזב"', '"מצביעים"', '"כשרים"'] + [f'"{p}"' for p in parties]
    agg = "concat_ws('|', " + ', '.join(f"coalesce({c}::text,'')" for c in cols) + ")"
    for half in ['< 3000', '>= 3000']:
        # two requests (localities below / above code 3000) so neither returns more than 1,000 rows
        packed(f'''select "סמל ישוב" y, string_agg({agg}, '~') s from public.{t} where "סמל ישוב"::int {half} group by 1''',
               None, f'votes_{k}{"_a" if half[0] == "<" else "_b"}.csv',
               ['locality', 'box', 'cluster', 'eligible', 'voters', 'valid'] + ['p_' + p for p in parties])
for k, t in [('k26a', 'idx.govmap_235036_b85d02f9_1655625d'), ('k26', 'idx.govmap_243675_16d94168_777c7b7e')]:
    for half in ['< 3000', '>= 3000']:
        packed(f'''select settlement_code y, string_agg(concat_ws('|', polling_station_code, cluster_code, coalesce(eligible_voters,''),
                   round(extensions.ST_X(extensions.ST_PointOnSurface(geom))::numeric, 6), round(extensions.ST_Y(extensions.ST_PointOnSurface(geom))::numeric, 6)), '~') s
                   from {t} where settlement_code::int {half} group by 1''', None, f'boxes_{k}{"_a" if half[0] == "<" else "_b"}.csv',
               ['locality', 'box', 'cluster', 'eligible', 'lon', 'lat'])
# concatenate the halves
import pandas as pd, glob
for k in ['k25', 'k24', 'k23']:
    pd.concat([pd.read_csv(f'votes_{k}_a.csv'), pd.read_csv(f'votes_{k}_b.csv')]).to_csv(f'votes_{k}.csv', index=False)
for k in ['k26a', 'k26']:
    pd.concat([pd.read_csv(f'boxes_{k}_a.csv'), pd.read_csv(f'boxes_{k}_b.csv')]).to_csv(f'boxes_{k}.csv', index=False)
