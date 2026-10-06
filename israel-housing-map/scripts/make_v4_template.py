# One-off: turn map_v3_template.html (one heavy page) into map_v4_template.html, a template for two
# pages built by build_page_v4.py: the map app (PAGE = 'map') and the analysis report (PAGE = 'report').
# Page-specific HTML sits between <!--MAP-->..<!--/MAP--> or <!--REPORT-->..<!--/REPORT-->; the JS
# branches on PAGE. The street background becomes OSM tiles fetched from roads/ (build_basemap_osm.py).
s = open('map_v3_template.html').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (s.count(a), a[:90])
    s = s.replace(a, b)
def cut(a, b):
    """return text from anchor a (inclusive) to anchor b (exclusive), removing it from s"""
    global s
    i = s.index(a); j = s.index(b, i)
    t = s[i:j]; s = s[:i] + s[j:]; return t

# ---------- title + headers ----------
rep('<title>מחירי הדיור בישראל לפי חלקה</title>', '<title>/*TITLE*/</title>')
rep('<div class="app" dir="rtl">', '<!--MAP-->\n<div class="app" dir="rtl">')
rep('''  <div class="apphead"><h1>מחירי הדיור בישראל לפי חלקה</h1>''',
    '''  <div class="apphead"><h1>מחירי הדיור בישראל לפי חלקה</h1><a class="xlink" href="/*OTHER_URL*/" target="_blank" rel="noopener">לניתוח המלא: מדדים, רגרסיות ומפת משתנים ←</a>''')
rep('<div class="wrap" dir="rtl">\n  <div class="kpis" id="kpis"></div>',
    '''<!--/MAP-->
<!--REPORT-->
<div class="apphead rephead" dir="rtl"><h1>ניתוח מחירי הדיור בישראל</h1><a class="xlink" href="/*OTHER_URL*/" target="_blank" rel="noopener">למפת החלקות האינטראקטיבית ←</a>
  <p class="sub">/*SUB*/</p></div>
<div class="wrap" dir="rtl">
  <div class="kpis" id="kpis"></div>''')
rep('<dialog id="areaDlg"', '<!--/REPORT-->\n<dialog id="areaDlg"')
rep('.apphead .sub{', '.xlink{color:#fff;font-weight:700;font-size:.92em;text-decoration:underline;text-decoration-color:#8fb3d9;text-underline-offset:3px}\n.xlink:hover{color:#f1c40f}\n.rephead{padding-block:14px}\n.apphead .sub{')
# street background option
rep('<option value="streets">רשת רחובות (מהקדסטר)</option>', '<option value="streets">רחובות (OpenStreetMap)</option>')
rep('<div class="osm-attr" id="osmattr" hidden>© OpenStreetMap contributors © CARTO</div>',
    '<div class="osm-attr" id="osmattr">© OpenStreetMap contributors</div>')

# ---------- data blocks per page ----------
for k in ['meta', 'pts', 'gush']:
    s = s.replace(f'<script type="application/json" id="{k}">', f'<!--MAP--><script type="application/json" id="{k}">', 1) if k != 'pts' else \
        s.replace('<script type="application/octet-stream" id="pts">', '<!--MAP--><script type="application/octet-stream" id="pts">', 1)
rep('<script type="application/octet-stream" id="pts">/*PTS*/</script>', '<script type="application/octet-stream" id="pts">/*PTS*/</script><!--/MAP-->')
rep('<script type="application/json" id="meta">/*META*/</script>', '<script type="application/json" id="meta">/*META*/</script><!--/MAP-->')
rep('<script type="application/json" id="gush">/*GUSH*/</script>', '<script type="application/json" id="gush">/*GUSH*/</script><!--/MAP-->')
for k, ph in [('res', 'RES'), ('txn-data', 'TXN'), ('urb-data', 'URB'), ('jval-data', 'JVAL'), ('floor-data', 'FLOOR'), ('hed-data', 'HED'), ('iv-data', 'IV')]:
    rep(f'<script type="application/json" id="{k}">/*{ph}*/</script>', f'<!--REPORT--><script type="application/json" id="{k}">/*{ph}*/</script><!--/REPORT-->')
rep('<script type="application/octet-stream" id="varmap">/*VARMAP*/</script>', '<!--REPORT--><script type="application/octet-stream" id="varmap">/*VARMAP*/</script><!--/REPORT-->')
rep('<script type="application/octet-stream" id="roads">/*ROADS*/</script>\n', '')

# ---------- JS ----------
rep("  const meta = J('meta'), gush = J('gush'), R = J('res'), land = J('land'), labels = J('labels');",
    "  const PAGE = '/*PAGE*/', isMap = PAGE === 'map';\n  const meta = isMap ? J('meta') : null, gush = isMap ? J('gush') : null, R = isMap ? null : J('res'), land = J('land'), labels = J('labels');")
