"""Shared ReportLab helpers: fonts (incl. Urdu shaping), letterhead, footer, tables."""
from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib.pagesizes import A4, A5, A6, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle, Image

from core import config
from core.utils import resolve_upload

TEAL = colors.HexColor(config.COLORS["primary"])
NAVY = colors.HexColor(config.COLORS["navy"])
MUTED = colors.HexColor(config.COLORS["muted"])
BORDER = colors.HexColor(config.COLORS["border"])
SOFT = colors.HexColor(config.COLORS["primary_soft"])

_FONTS: dict[str, str] = {}

WINDOWS_FONTS = Path("C:/Windows/Fonts")
URDU_CANDIDATES = [
    # user-provided fonts first (drop any Nastaliq .ttf into assets/fonts)
    *sorted(config.FONT_DIR.glob("*.ttf")),
    WINDOWS_FONTS / "NotoNastaliqUrdu-Regular.ttf",
    WINDOWS_FONTS / "tahoma.ttf",
    WINDOWS_FONTS / "arial.ttf",
    WINDOWS_FONTS / "segoeui.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoNastaliqUrdu-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]
LATIN_CANDIDATES = [
    config.FONT_DIR / "Inter-Regular.ttf",
    WINDOWS_FONTS / "segoeui.ttf",
    WINDOWS_FONTS / "arial.ttf",
    WINDOWS_FONTS / "tahoma.ttf",
]
LATIN_BOLD_CANDIDATES = [
    config.FONT_DIR / "Inter-Bold.ttf",
    WINDOWS_FONTS / "segoeuib.ttf",
    WINDOWS_FONTS / "arialbd.ttf",
    WINDOWS_FONTS / "tahomabd.ttf",
]


def _register(name: str, candidates) -> str | None:
    for p in candidates:
        try:
            if Path(p).exists():
                pdfmetrics.registerFont(TTFont(name, str(p)))
                return name
        except Exception:
            continue
    return None


def fonts() -> dict[str, str]:
    """Return {'latin','bold','urdu'} font names, registering TTFs on first use."""
    if _FONTS:
        return _FONTS
    latin = _register("CML-Latin", LATIN_CANDIDATES) or "Helvetica"
    bold = _register("CML-Bold", LATIN_BOLD_CANDIDATES) or ("Helvetica-Bold" if latin == "Helvetica" else latin)
    urdu = _register("CML-Urdu", URDU_CANDIDATES) or latin
    _FONTS.update(latin=latin, bold=bold, urdu=urdu)
    return _FONTS


def ur(text: str) -> str:
    """Shape and reorder Urdu/Arabic text for ReportLab (which has no bidi engine)."""
    if not text:
        return ""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def has_arabic(text) -> bool:
    return any("\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F" or "\uFB50" <= ch <= "\uFEFF" for ch in str(text or ""))


def txt(text) -> str:
    """Shape text automatically when it contains Arabic-script characters."""
    s = "" if text is None else str(text)
    return ur(s) if has_arabic(s) else s


def style(name: str = "body", size: float = 9.5, bold: bool = False, color=NAVY, align: str = "left",
          urdu: bool = False, leading: float | None = None) -> ParagraphStyle:
    f = fonts()
    font = f["urdu"] if urdu else (f["bold"] if bold else f["latin"])
    alignment = {"left": TA_LEFT, "right": TA_RIGHT, "center": TA_CENTER}[align]
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading or (size * (1.8 if urdu else 1.3)),
                          textColor=color, alignment=alignment)


def starts_arabic(text) -> bool:
    s = str(text or "").strip()
    return bool(s) and has_arabic(s[0])


