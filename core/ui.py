"""UI toolkit: global CSS, Lucide icon buttons, cards, KPI tiles, badges and chart styling."""
from __future__ import annotations

import html as _html
from typing import Iterable

import pandas as pd
import streamlit as st

from core import config, icons
from core.i18n import is_rtl, t

C = config.COLORS

TONES = {
    "primary": (C["primary_soft"], C["primary_dark"]),
    "success": (C["success_soft"], C["success"]),
    "warning": (C["warning_soft"], C["warning"]),
    "danger": (C["danger_soft"], C["danger"]),
    "info": (C["info_soft"], C["info"]),
    "neutral": ("#EEF2F4", C["muted"]),
}

STATUS_TONES = {
    "Scheduled": "info", "Arrived": "primary", "Waiting": "primary", "In Consultation": "warning",
    "Completed": "success", "Cancelled": "danger", "No Show": "neutral",
    "Paid": "success", "Partial": "warning", "Unpaid": "danger",
    "Signed": "success", "Draft": "neutral", "Active": "success", "Inactive": "neutral",
    "Low stock": "warning", "Expired": "danger", "Expiring soon": "warning", "OK": "success",
}

STATUS_LABELS_UR = {
    "Scheduled": "شیڈولڈ", "Arrived": "پہنچ گئے", "Waiting": "انتظار", "In Consultation": "معائنہ جاری",
    "Completed": "مکمل", "Cancelled": "منسوخ", "No Show": "نہیں آئے", "Paid": "ادا شدہ",
    "Partial": "جزوی", "Unpaid": "غیر ادا شدہ", "Signed": "دستخط شدہ", "Draft": "مسودہ",
    "New Visit": "نیا وزٹ", "Follow-up": "فالو اپ", "Walk-in": "واک اِن", "Procedure": "پروسیجر",
}

# Chart palette: categorical hues chosen for hue and lightness separation.
CHART_COLORS = ["#087F8C", "#4C5FD5", "#C6862A", "#B9507A", "#5B7483", "#2F9E6B"]


def esc(value) -> str:
    return _html.escape("" if value is None else str(value))


def status_label(status: str) -> str:
    if is_rtl():
        return STATUS_LABELS_UR.get(status, status)
    return status


# ------------------------------------------------------------------ CSS
def _icon_rules() -> str:
    rules = []
    for name in icons.ICONS:
        rules.append(f'[class*="st-key-ib-{name}--"]{{--icon:url("{icons.data_uri(name)}");}}')
    return "\n".join(rules)


def inject_css() -> None:
    rtl = is_rtl()
    font_main = "'Noto Nastaliq Urdu', 'Jameel Noori Nastaleeq', 'Segoe UI', Tahoma, sans-serif" if rtl else \
        "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"
    line_h = "2.1" if rtl else "1.5"
    css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Nastaliq+Urdu:wght@400;600;700&display=swap');
