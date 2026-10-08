# One-off edit of map_v4_template.html (2026-10-08): binned scatters for the commerce measures (businesses
# per km2 and commerce share of land use), raw and within city, like the junction chart; shared plotting
# function; note on case-wise deletion of missing values in the method box.
s = open('map_v4_template.html').read()
def rep(a, b):
    global s; assert s.count(a) == 1, (s.count(a), a[:90]); s = s.replace(a, b)
rep("""        <svg id="uvar" viewBox="0 0 560 260" role="img" aria-label="שונות מוסברת"></svg></div>
    </div>""", """        <svg id="uvar" viewBox="0 0 560 260" role="img" aria-label="שונות מוסברת"></svg></div>
    </div>
    <h3 style="margin-top:22px">מסחר ומחיר</h3>
    <p class="lede" id="commlede"></p>
    <div class="two">
      <div class="chart"><h3>אפקט הבניין מול עסקים לקמ"ר באזור הסטטיסטי (20 קבוצות שוות)</h3>
        <div class="key"><span><i style="background:var(--nodata)"></i>כל הארץ</span><span><i style="background:var(--accent)"></i>בתוך אותה עיר</span></div>
        <svg id="ubins_comm" viewBox="0 0 560 260" role="img" aria-label="אפקט בניין מול צפיפות עסקים"></svg></div>
      <div class="chart"><h3>אפקט הבניין מול שיעור המסחר בשימושי הקרקע (קבוצות שוות)</h3>
        <div class="key"><span><i style="background:var(--nodata)"></i>כל הארץ</span><span><i style="background:var(--accent)"></i>בתוך אותה עיר</span></div>
        <svg id="ubins_cshare" viewBox="0 0 560 260" role="img" aria-label="אפקט בניין מול שיעור מסחר"></svg></div>
    </div>""")
old_start = "  { const el = document.getElementById('ubins'), W = 560, H = 260, L0 = 46, R0 = 10, T0 = 14, B = 34;"
a = s.index(old_start); b = s.index("    el.innerHTML = s; }", a) + len("    el.innerHTML = s; }")
s = s[:a] + """  // binned scatter: building effect vs an SA measure, all of Israel (grey) and within city (accent)
  const binChart = (id, raw, city, xlab, ticks, tx, lab) => { const el = document.getElementById(id), W = 560, H = 260, L0 = 46, R0 = 10, T0 = 14, B = 34;
    const xs = [...raw, ...city].map(r => r[0]), pad = (Math.max(...xs) - Math.min(...xs))*0.04 || 0.1, x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad;
    const y0 = Math.log(0.76), y1 = Math.log(1.27);
    const x = v => L0 + (v - x0)/(x1 - x0)*(W - L0 - R0), y = v => H - B - (v - y0)/(y1 - y0)*(H - T0 - B);
    let s = '';
    for (const p of [-0.2,-0.1,0,0.1,0.2]) { const t = Math.log(1+p); s += `<line class="grid" x1="${L0}" x2="${W-R0}" y1="${y(t)}" y2="${y(t)}"${p===0?' style="stroke:var(--muted)"':''}></line><text x="${L0-6}" y="${y(t)+4}" text-anchor="end">${(p>0?'+':'') + Math.round(p*100)}%</text>`; }
    for (const [t, l] of ticks) { const lx = tx(t); if (lx < x0 || lx > x1) continue; s += `<text x="${x(lx)}" y="${H-18}" text-anchor="middle">${l}</text>`; }
    s += `<text x="${(W+L0)/2}" y="${H-2}" text-anchor="middle">${xlab}</text>`;
    for (const [rows, cls] of [[raw, 'b'], [city, 'a']])
      for (const p of rows) s += `<circle class="${cls}" cx="${x(p[0])}" cy="${y(Math.max(y0, Math.min(y1, p[1])))}" r="4"><title>${lab(p[0])}: ${sg(pc(p[1]))} (${fmt(p[2])} בניינים)</title></circle>`;
    el.innerHTML = s; };
  binChart('ubins', UR.bins_raw, UR.bins_city, 'צמתים לקמ"ר (סקאלה לוגריתמית)', [10,25,50,100,200].map(t => [t, t]), Math.log, v => `${Math.round(Math.exp(v))} צמתים לקמ"ר`);
  if (UR.bins_comm) {
    const BC = UR.bins_comm.l_comm, BS = UR.bins_comm.comm_share;
    binChart('ubins_comm', BC.raw, BC.city, 'עסקים לקמ"ר (סקאלה לוגריתמית של 1+x)', [0,10,30,100,300,1000,3000].map(t => [t, fmt(t)]), Math.log1p, v => `${fmt(Math.round(Math.expm1(v)))} עסקים לקמ"ר`);
    binChart('ubins_cshare', BS.raw, BS.city, 'שיעור המסחר והמשרדים בשימושי הקרקע', [0,0.05,0.1,0.2,0.3,0.4,0.5].map(t => [t, Math.round(t*100) + '%']), v => v, v => `${(v*100).toFixed(1)}% מסחר`);
    const MC = UR.m_comm, f = (m, k) => `${sg(pc(m.b[k]))} (${(m.se[k]*100).toFixed(1)})`;
    document.getElementById('commlede').textContent =
      `עסקים הם מקומות עם רישום ציבורי ב־Overture (חנויות, מסעדות, משרדים ושירותים), לקמ"ר של שטח עירוני. שיעור המסחר הוא חלק התאים בגריד שימושי הקרקע של הלמ"ס שמסומנים כמסחר או מרכז עיר. `+
      `בכל הארץ, עלייה של סטיית תקן בצפיפות העסקים קשורה ל־${f(MC.l_comm[0], 'l_comm_z')} במחיר הבניין. בתוך אותה עיר נשאר ${f(MC.l_comm[1], 'l_comm_z')}, ועם אשכול חברתי־כלכלי ${f(MC.l_comm[2], 'l_comm_z')} (בסוגריים: שגיאת תקן באחוזים). `+
      `בתוך העיר הקשר הוא בעיקר מדרגה: האזורים הדלילים ביותר בעסקים זולים, ומעבר לכך הקו כמעט שטוח. שיעור המסחר בשימושי הקרקע: ${f(MC.comm_share[0], 'comm_share_z')} בכל הארץ, ${f(MC.comm_share[1], 'comm_share_z')} בתוך העיר. `+
      `${fmt(BC.n)} בניינים. מתאם, לא סיבתיות: עסקים נפתחים גם במקום שבו יש ביקוש ותושבים אמידים.`; }""" + s[b:]
rep("""רק בניינים עם 3 עסקאות לפחות. שגיאות התקן""", """רק בניינים עם 3 עסקאות לפחות. בניין שחסר לו ערך באחד המשתנים (למשל שטח דרכים קדסטרי ביהודה ושומרון, שנת בנייה או מספר קומות) נשמט רק מהרגרסיות שבהן המשתנה נכנס, ולכן מספר התצפיות שונה בין המודלים. שגיאות התקן""")
open('map_v4_template.html', 'w').write(s); print('ok')
