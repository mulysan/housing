# One-off edit of map_v4_template.html (2026-10-08): coefficients in natural units (build_urban_reg.py):
# log variables -> elasticity, shares -> % per 10 percentage points, indices -> % per SD. Keys _z -> _x.
s = open('map_v4_template.html').read()
def rep(a, b, n=1):
    global s; assert s.count(a) == n, (s.count(a), a[:90]); s = s.replace(a, b)
s = s.replace("_z:'", "_x:'").replace("_z')", "_x')").replace(".l_junc_z", ".l_junc_x").replace("v + '_z'", "v + '_x'")
# shared formatter
rep("""  const pc = b => Math.exp(b) - 1, sg = v => (v >= 0 ? '+' : '') + (v*100).toFixed(1) + '%';""",
"""  const pc = b => Math.exp(b) - 1, sg = v => (v >= 0 ? '+' : '') + (v*100).toFixed(1) + '%';
  // coefficient in the variable's natural unit: log -> elasticity, share -> % per 10 pp, index -> % per SD
  const UU = (UR.units || {}), unitOf = k => UU[k.replace(/_x$/, '')] || 'sd';
  const ef = (k, b) => b == null ? '—' : unitOf(k) === 'log' ? (b >= 0 ? '+' : '−') + Math.abs(b).toFixed(3) : sg(pc(b));
  const efse = (k, b, se) => b == null ? '—' : unitOf(k) === 'log' ? `${ef(k, b)} (${se.toFixed(3)})` : `${sg(pc(b))} (${(se*100).toFixed(1)})`;
  const UNITLAB = { log: 'גמישות', '10pp': 'ל־10 נק"א', sd: 'לסטיית תקן' };""")
# main coefficient table
rep("""      const b = m.b[k]; if (b == null) return '<td class="num">—</td>'; const t = Math.abs(b / m.se[k]);
      return `<td class="num"${t >= 2 ? ' style="font-weight:700;color:var(--fg)"' : ' style="color:var(--muted)"'}>${sg(pc(b))}</td>`; }).join('') + '</tr>').join('') +""",
"""      const b = m.b[k]; if (b == null) return '<td class="num">—</td>'; const t = Math.abs(b / m.se[k]);
      return `<td class="num"${t >= 2 ? ' style="font-weight:700;color:var(--fg)"' : ' style="color:var(--muted)"'}>${ef(k, b)}</td>`; }).join('') + '</tr>').join('') +""")
rep("""  document.getElementById('ucoef').innerHTML = Object.keys(ULAB).map(k => `<tr><td>${ULAB[k]}</td>` + models.map(m => {""",
"""  document.getElementById('ucoef').innerHTML = Object.keys(ULAB).map(k => `<tr><td>${ULAB[k]}</td><td style="color:var(--muted);font-size:12px">${UNITLAB[unitOf(k)]}</td>` + models.map(m => {""")
rep("""    `<tr><td>R²</td>${models""", """    `<tr><td>R²</td><td></td>${models""")
rep("""    `<tr><td>בניינים</td>${models""", """    `<tr><td>בניינים</td><td></td>${models""")
rep("""<thead><tr><th>משתנה</th><th class="num">צורה בלבד</th>""", """<thead><tr><th>משתנה</th><th>יחידה</th><th class="num">צורה בלבד</th>""")
rep("""        <p class="lede">אחוז השינוי במחיר הבניין למ"ר כשהמשתנה עולה בסטיית תקן אחת. מודגש = לפחות 2 שגיאות תקן מאפס (מקובצות לפי אזור סטטיסטי).</p>""",
"""        <p class="lede">כל משתנה ביחידות הטבעיות שלו. משתנה בלוג: גמישות, כלומר אחוז השינוי במחיר הבניין לאחוז שינוי במשתנה (הכפלה של המשתנה = 2<sup>β</sup>−1). שיעור: אחוז השינוי במחיר כשהשיעור עולה ב־10 נקודות אחוז. מדד בלי יחידה טבעית (עירוב שימושים, עקמומיות): אחוז השינוי לסטיית תקן. עסקים, תחנות וחניונים: לוג למי שיש לו, ועוד משתנה דמי לאזורים בלי אף אחד (לא מוצג). מודגש = לפחות 2 שגיאות תקן מאפס (מקובצות לפי אזור סטטיסטי).</p>""")
# junction lede
rep("""sd = UR.sd_raw.l_junc;""", """d2 = b => sg(Math.pow(2, b) - 1);""")
rep("""      `בכל הארץ, עלייה של סטיית תקן אחת בצמתים לקמ"ר (פי ${Math.exp(sd).toFixed(1)}) קשורה לשינוי של ${sg(pc(m1))} במחיר, כמעט אפס. כשמוסיפים""",
"""      `בכל הארץ, גמישות המחיר לצפיפות הצמתים היא ${m1.toFixed(3)}: אזור עם פי 2 צמתים לקמ"ר יקר ב־${d2(m1)}. כשמוסיפים""")
rep("""בתוך אותה עיר הוא ${sg(pc(mc))}, כי שכונות ותיקות עם רשת צפופה זולות יותר, ואחרי פיקוח על מעמד חברתי־כלכלי הוא ${sg(pc(mcs))}. `""",
"""בתוך אותה עיר הגמישות היא ${mc.toFixed(3)} (הכפלה: ${d2(mc)}), ואחרי פיקוח על מעמד חברתי־כלכלי ${mcs.toFixed(3)} (${d2(mcs)}). `""")
# junction validation note
rep("""nb = (v, i) => NC[v] ? sg(pc(NC[v].b[i])) : '—';""", """nb = (v, i) => NC[v] ? ef(v, NC[v].b[i]) : '—';""")
rep("""<b>הקשר למחיר:</b> בתוך העיר, ${nb('l_junc_osm',1)} לסטיית תקן בצמתים מ־OSM, לעומת""", """<b>הקשר למחיר:</b> בתוך העיר, גמישות של ${nb('l_junc_osm',1)} לצמתים מ־OSM, לעומת""")
# network table
rep("""    const cell = (b, se) => b == null ? '<td class="num">—</td>' : `<td class="num"${Math.abs(b/se) >= 2 ? ' style="font-weight:700;color:var(--fg)"' : ' style="color:var(--muted)"'}>${sg(pc(b))}</td>`;""",
"""    const cell = (v, b, se) => b == null ? '<td class="num">—</td>' : `<td class="num"${Math.abs(b/se) >= 2 ? ' style="font-weight:700;color:var(--fg)"' : ' style="color:var(--muted)"'}>${ef(v, b)}</td>`;""")
rep("""<td class="num">${lg(v) ? '×' + Math.exp(NC[v].sd).toFixed(2) : NC[v].sd.toFixed(2)}</td>` +
      [0,1,2].map(i => cell(NC[v].b[i], NC[v].se[i])).join('') + cell(ALL.b[v + '_x'], ALL.se[v + '_x']) + '</tr>').join('');""",
"""<td style="color:var(--muted);font-size:12px">${UNITLAB[unitOf(v)]}</td><td class="num">${lg(v) ? '×' + Math.exp(NC[v].sd).toFixed(2) : NC[v].sd.toFixed(2)}</td>` +
      [0,1,2].map(i => cell(v, NC[v].b[i], NC[v].se[i])).join('') + cell(v, ALL.b[v + '_x'], ALL.se[v + '_x']) + '</tr>').join('');""")
