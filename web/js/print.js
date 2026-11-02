/* Print-ready HTML documents: prescription, receipt, token slip and tabular report, with clinic letterhead,
   bilingual labels (pdf/prescription.py, pdf/receipt.py, pdf/token_slip.py) and a signature area. */
import { ageFromDob, formatMoney, nowISO } from "./store.js";
import { esc, fmtDate, fmtTime, fmtDateTime, logoSrc, hasLogo } from "./ui.js";

const RX = {
  rx_no: ["Rx No.", "نسخہ نمبر"], date: ["Date", "تاریخ"], patient: ["Patient", "مریض"], age_sex: ["Age / Sex", "عمر / جنس"], pid: ["Patient ID", "مریض آئی ڈی"],
  phone: ["Phone", "فون"], diagnosis: ["Diagnosis", "تشخیص"], vitals: ["Vitals", "وائٹلز"], medicine: ["Medicine", "دوا"], dosage: ["Dosage", "خوراک"],
  frequency: ["Frequency", "تعداد"], duration: ["Duration", "مدت"], instructions: ["Instructions", "ہدایات"], notes: ["Advice / Notes", "ہدایات / نوٹس"],
  follow_up: ["Follow-up", "فالو اپ"], allergies: ["Allergies", "الرجی"], signature: ["Doctor's signature & stamp", "ڈاکٹر کے دستخط و مہر"],
  no_meds: ["No medicines listed.", "کوئی دوا درج نہیں۔"], draft: ["DRAFT - not yet signed by the doctor", "مسودہ - ڈاکٹر کے دستخط باقی ہیں"],
  generated: ["Computer-generated prescription", "کمپیوٹر سے تیار کردہ نسخہ"],
};
const RC = {
  title: ["Payment Receipt", "ادائیگی کی رسید"], invoice: ["Invoice No.", "انوائس نمبر"], date: ["Date", "تاریخ"], patient: ["Patient", "مریض"], pid: ["Patient ID", "مریض آئی ڈی"],
  doctor: ["Doctor", "ڈاکٹر"], desc: ["Description", "تفصیل"], qty: ["Qty", "تعداد"], rate: ["Rate", "قیمت"], amount: ["Amount", "رقم"], fee: ["Consultation fee", "معائنہ فیس"],
  subtotal: ["Subtotal", "ذیلی کل"], discount: ["Discount", "رعایت"], total: ["Total", "کل"], received: ["Received", "وصول شدہ"], balance: ["Balance due", "بقایا"],
  payments: ["Payments", "ادائیگیاں"], method: ["Method", "طریقہ"], ref: ["Reference", "حوالہ"], status: ["Status", "حیثیت"], sig: ["Received by", "وصول کنندہ"],
  generated: ["Computer-generated receipt", "کمپیوٹر سے تیار کردہ رسید"],
};
const TK = { token: ["TOKEN", "ٹوکن"], patient: ["Patient", "مریض"], doctor: ["Doctor", "ڈاکٹر"], date: ["Date", "تاریخ"], issued: ["Issued", "جاری"], appointment: ["Appointment", "اپائنٹمنٹ"],
  wait: ["Please wait for your number to be called.", "براہ کرم اپنے نمبر کے پکارے جانے کا انتظار کریں۔"] };
const STATUS_UR = { Paid: "ادا شدہ", Partial: "جزوی", Unpaid: "غیر ادا شدہ", Cancelled: "منسوخ", Signed: "دستخط شدہ", Draft: "مسودہ" };
const SEX = { Male: ["M", "مرد"], Female: ["F", "عورت"], Other: ["-", "دیگر"] };

/** Label in the requested language: "en", "ur" or "both" (English with Urdu underneath). */
const lab = (L, key, lang) => { const [en, ur] = L[key]; return lang === "ur" ? `<span class="ur">${esc(ur)}</span>` : lang === "both" ? `${esc(en)}<span class="ur sub">${esc(ur)}</span>` : esc(en); };
const sym = (settings) => settings.currency_symbol || "Rs.";
const paperClass = (settings) => `paper-${(settings.paper_size || "A5").toLowerCase()}`;
const wrap = (settings, lang, inner, cls = "") => `<div class="doc ${paperClass(settings)} ${cls} ${lang === "ur" ? "doc-ur" : ""}" dir="${lang === "ur" ? "rtl" : "ltr"}">${inner}</div>`;

