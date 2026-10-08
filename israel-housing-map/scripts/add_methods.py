# One-off edit of map_v4_template.html: a "how this is computed" box (equation + definitions) under
# every result on the analysis page, and a new section on the floor premium by area type
# (Arab / Haredi / other) and the building-height effect at a fixed unit floor (build_floor_groups.py).
s = open('map_v4_template.html').read()
V = lambda x: f'<i>{x}</i>'
def box(eqs, text):
    eq = ''.join(f'<div class="eq" dir="ltr">{e}</div>' for e in eqs)
    return f'\n    <div class="method"><b>איך זה חושב</b>{eq}<p>{text}</p></div>'
lnp = 'ln <i>P</i><sub><i>i</i></sub>'
lnpm = 'ln(<i>P</i>/m²)<sub><i>i</i></sub>'
M = {
 '<h2>כל משתנה על המפה: בחירת משתנה, שנה ויחידה</h2>': box(
   ['value<sub><i>u</i></sub> = Σ<sub><i>s</i>∈<i>u</i></sub> numerator<sub><i>s</i></sub> / Σ<sub><i>s</i>∈<i>u</i></sub> denominator<sub><i>s</i></sub>'],
   'אין כאן רגרסיה. כל ערך של יחידה (מחוז, נפה, עיר) מחושב כיחס סכומים על האזורים הסטטיסטיים <i>s</i> שבה. למשל, דירות לקמ"ר הן סך הדירות חלקי סך השטח העירוני, ולא ממוצע של יחסים. משתני עסקאות לפי שנה: חציון (מחיר) או ממוצע (שטח, חדרים, גיל) של עסקאות הדירה באותה שנה ביחידה.'),
 '<h2>מדד מחירי דירות ריאלי: ארבע שיטות על אותן עסקאות</h2>': box(
   [f'(1) למ"ס: לכל חודש <i>t</i>, על עסקאות <i>t</i>−1 ו־<i>t</i>: {lnp} = θ<sub><i>t</i></sub>·1[<i>t<sub>i</sub></i>=<i>t</i>] + <i>X<sub>i</sub></i>′β<sub><i>t</i></sub> + α<sub><i>s</i>(<i>i</i>)</sub> + ε<sub><i>i</i></sub>,   <i>I<sub>t</sub></i> = <i>I</i><sub><i>t</i>−1</sub>·exp(θ̂<sub><i>t</i></sub>)',
    f'(2) משולב: {lnp} = θ<sub><i>t</i>(<i>i</i>)</sub> + <i>X<sub>i</sub></i>′β + α<sub><i>s</i>(<i>i</i>)</sub> + ε<sub><i>i</i></sub>',
    f'(3) אותו בניין: {lnpm} = θ<sub><i>t</i>(<i>i</i>)</sub> + α<sub><i>b</i>(<i>i</i>)</sub> + κ<sub><i>a</i>(<i>i</i>)</sub> + ε<sub><i>i</i></sub>',
    f'(4) אותה דירה: {lnpm} = θ<sub><i>t</i>(<i>i</i>)</sub> + α<sub><i>d</i>(<i>i</i>)</sub> + κ<sub><i>a</i>(<i>i</i>)</sub> + ε<sub><i>i</i></sub>,   <i>I<sub>t</sub></i> = 100·exp(θ̂<sub><i>t</i></sub> − θ̄<sub>2015</sub>)'],
   '<i>P</i> = מחיר העסקה ריאלי (מדד המחירים לצרכן, מחירי 2015). <i>t</i> = חודש. <i>s</i> = אזור סטטיסטי 2011, <i>b</i> = בניין (גוש־חלקה), <i>d</i> = דירה (גוש־חלקה־תת חלקה), <i>a</i> = שטח מעוגל למ"ר. <i>X</i> = לוג שטח, מספר חדרים (דמי), קומה (מ־govmap כשהעסקה מתאימה, אחרת "לא ידוע"), גיל הבניין (קבוצות), סוג (רגילה / גן / גג). אותו מדגם בכל ארבע השיטות: עסקאות רשות המסים, דירה שלמה, 1998 עד אוגוסט 2026.'),
 '<h3>שינוי ב־12 החודשים האחרונים, לפי שיטה</h3>': None,
 '<h2>גודל הדירה, מספר החדרים והטיית החלוקה</h2>': box(
   [f'OLS: {lnp} = β·ln m²<sub><i>i</i></sub> + <i>W<sub>i</sub></i>′γ + α<sub><i>s</i></sub> + τ<sub><i>t</i></sub> + ε<sub><i>i</i></sub>',
    'שלב ראשון: ln m²<sub><i>i</i></sub> = Σ<sub><i>r</i>≠3</sub> π<sub><i>r</i></sub>·1[<i>R<sub>i</sub></i>=<i>r</i>] + <i>W<sub>i</sub></i>′γ + α<sub><i>s</i></sub> + τ<sub><i>t</i></sub> + <i>u<sub>i</sub></i>',
    f'למ"ר: {lnpm} = (β−1)·ln m²<sub><i>i</i></sub> + <i>W<sub>i</sub></i>′γ + α<sub><i>s</i></sub> + τ<sub><i>t</i></sub> + ε<sub><i>i</i></sub>'],
   '<i>R</i> = מספר החדרים מעוגל כלפי מעלה (1 עד 8+, הבסיס 3), והדמי שלו הם המכשירים לשטח ב־2SLS. <i>W</i> = קומה, גיל הבניין, סוג הדירה. α<sub><i>s</i></sub> = אפקט קבוע לאזור סטטיסטי, τ<sub><i>t</i></sub> = לחודש. שגיאות התקן מקובצות לפי אזור סטטיסטי. אומדן ה־IV לשיפוע הוא היחס בין ההבדלים בלוג המחיר להבדלים בלוג השטח בין קבוצות החדרים (הנקודות בתרשים השמאלי).'),
 '<h2>הרגרסיה ההדונית: מה מעלה את מחיר הדירה</h2>': box(
   [f'{lnp} = θ<sub><i>t</i></sub> + <i>X<sub>i</sub></i>′β + α<sub><i>s</i></sub> + ε<sub><i>i</i></sub>,   effect = exp(β) − 1'],
   'זו רגרסיה (2) של המדד המשולב למעלה. בעמודה של לוג המחיר למ"ר המשתנה המוסבר הוא ln(<i>P</i>/m²), וההבדל היחיד הוא שמקדם לוג השטח קטן ב־1.'),
 '<h2>שינוי במחיר לפי עיר, 2015 עד 2025</h2>': box(
   ['Δ<sub><i>g</i></sub> = median(<i>P</i>/m²)<sub><i>g</i>, 2023–25</sub> / median(<i>P</i>/m²)<sub><i>g</i>, 2014–16</sub> − 1,   Δ<sub>city</sub> = median<sub><i>g</i>∈city</sub> Δ<sub><i>g</i></sub>',
    'turnover<sub>city</sub> = deals<sub>2015–25</sub> / (registered units × 11)'],
   'נומינלי, לגושים <i>g</i> עם 10 עסקאות לפחות בכל חלון. זה לא מדד מכירות חוזרות, ולכן בגוש שבו נבנו פרויקטים חדשים בין התקופות השינוי גדול יותר.'),
 '<h2>עליית מחירים ריאלית לפי עיר, 2008 עד 2025</h2>': box(
   [f'לכל עיר <i>c</i> בנפרד: {lnpm} = θ<sub><i>c</i>,<i>y</i>(<i>i</i>)</sub> + α<sub><i>d</i>(<i>i</i>)</sub> + κ<sub><i>a</i>(<i>i</i>)</sub> + ε<sub><i>i</i></sub>,   ratio = exp(θ̂<sub><i>c</i>,2025</sub> − θ̂<sub><i>c</i>,2008</sub>)'],
   '<i>y</i> = שנת המכירה, <i>d</i> = דירה, <i>a</i> = שטח מעוגל. רק דירות שנמכרו פעמיים לפחות. עסקאות לחודש: ספירה פשוטה של כל העסקאות (אחרי הסרת כפילויות) ושל דירות במדגם.'),
 '<h2>השטח הרשום של אותה דירה גדל ב־10%</h2>': box(
   ['ln m²<sub><i>it</i></sub> = θ<sub><i>y</i>(<i>t</i>)</sub> + α<sub><i>d</i>(<i>i</i>)</sub> + ε<sub><i>it</i></sub>,   drift<sub><i>y</i></sub> = exp(θ̂<sub><i>y</i></sub> − θ̂<sub>2015</sub>) − 1'],
   'על מכירות חוזרות של אותה דירה (<i>d</i>), עם אפקט קבוע לשנה. דירה לא גדלה, אז כל שינוי ב־θ הוא שינוי ברישום. התרשים הימני: ממוצע השטח ומ"ר לחדר לפי שנת הבנייה, בלי רגרסיה.'),
 '<h2>בתוך אותו בניין: דירה קטנה יקרה יותר למ"ר</h2>': box(
   [f'{lnpm} = Σ<sub><i>k</i></sub> φ<sub><i>k</i></sub>·1[m²<sub><i>i</i></sub> ∈ bin<sub><i>k</i></sub>] + α<sub><i>b</i>(<i>i</i>)</sub> + τ<sub><i>y</i>(<i>i</i>)</sub> + ε<sub><i>i</i></sub>,   gap<sub><i>k</i></sub> = exp(φ̂<sub><i>k</i></sub> − φ̂<sub>70–80</sub>) − 1'],
   'אותו בניין (<i>b</i>) ואותה שנה (<i>y</i>). התרשים השמאלי זהה, עם דמי למספר החדרים (מעוגל למעלה) במקום קבוצות השטח, והבסיס 3 חדרים.'),
 '<h2>תשואה ריאלית במכירה חוזרת</h2>': box(
   ['<i>r</i> = [ (<i>P</i><sub>2</sub>/CPI<sub>2</sub>) / (<i>P</i><sub>1</sub>/CPI<sub>1</sub>) ]<sup>1/years</sup> − 1'],
   'לכל זוג מכירות עוקבות של אותה דירה, שבו השטח הרשום השתנה בפחות מ־5% והמרווח חצי שנה לפחות. מוצג החציון של <i>r</i>, לפני עלויות עסקה ושכירות.'),
 '<h2>עירוניות ומחיר: האם צפיפות הצמתים מסבירה את ערך הבניין?</h2>': box(
   [f'שלב 1: {lnpm} = α<sub><i>b</i>(<i>i</i>)</sub> + τ<sub><i>t</i>(<i>i</i>)</sub> + κ<sub><i>a</i>(<i>i</i>)</sub> + ε<sub><i>i</i></sub>   →   α̂<sub><i>b</i></sub> = "אפקט הבניין"',
    'שלב 2: α̂<sub><i>b</i></sub> = <i>Z</i><sub><i>s</i>(<i>b</i>)</sub>′β + <i>L<sub>b</sub></i>′λ + μ<sub>city</sub> + Σ<sub><i>k</i></sub> 1[SES<sub><i>s</i></sub>=<i>k</i>] + <i>v<sub>b</sub></i>,   weight = min(<i>n<sub>b</sub></i>, 50)'],
   '<i>Z</i> = מדדי צורה של האזור הסטטיסטי (צמתים לקמ"ר מ־OSM, שיעור שטח דרכים, גודל חלקה, דירות לקמ"ר, עירוב שימושים, מסחר, תחנות אוטובוס), כל אחד בסטיות תקן. <i>L</i> = מיקום: לוג המרחק לתחנת רכבת או רק"ל, למרכז תל אביב ולחוף. μ<sub>city</sub> = אפקט קבוע ליישוב, SES = אשכול חברתי־כלכלי 2021. רק בניינים עם 3 עסקאות לפחות. שגיאות התקן מקובצות לפי אזור סטטיסטי. האחוז המדווח הוא exp(β)−1 לסטיית תקן. R² בתרשים הימני: מה שמודל עם קבוצת המשתנים בלבד מסביר מהשונות של α̂<sub><i>b</i></sub>.'),
 '<h2>בדיקת הצמתים מול OpenStreetMap</h2>': box(
   ['<i>k</i>(<i>v</i>) = number of street-segment ends at node <i>v</i>,   intersections = {<i>v</i> : <i>k</i>(<i>v</i>) ≥ 3}, merged when ‖<i>v</i> − <i>w</i>‖ ≤ 20 m',
    'density<sub><i>s</i></sub> = intersections in <i>s</i> / urban km²<sub><i>s</i></sub>'],
   'רשת הנסיעה של OSM (דרך Overture). מחבר באמצע קטע נספר פעמיים. שטח עירוני = סך שטח החלקות הקטנות מ־5 הקטאר באזור הסטטיסטי, וביהודה ושומרון השטח שבטווח 60 מ\' מרחוב. בטבלת המדדים: אותו שלב 2 כמו למעלה, עם מדד אחד בכל פעם, על מדגם משותף.'),
 '<h2>האפקט של כל משתנה, בכמה מודלים</h2>': box(
   ['α̂<sub><i>b</i></sub> = <i>Z</i>′β  →  + <i>L</i>′λ  →  + SES<sub><i>s</i></sub>  →  + μ<sub>city</sub>  →  + decade<sub><i>b</i></sub> + height<sub><i>b</i></sub>'],
   'כל עמודה מוסיפה קבוצת בקרות לשלב 2 של הסעיף הקודם. בטבלת הערים: ממוצע צמתים לקמ"ר ואפקט הבניין, משוקלל לפי דירות רשומות.'),
 '<h2>פרמיית קומה: אותו בניין, קומה אחרת</h2>': box(
   [f'{lnpm} = Σ<sub><i>f</i>≠1</sub> γ<sub><i>f</i></sub>·1[floor<sub><i>i</i></sub> = <i>f</i>] + α<sub><i>b</i>(<i>i</i>)</sub> + τ<sub><i>t</i>(<i>i</i>)</sub> + κ<sub><i>a</i>(<i>i</i>)</sub> + ε<sub><i>i</i></sub>,   premium<sub><i>f</i></sub> = exp(γ̂<sub><i>f</i></sub>) − 1'],
   'עסקאות govmap (שבהן רשומה קומת הדירה), אותו בניין <i>b</i>, חודש <i>t</i> ושטח מעוגל <i>a</i>. קומות 25 ומעלה מאוחדות. בתרשים הימני הדמי לקומה מוחלפים בדמי למיקום בבניין (קרקע, שליש תחתון, אמצעי, עליון, הקומה העליונה), לפי קבוצות גובה של הבניין.'),
 '<h2>פרמיית הגובה: רובה מיקום, מעט ממנה גובה</h2>': box(
   [f'{lnpm} = Σ<sub><i>h</i></sub> β<sub><i>h</i></sub>·1[floors<sub><i>b</i></sub> ∈ <i>h</i>] + δ·ln m²<sub><i>i</i></sub> + rooms<sub><i>i</i></sub> + age<sub><i>i</i></sub> + type<sub><i>i</i></sub> + quarter<sub><i>i</i></sub> + μ<sub><i>g</i>×<i>y</i></sub> + ε<sub><i>i</i></sub>'],
   'עסקאות רשות המסים 2015–2026. floors = מספר הקומות בבניין לפי הגזטיר (קבוצות, הבסיס 1–2). μ<sub><i>g</i>×<i>y</i></sub> = אפקט קבוע לגוש×שנה, כלומר השוואה בין בניינים גבוהים לנמוכים באותו גוש ובאותה שנה. "ללא השוואה בתוך הגוש" = אותה רגרסיה בלי μ, עם דמי לשנה. שגיאות התקן מקובצות לפי גוש. במאגר הזה אין קומת דירה, ולכן חלק מפרמיית המגדל כאן הוא קומה גבוהה. הסעיף "גובה הבניין בפיקוח על הקומה" למעלה מפריד בין השניים.'),
 '<h2>היצע דיור אפקטיבי: כמה "דירות ממוצעות" יש בכל עיר</h2>': box(
   ['<i>v<sub>p</sub></i> = m̃²<sub><i>p</i></sub> × p̃<sub><i>g</i>(<i>p</i>)</sub>,   effective units<sub>city</sub> = Σ<sub><i>p</i>∈city</sub> units<sub><i>p</i></sub> · <i>v<sub>p</sub></i> / <i>v̄</i>'],
   'm̃² = שטח חציוני לעסקה בחלקה <i>p</i> (אחרת בגוש, אחרת בעיר). p̃ = חציון המחיר למ"ר בגוש ב־2023–2026 (אחרת בעיר). <i>v̄</i> = השווי הממוצע לדירה בארץ. שווי המלאי = Σ units × <i>v</i>.'),
 '<h2>כלכלת ההתחדשות העירונית</h2>': box(
   ['profitable ⇔ (<i>m</i> − 1)·<i>P</i> ≥ <i>m</i>·<i>C</i>·1.15   ⇔   <i>P</i> ≥ 1.15·<i>C</i>·<i>m</i>/(<i>m</i> − 1)'],
   '<i>m</i> = מספר הדירות החדשות על כל דירה קיימת (אחת חוזרת לדייר), <i>C</i> = עלות לכל מ"ר שנבנה (בנייה, תכנון, שכירות לדיירים, מסים), 15% = רווח יזמי. <i>P</i> = חציון המחיר למ"ר בגוש. חסם עליון כלכלי בלבד.'),
 '<h2>סייר אזורים: הכל לפי מחוז, נפה ועיר</h2>': box(
   ['I<sub>area, t</sub>: equations (1)–(4) of the price-index section, estimated on the deals in the area'],
   'ארבעת המדדים מחושבים מחדש לכל אזור, חודשי ברמת הארץ והמחוז ורבעוני מתחת לזה. היסטוגרמות על קבוצות קבועות, אחידות לכל האזורים, עם ההתפלגות הארצית בקו מקווקו.'),
}
for h, b in M.items():
    if b is None: continue
    assert s.count(h) == 1, h
    i = s.index(h); j = s.index('\n  </section>', i)
    s = s[:j] + b + s[j:]
