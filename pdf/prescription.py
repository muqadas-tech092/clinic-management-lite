"""Printable prescription with clinic letterhead, bilingual labels and signature area."""
from __future__ import annotations

from reportlab.lib.units import mm
from reportlab.platypus import Spacer, Table, TableStyle

from core.utils import age_from_dob, fmt_date, money
from pdf.base import (BORDER, MUTED, NAVY, SOFT, TEAL, P, build_pdf, data_table, kv_table, letterhead, page_size,
                      signature_block)

L = {
    "rx_no": ("Rx No.", "نسخہ نمبر"), "date": ("Date", "تاریخ"), "patient": ("Patient", "مریض"),
    "age_sex": ("Age / Sex", "عمر / جنس"), "pid": ("Patient ID", "مریض آئی ڈی"), "phone": ("Phone", "فون"),
    "diagnosis": ("Diagnosis", "تشخیص"), "vitals": ("Vitals", "وائٹلز"), "medicine": ("Medicine", "دوا"),
    "dosage": ("Dosage", "خوراک"), "frequency": ("Frequency", "تعداد"), "duration": ("Duration", "مدت"),
    "instructions": ("Instructions", "ہدایات"), "notes": ("Advice / Notes", "ہدایات / نوٹس"),
    "follow_up": ("Follow-up", "فالو اپ"), "allergies": ("Allergies", "الرجی"), "signature": ("Doctor's signature & stamp", "ڈاکٹر کے دستخط و مہر"),
}


def lab(key: str, lang: str) -> str:
    en, ur = L[key]
    if lang == "ur":
        return ur
    if lang == "both":
        return f"{en}\n{ur}"
    return en


def build(rx: dict, items: list[dict], settings: dict, lang: str = "en") -> bytes:
    size = page_size(settings)
    width = size[0] - 24 * mm
    doctor = {k: rx.get(k) for k in ("name", "qualification", "specialization", "registration_no")}
    doctor["name"] = rx.get("doctor_name")
    el = letterhead(settings, doctor, width, lang)
    el.append(Spacer(1, 3 * mm))

    sex = {"Male": ("M", "مرد"), "Female": ("F", "عورت")}.get(rx.get("gender"), ("-", "-"))
    pairs = [
        (lab("rx_no", lang), rx["rx_number"]), (lab("date", lang), fmt_date(rx.get("visit_date") or rx["created_at"])),
        (lab("patient", lang), rx["patient_name"]), (lab("age_sex", lang), f"{age_from_dob(rx.get('dob'))} / {sex[0] if lang != 'ur' else sex[1]}"),
        (lab("pid", lang), rx["patient_code"]), (lab("phone", lang), rx.get("phone") or "-"),
    ]
    el.append(kv_table(pairs, width, cols=2, size=8.5, rtl=(lang == "ur")))

    vitals = []
    if rx.get("bp_systolic") or rx.get("bp_diastolic"):
        vitals.append(f"BP {rx.get('bp_systolic') or '-'}/{rx.get('bp_diastolic') or '-'} mmHg")
    if rx.get("pulse"):
        vitals.append(f"Pulse {rx['pulse']}/min")
    if rx.get("temperature"):
        vitals.append(f"Temp {rx['temperature']} F")
    if rx.get("weight"):
        vitals.append(f"Wt {rx['weight']} kg")
    extra = []
    if vitals:
        extra.append((lab("vitals", lang), "   ".join(vitals)))
    if rx.get("allergies"):
        extra.append((lab("allergies", lang), rx["allergies"]))
    if rx.get("diagnosis") and settings.get("rx_show_diagnosis", "1") == "1":
        extra.append((lab("diagnosis", lang), rx["diagnosis"]))
    if extra:
        el.append(Spacer(1, 1.5 * mm))
        el.append(kv_table(extra, width, cols=1, size=8.5, rtl=(lang == "ur")))

    el.append(Spacer(1, 3 * mm))
    rx_head = Table([[P("Rx", 18, bold=True, color=TEAL), P("", 8)]], colWidths=[14 * mm, width - 14 * mm])
    rx_head.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, BORDER), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    el.append(rx_head)
    el.append(Spacer(1, 2 * mm))

    if items:
        header = ["#", lab("medicine", lang), lab("dosage", lang), lab("frequency", lang), lab("duration", lang), lab("instructions", lang)]
        rows = [[str(i + 1), it["medicine_name"], it.get("dosage") or "", it.get("frequency") or "", it.get("duration") or "",
                 it.get("instructions") or ""] for i, it in enumerate(items)]
        widths = [width * w for w in (0.06, 0.30, 0.15, 0.19, 0.12, 0.18)]
        el.append(data_table(header, rows, widths, size=8.5, rtl=(lang == "ur")))
    else:
        el.append(P("No medicines listed." if lang != "ur" else "کوئی دوا درج نہیں۔", 9, color=MUTED))

    if rx.get("notes"):
        el.append(Spacer(1, 3 * mm))
        el.append(P(lab("notes", lang), 8.5, bold=True))
        el.append(P(rx["notes"], 9))
    if rx.get("follow_up_date"):
        el.append(Spacer(1, 2 * mm))
        el.append(P(f"{lab('follow_up', lang)}: {fmt_date(rx['follow_up_date'])}", 9, bold=True, color=TEAL))

    el.append(Spacer(1, 8 * mm))
    el.append(signature_block(width, L["signature"][0], L["signature"][1], "en" if lang == "en" else "both"))
    el.append(Spacer(1, 3 * mm))
    foot = []
    if lang in ("en", "both") and settings.get("rx_footer_en"):
        foot.append(P(settings["rx_footer_en"], 8, color=MUTED, align="center"))
    if lang in ("ur", "both") and settings.get("rx_footer_ur"):
        foot.append(P(settings["rx_footer_ur"], 8.5, color=MUTED, align="center"))
    el += foot
    status_note = "" if rx.get("status") == "Signed" else "DRAFT - not yet signed by the doctor"
    gen = f"Computer-generated prescription · {rx['rx_number']} · {status_note}".strip(" ·")
    return build_pdf(el, size, margins_mm=12, footer_text=gen, title=f"Prescription {rx['rx_number']}")
