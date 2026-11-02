"""Generic tabular report PDF (landscape A4) used by Reports & Analytics."""
from __future__ import annotations

import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import Spacer

from core.utils import fmt_datetime, now
from pdf.base import MUTED, TEAL, P, build_pdf, data_table, letterhead


def build(title: str, subtitle: str, df: pd.DataFrame, settings: dict, summary: list[tuple] | None = None,
          numeric_cols: tuple = (), landscape_mode: bool = True, max_rows: int = 2000) -> bytes:
    size = landscape(A4) if landscape_mode else A4
    width = size[0] - 24 * mm
    el = letterhead(settings, None, width)
    el += [Spacer(1, 3 * mm), P(title, 13, bold=True, color=TEAL), P(subtitle, 8.5, color=MUTED),
           P(f"Generated {fmt_datetime(now().strftime('%Y-%m-%d %H:%M:%S'))}", 7.5, color=MUTED), Spacer(1, 3 * mm)]
    if summary:
        from pdf.base import kv_table
        el.append(kv_table(summary, width, cols=min(3, max(1, len(summary)))))
        el.append(Spacer(1, 3 * mm))
    if df is None or df.empty:
        el.append(P("No data for the selected filters.", 9, color=MUTED))
    else:
        d = df.head(max_rows)
        cols = list(d.columns)
        header = [str(c) for c in cols]
        rows = [["" if pd.isna(v) else str(v) for v in r] for r in d.itertuples(index=False)]
        # proportional widths based on content length
        lens = [max(len(str(c)), *(len(str(v)) for v in d[c].astype(str).head(200))) for c in cols]
        lens = [min(max(l, 4), 40) for l in lens]
        total = float(sum(lens))
        widths = [width * l / total for l in lens]
        right = tuple(i for i, c in enumerate(cols) if c in numeric_cols)
        el.append(data_table(header, rows, widths, size=7.5, align_right_cols=right))
        if len(df) > max_rows:
            el.append(P(f"Showing first {max_rows} of {len(df)} rows.", 8, color=MUTED))
    return build_pdf(el, size, margins_mm=12, footer_text=f"{settings.get('clinic_name', '')} · {title}", title=title)