# shared chart helpers (used by the area view on both pages): move barChart, yrs, lineChart, HCOL, keyHtml up
bar = cut('  const barChart = (id, cats, series, opts) => {', '  const ex = b => Math.exp(b) - 1;')
yl = cut("  const yrs = m => +m.slice(0,4)", '\n  // ---------- price indices: four methods ----------')
hc = cut("  const HCOL = [", "  document.getElementById('hkey').innerHTML = keyHtml;")
rep('  // ---------- metrics ----------', '  // ---------- shared chart helpers ----------\n' + bar + yl + '\n' + hc + '\n  // ---------- metrics ----------')
# the map app: everything from the map setup through the point decoding
rep('  // ---------- map ----------', '  if (isMap) {\n  // ---------- map ----------')
rep("  }).catch(err => { document.getElementById('status').textContent = 'הדפדפן לא הצליח לפרוס את נתוני החלקות (' + err.message + ')'; });",
    "  }).catch(err => { document.getElementById('status').textContent = 'הדפדפן לא הצליח לפרוס את נתוני החלקות (' + err.message + ')'; });\n  }")
# report: KPIs .. floor premium
rep('  // ---------- KPIs ----------', '  if (!isMap) {\n  // ---------- KPIs ----------')
rep('  // ---------- side-panel tabs ----------', '  }\n  // ---------- side-panel tabs ----------')
# side panel area picker: map only
rep("  const areaSel = document.getElementById('areaSel'), areaSide = document.getElementById('areaSide');",
    "  if (isMap) {\n  const areaSel = document.getElementById('areaSel'), areaSide = document.getElementById('areaSide');")
rep("  renderArea(areaSide, 'IL', false);", "  renderArea(areaSide, 'IL', false);\n  }")
# explorer: report only
rep("  // explorer section: level chips + picker", "  if (!isMap) {\n  // explorer section: level chips + picker")
rep("  { let k = 'IL'; try { const t = localStorage.getItem('v3-area'); if (t && AREA[t]) k = t; } catch(e){} setEx(k); }",
    "  { let k = 'IL'; try { const t = localStorage.getItem('v3-area'); if (t && AREA[t]) k = t; } catch(e){} setEx(k); }\n  }")
# sources: whichever container exists
rep("  document.getElementById('srcbody').innerHTML = srcRows;", "  if (!isMap) document.getElementById('srcbody').innerHTML = srcRows;")
rep("  document.getElementById('srcSide').innerHTML = SRC.map(", "  if (isMap) document.getElementById('srcSide').innerHTML = SRC.map(")
rep("  fixBidi(document.getElementById('srcSide'));", "  if (isMap) fixBidi(document.getElementById('srcSide'));")
# variable map + IV: report only
rep("  // ---------- every variable: map + histograms, by year and unit ----------", "  if (!isMap) {\n  // ---------- every variable: map + histograms, by year and unit ----------")
rep("  fixBidi(document.querySelector('.wrap'));", "  }\n  if (!isMap) fixBidi(document.querySelector('.wrap'));")

