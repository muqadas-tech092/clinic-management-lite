"""Printable payment receipt / invoice."""
from __future__ import annotations

from reportlab.lib.units import mm
from reportlab.platypus import Spacer, Table, TableStyle

from core.utils import fmt_date, fmt_datetime, money
from pdf.base import BORDER, MUTED, NAVY, SOFT, TEAL, P, build_pdf, data_table, kv_table, letterhead, page_size, signature_block

L = {
    "title": ("Payment Receipt", "ادائیگی کی رسید"), "invoice": ("Invoice No.", "انوائس نمبر"), "date": ("Date", "تاریخ"),
    "patient": ("Patient", "مریض"), "pid": ("Patient ID", "مریض آئی ڈی"), "doctor": ("Doctor", "ڈاکٹر"),
    "desc": ("Description", "تفصیل"), "qty": ("Qty", "تعداد"), "rate": ("Rate", "قیمت"), "amount": ("Amount", "رقم"),
    "fee": ("Consultation fee", "معائنہ فیس"), "subtotal": ("Subtotal", "ذیلی کل"), "discount": ("Discount", "رعایت"),
    "total": ("Total", "کل"), "received": ("Received", "وصول شدہ"), "balance": ("Balance due", "بقایا"),
    "payments": ("Payments", "ادائیگیاں"), "method": ("Method", "طریقہ"), "ref": ("Reference", "حوالہ"),
    "status": ("Status", "حیثیت"), "sig": ("Received by", "وصول کنندہ"),
}


def lab(key: str, lang: str) -> str:
    en, ur = L[key]
    return ur if lang == "ur" else (f"{en}\n{ur}" if lang == "both" else en)


def build(inv: dict, settings: dict, lang: str = "en") -> bytes:
    size = page_size(settings)
    width = size[0] - 24 * mm
    sym = settings.get("currency_symbol", "Rs.")
    el = letterhead(settings, None, width, lang)
    el.append(Spacer(1, 2 * mm))
    el.append(P(lab("title", lang), 13, bold=True, color=TEAL))
    el.append(Spacer(1, 2 * mm))
    el.append(kv_table([
        (lab("invoice", lang), inv["invoice_no"]), (lab("date", lang), fmt_date(inv["invoice_date"])),
        (lab("patient", lang), inv["patient_name"]), (lab("pid", lang), inv["patient_code"]),
        (lab("doctor", lang), inv.get("doctor_name") or "-"), (lab("status", lang), inv["status"]),
    ], width, cols=2, rtl=(lang == "ur")))
    el.append(Spacer(1, 3 * mm))

    rows = []
    if inv["consultation_fee"]:
        rows.append([lab("fee", lang), "1", money(inv["consultation_fee"], sym), money(inv["consultation_fee"], sym)])
    for it in inv.get("items", []):
        rows.append([it["description"], f"{it['qty']:g}", money(it["unit_price"], sym), money(it["amount"], sym)])
    widths = [width * 0.52, width * 0.12, width * 0.18, width * 0.18]
    el.append(data_table([lab("desc", lang), lab("qty", lang), lab("rate", lang), lab("amount", lang)], rows, widths,
                         align_right_cols=(1, 2, 3), rtl=(lang == "ur")))
    subtotal = inv["consultation_fee"] + inv["services_total"]
    totals = [[lab("subtotal", lang), money(subtotal, sym)]]
    if inv["discount_amount"]:
        totals.append([f"{lab('discount', lang)} ({inv.get('discount_reason') or ''})", f"- {money(inv['discount_amount'], sym)}"])
    totals += [[lab("total", lang), money(inv["total"], sym)], [lab("received", lang), money(inv["paid"], sym)],
               [lab("balance", lang), money(inv["outstanding"], sym)]]
    tt = Table([[P(k, 9, bold=(k == lab("total", lang) or k == lab("balance", lang)), align="right"),
                 P(v, 9, bold=(k == lab("total", lang) or k == lab("balance", lang)), align="right")] for k, v in totals],
               colWidths=[width * 0.72, width * 0.28])
    tt.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                            ("LINEABOVE", (0, len(totals) - 3), (-1, len(totals) - 3), 0.6, NAVY),
                            ("BACKGROUND", (0, len(totals) - 1), (-1, len(totals) - 1), SOFT)]))
    el += [Spacer(1, 2 * mm), tt]

    if inv.get("payments"):
        el.append(Spacer(1, 4 * mm))
        el.append(P(lab("payments", lang), 9.5, bold=True))
        el.append(Spacer(1, 1 * mm))
        prow = [[fmt_datetime(p["paid_at"]), p["method"], p.get("reference") or "-", money(p["amount"], sym)] for p in inv["payments"]]
        el.append(data_table([lab("date", lang), lab("method", lang), lab("ref", lang), lab("amount", lang)], prow,
                             [width * 0.34, width * 0.22, width * 0.24, width * 0.20], align_right_cols=(3,), rtl=(lang == "ur")))

    el.append(Spacer(1, 8 * mm))
    el.append(signature_block(width, L["sig"][0], L["sig"][1], "en" if lang == "en" else "both"))
    el.append(Spacer(1, 3 * mm))
    if lang in ("en", "both") and settings.get("receipt_footer_en"):
        el.append(P(settings["receipt_footer_en"], 8, color=MUTED, align="center"))
    if lang in ("ur", "both") and settings.get("receipt_footer_ur"):
        el.append(P(settings["receipt_footer_ur"], 8.5, color=MUTED, align="center"))
    return build_pdf(el, size, margins_mm=12, footer_text=f"Computer-generated receipt · {inv['invoice_no']}", title=f"Receipt {inv['invoice_no']}")
