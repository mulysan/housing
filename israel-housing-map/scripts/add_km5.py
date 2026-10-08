# One-off edit of map_v4_template.html (2026-10-08): Katz-Murphy in 5-year periods (build_km.py, out.p5):
# table (levels / differences / IV, cities and SES clusters), scatter of period-to-period price change vs
# supply change across cities, and a popup subsection on the specification.
s = open('map_v4_template.html').read()
def rep(a, b):
    global s; assert s.count(a) == 1, (s.count(a), a[:90]); s = s.replace(a, b)
rep("""    <div class="tablewrap" style="max-height:none;margin-top:12px"><table style="font-size:13px" id="kmtab"></table></div>""",
"""    <div class="tablewrap" style="max-height:none;margin-top:12px"><table style="font-size:13px" id="kmtab"></table></div>
    <h3 style="margin-top:22px">תקופות של 5 שנים, כמו תתי־התקופות במאמר המקורי</h3>
    <p class="lede" id="km5lede"></p>
    <div class="two">
      <div class="chart"><h3>שינוי במחיר מול שינוי בהיצע בין תקופות עוקבות, לפי עיר</h3>
        <svg id="km5sc" viewBox="0 0 560 300" role="img" aria-label="שינוי במחיר מול שינוי בהיצע בין תקופות"></svg></div>
      <div class="tablewrap" style="max-height:none;min-width:0"><table style="font-size:13px" id="km5tab"></table></div>
    </div>""")
rep("""    const gc = C.growth_corr;""", """    const gc = C.growth_corr;
    if (KM.p5) { const P5 = KM.p5, PC = P5.city.models, PT = P5.tier.models;
      const pts5 = P5.city.pts.map(([m, p, x, y]) => [`${m} · ${P5.city.periods[p-1]}→${P5.city.periods[p]}`, x, y]);
      scatter('km5sc', pts5, lf(pts5), { xlab:'שינוי בלוג מלאי הדירות בין תחילות התקופות', ylab:'שינוי במקדם המחיר בין התקופות (לוג)', r:3 });
      const cl5 = m => `<td class="num"${star(m.b[0], m.se[0])}>${f3(m.b[0])} <span style="font-weight:400;color:var(--muted)">(${m.se[0].toFixed(3)})</span></td>`;
      document.getElementById('km5tab').innerHTML = `<thead><tr><th>מדד ההיצע</th><th class="num">רמות: תקופה + עיר</th><th class="num">+ מגמה לעיר</th><th class="num">הפרשים: תקופה</th><th class="num">הפרשים + עיר</th><th class="num">הפרשים, IV</th><th class="num">אשכולות SES, הפרשים</th></tr></thead><tbody>` +
        W3.map(([w, lab]) => `<tr><td>${lab}</td>${cl5(PC['lev_'+w])}${cl5(PC['levtr_'+w])}${cl5(PC['dif_'+w])}${cl5(PC['diftr_'+w])}${cl5(PC['dif_'+w+'_iv'])}${cl5(PT['dif_'+w])}</tr>`).join('') +
        `<tr><td>R² פנימי, N מול E (הפרשים)</td><td colspan="6" class="num">${(PC.dif_n.r2_within*100).toFixed(1)}% מול ${(PC.dif_val.r2_within*100).toFixed(1)}%</td></tr></tbody>`;
      document.getElementById('km5lede').textContent =
        `Katz ו־Murphy (1992) אמדו את המודל של שתי הקבוצות על סדרה שנתית (1963–1987), ואת 64 הקבוצות המפורטות בחנו דרך שינויים בשלוש תתי־תקופות (1963–71, 1971–79, 1979–87). כאן: שנות המכירה בחמש תקופות (${P5.city.periods.join(', ')}), מקדם מחיר לכל עיר ותקופה ממודל אפקט קבוע לבניין, וההיצע הוא לוג המלאי בסוף השנה שלפני תחילת התקופה. `+
        `בהפרשים בין תקופות עוקבות (${P5.city.n_mk} ערים, ${PC.dif_n.n} שינויים) המקדם של מספר הדירות הוא ${f3(PC.dif_n.b[0])} (${PC.dif_n.se[0]}), ועם מכשיר ה"חלק ההיסטורי" ${f3(PC.dif_n_iv.b[0])} (F = ${PC.dif_n_iv.first_stage_F}). כמו בנתונים השנתיים, אין שיפוע שלילי: ערים שבהן המלאי גדל יותר לא נעשו זולות יחסית. `+
        `גם כאן היצע אפקטיבי לא מסביר יותר ממספר הדירות. בכל העמודות המספר הוא −1/σ; ערך חיובי אינו מתאים לעקומת ביקוש יורדת.`; }""")
rep("""      <h3>8. תוצאות: 10 אשכולות SES""", """      ${KM.p5 ? `<h3>7א. תקופות של 5 שנים</h3>
      <p>זה הניתוח הקרוב ביותר לתתי־התקופות של Katz ו־Murphy. τ = ${KM.p5.city.periods.join(', ')}. מחיר: θ<sub>jτ</sub> = אפקט עיר×תקופה מאותה רגרסיה עם אפקט קבוע לבניין ולשטח מעוגל, מנורמל ל־0 ב־2013–17. היצע: ln S<sub>j</sub> בסוף השנה שלפני תחילת התקופה (1997, 2002, 2007, 2012, 2017). כל נתוני ההיצע הם לפני חיתוך פיגור הרישום, ולכן המחירים כאן ממשיכים עד 2022. רק ערים עם חמש התקופות.</p>
      <div class="eq">רמות:   θ<sub>jτ</sub> = μ<sub>τ</sub> + δ<sub>j</sub> [+ γ<sub>j</sub>τ] − (1/σ) ln S<sub>jτ</sub> + u<sub>jτ</sub></div>
      <div class="eq">הפרשים:   Δθ<sub>jτ</sub> = Δμ<sub>τ</sub> [+ γ<sub>j</sub>] − (1/σ) Δln S<sub>jτ</sub> + Δu<sub>jτ</sub></div>
      <p>ערים, הפרשים: N ${f3(KM.p5.city.models.dif_n.b[0])} (${KM.p5.city.models.dif_n.se[0]}), F ${f3(KM.p5.city.models.dif_m2.b[0])} (${KM.p5.city.models.dif_m2.se[0]}), E ${f3(KM.p5.city.models.dif_val.b[0])} (${KM.p5.city.models.dif_val.se[0]}). IV: N ${f3(KM.p5.city.models.dif_n_iv.b[0])} (${KM.p5.city.models.dif_n_iv.se[0]}), F ראשון ${KM.p5.city.models.dif_n_iv.first_stage_F}. N ו־E יחד: N ${f3(KM.p5.city.models.dif_horse.b[0])}, E ${f3(KM.p5.city.models.dif_horse.b[1])}, אבל השניים כמעט זהים, ולכן הפיצול לא יציב. אשכולות SES, הפרשים: N ${f3(KM.p5.tier.models.dif_n.b[0])} (${KM.p5.tier.models.dif_n.se[0]}); עם מכשיר ${f3(KM.p5.tier.models.dif_n_iv.b[0])}, אבל המכשיר חלש (F = ${KM.p5.tier.models.dif_n_iv.first_stage_F}). שגיאות תקן מקובצות לפי שוק.</p>` : ''}
      <h3>8. תוצאות: 10 אשכולות SES""")
open('map_v4_template.html', 'w').write(s); print('ok')