# yoy table: short note inside the same section as the 12-month chart
h = '<h3>שינוי ב־12 החודשים האחרונים, לפי שיטה</h3>'; i = s.index(h); j = s.index('\n  </section>', i)
s = s[:j] + box(['<i>g<sub>t</sub></i> = <i>I<sub>t</sub></i> / <i>I</i><sub><i>t</i>−12</sub> − 1,   cumulative = Ī<sub>end</sub> / Ī<sub>start</sub> − 1 (annual means)'],
               'מתוך ארבעת המדדים של הסעיף הקודם. המתאמים וסטיות התקן מחושבים על השינויים החודשיים והשנתיים.') + s[j:]

# ---------- new section: floor premium by area type, and building height at a fixed unit floor
NEW = '''
  <section id="floorgrp">
    <h2>קומה גבוהה לפי סוג אזור, וגובה הבניין בפיקוח על הקומה</h2>
    <p class="lede" id="fglede"></p>
    <div class="two">
      <div class="chart"><h3>פער במחיר למ"ר מול קומה ראשונה, באותו בניין, לפי סוג אזור</h3><div class="key" id="fgkey"></div>
        <svg id="fgline" viewBox="0 0 560 270" role="img" aria-label="פרמיית קומה לפי סוג אזור"></svg></div>
      <div class="chart"><h3>פער במחיר למ"ר מול בניין של 3–4 קומות, באותו גוש ובאותה שנה</h3>
        <div class="key"><span><i style="background:var(--btn)"></i>באותה קומת דירה</span><span><i style="background:var(--nodata)"></i>בלי פיקוח על קומת הדירה</span></div>
        <svg id="fgh" viewBox="0 0 560 250" role="img" aria-label="אפקט גובה הבניין"></svg></div>
    </div>
    <div class="tablewrap" style="max-height:none;margin-top:12px"><table style="font-size:13px" id="fgtab"></table></div>''' + box(
   [f'מודל 1, לכל קבוצה: {lnpm} = Σ<sub><i>f</i>≠1</sub> γ<sub><i>f</i></sub>·1[floor<sub><i>i</i></sub> = <i>f</i>] + α<sub><i>b</i></sub> + τ<sub><i>t</i></sub> + κ<sub><i>a</i></sub> + ε<sub><i>i</i></sub>',
    f'מודל 2: {lnpm} = Σ<sub><i>h</i>≠3–4</sub> β<sub><i>h</i></sub>·1[floors<sub><i>b</i></sub> ∈ <i>h</i>] + Σ<sub><i>f</i>≠1</sub> γ<sub><i>f</i></sub>·1[floor<sub><i>i</i></sub> = <i>f</i>] + δ·ln m²<sub><i>i</i></sub> + rooms<sub><i>i</i></sub> + age<sub><i>b</i></sub> + μ<sub><i>g</i>×<i>y</i></sub> + τ<sub><i>t</i></sub> + ε<sub><i>i</i></sub>'],
   'עסקאות govmap עם קומת דירה, 1998–2026. <b>סוג אזור</b> לפי מיקום החלקה: <b>ערבי</b> = אזור סטטיסטי (מפקד 2008) שהדת העיקרית בו אינה יהודית; <b>חרדי</b> = אזור יהודי שבו 40% ומעלה מבני 15+ למדו לאחרונה בישיבה (מפקד 2008, שכבת ההשכלה; בבני ברק החציון 72%, במודיעין עילית 94%, בתל אביב 1.4%); <b>אחר</b> = כל השאר. מודל 1: אותו בניין <i>b</i>, חודש <i>t</i>, שטח מעוגל <i>a</i>; שגיאות תקן לפי בניין. מודל 2: floors = קומות בבניין לפי הגזטיר; μ<sub><i>g</i>×<i>y</i></sub> = גוש×שנה, כך שההשוואה היא בין בניינים גבוהים לנמוכים באותו גוש ובאותה שנה, באותה קומת דירה; age = גיל הבניין (קבוצות); שגיאות תקן לפי גוש. העמודה האפורה היא אותה רגרסיה בלי הדמי לקומת הדירה.') + '\n  </section>'
