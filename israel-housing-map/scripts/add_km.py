# One-off edit of map_v4_template.html (2026-10-08):
#  1. a Katz-Murphy section (build_km.py) with a "technical details" dialog: model derivation, data
#     decisions, all estimates, supply series, caveats;
#  2. the floor-by-group section gets a switch between the census (2008) and vote (2022) classifications;
#  3. the urban-form tables get the new measures (commerce, parking, street curvature) and a model with
#     vote shares as the group control.
s = open('map_v4_template.html').read()
def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:80]); s = s.replace(a, b)

# ---------------------------------------------------------------- 1. Katz-Murphy section
KM_HTML = '''
  <section id="kmsec">
    <h2>היצע דיור אפקטיבי ומחירים: ניתוח בסגנון Katz–Murphy</h2>
    <p class="lede" id="kmlede"></p>
    <div class="chips"><button class="chip" id="kmOpen" aria-pressed="false">פרטים טכניים: המודל, הנתונים וכל האומדנים</button></div>
    <div class="two">
      <div class="chart"><h3>הפרש ארוך 2008→2020: שינוי במחיר מול שינוי בהיצע, לפי אשכול חברתי־כלכלי</h3>
        <svg id="kmses" viewBox="0 0 560 300" role="img" aria-label="שינוי במחיר מול שינוי בהיצע לפי אשכול"></svg></div>
      <div class="chart"><h3>אותו דבר, לפי עיר (48 ערים)</h3>
        <svg id="kmcity" viewBox="0 0 560 300" role="img" aria-label="שינוי במחיר מול שינוי בהיצע לפי עיר"></svg></div>
    </div>
    <div class="tablewrap" style="max-height:none;margin-top:12px"><table style="font-size:13px" id="kmtab"></table></div>
  </section>'''
KM_METHOD = '''
    <div class="method"><b>איך זה חושב</b>
      <div class="eq" dir="ltr">ln <i>P<sub>jt</sub></i> = θ<sub><i>t</i></sub> + δ<sub><i>j</i></sub> + γ<sub><i>j</i></sub><i>t</i> − (1/σ)·ln <i>S</i><sub><i>j</i>,<i>t</i>−1</sub> + <i>u<sub>jt</sub></i></div>
      <div class="eq" dir="ltr"><i>N<sub>jt</sub></i> = Σ<sub><i>i</i>∈<i>j</i>, built≤<i>t</i></sub> 1,   <i>F<sub>jt</sub></i> = Σ m²<sub><i>i</i></sub>,   <i>E<sub>jt</sub></i> = Σ <i>v<sub>i</sub></i>/<i>v̄</i></div>
      <p><i>P<sub>jt</sub></i> = מקדם שנת המכירה של שוק <i>j</i> ממודל אפקט קבוע לבניין (מחיר למ"ר של דיור באיכות קבועה). <i>S</i> = מלאי הדירות בסוף השנה הקודמת, בשלוש גרסאות: מספר דירות (<i>N</i>), שטח רצפה (<i>F</i>) ויחידות יעילות (<i>E</i>, כל דירה לפי שוויה היחסי במחירים קבועים, כמו "עבודה אפקטיבית" אצל Katz ו־Murphy). θ = אפקט שנה, δ = אפקט שוק, γ = מגמה לינארית לשוק (ביקוש יחסי). σ = גמישות התחליף בין שווקים. הפרטים המלאים, כולל הגזירה והחלטות הנתונים, בחלון "פרטים טכניים".</p></div>'''
anchor = '\n  <section>\n    <h2>היצע דיור אפקטיבי: כמה "דירות ממוצעות" יש בכל עיר</h2>'
assert s.count(anchor) == 1
i = s.index(anchor); j = s.index('\n  </section>', i + 10) + len('\n  </section>')
s = s[:j] + KM_HTML.replace('\n  </section>', KM_METHOD + '\n  </section>') + s[j:]