rep("""<thead><tr><th>מדד (אזור סטטיסטי)</th><th class="num">סטיית תקן</th>""", """<thead><tr><th>מדד (אזור סטטיסטי)</th><th>יחידה</th><th class="num">סטיית תקן</th>""")
rep("""`אחוז השינוי באפקט הבניין כשהמדד עולה בסטיית תקן אחת. כל מדד נבדק לבד, על אותו מדגם (${fmt(UR.net_cmp_n || 0)} בניינים).""",
"""`מדדים בלוג: גמישות. שיעורים: אחוז השינוי באפקט הבניין ל־10 נקודות אחוז. אנטרופיה: לסטיית תקן. כל מדד נבדק לבד, על הבניינים שיש להם ערך שלו; העמודה האחרונה על ${fmt(UR.net_cmp_n || 0)} בניינים שיש להם את כולם.""")
# commerce lede
rep("""const MC = UR.m_comm, f = (m, k) => `${sg(pc(m.b[k]))} (${(m.se[k]*100).toFixed(1)})`;""",
"""const MC = UR.m_comm, f = (m, k) => efse(k, m.b[k], m.se[k]), d2 = b => sg(Math.pow(2, b) - 1);""")
rep("""      `בכל הארץ, עלייה של סטיית תקן בצפיפות העסקים קשורה ל־${f(MC.l_comm[0], 'l_comm_x')} במחיר הבניין. בתוך אותה עיר נשאר ${f(MC.l_comm[1], 'l_comm_x')}, ועם אשכול חברתי־כלכלי ${f(MC.l_comm[2], 'l_comm_x')} (בסוגריים: שגיאת תקן באחוזים). `+""",
"""      `גמישות המחיר לצפיפות העסקים בכל הארץ: ${f(MC.l_comm[0], 'l_comm_x')}, כלומר פי 2 עסקים לקמ"ר = ${d2(MC.l_comm[0].b.l_comm_x)} במחיר. בתוך אותה עיר ${f(MC.l_comm[1], 'l_comm_x')} (הכפלה: ${d2(MC.l_comm[1].b.l_comm_x)}), ועם אשכול חברתי־כלכלי ${f(MC.l_comm[2], 'l_comm_x')} (בסוגריים: שגיאת תקן). אזורים בלי אף עסק נכנסים עם משתנה דמי ולא מוצגים בתרשים. `+""")
rep("""שיעור המסחר בשימושי הקרקע: ${f(MC.comm_share[0], 'comm_share_x')} בכל הארץ, ${f(MC.comm_share[1], 'comm_share_x')} בתוך העיר. `""",
"""שיעור המסחר בשימושי הקרקע, ל־10 נקודות אחוז: ${f(MC.comm_share[0], 'comm_share_x')} בכל הארץ, ${f(MC.comm_share[1], 'comm_share_x')} בתוך העיר. `""")
rep("""הצפיפות מחושבת לכל אזור סטטיסטי""", """הצפיפות מחושבת לכל אזור סטטיסטי""")
rep("""האחוז המדווח הוא exp(β)−1 לסטיית תקן.""", """משתנים בלוג נכנסים כלוג (β = גמישות), שיעורים ל־10 נקודות אחוז (מדווח exp(β)−1), ומדדים בלי יחידה טבעית מתוקננים (לסטיית תקן). עסקים, תחנות אוטובוס וחניונים: ln(x) כש־x > 0, ומשתנה דמי 1[x = 0] לאזורים בלי אף אחד, במקום ln(1+x) שתלוי ביחידות. מרחקים: ln(ק"מ + 0.2) לרכבת ולחוף ו־ln(ק"מ + 1) למרכז תל אביב.""")
open('map_v4_template.html', 'w').write(s); print('ok', s.count('_z'))