anchor = '\n  <section>\n    <h2>פרמיית הגובה: רובה מיקום, מעט ממנה גובה</h2>'
assert s.count(anchor) == 1
s = s.replace(anchor, NEW + anchor)
s = s.replace('<!--REPORT--><script type="application/json" id="floor-data">/*FLOOR*/</script><!--/REPORT-->',
              '<!--REPORT--><script type="application/json" id="floor-data">/*FLOOR*/</script><!--/REPORT-->\n<!--REPORT--><script type="application/json" id="floorg-data">/*FLOORG*/</script><!--/REPORT-->')
JS = r'''
  // ---------- floor premium by area type; building height at a fixed unit floor ----------
  { const FG = J('floorg-data'), GR = [['אחר','k1','אחר'],['חרדי','k2','חרדי'],['ערבי','k3','ערבי']];
    const pct1 = v => (v > 0 ? '+' : '') + (v*100).toFixed(1) + '%';
    document.getElementById('fgkey').innerHTML = GR.map(([g,k,l]) => `<span><i style="background:var(--${k})"></i>${l} (${fmt(FG.groups[g].n)} עסקאות)</span>`).join('');
    const ser = GR.map(([g,k]) => ({ cls:k, end:true, pts: Object.entries(FG.groups[g].floor).map(([f,v]) => [+f, v[2] >= 150 ? v[0]*100 : null]).filter(p => p[0] <= 12 && p[1] != null).sort((a,b) => a[0]-b[0]) }));
    lineChart('fgline', ser, { x0:0, x1:12, y0:-6, y1:12, yt:[-5,0,5,10], xt:[0,2,4,6,8,10,12], base:0, yf: v => (v > 0 ? '+' : '') + v + '%', xf: v => v === 0 ? 'קרקע' : v, l:42 });
    const HB = ['1–2','3–4','5–8','9–12','13–20','21–30','31+'], A = FG.height['הכול'];
    barChart('fgh', HB, [{ cls:'a', label:true, vals: HB.map(h => A.with_floor[h] ? A.with_floor[h][0] : null) },
                         { cls:'b', label:false, vals: HB.map(h => A.no_floor[h] ?? null) }],
      { lo:-0.02, hi:0.2, ticks:[0,0.05,0.1,0.15,0.2], tf: v => (v>0?'+':'') + Math.round(v*100) + '%', xlab:'קומות בבניין' });
    const cell = (x, n) => x == null ? '<td class="num">—</td>' : `<td class="num"${x[1] && Math.abs(x[0]) > 2*x[1] ? ' style="font-weight:700;color:var(--fg)"' : ' style="color:var(--muted)"'}>${pct1(x[0])}${n ? ` <span style="color:var(--muted);font-weight:400">(${fmt(x[2])})</span>` : ''}</td>`;
    const FL = ['0','2','3','4','5','6','8','10','15','20'];
    document.getElementById('fgtab').innerHTML = `<thead><tr><th>קומת הדירה (מול ראשונה)</th>${GR.map(([g,,l]) => `<th class="num">${l}</th>`).join('')}<th>גובה הבניין (מול 3–4)</th>${['הכול','חרדי','ערבי'].map(g => `<th class="num">${g === 'הכול' ? 'כל האזורים' : g}</th>`).join('')}</tr></thead><tbody>` +
      FL.map((f, r) => `<tr><td>${f === '0' ? 'קרקע' : f}</td>${GR.map(([g]) => cell(FG.groups[g].floor[f], true)).join('')}<td>${HB[r] ?? ''}</td>${HB[r] ? ['הכול','חרדי','ערבי'].map(g => cell(FG.height[g].with_floor[HB[r]], true)).join('') : '<td></td><td></td><td></td>'}</tr>`).join('') + '</tbody>';
    const O = FG.groups['אחר'].floor, Hh = FG.groups['חרדי'].floor, Ar = FG.groups['ערבי'].floor;
    document.getElementById('fglede').textContent =
      `באזורים שאינם חרדיים או ערביים, דירת קרקע יקרה ב־${pct1(O['0'][0])} מקומה ראשונה באותו בניין, קומות 2–4 כמעט שוות לה, ומקומה 5 המחיר עולה: קומה 10 ב־${pct1(O['10'][0])}. `+
      `באזורים חרדיים אין פרמיה לקומת קרקע (${pct1(Hh['0'][0])}), וקומות 4–5 זולות מהראשונה (${pct1(Hh['4'][0])}, ${pct1(Hh['5'][0])}), אולי בגלל השימוש המוגבל במעלית בשבת. מעל קומה 8 יש מעט עסקאות. `+
      `באזורים ערביים יש רק ${fmt(FG.groups['ערבי'].n)} עסקאות עם קומה ב־govmap, רובן בערים מעורבות, והאומדנים רועשים: קומה 2 ${pct1(Ar['2'][0])}, קרקע ${pct1(Ar['0'][0])}. `+
      `גובה הבניין: באותו גוש ובאותה שנה, ובאותה קומת דירה, בניין של 31 קומות ומעלה יקר ב־${pct1(A.with_floor['31+'][0])} מבניין של 3–4 קומות. בלי הפיקוח על הקומה הפער הוא ${pct1(A.no_floor['31+'])}, כלומר כשני שלישים מפרמיית המגדל הם הקומה הגבוהה של הדירה עצמה. בניינים של 1–2 קומות יקרים ב־${pct1(A.with_floor['1–2'][0])} (חצר, צמוד קרקע).`;
    fixBidi(document.getElementById('floorgrp')); }
'''
a = "  // ---------- side-panel tabs ----------"
assert s.count(a) == 1
s = s.replace("  }\n" + a, JS + "  }\n" + a, 1) if s.count("  }\n" + a) == 1 else None
assert s is not None
css = '''.method{background:#f7f9fa;border:1px solid var(--rule);border-radius:5px;padding:10px 12px;margin-top:12px;font-size:13.5px;color:var(--fg);max-width:100%;min-width:0}
.method>b{display:block;font-size:12.5px;color:var(--muted);letter-spacing:.02em;margin-bottom:4px}
.method .eq{direction:ltr;text-align:left;font-family:"Cambria Math","STIX Two Math","Latin Modern Math",Georgia,serif;font-size:15px;background:#fff;border-radius:4px;padding:6px 10px;margin:4px 0;overflow-x:auto;white-space:nowrap;unicode-bidi:isolate}
.method p{margin:6px 0 0;color:var(--muted);max-width:110ch;line-height:1.55}
.method p i,.method p b{color:var(--fg)}
'''
s = s.replace('@media (prefers-reduced-motion:reduce)', css + '@media (prefers-reduced-motion:reduce)', 1)
open('map_v4_template.html', 'w').write(s)
print('ok')