KM_DLG = '''<!--REPORT-->
<dialog id="kmDlg" dir="rtl" aria-labelledby="kmDlgTitle"><div class="dlghead"><h2 id="kmDlgTitle">Katz–Murphy לדיור: פרטים טכניים</h2><button id="kmClose">סגירה</button></div><div id="kmBody" class="kmbody"></div></dialog>
<!--/REPORT-->'''
rep('<dialog id="areaDlg"', KM_DLG + '\n<dialog id="areaDlg"')
rep('dialog#areaDlg{', 'dialog#kmDlg{border:none;border-radius:8px;padding:0;width:min(1000px,96vw);max-height:92vh;box-shadow:0 10px 40px rgba(0,0,0,.35);background:var(--bg);color:var(--fg)}\n'
    'dialog#kmDlg::backdrop{background:rgba(44,62,80,.55)}\n.kmbody{padding:14px 18px;overflow:auto;line-height:1.6}\n.kmbody h3{margin:18px 0 6px;font-size:1.02rem;border-bottom:1px solid var(--rule);padding-bottom:3px}\n'
    '.kmbody ol,.kmbody ul{padding-inline-start:20px;margin:4px 0}\n.kmbody li{margin:0 0 6px;max-width:100ch}\n.kmbody .eq{direction:ltr;text-align:left;font-family:"Cambria Math","STIX Two Math",Georgia,serif;font-size:15px;background:#fff;border:1px solid var(--rule);border-radius:4px;padding:6px 10px;margin:6px 0;overflow-x:auto;white-space:nowrap;unicode-bidi:isolate}\n'
    'dialog#areaDlg{')
rep('<!--REPORT--><script type="application/json" id="floorg-data">/*FLOORG*/</script><!--/REPORT-->',
    '<!--REPORT--><script type="application/json" id="floorg-data">/*FLOORG*/</script><!--/REPORT-->\n<!--REPORT--><script type="application/json" id="km-data">/*KM*/</script><!--/REPORT-->')