# ---------- street background: OSM tiles fetched on demand ----------
a = s.index("  let ROADS = null; const rcv"); b = s.index("  map.on('moveend', drawRoads); map.on('resize', drawRoads);")
s = s[:a] + r'''  // OSM streets (build_basemap_osm.py): roads/major.txt for zoom < 12, 0.2-degree tiles roads/t_i_j.txt from zoom 12.
  // Files are base64 of gzip'd: uint32 n | uint8 class[n] | uint16 npts[n] | int32 first[2n] | int16 deltas (lon/lat x 1e5).
  const rcv = document.createElement('canvas'); rcv.className = 'leaflet-zoom-hide'; map.getPane('roads').appendChild(rcv);
  const rctx = rcv.getContext('2d'), RT = {}; let RIDX = null;
  const gunzip = async buf => { const u = new Uint8Array(buf); if (u[0] !== 0x1f || u[1] !== 0x8b) return buf;
    return new Response(new Blob([u]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer(); };
  const parseRoads = buf => { const n = new DataView(buf).getUint32(0, true);
    const k = new Uint8Array(buf.slice(4, 4 + n)), np = new Uint16Array(buf.slice(4 + n, 4 + 3*n)),
      first = new Int32Array(buf.slice(4 + 3*n, 4 + 11*n)), del = new Int16Array(buf.slice(4 + 11*n));
    let tot = 0; for (let r = 0; r < n; r++) tot += np[r];
    const X = new Int32Array(tot), Y = new Int32Array(tot), off = new Uint32Array(n), bb = new Int32Array(4*n);
    let q = 0, dq = 0;
    for (let r = 0; r < n; r++) { off[r] = q; let x = first[2*r], y = first[2*r+1], a0 = x, a1 = y, a2 = x, a3 = y;
      for (let j = 0; j < np[r]; j++) { if (j) { x += del[2*dq]; y += del[2*dq+1]; dq++; } X[q] = x; Y[q] = y;
        if (x < a0) a0 = x; if (x > a2) a2 = x; if (y < a1) a1 = y; if (y > a3) a3 = y; q++; }
      bb[4*r] = a0; bb[4*r+1] = a1; bb[4*r+2] = a2; bb[4*r+3] = a3; }
    return { n, k, np, X, Y, off, bb }; };
  const getRoads = name => { if (RT[name]) return RT[name] === 'wait' || RT[name] === 'fail' ? null : RT[name];
    RT[name] = 'wait';
    fetch('roads/' + name + '.txt').then(r => { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(t => Uint8Array.from(atob(t.trim()), c => c.charCodeAt(0)).buffer).then(gunzip)
      .then(b => { RT[name] = parseRoads(b); drawRoads(); }).catch(() => { RT[name] = 'fail'; });
    return null; };
  fetch('roads/index.json').then(r => r.json()).then(a => { RIDX = new Set(a.map(([i,j]) => i + '_' + j)); drawRoads(); }).catch(() => {});
  // width per class (0 motorway/trunk, 1 primary, 2 secondary/tertiary, 3 residential, 4 service, 5 footway) by zoom
  const RW = z => z < 10 ? [1.2, 0.8, 0, 0, 0, 0] : z < 12 ? [1.8, 1.3, 0, 0, 0, 0] : z < 13 ? [2.6, 2, 1.6, 0.9, 0.5, 0]
    : z < 14 ? [3.4, 2.8, 2.3, 1.6, 0.9, 0] : z < 15 ? [5, 4.2, 3.4, 2.6, 1.4, 0] : [7, 6, 5, 4, 2.2, 1];
  const drawRoads = () => {
    if (!map._loaded) return;                     // before the first fitBounds
    const size = map.getSize(), pad = size.multiplyBy(0.3), tl = map.containerPointToLayerPoint([0,0]).subtract(pad);
    const W = size.x + 2*pad.x, H = size.y + 2*pad.y, dpr = window.devicePixelRatio || 1;
    rcv.width = W*dpr; rcv.height = H*dpr; rcv.style.width = W+'px'; rcv.style.height = H+'px'; L.DomUtil.setPosition(rcv, tl);
    rctx.setTransform(dpr,0,0,dpr,0,0); rctx.clearRect(0,0,W,H);
    const z = map.getZoom(); if (bmsel.value !== 'streets' || z < 8) return;
    const sc = 256*Math.pow(2, z), po = map.getPixelOrigin(), ox = po.x + tl.x, oy = po.y + tl.y;
    const b = map.getBounds().pad(0.3), x0 = b.getWest()*1e5, x1 = b.getEast()*1e5, y0 = b.getSouth()*1e5, y1 = b.getNorth()*1e5;
    const sets = [];
    if (z < 12) { const m = getRoads('major'); if (m) sets.push(m); }
    else if (RIDX) { const bt = b.pad(0.15);
      for (let i = Math.floor(bt.getWest()*5); i <= Math.floor(bt.getEast()*5); i++)
        for (let j = Math.floor(bt.getSouth()*5); j <= Math.floor(bt.getNorth()*5); j++)
          if (RIDX.has(i + '_' + j)) { const t = getRoads('t_' + i + '_' + j); if (t) sets.push(t); } }
    const w = RW(z), px = v => (0.5 + v/36e6)*sc - ox,
      py = v => { const s_ = Math.sin(v/1e5*Math.PI/180); return (0.5 - Math.log((1+s_)/(1-s_))/(4*Math.PI))*sc - oy; };
    rctx.lineCap = 'round'; rctx.lineJoin = 'round';
    const path = cls => { rctx.beginPath();
      for (const R_ of sets) { const { n, k, np, X, Y, off, bb } = R_;
        for (let r = 0; r < n; r++) { if (k[r] !== cls || bb[4*r] > x1 || bb[4*r+2] < x0 || bb[4*r+1] > y1 || bb[4*r+3] < y0) continue;
          const o = off[r]; rctx.moveTo(px(X[o]), py(Y[o])); for (let j = 1; j < np[r]; j++) rctx.lineTo(px(X[o+j]), py(Y[o+j])); } } };
    const edge = tok('--road-edge'), fill = tok('--road');
    for (const pass of [0, 1]) for (let cls = 5; cls >= 0; cls--) { if (!w[cls]) continue; path(cls);
      if (cls === 5) { if (pass) continue; rctx.setLineDash([2, 2]); rctx.strokeStyle = edge; rctx.lineWidth = w[cls]; rctx.stroke(); rctx.setLineDash([]); continue; }
      rctx.strokeStyle = pass ? fill : edge; rctx.lineWidth = pass ? w[cls] : w[cls] + (z < 12 ? 0.8 : 1.4); rctx.stroke(); }
  };
''' + s[b:]
rep("const setBase = v => { bmsel.value = v; if (v === 'tiles') tiles.addTo(map); else tiles.remove(); oa.hidden = v !== 'tiles';",
    "const setBase = v => { bmsel.value = v; if (v === 'tiles') tiles.addTo(map); else tiles.remove(); oa.hidden = v === 'none'; oa.textContent = v === 'tiles' ? '© OpenStreetMap contributors © CARTO' : '© OpenStreetMap contributors';")
open('map_v4_template.html', 'w').write(s)
print('ok', len(s))
