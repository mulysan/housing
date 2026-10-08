# govmap deals with a parsed unit floor, CPI-deflated log price per m2 and building height
# (gazetteer max floors, or the highest floor sold). Shared by build_floor.py and build_floor_groups.py.
import re, numpy as np, pandas as pd, duckdb
def load():
    D = pd.read_csv('govmap_deals.csv', dtype={'floor': str, 'nature': str}, keep_default_na=False)
    for c in ['gush', 'parcel', 'sub', 'amount', 'area', 'rooms']: D[c] = pd.to_numeric(D[c], errors='coerce')
    D['dt'] = pd.to_datetime(D.date, errors='coerce')
    D = D[D.dt.between('1998-01-01', '2026-09-30') & D.nature.isin(['דירה בבית קומות', 'דירה'])]
    D = D[(D.area.between(25, 400)) & (D.amount >= 150000) & (D.amount/D.area).between(1500, 150000)]
    D = D.drop_duplicates(['gush', 'parcel', 'sub', 'date', 'amount'])

    ORD = {'קרקע': 0, 'ראשונה': 1, 'שניה': 2, 'שנייה': 2, 'שלישית': 3, 'רביעית': 4, 'חמישית': 5, 'שישית': 6, 'שביעית': 7,
           'שמינית': 8, 'תשיעית': 9, 'עשירית': 10}
    UNITS = {'אחת': 1, 'אחד': 1, 'שתים': 2, 'שתיים': 2, 'שניים': 2, 'שלוש': 3, 'ארבע': 4, 'חמש': 5, 'שש': 6, 'שבע': 7, 'שמונה': 8, 'תשע': 9}
    TENS = {'עשרים': 20, 'שלושים': 30, 'ארבעים': 40, 'חמישים': 50}
    def parse_floor(s):
        s = re.sub(r'[‎‏]', '', s or '').strip()
        if not s: return np.nan
        m = re.fullmatch(r'קומה\s*(-?\d+)', s) or re.fullmatch(r'(-?\d+)', s)
        if m: return int(m.group(1))
        if s in ORD: return ORD[s]
        m = re.fullmatch(r'(\S+) עשרה', s)                     # 11-19: "אחת עשרה"
        if m and m.group(1) in UNITS: return 10 + UNITS[m.group(1)]
        if s in TENS: return TENS[s]
        m = re.fullmatch(r'(\S+) ו(\S+)', s)                    # 21-59: "עשרים ושלוש"
        if m and m.group(1) in TENS and m.group(2) in UNITS: return TENS[m.group(1)] + UNITS[m.group(2)]
        return np.nan                                          # duplexes, letters, basements, blanks
    fl = {v: parse_floor(v) for v in D.floor.unique()}
    D['fl'] = D.floor.map(fl)
    print('deals', len(D), 'with parsed floor', D.fl.notna().mean().round(3))
    D = D[D.fl.between(0, 60)]

    cx = pd.read_excel('cpi.xlsx'); cx['date'] = cx['date'].astype(str).str[:7]
    cs = cx.set_index('date').cpi
    D['ym'] = D.dt.dt.to_period('M').astype(str)
    D['lp'] = np.log(D.amount/D.area / D.ym.map(cs.reindex(sorted(D.ym.unique())).ffill()))
    D['bld'] = D.gush.astype(np.int64)*100000 + D.parcel
    g = duckdb.connect('h.db', read_only=True).sql("select gush, parcel, fl from p").df()
    D = D.merge(g.rename(columns={'fl': 'bfl'}), on=['gush', 'parcel'], how='left')
    D['obs_max'] = D.groupby('bld').fl.transform('max')
    D['height'] = np.fmax(D.bfl.astype(float).fillna(0), D.obs_max.astype(float))          # building floors: gazetteer, or highest floor sold
    D = D[D.groupby('bld').bld.transform('size') >= 2]
    print('sample', len(D), 'buildings', D.bld.nunique())
    return D
