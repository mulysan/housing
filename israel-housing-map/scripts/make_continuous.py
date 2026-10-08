# One-off edit of map_v4_template.html (2026-10-08): continuous colour scales instead of classes.
#  - Parcel map: each numeric metric maps its value onto the spectral scale between fixed bounds (log
#    scale for skewed, positive variables; linear otherwise); values outside are clamped. Drawing uses
#    64 colour levels (visually continuous, one canvas fill per level). The renewal metric stays
#    categorical (three outcomes). Legend: a gradient bar with ticks.
#  - Variable map: the same, with bounds at the 2nd and 98th percentiles of the values pooled over all
#    years (so a colour means the same value in every year), log scale for the variables flagged log.
#    The unit histogram colours each bar by its own value on the same scale.
s = open('map_v4_template.html').read()
def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:90]); s = s.replace(a, b)

# ---- shared helpers (after spectral)
rep("""  const AR = J('areas-data'), AREA = Object.fromEntries(AR.areas.map(a => [a.key, a]));""",
    """  // continuous scale: value -> t in [0,1] between lo and hi (log or linear), clamped
  const scaleT = (v, lo, hi, lg) => { if (v == null || !isFinite(v) || (lg && v <= 0)) return null;
    const t = lg ? Math.log(v/lo)/Math.log(hi/lo) : (v - lo)/(hi - lo); return Math.max(0, Math.min(1, t)); };
  const scaleV = (t, lo, hi, lg) => lg ? lo*Math.pow(hi/lo, t) : lo + (hi - lo)*t;
  const gradCSS = () => 'linear-gradient(to right,' + Array.from({ length: 11 }, (_, k) => spectral(k/10)).join(',') + ')';
  const gradBar = (lo, hi, lg, f, nt = 5) => `<div dir="ltr" style="margin:4px 2px 0"><div style="height:12px;border-radius:3px;background:${gradCSS()}"></div>` +
    `<div style="display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-top:2px;font-variant-numeric:tabular-nums">` +
    Array.from({ length: nt }, (_, k) => `<span>${f(scaleV(k/(nt-1), lo, hi, lg))}</span>`).join('') + `</div></div>`;
  const AR = J('areas-data'), AREA = Object.fromEntries(AR.areas.map(a => [a.key, a]));""")

# ---- parcel map metrics: continuous domains
rep("""    price:{ title:'מחיר למ"ר, 2023–2026 (₪)', breaks:""", """    price:{ title:'מחיר למ"ר, 2023–2026 (₪)', cont:[8000, 50000, true], tf: v => fmt(Math.round(v/1000)) + 'K', breaks:""")
rep("""    chg:{ title:'שינוי במחיר למ"ר בגוש, 2014–16 עד 2023–25', breaks:""", """    chg:{ title:'שינוי במחיר למ"ר בגוש, 2014–16 עד 2023–25', cont:[0, 1.2, false], tf: v => '+' + Math.round(v*100) + '%', breaks:""")
rep("""    turn:{ title:'עסקאות ל־100 דירות בשנה (גוש)', breaks:""", """    turn:{ title:'עסקאות ל־100 דירות בשנה (גוש)', cont:[0.01, 0.08, true], tf: v => (v*100).toFixed(1), breaks:""")
rep("""    fl:{ title:'קומות בבניין', breaks:""", """    fl:{ title:'קומות בבניין', cont:[1, 40, true], tf: v => Math.round(v), breaks:""")
rep("""    dec:{ title:'עשור הבנייה', breaks:""", """    dec:{ title:'עשור הבנייה', cont:[194, 202, false], tf: v => Math.round(v)*10, breaks:""")
rep("""    junc:{ title:'צמתים לקמ"ר של שטח עירוני', breaks:""", """    junc:{ title:'צמתים לקמ"ר של שטח עירוני', cont:[15, 200, true], tf: v => Math.round(v), breaks:""")
rep("""    bfe:{ title:'אפקט קבוע של בניין: מחיר למ"ר מול הממוצע', breaks:""", """    bfe:{ title:'אפקט קבוע של בניין: מחיר למ"ר מול הממוצע', cont:[-0.6, 0.6, false], tf: v => (v >= 0 ? '+' : '') + Math.round((Math.exp(v)-1)*100) + '%', breaks:""")

# classify: 64 levels for continuous metrics
rep("""    const classify = () => { const m = METRICS[metric], f = val[metric]; counts = new Array(m.tokens.length + 1).fill(0);
      for (let i = 0; i < n; i++) { const v = f(i); const k = (v === null || v === undefined) ? 255 : (metric === 'ren' ? v : cls(m, v));
        klass[i] = k; counts[k === 255 ? m.tokens.length : k]++; } };""",
    """    const NL = 64;                                    // colour levels for continuous metrics
    const nCls = m => m.cont ? NL : m.tokens.length;
    const classify = () => { const m = METRICS[metric], f = val[metric], K = nCls(m); counts = new Array(K + 1).fill(0);
      for (let i = 0; i < n; i++) { const v = f(i); let k;
        if (v === null || v === undefined) k = 255;
        else if (m.cont) { const t = scaleT(v, m.cont[0], m.cont[1], m.cont[2]); k = t === null ? 255 : Math.min(NL - 1, Math.floor(t*NL)); }
        else k = metric === 'ren' ? v : cls(m, v);
        klass[i] = k; counts[k === 255 ? K : k]++; } };""")
