# One-off edit of map_v4_template.html (2026-10-08): variable dictionary (var_dict.py, embedded as
# id="vardict"): definition/unit/source line under the variable-map selector, tooltip + info line on
# every area histogram, and a full table section "מילון משתנים" before the sources table.
s = open('map_v4_template.html').read()
def rep(a, b, n=1):
    global s; assert s.count(a) == n, (s.count(a), a[:90]); s = s.replace(a, b)
rep("""<script type="application/json" id="areas-data">/*AREAS*/</script>""",
    """<script type="application/json" id="areas-data">/*AREAS*/</script>
<script type="application/json" id="vardict">/*VARDICT*/</script>""")
rep("""      <button class="chip" id="vPlay" aria-pressed="false">הנפשה</button>
    </div>""", """      <button class="chip" id="vPlay" aria-pressed="false">הנפשה</button>
    </div>
    <p class="lede" id="vdef" style="font-size:13px;margin:6px 0 10px"></p>""")
rep("""הצבעים לפי שביעונים של כל השנים יחד, כך שאפשר להשוות בין שנים.""", """הצבעים בסולם רציף בין האחוזון ה־2 ל־98 של כל השנים יחד, כך שאפשר להשוות בין שנים. ההגדרה והמקור של כל משתנה מופיעים מתחת לבחירה, וכולם יחד במילון המשתנים למטה.""")
# dictionary helpers, right after the areas data are parsed
rep("""  const AR = J('areas-data'), AREA = Object.fromEntries(AR.areas.map(a => [a.key, a]));""",
    """  const AR = J('areas-data'), AREA = Object.fromEntries(AR.areas.map(a => [a.key, a]));
  const VD = J('vardict'), vdOf = k => VD.v[k] || VD.v[k.replace(/_pct$/, '')];
  const vdText = k => { const e = vdOf(k); return e ? `${e.d} יחידה: ${e.u}. רמה: ${e.lv}. מקור: ${VD.src[e.s] || e.s}.` + (e.r ? ` ברגרסיות: ${e.r}` : '') : ''; };""")
rep("""    return `<div class="hist"><h4>${lab}</h4>""", """    return `<div class="hist" title="${vdText(k).replace(/"/g, '&quot;')}"><h4>${lab} <span style="color:var(--muted);font-weight:400;cursor:help">ⓘ</span></h4>""")
rep("""      vYear.disabled = !v.yearly; vPlay.disabled = !v.yearly; vYearLab.textContent = v.yearly ? y : '—';""",
    """      vYear.disabled = !v.yearly; vPlay.disabled = !v.yearly; vYearLab.textContent = v.yearly ? y : '—';
      document.getElementById('vdef').textContent = vdText(v.k);""")
rep("""  <section id="sources">""", """  <section id="vardictsec">
    <h2>מילון משתנים</h2>
    <p class="lede">כל משתנה שמופיע בעמודים: הגדרה, יחידה, רמת מדידה, מקור, ואיך הוא נכנס לרגרסיות של צורה עירונית. "שטח עירוני" הוא המכנה של כל הצפיפויות. כללי חסרים: בניין שחסר לו ערך במשתנה נשמט רק מהרגרסיות שבהן המשתנה נכנס.</p>
    <div class="tablewrap" style="max-height:600px"><table style="font-size:12.5px"><thead><tr><th>קבוצה</th><th>משתנה</th><th>הגדרה</th><th>יחידה</th><th>רמה</th><th>מקור</th><th>ברגרסיות</th></tr></thead><tbody id="vdbody"></tbody></table></div>
  </section>

  <section id="sources">""")
# fill the table (report page; the element exists only there)
rep("""  // ---------- urbanism ----------""", """  { const el = document.getElementById('vdbody'); if (el) {
      const LBL = {}; (AR.hist_vars || []).forEach(h => LBL[h[0].replace(/_pct$/, '')] = h[1]);
      try { const VMl = JSON.parse(new TextDecoder().decode(window._vmRaw || new Uint8Array())); } catch (e) {}
      el.innerHTML = Object.entries(VD.v).map(([k, e]) => `<tr><td>${e.g}</td><td><b>${VD.lab[k] || LBL[k] || k}</b><br><code style="font-size:11px;color:var(--muted)">${k}</code></td><td>${e.d}</td><td>${e.u}</td><td>${e.lv}</td><td>${VD.src[e.s] || e.s}</td><td>${e.r || '—'}</td></tr>`).join(''); } }
  // ---------- urbanism ----------""")
open('map_v4_template.html', 'w').write(s); print('ok')
