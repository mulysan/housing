# One-off edit of map_v4_template.html (2026-10-08): Katz-Murphy over market definitions (km_grid.json,
# build_km_grid.py): geography x dwelling size x period length table, and the national size-class chart.
s = open('map_v4_template.html').read()
def rep(a, b):
    global s; assert s.count(a) == 1, (s.count(a), a[:90]); s = s.replace(a, b)
rep("""<!--REPORT--><script type="application/json" id="km-data">/*KM*/</script><!--/REPORT-->""",
    """<!--REPORT--><script type="application/json" id="km-data">/*KM*/</script><!--/REPORT-->
<!--REPORT--><script type="application/json" id="kmg-data">/*KMG*/</script><!--/REPORT-->""")
rep("""      <div class="tablewrap" style="max-height:none;min-width:0"><table style="font-size:13px" id="km5tab"></table></div>
    </div>""", """      <div class="tablewrap" style="max-height:none;min-width:0"><table style="font-size:13px" id="km5tab"></table></div>
    </div>
    <h3 style="margin-top:22px">מה זה "שוק"? גאוגרפיה × גודל דירה × אורך תקופה</h3>
    <p class="lede" id="kmglede"></p>
    <div class="two">
      <div class="chart"><h3>כל הארץ לפי מספר חדרים: מחיר ריאלי למ"ר (מקדם שנה, 2015 = 0)</h3>
        <div class="key"><span><i style="background:var(--k1)"></i>1–2</span><span><i style="background:var(--k2)"></i>3</span><span><i style="background:var(--k3)"></i>4</span><span><i style="background:var(--k4)"></i>5+</span></div>
        <svg id="kmgP" viewBox="0 0 560 240" role="img" aria-label="מחיר לפי גודל דירה"></svg></div>
      <div class="chart"><h3>אותו דבר: לוג מלאי הדירות, שינוי מ־1997</h3>
        <div class="key"><span><i style="background:var(--k1)"></i>1–2</span><span><i style="background:var(--k2)"></i>3</span><span><i style="background:var(--k3)"></i>4</span><span><i style="background:var(--k4)"></i>5+</span></div>
        <svg id="kmgS" viewBox="0 0 560 240" role="img" aria-label="מלאי לפי גודל דירה"></svg></div>
    </div>
    <div class="tablewrap" style="max-height:none;margin-top:12px"><table style="font-size:12.5px" id="kmgtab"></table></div>
    <p class="lede" style="font-size:12.5px" id="kmgnote"></p>""")
