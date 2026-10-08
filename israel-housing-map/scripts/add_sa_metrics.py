# One-off edit of map_v4_template.html (2026-10-08): every SA-level variable of the variable dictionary
# and the three building distances as colour options on the parcel map (meta.sa, built by
# build_page_v4.sa_table; point fields s, dc, dr, ds). Continuous scale between the parcel-weighted
# p2 and p98; definition and source from the dictionary in the legend note; value in the hover card.
s = open('map_v4_template.html').read()
def rep(a, b, n=1):
    global s; assert s.count(a) == n, (s.count(a), a[:90]); s = s.replace(a, b)
rep("""  let metric = 'price';
  try { const m""", """  // SA variables and building distances (map page only)
  const SAV = {}, vdNote = k => { const e = vdOf(k); return e ? `${e.d} מקור: ${VD.src[e.s] || e.s}.` : ''; };
  const numF = (v, share) => share ? (v*100).toFixed(v < 0.1 ? 1 : 0) + '%' : Math.abs(v) >= 100 ? fmt(Math.round(v)) : Math.abs(v) >= 10 ? v.toFixed(0) : Math.abs(v) >= 1 ? v.toFixed(1) : v.toFixed(2);
  if (isMap && meta.sa) {
    for (const d of meta.sa.vars) { SAV[d.k] = d;
      METRICS['sa_' + d.k] = { title: d.lab, cont: [d.lg ? Math.max(d.lo, 1e-3) : d.lo, d.hi > d.lo ? d.hi : d.lo + 1, d.lg], tf: v => numF(v, d.share),
        note: 'לפי האזור הסטטיסטי (2011) של החלקה. ' + vdNote(d.k), sa: d.k, share: d.share }; }
    for (const [k, f, t] of [['d_cbd', 'dc', 'מרחק למרכז תל אביב (ק"מ)'], ['d_rail', 'dr', 'מרחק לתחנת רכבת או רק"ל (ק"מ)'], ['d_coast', 'ds', 'מרחק לחוף (ק"מ)']])
      METRICS['dist_' + k] = { title: t, cont: [k === 'd_cbd' ? 2 : 0.3, k === 'd_cbd' ? 150 : 40, true], tf: v => numF(v, false), note: vdNote(k), field: f };
    METRICS.junc.note += ' ' + vdNote('junc_dens');
  }
  let metric = 'price';
  try { const m""")
rep("""      <option value="bfe">אפקט קבוע של בניין</option>
    </select>""", """      <option value="bfe">אפקט קבוע של בניין</option>
    </select>""")
# fill the select with groups after the static options (map page)
rep("""    const msel = document.getElementById('metric');""", """    const msel = document.getElementById('metric');
    if (!msel.dataset.grouped) { msel.dataset.grouped = '1';
      const og0 = document.createElement('optgroup'); og0.label = 'חלקה, בניין וגוש'; [...msel.options].forEach(o => og0.appendChild(o)); msel.appendChild(og0);
      const GR = [['מיקום (מרחק מהבניין)', k => k.startsWith('dist_')], ['אזור סטטיסטי: רשת רחובות', k => /junc|street|deadend|fourway|orient|circuity|road_share/.test(k)],
        ['אזור סטטיסטי: צפיפות, שימושים ומסחר', k => /units_dens|pop_dens|parcel_med|mix|comm_|school/.test(k)], ['אזור סטטיסטי: תחבורה וחניה', k => /bus|parking/.test(k)],
        ['אזור סטטיסטי: חברה והצבעה', k => /ses21|haredi|arab|turnout/.test(k)]];
      const extra = Object.keys(METRICS).filter(k => k.startsWith('sa_') || k.startsWith('dist_'));
      for (const [lab, f] of GR) { const og = document.createElement('optgroup'); og.label = lab;
        extra.filter(k => f(k.replace(/^sa_|^dist_/, ''))).forEach(k => { const o = document.createElement('option'); o.value = k; o.textContent = METRICS[k].title; og.appendChild(o); });
        if (og.children.length) msel.appendChild(og); }
      msel.value = metric; }""")
# value functions
rep("""      ren: i => { const f = F.f[i], d = F.d[i];""", """      ...Object.fromEntries(Object.entries(METRICS).filter(([, m]) => m.sa).map(([k, m]) => { const x = SAV[m.sa].x;
        return [k, i => F.s && F.s[i] ? x[F.s[i] - 1] ?? null : null]; })),
      ...Object.fromEntries(Object.entries(METRICS).filter(([, m]) => m.field).map(([k, m]) => [k, i => F[m.field] && F[m.field][i] ? (F[m.field][i] - 1)/100 : null])),
      ren: i => { const f = F.f[i], d = F.d[i];""")
# hover: selected metric value if it is an SA/distance metric
rep("""        (ren ? `<br><span class="k">ישן ונמוך:</span>""", """        ((METRICS[metric].sa || METRICS[metric].field) ? `<br><span class="k">${METRICS[metric].title}:</span> <b>${(v => v == null ? 'אין נתון' : METRICS[metric].tf(v))(val[metric](i))}</b>` : '') +
        (ren ? `<br><span class="k">ישן ונמוך:</span>""")
open('map_v4_template.html', 'w').write(s); print('ok')
