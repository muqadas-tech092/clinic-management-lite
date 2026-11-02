"""Clinic Management Lite - entry point.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from core import config

st.set_page_config(
    page_title=config.APP_NAME,
    page_icon=str(config.ASSETS_DIR / "favicon.svg"),
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"Get help": None, "Report a bug": None, "About": f"{config.APP_NAME} {config.APP_VERSION}"},
)

from core import auth, db, icons, ui  # noqa: E402
from core.i18n import LANGS, t  # noqa: E402
from core.utils import resolve_upload  # noqa: E402


@st.cache_resource(show_spinner=False)
def _bootstrap() -> bool:
    db.init_db()
    from core import seed
    if seed.needs_seed():
        seed.seed_demo(verbose=False)
    auth.cleanup_sessions()
    return True


_bootstrap()

if "lang" not in st.session_state:
    st.session_state.lang = db.get_setting("default_language", "en") or "en"
if "page" not in st.session_state:
    st.session_state.page = "dashboard"

ui.inject_css()


# ------------------------------------------------------------------- login
def _logo_html(settings: dict, size: int = 42) -> str:
    p = resolve_upload(settings.get("clinic_logo", ""))
    if p:
        import base64
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        return f'<img src="data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}" alt="logo">'
    return f'<div class="cml-logo-fallback">{icons.svg("hospital", 22)}</div>'


def render_login() -> None:
    settings = db.get_settings()
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="cml-login-brand"><div class="mark">{icons.svg("hospital", 30)}</div>'
            f'<h2>{ui.esc(settings["clinic_name"])}</h2><p>{ui.esc(t("login_sub"))}</p></div>',
            unsafe_allow_html=True,
        )
        with st.form("login_form", border=True):
            st.markdown(f"**{t('welcome_back')}**")
            username = st.text_input(t("username"), autocomplete="username")
            password = st.text_input(t("password"), type="password", autocomplete="current-password")
            submitted = st.form_submit_button(t("login"), type="primary", width="stretch")
        if st.session_state.pop("flash_expired", False):
            st.warning(t("session_expired"))
        if submitted:
            user, err = auth.login(username, password)
            if err:
                st.error(err)
            else:
                st.session_state.user = user
                st.session_state.page = "dashboard"
                st.rerun()
        lang_cols = st.columns(2)
        for i, (code, label) in enumerate(LANGS.items()):
            if lang_cols[i].button(label, key=f"login_lang_{code}", width="stretch",
                                   type="primary" if st.session_state.lang == code else "secondary"):
                st.session_state.lang = code
                st.rerun()
        if settings.get("demo_mode") == "1":
            with st.expander(t("demo_accounts")):
                st.markdown(
                    "| Role | Username | Password |\n|---|---|---|\n"
                    "| Administrator | `admin` | `Admin@123` |\n"
                    "| Receptionist | `reception` | `Reception@123` |\n"
                    "| Doctor | `dr.ayesha` | `Doctor@123` |\n"
                    "| Doctor | `dr.imran` | `Doctor@123` |"
                )
        st.caption(t("prototype_notice"))


# ----------------------------------------------------------------- session
user = st.session_state.get("user")
if user:
    user = auth.validate_session(user.get("session_token", ""))
    if not user:
        st.session_state.pop("user", None)
        st.session_state.flash_expired = True
    else:
        st.session_state.user = user

if not user:
    render_login()
    st.stop()


# ----------------------------------------------------------------- sidebar
def render_sidebar(user: dict) -> str:
    settings = db.get_settings()
    with st.sidebar:
        st.markdown(
            f'<div class="cml-brand">{_logo_html(settings)}<div><div class="name">{ui.esc(settings["clinic_name"])}</div>'
            f'<div class="sub">{ui.esc(settings.get("clinic_tagline", ""))}</div></div></div>',
            unsafe_allow_html=True,
        )
        allowed = [item for item in config.NAV_ITEMS if auth.can_view(user, item[0])]
        if st.session_state.page not in {a[0] for a in allowed}:
            st.session_state.page = allowed[0][0]
        for module, key, icon in allowed:
            active = st.session_state.page == module
            if ui.icon_button(t(module), icon, key, type="primary" if active else "secondary", use_container_width=True):
                st.session_state.page = module
                st.session_state.pop("patient_view_id", None)
                st.rerun()
        st.markdown(f'<div class="cml-sidebar-label">{t("language")}</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, (code, label) in enumerate(LANGS.items()):
            if cols[i].button(label, key=f"lang_{code}", width="stretch",
                              type="primary" if st.session_state.lang == code else "secondary"):
                st.session_state.lang = code
                st.rerun()
        initials = "".join(w[0] for w in user["full_name"].replace("Dr.", "").split()[:2]).upper()
        st.markdown(
            f'<div class="cml-user"><div class="avatar">{ui.esc(initials)}</div><div class="meta">'
            f'<div class="n">{ui.esc(user["full_name"])}</div><div class="r">{t(user["role"])}</div></div></div>',
            unsafe_allow_html=True,
        )
        if ui.icon_button(t("logout"), "log-out", "logout", use_container_width=True):
            auth.logout(user.get("session_token", ""), user)
            for k in list(st.session_state.keys()):
                if k not in ("lang",):
                    del st.session_state[k]
            st.rerun()
        st.caption(f"{config.APP_NAME} v{config.APP_VERSION}")
    return st.session_state.page


page = render_sidebar(user)

# ------------------------------------------------------------------ router
from modules import (appointments, billing, consultations, dashboard, inventory, patients, prescriptions,  # noqa: E402
                     queue, reports, settings)

ROUTES = {
    "dashboard": dashboard.render,
    "appointments": appointments.render,
    "patients": patients.render,
    "queue": queue.render,
    "consultations": consultations.render,
    "prescriptions": prescriptions.render,
    "billing": billing.render,
    "inventory": inventory.render,
    "reports": reports.render,
    "settings": settings.render,
}

if not auth.can_view(user, page):
    st.error(t("permission_denied"))
    st.stop()

try:
    ROUTES[page](user)
except Exception as exc:  # last-resort guard so one module error never blanks the app
    st.error(t("error"))
    with st.expander("Details"):
        st.exception(exc)