rep("""    if (KM.p5) { const P5 = KM.p5,""", """    { const KG = J('kmg-data'), RS = KG.results, SZ = KG.sizes, CLS = ['k1','k2','k3','k4'];
      const il = RS.find(r => r.geo === 'IL' && r.per === 'annual');
      if (il && il.series) {
        lineChart('kmgP', SZ.map((z, k) => ({ cls: CLS[k], pts: (il.series['IL|' + z] || {t:[]}).t.map((t, i) => [t, il.series['IL|' + z].theta[i]]) })),
          { x0:1998, x1:2020, y0:-0.6, y1:0.3, yt:[-0.6,-0.4,-0.2,0,0.2], xt:[1998,2002,2006,2010,2014,2018,2020], base:0, yf: v => (v > 0 ? '+' : '') + Math.round(v*100) + '%', l: 44 });
        lineChart('kmgS', SZ.map((z, k) => { const d = il.series['IL|' + z] || {t:[], lS_n:[]}; return { cls: CLS[k], pts: d.t.map((t, i) => [t, d.lS_n[i] - d.lS_n[0]]) }; }),
          { x0:1998, x1:2020, y0:0, y1:0.9, yt:[0,0.2,0.4,0.6,0.8], xt:[1998,2002,2006,2010,2014,2018,2020], base:0, yf: v => '+' + Math.round(v*100) + '%', l: 44 }); }
      const fm = m => m ? `<span${star(m.b, m.se)}>${f3(m.b)}</span> <span style="color:var(--muted)">(${m.se.toFixed(3)}${m.se_hc != null ? '; ' + m.se_hc.toFixed(3) : ''})</span>${m.F ? ` <span style="color:var(--muted)">F=${m.F}</span>` : ''}` : '—';
      const PER = { annual: 'שנתי', '5y': '5 שנים' };
      document.getElementById('kmgtab').innerHTML = `<thead><tr><th>גאוגרפיה</th><th>גודל</th><th>תקופה</th><th class="num">שווקים</th><th class="num">תצפיות</th><th class="num">אפקט תקופה + שוק</th><th class="num">R² פנימי: N / E</th><th class="num">+ מגמה לשוק</th><th class="num">אזור×תקופה + גודל×תקופה</th><th class="num">IV</th><th class="num">הפרשי 5 שנים</th><th class="num">הפרשים, IV</th></tr></thead><tbody>` +
        RS.map(r => { const m = r.m; return `<tr><td>${r.geo_lab}</td><td>${r.size === 'rooms' ? 'לפי חדרים' : 'כל הדירות'}</td><td>${PER[r.per]}</td><td class="num">${r.n_mk}</td><td class="num">${fmt(r.n_obs)}</td>` +
          `<td class="num">${fm(m.fe_n)}</td><td class="num">${(m.fe_n.r2w*100).toFixed(1)}% / ${(m.fe_val.r2w*100).toFixed(1)}%</td><td class="num">${fm(m.tr_n)}</td><td class="num">${fm(m.cross_n)}</td><td class="num">${fm(m.iv_n)}</td><td class="num">${fm(m.dif_n)}</td><td class="num">${fm(m.difiv_n)}</td></tr>`; }).join('') + '</tbody>';
      const g = (geo, size, per) => RS.find(r => r.geo === geo && r.size === size && r.per === per);
      const a = g('IL', 'rooms', 'annual'), cr = g('city', 'rooms', '5y'), cy = g('city', 'all', 'annual');
      document.getElementById('kmglede').textContent =
        `שוק יכול להיות גם גודל דירה: למשל דירות 3 חדרים במחוז ירושלים ב־1998–2002. בדקתי חמש הגדרות של גאוגרפיה (כל הארץ, מחוז, נפה, עיר, אשכול SES), עם ובלי חלוקה לארבעה גדלים (1–2, 3, 4, 5+ חדרים), בשנים בודדות ובתקופות של 5 שנים. `+
        `התמונה עקבית: בין אזורים ההיצע והמחיר עולים יחד (המקדם חיובי), כי הבנייה הולכת לאן שהביקוש גדל. בין גדלי דירה בכל הארץ המקדם שלילי, כמו שהמודל צופה: ${f3(a.m.fe_n.b)} (${a.m.fe_n.se}), כלומר σ ≈ ${(-1/a.m.fe_n.b).toFixed(1)}, ו־R² פנימי של ${Math.round(a.m.fe_n.r2w*100)}%. `+
        `מלאי הדירות של 5 חדרים ומעלה גדל בכ־80 נקודות לוג מאז 1997, ושל 1–2 חדרים רק בכ־10, והמחיר למ"ר של הדירות הקטנות עלה מעט יותר. גמישות תחלופה של כ־5 אומרת שדירות בגדלים שונים הן תחליפים קרובים. `+
        `בתוך ערים, עם אפקט לכל עיר×תקופה ולכל גודל×תקופה (הזיהוי בסגנון KM), המקדם קטן: ${f3(cr.m.cross_n.b)} (${cr.m.cross_n.se}).`;
      document.getElementById('kmgnote').textContent =
        `בכל תא: −1/σ, ובסוגריים שגיאת תקן מקובצת לפי שוק; אחרי ";" שגיאת תקן חסינה להטרוסקדסטיות בלי קיבוץ. עם 4–7 שווקים (כל הארץ לפי גודל, מחוזות) הקיבוץ לא אמין. `+
        `גודל הדירות במלאי: הגזטיר לא מציין חדרים. 31% מהדירות מקבלות את מספר החדרים מעסקאות של אותה תת־חלקה, 54% לפי התפלגות החדרים בעסקאות של החלקה, והשאר לפי הגוש או העיר. `+
        `לכן החלוקה לגדלים היא קירוב. "+ מגמה לשוק" בכל הארץ לפי גודל לא מזוהה היטב (4 שווקים, 23 שנים). F = מבחן שלב ראשון של המכשיר.`; }
    if (KM.p5) { const P5 = KM.p5,""")
open('map_v4_template.html', 'w').write(s); print('ok')