def P(text, size: float = 9.5, bold: bool = False, color=NAVY, align: str = "left", urdu: bool | None = None) -> Paragraph:
    s = "" if text is None else str(text)
    is_ur = has_arabic(s) if urdu is None else urdu
    if is_ur and align == "left" and starts_arabic(s):
        align = "right"
    safe = (txt(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")).replace("\n", "<br/>")
    return Paragraph(safe, style(f"p{size}{bold}{align}{is_ur}", size, bold, color, align, is_ur))


def page_size(settings: dict, land: bool = False):
    name = (settings.get("paper_size") or "A5").upper()
    size = {"A4": A4, "A5": A5, "A6": A6}.get(name, A5)
    return landscape(size) if land else size


def logo_flowable(settings: dict, size_mm: float = 16) -> Image | None:
    p = resolve_upload(settings.get("clinic_logo", ""))
    if not p:
        return None
    try:
        img = Image(str(p))
        ratio = img.imageWidth / float(img.imageHeight or 1)
        img.drawHeight = size_mm * mm
        img.drawWidth = size_mm * mm * ratio
        return img
    except Exception:
        return None


def letterhead(settings: dict, doctor: dict | None, width: float, lang: str = "en") -> list:
    """Flowables for the clinic letterhead: logo + clinic block on the left, doctor block on the right."""
    f = fonts()
    clinic = [
        P(settings.get("clinic_name", ""), 15, bold=True, color=TEAL),
        P(settings.get("clinic_tagline", ""), 8.5, color=MUTED),
        P(f"{settings.get('clinic_address', '')}", 8, color=MUTED),
        P(f"{settings.get('clinic_phone', '')}   {settings.get('clinic_email', '')}", 8, color=MUTED),
    ]
    doc_block = []
    if doctor:
        doc_block = [
            P(doctor.get("name", ""), 11, bold=True, align="right"),
            P(doctor.get("qualification", "") or "", 8.5, color=MUTED, align="right"),
            P(doctor.get("specialization", "") or "", 8.5, color=MUTED, align="right"),
            P(f"Reg. No. {doctor.get('registration_no', '')}" if doctor.get("registration_no") else "", 8, color=MUTED, align="right"),
        ]
    logo = logo_flowable(settings, 16)
    left_cells = [[logo, clinic]] if logo else [[clinic]]
    left_widths = [20 * mm, width * 0.58 - 20 * mm] if logo else [width * 0.58]
    left = Table(left_cells, colWidths=left_widths)
    left.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 0),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    head = Table([[left, doc_block]], colWidths=[width * 0.58, width * 0.42])
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, TEAL),
    ]))
    return [head]


def kv_table(pairs: list[tuple], width: float, cols: int = 2, size: float = 8.5, rtl: bool = False) -> Table:
    """Grid of label/value pairs. With rtl=True the pairs are mirrored (value left of label, right-aligned)."""
    rows, row = [], []
    for i, (k, v) in enumerate(pairs):
        cells = [P(k, size, color=MUTED, align="right" if rtl else "left"), P(v, size, align="right" if rtl else "left")]
        row += cells[::-1] if rtl else cells
        if len(row) == cols * 2:
            rows.append(row)
            row = []
    if row:
        row += [""] * (cols * 2 - len(row))
        rows.append(row)
    unit = width / (cols * 3)
    widths = []
    for _ in range(cols):
        widths += [unit * 2.0, unit * 1.0] if rtl else [unit * 1.0, unit * 2.0]
    if rtl:
        rows = [r[::-1] if len(r) == cols * 2 else r for r in rows]
        widths = widths[::-1]
    tbl = Table(rows, colWidths=widths)
    tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    return tbl


def data_table(header: list, rows: list[list], widths: list[float], size: float = 8.5, align_right_cols=(),
               rtl: bool = False) -> Table:
    if rtl:
        header, widths = header[::-1], widths[::-1]
        rows = [r[::-1] for r in rows]
        n = len(header)
        align_right_cols = tuple(n - 1 - i for i in align_right_cols)
    data = [[P(h, size, bold=True, color=colors.white, align="right" if rtl else "left") for h in header]]
    for r in rows:
        data.append([c if isinstance(c, Paragraph) else P(c, size, align="right" if (i in align_right_cols or rtl) else "left")
                     for i, c in enumerate(r)])
    tbl = Table(data, colWidths=widths, repeatRows=1)
    st = [
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFB")]),
    ]
    tbl.setStyle(TableStyle(st))
    return tbl


def signature_block(width: float, label_en: str = "Signature & stamp", label_ur: str = "دستخط و مہر", lang: str = "en") -> Table:
    label = label_en if lang == "en" else f"{label_en}  |  {label_ur}"
    tbl = Table([["", P(label, 8, color=MUTED, align="center")]], colWidths=[width * 0.6, width * 0.4],
                rowHeights=[16 * mm])
    tbl.setStyle(TableStyle([("LINEABOVE", (1, 0), (1, 0), 0.8, NAVY), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                             ("TOPPADDING", (1, 0), (1, 0), 3)]))
    return tbl


def build_pdf(flowables: list, pagesize, margins_mm: float = 12, footer_text: str = "", title: str = "") -> bytes:
    from reportlab.platypus import SimpleDocTemplate

    buf = io.BytesIO()
    f = fonts()

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(f["latin"], 7)
        canvas.setFillColor(MUTED)
        w, h = pagesize
        if footer_text:
            canvas.drawString(margins_mm * mm, 7 * mm, footer_text[:140])
        canvas.drawRightString(w - margins_mm * mm, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=margins_mm * mm, rightMargin=margins_mm * mm,
                            topMargin=margins_mm * mm, bottomMargin=(margins_mm + 4) * mm, title=title,
                            author=config.APP_NAME)
    doc.build(flowables, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