:root {{
  --primary:{C['primary']}; --primary-dark:{C['primary_dark']}; --primary-soft:{C['primary_soft']};
  --navy:{C['navy']}; --bg:{C['bg']}; --card:{C['card']}; --border:{C['border']}; --muted:{C['muted']};
  --success:{C['success']}; --warning:{C['warning']}; --danger:{C['danger']}; --info:{C['info']};
  --radius:14px; --shadow:0 1px 2px rgba(23,59,72,.04), 0 6px 16px rgba(23,59,72,.06);
}}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], .stMarkdown, p, label, input, textarea, button, div {{
  font-family: {font_main};
}}
.stApp {{ background: var(--bg); color: var(--navy); }}
.stApp, .stMarkdown p {{ line-height: {line_h}; }}
header[data-testid="stHeader"] {{ background: transparent; pointer-events: none; }}
header[data-testid="stHeader"] * {{ pointer-events: auto; }}
[data-testid="stDecoration"], #MainMenu, footer, .stDeployButton {{ display: none !important; }}
.block-container {{ padding: 1.4rem 2.2rem 4rem; max-width: 1440px; }}
h1, h2, h3, h4 {{ color: var(--navy); font-weight: 600; letter-spacing: -0.01em; }}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {{ background: var(--card); border-right: 1px solid var(--border); }}
section[data-testid="stSidebar"] > div:first-child {{ padding: 1.1rem 0.9rem 1rem; }}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.3rem; }}
section[data-testid="stSidebar"] [class*="st-key-ib-"] button {{
  width: 100%; justify-content: flex-start; border: 1px solid transparent; background: transparent;
  color: var(--navy); font-weight: 500; padding: 0.5rem 0.8rem; border-radius: 10px; box-shadow: none;
  min-height: 2.5rem; transition: background .15s ease;
}}
section[data-testid="stSidebar"] [class*="st-key-ib-"] button > div {{ flex: 0 1 auto; width: auto !important; justify-content: flex-start !important; text-align: start; }}
section[data-testid="stSidebar"] [class*="st-key-ib-"] button > div > span {{ justify-content: flex-start !important; }}
section[data-testid="stSidebar"] [class*="st-key-ib-"] button p {{ text-align: start; }}
section[data-testid="stSidebar"] [class*="st-key-ib-"] button:hover {{ background: var(--primary-soft); color: var(--primary-dark); border-color: transparent; }}
section[data-testid="stSidebar"] [class*="st-key-ib-"] button[kind="primary"],
section[data-testid="stSidebar"] [class*="st-key-ib-"] button[data-testid="stBaseButton-primary"] {{
  background: var(--primary); color: #fff; font-weight: 600;
}}
section[data-testid="stSidebar"] [class*="st-key-ib-"] button[kind="primary"]:hover {{ background: var(--primary-dark); color:#fff; }}
.cml-brand {{ display:flex; align-items:center; gap:.7rem; padding:.2rem .3rem 1rem; border-bottom:1px solid var(--border); margin-bottom:.6rem; }}
.cml-brand img, .cml-brand .cml-logo-fallback {{ width:42px; height:42px; border-radius:11px; object-fit:cover; background:var(--primary-soft); display:flex; align-items:center; justify-content:center; color:var(--primary); flex:0 0 auto; }}
.cml-brand .name {{ font-weight:700; font-size:.98rem; line-height:1.25; color:var(--navy); }}
.cml-brand .sub {{ font-size:.74rem; color:var(--muted); }}
.cml-user {{ display:flex; align-items:center; gap:.6rem; padding:.7rem .6rem; border:1px solid var(--border); border-radius:12px; margin-top:.6rem; background:#FAFCFC; }}
.cml-user .avatar {{ width:34px; height:34px; border-radius:50%; background:var(--primary); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:600; font-size:.85rem; flex:0 0 auto; }}
.cml-user .meta {{ line-height:1.25; min-width:0; }}
.cml-user .meta .n {{ font-weight:600; font-size:.86rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.cml-user .meta .r {{ font-size:.74rem; color:var(--muted); }}
.cml-sidebar-label {{ font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-weight:600; padding:.6rem .5rem .2rem; }}

/* ---------- icon buttons (CSS mask on native buttons) ---------- */
[class*="st-key-ib-"] button::before {{
  content:""; display:inline-block; width:16px; height:16px; flex:0 0 auto; background-color: currentColor;
  -webkit-mask-image: var(--icon); mask-image: var(--icon);
  -webkit-mask-repeat:no-repeat; mask-repeat:no-repeat; -webkit-mask-position:center; mask-position:center;
  -webkit-mask-size:contain; mask-size:contain; margin-inline-end: 8px;
}}
{_icon_rules()}

/* ---------- buttons ---------- */
.stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button {{
  border-radius: 10px; font-weight: 500; border: 1px solid var(--border); background: #fff; color: var(--navy);
  box-shadow: 0 1px 2px rgba(23,59,72,.05); transition: all .15s ease;
}}
.stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover {{
  border-color: var(--primary); color: var(--primary-dark); background: #fff;
}}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"],
button[data-testid="stBaseButton-primary"] {{
  background: var(--primary); border-color: var(--primary); color: #fff;
}}
.stButton button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {{ background: var(--primary-dark); border-color: var(--primary-dark); color:#fff; }}
.stButton button:focus:not(:active), button:focus-visible {{ box-shadow: 0 0 0 3px rgba(8,127,140,.25) !important; outline: none; }}
button[kind="tertiary"] {{ border: none !important; background: transparent !important; box-shadow: none !important; }}

/* ---------- cards / containers ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--card); border: 1px solid var(--border) !important; border-radius: var(--radius); box-shadow: var(--shadow);
  padding: .4rem .6rem;
}}
.cml-card {{ background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 1rem 1.2rem; box-shadow: var(--shadow); margin-bottom: .9rem; }}
.cml-card .title {{ font-weight: 600; font-size: .95rem; color: var(--navy); display:flex; align-items:center; gap:.5rem; margin-bottom:.6rem; }}
.cml-card .title svg {{ color: var(--primary); }}
.cml-section {{ display:flex; align-items:center; gap:.5rem; font-weight:600; font-size:1rem; color:var(--navy); margin: .4rem 0 .6rem; }}
.cml-section svg {{ color: var(--primary); }}
.cml-section .count {{ margin-inline-start:auto; font-size:.78rem; color:var(--muted); font-weight:500; }}

/* ---------- page header ---------- */
.cml-page-head {{ display:flex; align-items:center; gap:.9rem; margin-bottom: 1rem; }}
.cml-page-head .ic {{ width:44px; height:44px; border-radius:12px; background: var(--primary-soft); color: var(--primary); display:flex; align-items:center; justify-content:center; flex:0 0 auto; }}
.cml-page-head h1 {{ font-size:1.45rem; margin:0; padding:0; line-height:1.2; }}
.cml-page-head .sub {{ color: var(--muted); font-size:.86rem; margin-top:.15rem; }}

/* ---------- KPI tiles ---------- */
.cml-kpi-grid {{ display:grid; gap:.8rem; margin-bottom:.4rem; }}
.cml-kpi {{ background: var(--card); border:1px solid var(--border); border-radius: var(--radius); padding: 1rem 1.1rem; box-shadow: var(--shadow); display:flex; gap:.9rem; align-items:flex-start; min-height: 104px; }}
.cml-kpi .ic {{ width:40px; height:40px; border-radius:11px; display:flex; align-items:center; justify-content:center; flex:0 0 auto; }}
.cml-kpi .label {{ font-size:.78rem; color: var(--muted); font-weight:500; }}
.cml-kpi .value {{ font-size:1.35rem; font-weight:700; color: var(--navy); line-height:1.2; margin-top:.15rem; letter-spacing:-0.02em; white-space:nowrap; }}
.cml-kpi .label {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.cml-kpi > div:last-child {{ min-width:0; }}
.cml-kpi .hint {{ font-size:.74rem; color: var(--muted); margin-top:.2rem; }}

/* ---------- badges / lists ---------- */
.cml-badge {{ display:inline-flex; align-items:center; gap:.3rem; padding:.14rem .55rem; border-radius:999px; font-size:.74rem; font-weight:600; white-space:nowrap; line-height:1.5; }}
.cml-list {{ display:flex; flex-direction:column; gap:.45rem; }}
.cml-row {{ display:flex; align-items:center; gap:.7rem; padding:.55rem .7rem; border:1px solid var(--border); border-radius:11px; background:#fff; }}
.cml-row .main {{ flex:1; min-width:0; }}
.cml-row .main .t {{ font-weight:600; font-size:.88rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.cml-row .main .s {{ font-size:.76rem; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.cml-row .tok {{ width:40px; height:40px; border-radius:10px; background:var(--primary-soft); color:var(--primary-dark); font-weight:700; display:flex; align-items:center; justify-content:center; flex:0 0 auto; font-size:.95rem; }}
.cml-row .time {{ font-size:.8rem; color:var(--navy); font-weight:600; min-width:64px; }}
.cml-empty {{ text-align:center; padding:1.6rem 1rem; color:var(--muted); }}
.cml-empty svg {{ color:#B6C6CC; }}
.cml-empty .t {{ font-weight:600; color:var(--navy); margin-top:.5rem; font-size:.92rem; }}
.cml-empty .s {{ font-size:.8rem; margin-top:.15rem; }}
.cml-notice {{ display:flex; gap:.6rem; align-items:flex-start; padding:.7rem .9rem; border-radius:11px; font-size:.84rem; border:1px solid; margin-bottom:.8rem; }}
.cml-notice svg {{ flex:0 0 auto; margin-top:.1rem; }}
.cml-kv {{ display:grid; grid-template-columns: 1fr 1fr; gap:.35rem 1rem; font-size:.86rem; }}
.cml-kv .k {{ color:var(--muted); }}
.cml-kv .v {{ font-weight:500; }}
.cml-avatar {{ width:64px; height:64px; border-radius:50%; object-fit:cover; border:2px solid var(--primary-soft); }}
.cml-avatar-fallback {{ width:64px; height:64px; border-radius:50%; background:var(--primary-soft); color:var(--primary); display:flex; align-items:center; justify-content:center; font-weight:700; font-size:1.2rem; }}

/* ---------- widgets ---------- */
[data-testid="stTextInput"] [data-baseweb="input"], [data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stTextArea"] [data-baseweb="textarea"], [data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stTimeInput"] [data-baseweb="input"], [data-baseweb="select"] > div:first-child {{
  border: 1px solid var(--border) !important; border-radius: 10px !important; background:#fff !important;
}}
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within, [data-testid="stNumberInput"] [data-baseweb="input"]:focus-within,
[data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:first-child:focus-within {{
  border-color: var(--primary) !important; box-shadow: 0 0 0 3px rgba(8,127,140,.15);
}}
[data-testid="stNumberInput"] button {{ border: none; background: transparent; }}
[data-testid$="RootElement"] {{ border: 1px solid var(--border) !important; border-radius: 10px !important; background:#fff; }}
[data-testid$="RootElement"]:focus-within {{ border-color: var(--primary) !important; box-shadow: 0 0 0 3px rgba(8,127,140,.15); }}
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label {{ font-size:.82rem; color: var(--navy); font-weight:500; }}
.stTabs [data-baseweb="tab-list"] {{ gap: .3rem; border-bottom: 1px solid var(--border); }}
.stTabs [data-baseweb="tab"] {{ border-radius: 8px 8px 0 0; padding: .45rem .9rem; font-weight:500; }}
.stTabs [aria-selected="true"] {{ color: var(--primary-dark); }}
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow:hidden; border:1px solid var(--border); direction:ltr; }}
[data-testid="stMetric"] {{ background:#fff; border:1px solid var(--border); border-radius:12px; padding:.6rem .9rem; }}
[data-testid="stExpander"] {{ border:1px solid var(--border); border-radius:12px; background:#fff; }}
[data-testid="stExpander"] details {{ border:none; }}
hr {{ margin: .8rem 0; border-color: var(--border); }}
[data-testid="stForm"] {{ border:1px solid var(--border); border-radius: var(--radius); background:#fff; padding: 1rem 1.2rem; box-shadow: var(--shadow); }}
.stAlert {{ border-radius: 12px; }}
[data-testid="stImage"] img {{ border-radius: 12px; }}
[data-testid="stFileUploader"] section {{ border-radius: 12px; border: 1px dashed var(--border); background:#FAFCFC; }}
div[data-testid="stRadio"] [role="radiogroup"] {{ gap: .4rem; }}
.stProgress > div > div > div {{ background: var(--primary); }}

/* ---------- login ---------- */
.cml-login-brand {{ text-align:center; margin-bottom:.4rem; }}
.cml-login-brand .mark {{ width:60px; height:60px; border-radius:16px; background:var(--primary); color:#fff; display:inline-flex; align-items:center; justify-content:center; margin-bottom:.6rem; }}
.cml-login-brand h2 {{ margin:0; font-size:1.35rem; }}
.cml-login-brand p {{ color:var(--muted); font-size:.86rem; margin:.2rem 0 0; }}

/* ---------- RTL ---------- */
{'.block-container, section[data-testid="stSidebar"] > div { direction: rtl; text-align: right; }' if rtl else ''}
{'input, textarea, [data-baseweb="select"] { direction: rtl; text-align: right; }' if rtl else ''}
{'.stTabs [data-baseweb="tab-list"] { direction: rtl; }' if rtl else ''}
{'section[data-testid="stSidebar"] [class*="st-key-ib-"] button { justify-content: flex-start; flex-direction: row; }' if rtl else ''}
{'.cml-kpi .value { font-family: Inter, "Segoe UI", sans-serif; direction:ltr; }' if rtl else ''}

@media (max-width: 900px) {{
  .block-container {{ padding: 1rem 1rem 3rem; }}
  .cml-kpi {{ min-height: auto; }}
  .cml-kv {{ grid-template-columns: 1fr; }}
}}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


# --------------------------------------------------------------- widgets
def icon_button(label: str, icon: str, key: str, type: str = "secondary", use_container_width: bool = False,
                disabled: bool = False, help: str | None = None, on_click=None, args=None, kwargs=None):
    """Native st.button with a Lucide icon drawn via CSS mask. `key` must be unique per page."""
    return st.button(label, key=f"ib-{icon}--{key}", type=type, width="stretch" if use_container_width else "content",
                     disabled=disabled, help=help, on_click=on_click, args=args, kwargs=kwargs)


def icon_download(label: str, icon: str, key: str, data, file_name: str, mime: str, type: str = "secondary",
                  use_container_width: bool = False, disabled: bool = False):
    return st.download_button(label, data=data, file_name=file_name, mime=mime, key=f"ib-{icon}--{key}",
                              type=type, width="stretch" if use_container_width else "content", disabled=disabled)


def icon_submit(label: str, icon: str, key: str, type: str = "primary", use_container_width: bool = False,
                disabled: bool = False):
    return st.form_submit_button(label, type=type, width="stretch" if use_container_width else "content", disabled=disabled)


def page_header(title: str, subtitle: str = "", icon: str = "layout-dashboard") -> None:
    st.markdown(
        f'<div class="cml-page-head"><div class="ic">{icons.svg(icon, 22)}</div>'
        f'<div><h1>{esc(title)}</h1><div class="sub">{esc(subtitle)}</div></div></div>',
        unsafe_allow_html=True,
    )


def section(title: str, icon: str = "list", count=None) -> None:
    cnt = f'<span class="count">{esc(count)}</span>' if count is not None else ""
    st.markdown(f'<div class="cml-section">{icons.svg(icon, 18)}<span>{esc(title)}</span>{cnt}</div>',
                unsafe_allow_html=True)


def badge(text: str, tone: str = "neutral") -> str:
    bg, fg = TONES.get(tone, TONES["neutral"])
    return f'<span class="cml-badge" style="background:{bg};color:{fg}">{esc(text)}</span>'


def status_badge(status: str) -> str:
    return badge(status_label(status), STATUS_TONES.get(status, "neutral"))


def kpi(label: str, value, icon: str, tone: str = "primary", hint: str = "") -> str:
    bg, fg = TONES.get(tone, TONES["primary"])
    return (
        f'<div class="cml-kpi"><div class="ic" style="background:{bg};color:{fg}">{icons.svg(icon, 20)}</div>'
        f'<div><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div>'
        f'<div class="hint">{esc(hint)}</div></div></div>'
    )


def kpi_row(items: Iterable[tuple], min_width: int = 190) -> None:
    tiles = []
    for item in items:
        label, value, icon, tone = item[:4]
        hint = item[4] if len(item) > 4 else ""
        tiles.append(kpi(label, value, icon, tone, hint))
    st.markdown(f'<div class="cml-kpi-grid" style="grid-template-columns:repeat(auto-fit,minmax({min_width}px,1fr))">'
                + "".join(tiles) + "</div>", unsafe_allow_html=True)


def card(title: str, body_html: str, icon: str | None = None) -> None:
    ic = icons.svg(icon, 18) if icon else ""
    st.markdown(f'<div class="cml-card"><div class="title">{ic}<span>{esc(title)}</span></div>{body_html}</div>',
                unsafe_allow_html=True)


def empty_state(title: str, text: str = "", icon: str = "inbox") -> None:
    st.markdown(f'<div class="cml-empty">{icons.svg(icon, 34, stroke_width=1.5)}<div class="t">{esc(title)}</div>'
                f'<div class="s">{esc(text)}</div></div>', unsafe_allow_html=True)


def notice(text: str, tone: str = "info", icon: str = "info") -> None:
    bg, fg = TONES.get(tone, TONES["info"])
    st.markdown(f'<div class="cml-notice" style="background:{bg};color:{fg};border-color:{fg}33">'
                f'{icons.svg(icon, 18)}<div>{esc(text)}</div></div>', unsafe_allow_html=True)


def kv(pairs: Iterable[tuple]) -> str:
    cells = "".join(f'<div class="k">{esc(k)}</div><div class="v">{v if raw else esc(v)}</div>'
                    for k, v, *rest in [(p[0], p[1], *p[2:]) for p in pairs]
                    for raw in [bool(rest and rest[0])])
    return f'<div class="cml-kv">{cells}</div>'


def row_item(title: str, sub: str, left_html: str = "", right_html: str = "") -> str:
    return (f'<div class="cml-row">{left_html}<div class="main"><div class="t">{esc(title)}</div>'
            f'<div class="s">{esc(sub)}</div></div>{right_html}</div>')


def rows(items: list[str]) -> None:
    st.markdown('<div class="cml-list">' + "".join(items) + "</div>", unsafe_allow_html=True)


def avatar_html(path_or_none, name: str, size: int = 64) -> str:
    from core.utils import resolve_upload
    import base64
    p = resolve_upload(path_or_none) if path_or_none else None
    if p:
        b64 = base64.b64encode(p.read_bytes()).decode()
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        return f'<img class="cml-avatar" style="width:{size}px;height:{size}px" src="data:{mime};base64,{b64}" alt="">'
    initials = "".join(w[0] for w in (name or "?").replace("Dr.", "").split()[:2]).upper() or "?"
    return f'<div class="cml-avatar-fallback" style="width:{size}px;height:{size}px">{esc(initials)}</div>'


def plot(fig, height: int | None = None):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def dataframe(data: pd.DataFrame, height: int | None = None, column_config: dict | None = None,
              hide_index: bool = True, key: str | None = None):
    if data is None or data.empty:
        empty_state(t("no_data"))
        return
    st.dataframe(data, hide_index=hide_index, width="stretch", height=height,
                 column_config=column_config, key=key)


def date_label(d) -> str:
    from core.utils import fmt_date, today
    dd = d
    return (t("today") + " · " if dd == today() else "") + fmt_date(dd, long=True)


# ---------------------------------------------------------------- charts
def style_fig(fig, height: int = 300, show_legend: bool = False):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=12, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", color=C["navy"], size=12),
        showlegend=show_legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11)),
        hoverlabel=dict(bgcolor="#fff", bordercolor=C["border"], font=dict(color=C["navy"], size=12)),
        bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=C["border"], tickfont=dict(color=C["muted"], size=11),
                     title=None)
    fig.update_yaxes(showgrid=True, gridcolor="#E9EFF1", zeroline=False, linecolor="rgba(0,0,0,0)",
                     tickfont=dict(color=C["muted"], size=11), title=None)
    return fig


def bar_chart(x, y, name: str = "", color: str | None = None, height: int = 300, text_fmt: str | None = None,
              hover_fmt: str = "%{y:,.0f}"):
    import plotly.graph_objects as go
    fig = go.Figure(go.Bar(x=list(x), y=list(y), name=name, marker=dict(color=color or CHART_COLORS[0], cornerradius=4),
                           hovertemplate=f"%{{x}}<br>{hover_fmt}<extra></extra>",
                           texttemplate=text_fmt, textposition="outside" if text_fmt else None))
    return style_fig(fig, height)


def line_chart(x, y, name: str = "", color: str | None = None, height: int = 300, hover_fmt: str = "%{y:,.0f}"):
    import plotly.graph_objects as go
    fig = go.Figure(go.Scatter(x=list(x), y=list(y), name=name, mode="lines+markers",
                               line=dict(color=color or CHART_COLORS[0], width=2),
                               marker=dict(size=7, color="#fff", line=dict(color=color or CHART_COLORS[0], width=2)),
                               hovertemplate=f"%{{x}}<br>{hover_fmt}<extra></extra>"))
    return style_fig(fig, height)


def grouped_bar(df: pd.DataFrame, x: str, series: list[str], height: int = 320, stacked: bool = False):
    import plotly.graph_objects as go
    fig = go.Figure()
    for i, s in enumerate(series):
        fig.add_bar(x=df[x], y=df[s], name=s, marker=dict(color=CHART_COLORS[i % len(CHART_COLORS)], cornerradius=3),
                    hovertemplate=f"{s}: %{{y:,.0f}}<extra></extra>")
    fig.update_layout(barmode="stack" if stacked else "group")
    return style_fig(fig, height, show_legend=len(series) > 1)


def hbar_chart(labels, values, height: int = 300, color: str | None = None, hover_fmt: str = "%{x:,.0f}"):
    import plotly.graph_objects as go
    fig = go.Figure(go.Bar(x=list(values), y=list(labels), orientation="h",
                           marker=dict(color=color or CHART_COLORS[0], cornerradius=4),
                           hovertemplate=f"%{{y}}<br>{hover_fmt}<extra></extra>"))
    fig.update_layout(yaxis=dict(autorange="reversed"))
    return style_fig(fig, height)
