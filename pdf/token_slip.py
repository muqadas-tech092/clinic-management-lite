"""Printable token slip (A6)."""
from __future__ import annotations

from reportlab.lib.pagesizes import A6
from reportlab.lib.units import mm
from reportlab.platypus import Spacer, Table, TableStyle

from core.utils import fmt_date, fmt_datetime, fmt_time
from pdf.base import P, TEAL, MUTED, SOFT, build_pdf, logo_flowable


def build(token: dict, settings: dict, lang: str = "en") -> bytes:
    w = A6[0] - 20 * mm
    prefix = settings.get("token_prefix", "T") or ""
    el = []
    logo = logo_flowable(settings, 12)
    if logo:
        el.append(logo)
    el += [
        P(settings.get("clinic_name", ""), 13, bold=True, color=TEAL, align="center"),
        P(settings.get("clinic_phone", ""), 8, color=MUTED, align="center"),
        Spacer(1, 4 * mm),
        P("TOKEN" if lang == "en" else "ٹوکن", 9, color=MUTED, align="center"),
    ]
    big = Table([[P(f"{prefix}{token['token_no']}", 40, bold=True, color=TEAL, align="center")]], colWidths=[w])
    big.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("TOPPADDING", (0, 0), (-1, -1), 8),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("ROUNDEDCORNERS", [6])]))
    el += [big, Spacer(1, 4 * mm)]
    rows = [
        ["Patient" if lang == "en" else "مریض", f"{token['patient_name']} ({token['patient_code']})"],
        ["Doctor" if lang == "en" else "ڈاکٹر", token["doctor_name"]],
        ["Date" if lang == "en" else "تاریخ", fmt_date(token["token_date"])],
        ["Issued" if lang == "en" else "جاری", fmt_datetime(token["created_at"])],
    ]
    if token.get("appt_time"):
        rows.append(["Appointment" if lang == "en" else "اپائنٹمنٹ", fmt_time(token["appt_time"])])
    tbl = Table([[P(k, 8.5, color=MUTED), P(v, 9)] for k, v in rows], colWidths=[w * 0.35, w * 0.65])
    tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    el += [tbl, Spacer(1, 5 * mm),
           P("Please wait for your number to be called." if lang == "en" else "براہ کرم اپنے نمبر کے پکارے جانے کا انتظار کریں۔",
             8.5, color=MUTED, align="center")]
    return build_pdf(el, A6, margins_mm=10, title=f"Token {prefix}{token['token_no']}")