KM_JS = r'''
  // ---------- Katz-Murphy: effective supply and selling-year coefficients ----------
  { const KM = J('km-data'), C = KM.city, T = KM.tier, CR = KM.core, M = C.models, MT = T.models;
    const f3 = v => v == null ? '—' : (v > 0 ? '+' : '') + v.toFixed(3);
    const star = (b, se) => se && Math.abs(b) > 1.96*se ? ' style="font-weight:700;color:var(--fg)"' : ' style="color:var(--muted)"';
    const scatter = (id, pts, fit, o) => { const el = document.getElementById(id), W = 560, H = 300, L0 = 52, R0 = 12, T0 = 12, B = 40;
      const xs = pts.map(p => p[1]), ys = pts.map(p => p[2]);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), px = (x1-x0)*0.08 || 0.01, py = (y1-y0)*0.08 || 0.01;
      const X = v => L0 + (v - x0 + px)/(x1 - x0 + 2*px)*(W - L0 - R0), Y = v => H - B - (v - y0 + py)/(y1 - y0 + 2*py)*(H - T0 - B);
      let s = '';
      const tk = (a, b, n) => { const st = (b - a)/n; return Array.from({length: n + 1}, (_, k) => a + k*st); };
      tk(y0, y1, 4).forEach(t => { s += `<line class="grid" x1="${L0}" x2="${W-R0}" y1="${Y(t)}" y2="${Y(t)}"></line><text x="${L0-6}" y="${Y(t)+4}" text-anchor="end">${(t*100).toFixed(0)}%</text>`; });
      tk(x0, x1, 4).forEach(t => { s += `<text x="${X(t)}" y="${H-B+16}" text-anchor="middle">${(t*100).toFixed(0)}%</text>`; });
      s += `<text x="${(W+L0)/2}" y="${H-4}" text-anchor="middle">${o.xlab}</text><text x="12" y="${T0+4}" style="direction:rtl;text-anchor:start" transform="rotate(0)">${o.ylab}</text>`;
      if (fit) { const [a, b] = fit; s += `<line x1="${X(x0)}" x2="${X(x1)}" y1="${Y(a + b*x0)}" y2="${Y(a + b*x1)}" style="stroke:var(--warm);stroke-width:2;stroke-dasharray:5 3"></line>`; }
      pts.forEach(p => { s += `<g class="h"><title>${p[0]}: היצע ${(p[1]*100).toFixed(1)}%, מחיר ${(p[2]*100).toFixed(1)}%</title><circle class="a" cx="${X(p[1])}" cy="${Y(p[2])}" r="${o.r || 4}"></circle>` +
        (o.labels ? `<text x="${X(p[1])+6}" y="${Y(p[2])-5}" style="direction:ltr;font-size:10.5px">${p[0].replace('SES ','')}</text>` : '') + '</g>'; });
      el.innerHTML = s; };
    const lf = pts => { const n = pts.length, mx = pts.reduce((a, p) => a + p[1], 0)/n, my = pts.reduce((a, p) => a + p[2], 0)/n;
      const b = pts.reduce((a, p) => a + (p[1]-mx)*(p[2]-my), 0) / pts.reduce((a, p) => a + (p[1]-mx)**2, 0); return [my - b*mx, b]; };
    const sl = T.long_diff.n.pts, cl = C.long_diff.n.pts;
    scatter('kmses', sl, lf(sl), { xlab:'שינוי בלוג מלאי הדירות, 2007→2019', ylab:'שינוי במחיר הריאלי, 2008→2020 (לוג)', labels:true });
    scatter('kmcity', cl, lf(cl), { xlab:'שינוי בלוג מלאי הדירות, 2007→2019', ylab:'שינוי במחיר הריאלי, 2008→2020 (לוג)', r:3.5 });
    const W3 = [['n','מספר דירות (N)'],['m2','שטח רצפה (F)'],['val','יחידות יעילות (E)']];
    const cellm = m => m ? `<td class="num"${star(m.b[0], m.se[0])}>${f3(m.b[0])} <span style="font-weight:400;color:var(--muted)">(${m.se[0].toFixed(3)})</span></td><td class="num">${(m.r2_within*100).toFixed(1)}%</td>` : '<td></td><td></td>';
    const cellc = r => `<td class="num"${star(r.b, r.se)}>${f3(r.b)} <span style="font-weight:400;color:var(--muted)">(${r.se.toFixed(3)})</span></td><td class="num">${(r.r2*100).toFixed(1)}%</td>`;
    document.getElementById('kmtab').innerHTML = `<thead><tr><th rowspan="2">מדד ההיצע</th><th colspan="2" class="num">ערים: אפקט שנה + עיר</th><th colspan="2" class="num">+ מגמה לכל עיר</th><th colspan="2" class="num">ערים, IV (חלק היסטורי)</th><th colspan="2" class="num">10 אשכולות SES</th><th colspan="2" class="num">הפרש ארוך, אשכולות</th><th colspan="2" class="num">ליבה מול שאר הארץ</th></tr>` +
      `<tr>${'<th class="num">−1/σ (se)</th><th class="num">R² פנימי</th>'.repeat(3)}<th class="num">−1/σ (se)</th><th class="num">R² פנימי</th><th class="num">שיפוע (se)</th><th class="num">R²</th><th class="num">שיפוע (se)</th><th class="num">R²</th></tr></thead><tbody>` +
      W3.map(([w, lab]) => `<tr><td>${lab}</td>${cellm(M[w+'_fe'])}${cellm(M[w+'_trend'])}${cellm(M[w+'_fe_iv'])}${cellm(MT[w+'_fe'])}${cellc(T.long_diff[w])}${cellc(CR[w])}</tr>`).join('') + '</tbody>';
    const gc = C.growth_corr;
    document.getElementById('kmlede').textContent =
      `לפי המודל, אם יחידות דיור בשווקים שונים הן תחליפים לא מושלמים, שוק שבו ההיצע גדל מהר יותר יראה עלייה איטית יותר במחיר היחסי, במקדם −1/σ. `+
      `בין ${C.n_mk} הערים הגדולות, ${C.years[0]}–${C.years[1]}, אין לכך תמיכה: בפיקוח על אפקט שנה ועיר המקדם ${f3(M.n_fe.b[0])} (לא מובהק), ועם מכשיר של חלק העיר בבנייה הארצית ב־1985–97 (F של שלב ראשון ${M.n_fe_iv.first_stage_F}) הוא ${f3(M.n_fe_iv.b[0])}. `+
      `הסבר סביר: בונים במקום שבו הביקוש עולה, ולכן היצע ומחיר עולים יחד. בין 10 אשכולות SES, ההפרש הארוך שלילי וחזק (שיפוע ${f3(T.long_diff.n.b)}, R² ${(T.long_diff.n.r2*100).toFixed(0)}%), אבל הוא מעורבב עם התכנסות המחירים בשכונות זולות. `+
      `ולשאלת ה־R²: בתוך עיר, הצמיחה של מספר הדירות ושל היחידות היעילות כמעט זהה (מתאם ${gc.n_val}), ולכן היצע אפקטיבי אינו מסביר יותר מספירה פשוטה. ה־R² הפנימי הוא ${(M.n_fe.r2_within*100).toFixed(1)}% מול ${(M.val_fe.r2_within*100).toFixed(1)}%.`;
    // ---- technical-details dialog
    const fm = (m, k=0) => m ? `${f3(m.b[k])} (${m.se[k].toFixed(3)})` : '—';
    const rows = (mods, keys) => keys.map(([k, lab]) => { const m = mods[k]; if (!m) return '';
      return `<tr><td>${lab}</td><td class="num">${fm(m)}</td><td class="num">${m.b.length > 1 ? fm(m, 1) : '—'}</td><td class="num">${m.sigma && m.sigma[m.sigma.length-1] ? m.sigma[m.sigma.length-1] : '—'}</td><td class="num">${(m.r2_within*100).toFixed(1)}%</td><td class="num">${(m.r2*100).toFixed(1)}%</td><td class="num">${m.first_stage_F ?? '—'}</td></tr>`; }).join('');
    const KEYS = [['n_fe','N, אפקט שנה + שוק'],['m2_fe','F, אפקט שנה + שוק'],['val_fe','E, אפקט שנה + שוק'],['horse_fe','N ו־E יחד (המקדם השני = E)'],
      ['n_trend','N, + מגמה לשוק'],['m2_trend','F, + מגמה'],['val_trend','E, + מגמה'],['horse_trend','N ו־E יחד, + מגמה'],
      ['n_fe_iv','N, 2SLS'],['m2_fe_iv','F, 2SLS'],['val_fe_iv','E, 2SLS'],['n_trend_iv','N, 2SLS + מגמה'],['m2_trend_iv','F, 2SLS + מגמה'],['val_trend_iv','E, 2SLS + מגמה']];
    const tab = (mods) => `<div class="tablewrap" style="max-height:none"><table style="font-size:12.5px"><thead><tr><th>מודל</th><th class="num">מקדם (se)</th><th class="num">מקדם שני</th><th class="num">σ משתמע</th><th class="num">R² פנימי</th><th class="num">R² כולל</th><th class="num">F שלב ראשון</th></tr></thead><tbody>${rows(mods, KEYS)}</tbody></table></div>`;
    const NS = KM.national_stock, raw = KM.raw_by_year;
    const lv = KM.levels_2015;
    const body = `
      <h3>1. השאלה</h3>
      <p>Katz ו־Murphy (1992, QJE) הסבירו את השינוי בפרמיית ההשכלה בשכר בעזרת שינויים בהיצע היחסי של עובדים משכילים, כשההיצע נמדד ב"יחידות יעילות": שעות עבודה משוקללות בשכר יחסי קבוע. כאן אותו מבנה על דיור. השאלה היא אם שינויים בהיצע הדיור (מלאי הדירות) מסבירים שינויים במחיר של דיור באיכות קבועה בין שווקים, והאם מדד היצע "אפקטיבי", שבו כל דירה נספרת לפי שוויה היחסי, מסביר יותר ממספר הדירות הפשוט.</p>
      <h3>2. המודל</h3>
      <p>משקי הבית צורכים שירותי דיור מ־<i>J</i> שווקים (ערים, או קבוצות שכונות). השירותים מהשווקים השונים הם תחליפים לא מושלמים ומצטרפים בפונקציית CES:</p>
      <div class="eq">H<sub>t</sub> = [ Σ<sub>j</sub> (A<sub>jt</sub> S<sub>jt</sub>)<sup>ρ</sup> ]<sup>1/ρ</sup>,   σ = 1/(1 − ρ)</div>
      <p><i>S<sub>jt</sub></i> = שירותי הדיור (המלאי ביחידות יעילות), <i>A<sub>jt</sub></i> = מזיז ביקוש לשוק (נוחות, תעסוקה, העדפות). בתמחור תחרותי, המחיר של יחידת שירות בשוק <i>j</i> הוא הערך השולי של H כפול ∂H/∂S<sub>jt</sub>:</p>
      <div class="eq">P<sub>jt</sub> = λ<sub>t</sub> H<sub>t</sub><sup>1−ρ</sup> A<sub>jt</sub><sup>ρ</sup> S<sub>jt</sub><sup>ρ−1</sup>   ⇒   ln P<sub>jt</sub> = θ<sub>t</sub> + ρ ln A<sub>jt</sub> − (1/σ) ln S<sub>jt</sub></div>
      <p>θ<sub>t</sub> = ln(λ<sub>t</sub>H<sub>t</sub><sup>1−ρ</sup>) משותף לכל השווקים (הכנסה, ריבית, אוכלוסייה, אשראי), ונספג באפקט קבוע לשנה. כמו אצל Katz ו־Murphy, הביקוש היחסי הוא אפקט שוק ועוד מגמה לינארית לשוק: ρ ln A<sub>jt</sub> = δ<sub>j</sub> + γ<sub>j</sub>t + u<sub>jt</sub>. מכאן משוואת האמידה:</p>
      <div class="eq">ln P<sub>jt</sub> = θ<sub>t</sub> + δ<sub>j</sub> + γ<sub>j</sub> t − (1/σ) ln S<sub>j,t−1</sub> + u<sub>jt</sub></div>
      <p>עם שני שווקים זו הרגרסיה הקלאסית של Katz ו־Murphy: ln(P<sub>1t</sub>/P<sub>2t</sub>) = a + g·t − (1/σ) ln(S<sub>1,t−1</sub>/S<sub>2,t−1</sub>) + e<sub>t</sub>. ההיצע נכנס בפיגור של שנה, כי המלאי בסוף השנה הקודמת כבר עומד כשנקבעים מחירי השנה. זה מסיר את התגובה הישירה של סיומי בנייה למחיר באותה שנה, אבל ההיצע עדיין תלוי במחירים הצפויים דרך החלטות בנייה מוקדמות יותר (ראו סעיף 6).</p>
      <h3>3. היצע: פשוט מול אפקטיבי</h3>
      <div class="eq">N<sub>jt</sub> = Σ<sub>i∈j, built≤t</sub> 1,    F<sub>jt</sub> = Σ<sub>i∈j, built≤t</sub> m²<sub>i</sub>,    E<sub>jt</sub> = Σ<sub>i∈j, built≤t</sub> v<sub>i</sub> / v̄</div>
      <p>m²<sub>i</sub> = שטח חציוני של עסקאות בחלקה של הדירה (אחרת בגוש, אחרת בעיר). v<sub>i</sub> = m²<sub>i</sub> × חציון המחיר הריאלי למ"ר בגוש ב־2023–26 (אחרת בעיר). v̄ = הממוצע הארצי. המשקלות קבועים בזמן, כמו אצל Katz ו־Murphy, ולכן E זז רק כשהרכב המלאי משתנה: דירות גדולות יותר או במיקומים יקרים יותר. לפי מודל ה־CES, המחיר המתאים ל־E הוא המחיר ליחידה יעילה, וזה מה שמודד מדד מחירים באיכות קבועה.</p>
      <h3>4. מחירים: מקדמי שנת המכירה</h3>
      <div class="eq">ln(P/m² / CPI)<sub>i</sub> = θ<sub>j(i),t(i)</sub> + α<sub>b(i)</sub> + κ<sub>a(i)</sub> + ε<sub>i</sub></div>
      <p>θ<sub>jt</sub> הוא מקדם שוק×שנת מכירה, עם אפקט קבוע לבניין (α<sub>b</sub>, גוש־חלקה) ולשטח מעוגל (κ<sub>a</sub>). האפקט לבניין קובע מיקום ומבנה, ולכן θ<sub>jt</sub> מודד שינוי במחיר של דיור באיכות קבועה. הנרמול הוא 0 ב־2015 בכל שוק, והרמה נספגת ב־δ<sub>j</sub>. העסקאות: מכירות דירה שלמה של רשות המסים (ו־govmap בגושים שאין להם עסקאות ברשות המסים), ${KM.years[0]}–${KM.years[1]}. רק בניינים עם שתי עסקאות לפחות, ותאי שוק×שנה עם 30 עסקאות לפחות (100 באשכולות).</p>
      <h3>5. החלטות נתונים (היצע)</h3>
      <ol>
        <li><b>המלאי לפי שנה</b> הוא הדירות בגזטיר הנכסים הלאומי (יחידות רשומות בבתים משותפים, כ־2.68 מיליון) לפי שנת הבנייה. הגזטיר הוא תמונת מצב מ־2024–25, ולכן המלאי ההיסטורי הוא מלאי הדירות ששרדו: דירות שנהרסו לפני כן (התחדשות עירונית, כ־1–2% מהמלאי) חסרות בשנים מוקדמות. דירות שאינן בבית משותף רשום (רוב הבתים צמודי הקרקע, ודיור לא רשום ביישובים ערביים) לא נמצאות בגזטיר בכלל.</li>
        <li><b>פיגור ברישום:</b> דירות נרשמות כיחידות בבית משותף כמה שנים אחרי הבנייה. לפי שנת בנייה: ${raw.filter(r => r[0] >= 2018).map(r => `${r[0]}: ${fmt(r[1])}`).join(', ')}. המלאי של השנים האחרונות חסר, ולכן הפאנל משתמש בהיצע עד 2019 (ובמחירים עד 2020).</li>
        <li><b>שנת בנייה חסרה</b> (26% מהדירות): מחולקת לשנים לפי ההתפלגות של השנים הידועות בעיר. זה מכפיל את המלאי של כל עיר בקבוע, שנספג ב־δ<sub>j</sub> בלוג. זה מטה את הצמיחה רק אם השנים החסרות מרוכזות במחזורי בנייה מסוימים.</li>
        <li><b>הצטברות על שנים עגולות:</b> שנות בנייה מתרכזות בכפולות של 5 (1990: 56 אלף דירות מול כ־16 אלף ב־1989 וב־1991; 2000: 53 אלף מול 31 ו־17 אלף). בכל עיר, העודף בשנה שהיא כפולה של 5 (המספר פחות החציון של שתי השנים מכל צד) מפוזר שווה על חמש השנים שסביבה.</li>
        <li><b>מיקום:</b> דירות משויכות לעיר לפי שם היישוב בגזטיר, ולאזור סטטיסטי לפי מיקום החלקה.</li>
        <li><b>שווקים:</b> ${C.n_mk} ערים עם 12 אלף דירות רשומות ומעלה; 10 אשכולות SES (2021) של האזור הסטטיסטי; ושני שווקים: "ליבה" (מחוזות תל אביב והמרכז) מול שאר הארץ.</li>
      </ol>
      <h3>6. זיהוי ומכשיר</h3>
      <p>ההיצע נקבע מראש, אבל הוא לא אקסוגני: יזמים בונים במקום שבו הם מצפים לעליית מחירים, וזה מטה את −1/σ כלפי אפס ואף לחיובי. המגמות לשוק סופגות צמיחה חלקה בביקוש, והזיהוי מגיע מסטיות של צמיחת ההיצע מהמגמה. המכשיר הוא מלאי חזוי מסוג shift-share: המלאי שהיה לשוק אילו שמר על חלקו בבנייה הארצית בתקופה שלפני מדגם המחירים (1985–1997):</p>
      <div class="eq">Ŝ<sub>jt</sub> = S<sub>j,1997</sub> + s<sub>j</sub>·(S<sub>nat,t</sub> − S<sub>nat,1997</sub>),    s<sub>j</sub> = (S<sub>j,1997</sub> − S<sub>j,1984</sub>) / (S<sub>nat,1997</sub> − S<sub>nat,1984</sub>)</div>
      <p>הבנייה הארצית נקבעת בביקוש הארצי, שנספג באפקטי השנה. הזיהוי מגיע משווקים עם חלק היסטורי גדול בבנייה (עתודות קרקע, יכולת תכנון) שמקבלים חלק גדול יותר מכל גל ארצי. ההנחה היא שחלק הבנייה בתקופה הקודמת אינו קשור לזעזועי ביקוש יחסיים מאוחרים יותר, בהינתן אפקטי השוק (והמגמות). גל העלייה של שנות ה־90 מעורר ספק לגבי ערי פריפריה שבנו הרבה ב־1990–97, ולכן התוצאות מוצגות כרמז בלבד.</p>
      <h3>7. תוצאות: ${C.n_mk} ערים, ${C.years[0]}–${C.years[1]} (${fmt(C.n_obs)} תצפיות עיר×שנה)</h3>${tab(M)}
      <p>R² פנימי = החלק מהשונות במחיר שנשארת אחרי האפקטים הקבועים (והמגמות), שמוסבר על ידי ההיצע. שגיאות התקן מקובצות לפי עיר. המתאם בין הצמיחה השנתית של N ושל E בתוך עיר הוא ${gc.n_val}, ובין N ל־F ${gc.n_m2}. כמעט אין שונות שמבחינה ביניהם, ולכן ה־R² שלהם כמעט זהה.</p>
      <h3>8. תוצאות: 10 אשכולות SES (${fmt(T.n_obs)} תצפיות)</h3>${tab(MT)}
      <p>הפרש ארוך (שינוי במקדם השנה 2008→2020 מול שינוי בלוג ההיצע 2007→2019, בין האשכולות): N: ${f3(T.long_diff.n.b)} (${T.long_diff.n.se}), R² ${(T.long_diff.n.r2*100).toFixed(0)}%; F: ${f3(T.long_diff.m2.b)}, R² ${(T.long_diff.m2.r2*100).toFixed(0)}%; E: ${f3(T.long_diff.val.b)}, R² ${(T.long_diff.val.r2*100).toFixed(0)}%. ההיצע גדל מהר יותר באשכולות 7–9 (שכונות חדשות), והמחירים עלו שם פחות. אבל זה גם דפוס של התכנסות: המחירים בשכונות הזולות עלו מהר יותר אחרי 2008. בפאנל עם מגמה לכל אשכול הקשר נעלם.</p>
      <h3>9. שני שווקים: ליבה מול שאר הארץ</h3>
      <p>ln(P<sub>ליבה</sub>/P<sub>שאר</sub>) על מגמה ועל ln(S<sub>ליבה</sub>/S<sub>שאר</sub>) בפיגור, שגיאות Newey–West (2 פיגורים): N: ${f3(CR.n.b)} (${CR.n.se}), R² ${(CR.n.r2*100).toFixed(0)}% (מגמה בלבד: ${(CR.n.r2_trend_only*100).toFixed(0)}%); F: ${f3(CR.m2.b)} (${CR.m2.se}); E: ${f3(CR.val.b)} (${CR.val.se}). אין קשר שלילי מובהק.</p>
      <h3>10. רמות, 2015: מחיר מול היצע לנפש</h3>
      <p>בין ערים, ברמות, המדדים כן שונים: בעיר של דירות גדולות יש יותר שטח לנפש משמספר הדירות מראה. ln(מחיר ממוצע למ"ר, 2014–16) על ln(היצע / אוכלוסייה 2015), ${KM.levels_n} ערים: מספר דירות ${f3(lv.n.b)} (${lv.n.se}), R² ${(lv.n.r2*100).toFixed(1)}%; שטח רצפה ${f3(lv.m2.b)} (${lv.m2.se}), R² ${(lv.m2.r2*100).toFixed(1)}%. יחידות יעילות לא נבדקות כאן: המשקלות שלהן בנויים מהמחירים, ולכן בין ערים הן קשורות מכנית לרמת המחיר.</p>
      <h3>11. סיכום</h3>
      <ul>
        <li>מדד היצע אפקטיבי לא מסביר יותר ממספר הדירות. בתוך שוק לאורך זמן, ההרכב של הבנייה החדשה משתנה לאט מדי (מתאם צמיחה ${gc.n_val}). בין שווקים ברמות, שטח רצפה לנפש מסביר פחות ממספר דירות לנפש.</li>
        <li>במקדמי שנת המכירה של ערים אין עקומת ביקוש יורדת: ההיצע גדל במקום שבו הביקוש גדל. כדי לזהות את σ צריך זעזוע היצע חיצוני, למשל מכרזי קרקע של רמ"י, הגרלות "מחיר למשתכן" לפי עיר ושנה, או אישורי תכניות.</li>
        <li>בין אשכולות SES, ההפרש הארוך מתאים ל־σ ≈ 1, אבל אי אפשר להפריד אותו מהתכנסות המחירים.</li>
      </ul>`;
    const dlgK = document.getElementById('kmDlg');
    document.getElementById('kmOpen').addEventListener('click', () => { document.getElementById('kmBody').innerHTML = body; fixBidi(document.getElementById('kmBody'));
      if (dlgK.showModal) dlgK.showModal(); else dlgK.setAttribute('open', ''); });
    document.getElementById('kmClose').addEventListener('click', () => dlgK.close());
    dlgK.addEventListener('click', e => { if (e.target === dlgK) dlgK.close(); });
    fixBidi(document.getElementById('kmsec')); }
'''
rep("  // ---------- floor premium by area type; building height at a fixed unit floor ----------", KM_JS + "  // ---------- floor premium by area type; building height at a fixed unit floor ----------")