export function letterhead(settings, doctor = null) {
  const logo = hasLogo() ? `<img class="doc-logo" src="${logoSrc()}" alt=""/>` : "";
  const doc = doctor ? `<div class="doc-doctor"><b>${esc(doctor.name || "")}</b>${doctor.qualification ? `<div>${esc(doctor.qualification)}</div>` : ""}${doctor.specialization ? `<div>${esc(doctor.specialization)}</div>` : ""}${doctor.registration_no ? `<div>Reg. No. ${esc(doctor.registration_no)}</div>` : ""}</div>` : "";
  return `<div class="doc-head"><div class="doc-clinic">${logo}<div><div class="doc-name">${esc(settings.clinic_name || "")}</div><div class="doc-meta">${esc(settings.clinic_tagline || "")}</div><div class="doc-meta">${esc(settings.clinic_address || "")}</div><div class="doc-meta">${esc(settings.clinic_phone || "")}${settings.clinic_email ? ` &nbsp; ${esc(settings.clinic_email)}` : ""}</div></div></div>${doc}</div>`;
}
const kvGrid = (pairs, cols = 2) => `<div class="doc-kv cols-${cols}">${pairs.map(([k, v]) => `<div class="k">${k}</div><div class="v">${v}</div>`).join("")}</div>`;
const tableHTML = (header, rows, right = []) => `<table class="doc-table"><thead><tr>${header.map((h, i) => `<th class="${right.includes(i) ? "r" : ""}">${h}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c, i) => `<td class="${right.includes(i) ? "r num" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
const signature = (L, lang) => `<div class="doc-sign"><div class="line"></div><div class="label">${lang === "en" ? esc(L.signature ? L.signature[0] : L.sig[0]) : `${esc(L.signature ? L.signature[0] : L.sig[0])} &nbsp;|&nbsp; <span class="ur">${esc(L.signature ? L.signature[1] : L.sig[1])}</span>`}</div></div>`;
const footers = (settings, lang, en, ur) => `${lang !== "ur" && settings[en] ? `<div class="doc-foot">${esc(settings[en])}</div>` : ""}${lang !== "en" && settings[ur] ? `<div class="doc-foot ur">${esc(settings[ur])}</div>` : ""}`;

export function prescriptionHTML(rx, items, settings, lang = "en") {
  const doctor = { name: rx.doctor_name, qualification: rx.qualification, specialization: rx.specialization, registration_no: rx.registration_no };
  const sex = SEX[rx.gender] || ["-", "-"];
  const pairs = [
    [lab(RX, "rx_no", lang), `<span class="num">${esc(rx.rx_number)}</span>`], [lab(RX, "date", lang), fmtDate(rx.visit_date || rx.created_at)],
    [lab(RX, "patient", lang), esc(rx.patient_name)], [lab(RX, "age_sex", lang), `${esc(ageFromDob(rx.dob))} / ${lang === "ur" ? sex[1] : sex[0]}`],
    [lab(RX, "pid", lang), `<span class="num">${esc(rx.patient_code)}</span>`], [lab(RX, "phone", lang), `<span class="num">${esc(rx.phone || "-")}</span>`],
  ];
  const vit = [];
  if (rx.bp_systolic || rx.bp_diastolic) vit.push(`BP ${rx.bp_systolic || "-"}/${rx.bp_diastolic || "-"} mmHg`);
  if (rx.pulse) vit.push(`Pulse ${rx.pulse}/min`); if (rx.temperature) vit.push(`Temp ${rx.temperature} F`); if (rx.weight) vit.push(`Wt ${rx.weight} kg`);
  const extra = [];
  if (vit.length) extra.push([lab(RX, "vitals", lang), `<span class="num">${esc(vit.join("   "))}</span>`]);
  if (rx.allergies) extra.push([lab(RX, "allergies", lang), esc(rx.allergies)]);
  if (rx.diagnosis && (settings.rx_show_diagnosis ?? "1") === "1") extra.push([lab(RX, "diagnosis", lang), esc(rx.diagnosis)]);
  const meds = items.length
    ? tableHTML(["#", lab(RX, "medicine", lang), lab(RX, "dosage", lang), lab(RX, "frequency", lang), lab(RX, "duration", lang), lab(RX, "instructions", lang)],
      items.map((it, i) => [String(i + 1), esc(it.medicine_name), esc(it.dosage || ""), esc(it.frequency || ""), esc(it.duration || ""), esc(it.instructions || "")]))
    : `<div class="doc-muted">${lab(RX, "no_meds", lang)}</div>`;
  const inner = `${letterhead(settings, doctor)}${kvGrid(pairs, 2)}${extra.length ? kvGrid(extra, 1) : ""}
    <div class="doc-rx">Rx</div>${meds}
    ${rx.notes ? `<div class="doc-block"><b>${lab(RX, "notes", lang)}</b><div>${esc(rx.notes).replace(/\n/g, "<br/>")}</div></div>` : ""}
    ${rx.follow_up_date ? `<div class="doc-block accent"><b>${lab(RX, "follow_up", lang)}:</b> ${fmtDate(rx.follow_up_date)}</div>` : ""}
    ${signature(RX, lang)}${footers(settings, lang, "rx_footer_en", "rx_footer_ur")}
    <div class="doc-gen">${lab(RX, "generated", lang)} &middot; <span class="num">${esc(rx.rx_number)}</span>${rx.status !== "Signed" ? ` &middot; ${lab(RX, "draft", lang)}` : ""}</div>`;
  return wrap(settings, lang, inner, "doc-rx-page");
}

export function receiptHTML(inv, settings, lang = "en") {
  const s = sym(settings); const m = (v) => `<span class="num">${esc(formatMoney(v, s))}</span>`;
  const rows = [];
  if (inv.consultation_fee) rows.push([lab(RC, "fee", lang), "1", m(inv.consultation_fee), m(inv.consultation_fee)]);
  for (const it of inv.items || []) rows.push([esc(it.description), `<span class="num">${it.qty}</span>`, m(it.unit_price), m(it.amount)]);
  const subtotal = inv.consultation_fee + inv.services_total;
  const status = lang === "ur" ? (STATUS_UR[inv.status] || inv.status) : inv.status;
  const totals = [[lab(RC, "subtotal", lang), m(subtotal)]];
  if (inv.discount_amount) totals.push([`${lab(RC, "discount", lang)} ${inv.discount_reason ? `(${esc(inv.discount_reason)})` : ""}`, `- ${m(inv.discount_amount)}`]);
  totals.push([`<b>${lab(RC, "total", lang)}</b>`, `<b>${m(inv.total)}</b>`], [lab(RC, "received", lang), m(inv.paid)], [`<b>${lab(RC, "balance", lang)}</b>`, `<b>${m(inv.outstanding)}</b>`]);
  const pays = (inv.payments || []).length ? `<div class="doc-block"><b>${lab(RC, "payments", lang)}</b>${tableHTML([lab(RC, "date", lang), lab(RC, "method", lang), lab(RC, "ref", lang), lab(RC, "amount", lang)],
    inv.payments.map((p) => [fmtDateTime(p.paid_at), esc(p.method), esc(p.reference || "-"), m(p.amount)]), [3])}</div>` : "";
  const inner = `${letterhead(settings, null)}<div class="doc-title">${lab(RC, "title", lang)}</div>
    ${kvGrid([[lab(RC, "invoice", lang), `<span class="num">${esc(inv.invoice_no)}</span>`], [lab(RC, "date", lang), fmtDate(inv.invoice_date)], [lab(RC, "patient", lang), esc(inv.patient_name)],
    [lab(RC, "pid", lang), `<span class="num">${esc(inv.patient_code)}</span>`], [lab(RC, "doctor", lang), esc(inv.doctor_name || "-")], [lab(RC, "status", lang), esc(status)]], 2)}
    ${tableHTML([lab(RC, "desc", lang), lab(RC, "qty", lang), lab(RC, "rate", lang), lab(RC, "amount", lang)], rows, [1, 2, 3])}
    <div class="doc-totals">${totals.map(([k, v]) => `<div class="k">${k}</div><div class="v">${v}</div>`).join("")}</div>
    ${pays}${signature(RC, lang)}${footers(settings, lang, "receipt_footer_en", "receipt_footer_ur")}
    <div class="doc-gen">${lab(RC, "generated", lang)} &middot; <span class="num">${esc(inv.invoice_no)}</span></div>`;
  return wrap(settings, lang, inner, "doc-receipt");
}

export function tokenSlipHTML(token, settings, lang = "en") {
  const L = (k) => lab(TK, k, lang);
  const prefix = settings.token_prefix || "";
  const rows = [[L("patient"), `${esc(token.patient_name)} (<span class="num">${esc(token.patient_code)}</span>)`], [L("doctor"), esc(token.doctor_name)], [L("date"), fmtDate(token.token_date)], [L("issued"), fmtDateTime(token.created_at)]];
  if (token.appt_time) rows.push([L("appointment"), fmtTime(token.appt_time)]);
  const inner = `<div class="doc-center">${hasLogo() ? `<img class="doc-logo" src="${logoSrc()}" alt=""/>` : ""}<div class="doc-name">${esc(settings.clinic_name || "")}</div><div class="doc-meta num">${esc(settings.clinic_phone || "")}</div></div>
    <div class="doc-center doc-muted" style="margin-top:4mm">${L("token")}</div>
    <div class="doc-token num">${esc(prefix)}${esc(token.token_no)}</div>
    ${kvGrid(rows, 1)}<div class="doc-center doc-muted" style="margin-top:5mm">${L("wait")}</div>`;
  return `<div class="doc paper-a6 doc-token-slip ${lang === "ur" ? "doc-ur" : ""}" dir="${lang === "ur" ? "rtl" : "ltr"}">${inner}</div>`;
}

export function reportHTML(title, subtitle, columns, rows, settings, summary = []) {
  const inner = `${letterhead(settings, null)}<div class="doc-title">${esc(title)}</div><div class="doc-meta">${esc(subtitle)}</div><div class="doc-meta">Generated ${fmtDateTime(nowISO())}</div>
    ${summary.length ? kvGrid(summary.map(([k, v]) => [esc(k), `<span class="num">${esc(v)}</span>`]), Math.min(3, summary.length)) : ""}
    ${rows.length ? tableHTML(columns.map((c) => esc(c.label)), rows.map((r) => columns.map((c) => esc(r[c.key] ?? ""))), columns.map((c, i) => (c.num ? i : -1)).filter((i) => i >= 0)) : `<div class="doc-muted">No data for the selected filters.</div>`}
    <div class="doc-gen">${esc(settings.clinic_name || "")} &middot; ${esc(title)}</div>`;
  return `<div class="doc paper-a4 landscape" dir="ltr">${inner}</div>`;
}