rep("""    const readColors = () => { const m = METRICS[metric], K = m.tokens.length; colors = m.tokens.map((_, i) => spectral(K === 1 ? 0 : i/(K-1))); nodata = tok('--nodata'); };""",
    """    const readColors = () => { const m = METRICS[metric], K = nCls(m);
      colors = m.cont ? Array.from({ length: NL }, (_, i) => spectral((i + 0.5)/NL)) : m.tokens.map((_, i) => spectral(K === 1 ? 0 : i/(K-1))); nodata = tok('--nodata'); };""")
# legend
rep("""    const drawLegend = () => { const m = METRICS[metric];
      legend.innerHTML = `<h3>${m.title}</h3>` + m.labels.map((l,k) =>""",
    """    const drawLegend = () => { const m = METRICS[metric];
      if (m.cont) { const K = NL, nd = counts[K], tot = counts.reduce((a, b) => a + b, 0);
        legend.innerHTML = `<h3>${m.title}</h3>` + gradBar(m.cont[0], m.cont[1], m.cont[2], m.tf) +
          `<div class="row"><span class="sw" style="background:${nodata}"></span><span>אין נתון</span><span class="n">${fmt(nd)}</span></div>` +
          `<div class="note">${m.note} סולם רציף${m.cont[2] ? ' לוגריתמי' : ''}; ערכים מחוץ לטווח נצבעים בקצה. ${fmt(tot - nd)} חלקות עם נתון.</div>`; fixBidi(legend);
        document.getElementById('metricInfo').innerHTML = `<h3>${m.title}</h3><p>${m.note}</p><div class="card">${gradBar(m.cont[0], m.cont[1], m.cont[2], m.tf)}</div>`;
        fixBidi(document.getElementById('metricInfo')); return; }
      legend.innerHTML = `<h3>${m.title}</h3>` + m.labels.map((l,k) =>""")

# ---- variable map: continuous scale between p2 and p98 of the pooled values
rep("""      const br = [1,2,3,4,5,6].map(j => quant(pool, j/7)).filter((x, i, a) => isFinite(x) && (i === 0 || x > a[i-1]));
      const col = x => { if (x == null || !isFinite(x)) return null; let i = 0; while (i < br.length && x >= br[i]) i++; return spectral(br.length ? i/br.length : 0.5); };""",
    """      const pos = pool.filter(x => x != null && isFinite(x) && (!v.lg || x > 0)), lgS = v.lg && pos.length > 0;
      const lo = quant(pos, 0.02), hi = quant(pos, 0.98), same = !(hi > lo);
      const br = [];
      const col = x => { if (x == null || !isFinite(x)) return null; if (same) return spectral(0.5); const t = scaleT(lgS ? Math.max(x, lo) : x, lo, hi, lgS); return t === null ? null : spectral(t); };""")
rep("""      const edges = [null, ...br, null];
      document.getElementById('vleg').innerHTML = `<h3>${v.lab}${v.yearly ? ' · ' + y : ''}</h3>` + edges.slice(0, -1).map((e, i) =>
        `<div class="row"><span class="sw" style="background:${spectral(br.length ? i/br.length : 0.5)}"></span><span>${e == null ? 'עד ' + fmtV(v, edges[1]) : edges[i+1] == null ? fmtV(v, e) + ' ומעלה' : fmtV(v, e) + ' – ' + fmtV(v, edges[i+1])}</span><span></span></div>`).join('') +
        `<div class="row"><span class="sw" style="background:#BEBEBE"></span><span>אין נתון</span><span></span></div>`;""",
    """      document.getElementById('vleg').innerHTML = `<h3>${v.lab}${v.yearly ? ' · ' + y : ''}</h3>` + gradBar(lo, hi, lgS, x => fmtV(v, x)) +
        `<div class="row"><span class="sw" style="background:#BEBEBE"></span><span>אין נתון</span><span></span></div>` +
        `<div class="note">סולם רציף${lgS ? ' לוגריתמי' : ''} בין האחוזון ה־2 ל־98 של כל השנים יחד.</div>`;""")
rep("""        counts.forEach((c, j) => { s += `<rect x="${L0 + j*bw + 0.5}" y="${yy(c)}" width="${Math.max(bw-1, 0.5)}" height="${H - B - yy(c)}" fill="${spectral(j/(n-1))}" opacity="0.9">""",
    """        counts.forEach((c, j) => { const mid = v_.lg && edges_[j] > 0 ? Math.sqrt(edges_[j]*edges_[j+1]) : (edges_[j] + edges_[j+1])/2;
          s += `<rect x="${L0 + j*bw + 0.5}" y="${yy(c)}" width="${Math.max(bw-1, 0.5)}" height="${H - B - yy(c)}" fill="${col(mid) || spectral(j/(n-1))}" opacity="0.9">""")
rep("""      const lo = quant(pool.filter(x => !v.lg || x > 0), 0.01), hi = quant(pool.filter(x => !v.lg || x > 0), 0.99);
      const nb = 20, edgesH = Array.from({ length: nb+1 }, (_, j) => v.lg && lo > 0 ? lo*Math.pow(hi/lo, j/nb) : lo + (hi - lo)*j/nb);""",
    """      const hlo = quant(pool.filter(x => !v.lg || x > 0), 0.01), hhi = quant(pool.filter(x => !v.lg || x > 0), 0.99);
      const nb = 20, edgesH = Array.from({ length: nb+1 }, (_, j) => v.lg && hlo > 0 ? hlo*Math.pow(hhi/hlo, j/nb) : hlo + (hhi - hlo)*j/nb);""")
open('map_v4_template.html', 'w').write(s)
print('ok')