# ---------------------------------------------------------------- 2. census / votes switch
rep('''    <p class="lede" id="fglede"></p>''', '''    <p class="lede" id="fglede"></p>
    <div class="seg" role="group" aria-label="הגדרת סוג האזור"><button id="fg-c" aria-pressed="true">לפי מפקד 2008</button><button id="fg-v" aria-pressed="false">לפי הצבעה 2022</button></div>''')
rep("""  { const FG = J('floorg-data'), GR = [['אחר','k1','אחר'],['חרדי','k2','חרדי'],['ערבי','k3','ערבי']];""",
    """  { const FG0 = J('floorg-data'); const drawFG = src => { const FG = src === 'v' ? { groups: FG0.groups_votes, height: FG0.height_votes } : FG0, GR = [['אחר','k1','אחר'],['חרדי','k2','חרדי'],['ערבי','k3','ערבי']];""")
rep("""    fixBidi(document.getElementById('floorgrp')); }""",
    """    fixBidi(document.getElementById('floorgrp')); };
    const bc = document.getElementById('fg-c'), bv = document.getElementById('fg-v');
    const setFG = v => { bc.setAttribute('aria-pressed', v === 'c'); bv.setAttribute('aria-pressed', v === 'v'); drawFG(v);
      if (v === 'v') document.getElementById('fglede').textContent += ` הגדרה לפי הצבעה (כנסת 25, לפי אזור סטטיסטי): חרדי = יהדות התורה + ש"ס 50% ומעלה מהקולות הכשרים; ערבי = רע"ם + חד"ש־תע"ל + בל"ד 50% ומעלה. ההתאמה להגדרה של המפקד: ${Math.round(FG0.agreement*100)}% מהעסקאות.`; };
    bc.addEventListener('click', () => setFG('c')); bv.addEventListener('click', () => setFG('v')); setFG('c'); }""")

# ---------------------------------------------------------------- 3. urban-form tables: new measures, votes model
rep("""  const ULAB = { l_junc_z:'צמתים לקמ"ר (לוג)', road_share_z:'שיעור שטח דרכים', l_parcel_z:'גודל חלקה (לוג)', l_units_z:'דירות לקמ"ר (לוג)',""",
    """  const ULAB = { l_junc_z:'צמתים לקמ"ר (לוג)', road_share_z:'שיעור שטח דרכים', l_parcel_z:'גודל חלקה (לוג)', l_units_z:'דירות לקמ"ר (לוג)',
    l_comm_z:'עסקים לקמ"ר (לוג)', l_park_z:'חניונים לקמ"ר (לוג)', circuity_z:'עקמומיות הרחובות', haredi_z:'קולות למפלגות חרדיות', arab_z:'קולות למפלגות ערביות',""")
rep("""  const models = [UR.m_form, UR.m2_urban, UR.m3_ses, UR.m4_city, UR.m5_bld];""",
    """  const models = [UR.m_form, UR.m2_urban, UR.m3_ses, UR.m4_city, UR.m5_bld, UR.m8_city_votes];""")
rep("""<th class="num">+ עיר</th><th class="num">+ גיל וגובה</th>""",
    """<th class="num">+ עיר</th><th class="num">+ גיל וגובה</th><th class="num">עיר + הצבעה (במקום SES)</th>""")
rep("""      ['עיר בלבד', UR.r2_city], ['אזור סטטיסטי (תקרה לכל משתנה שכונתי)', UR.r2_sa] ];""",
    """      ['הצבעה בלבד (חרדיות, ערביות)', UR.r2_votes], ['עיר בלבד', UR.r2_city], ['אזור סטטיסטי (תקרה לכל משתנה שכונתי)', UR.r2_sa] ];""")
rep("""`<rect class="${i === 6 ? 'b' : i === 0 ? 'w' : 'a'}\"""", """`<rect class="${i === bars.length - 1 ? 'b' : i === 0 ? 'w' : 'a'}\"""")
rep("""      ['צורה עירונית (צמתים, צפיפות, עירוב, תחבורה)', UR.m_form.r2]""", """      ['צורה עירונית (צמתים, צפיפות, עירוב, עסקים, חניה, עקמומיות, תחבורה)', UR.m_form.r2]""")
open('map_v4_template.html', 'w').write(s)
print('ok')
