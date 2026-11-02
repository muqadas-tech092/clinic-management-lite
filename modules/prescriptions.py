"""Prescriptions: history, editing before signing, signing, printable PDF (English / Urdu / bilingual)."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from core import auth, db, repo, ui
from core.i18n import t
from core.utils import age_from_dob, fmt_date, fmt_datetime, today


def pdf_buttons(rx: dict, items: list[dict], settings: dict, key: str) -> None:
    from pdf import prescription as rxpdf
    ui.icon_download(f"{t('download_pdf')} · English", "printer", f"{key}_en", rxpdf.build(rx, items, settings, "en"),
                     f"{rx['rx_number']}_en.pdf", "application/pdf", use_container_width=True)
    if settings.get("show_urdu_on_prints", "1") == "1":
        ui.icon_download(f"{t('download_pdf')} · اردو", "printer", f"{key}_ur", rxpdf.build(rx, items, settings, "ur"),
                         f"{rx['rx_number']}_ur.pdf", "application/pdf", use_container_width=True)
        ui.icon_download(f"{t('download_pdf')} · English + اردو", "printer", f"{key}_both", rxpdf.build(rx, items, settings, "both"),
                         f"{rx['rx_number']}_bilingual.pdf", "application/pdf", use_container_width=True)


def rx_detail(user: dict, rx_id: int) -> None:
    from modules.consultations import rx_editor, patient_summary
    settings = db.get_settings()
    rx = repo.prescription(rx_id)
    if not rx:
        st.session_state.pop("rx_view_id", None)
        st.rerun()
    items = repo.prescription_items(rx_id)
    is_owner = auth.is_doctor(user) and user.get("doctor_id") == rx["doctor_id"]
    editable = is_owner and rx["status"] != "Signed"

    top = st.columns([0.9, 4, 1.2])
    if top[0].button(t("back"), key="rx_back"):
        st.session_state.pop("rx_view_id", None)
        st.session_state.pop("rx_edit", None)
        st.rerun()
    with top[1]:
        ui.page_header(rx["rx_number"], f"{rx['patient_name']} · {rx['doctor_name']} · {fmt_date(rx.get('visit_date') or rx['created_at'])}", "file-text")
    with top[2]:
        st.markdown(f"<div style='padding-top:.6rem'>{ui.status_badge(rx['status'])}</div>", unsafe_allow_html=True)

    left, right = st.columns([1, 1.8])
    with left:
        patient_summary(repo.patient(rx["patient_id"]), clinical=user["role"] in ("admin", "doctor"))
        if rx.get("diagnosis"):
            ui.card(t("diagnosis"), f"<div style='font-size:.9rem'>{ui.esc(rx['diagnosis'])}</div>", "clipboard-list")
        pdf_buttons(rx, items, settings, "rx_pdf")
        if rx["status"] == "Signed":
            st.caption(f"{t('signed')}: {fmt_datetime(rx['signed_at'])}")
    with right:
        if editable and st.session_state.get("rx_edit"):
            with st.form("rx_edit_form", border=True):
                ui.section(f"{t('edit')} · {rx['rx_number']}", "pencil")
                new_items = rx_editor("rx_edit_editor", items)
                notes = st.text_input(t("notes"), value=rx.get("notes") or "", max_chars=500)
                c1, c2, c3 = st.columns([1, 1, 2])
                save = c1.form_submit_button(t("save"), type="primary")
                cancel = c2.form_submit_button(t("cancel"))
            if save:
                try:
                    repo.update_prescription(rx_id, new_items, notes, actor=user)
                    st.session_state.pop("rx_edit", None)
                    st.toast(t("saved"))
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if cancel:
                st.session_state.pop("rx_edit", None)
                st.rerun()
        else:
            with st.container(border=True):
                ui.section(t("medicine"), "pill", len(items))
                if items:
                    ui.dataframe(pd.DataFrame(items)[["medicine_name", "dosage", "frequency", "duration", "instructions"]]
                                 .rename(columns={"medicine_name": t("medicine"), "dosage": t("dosage"), "frequency": t("frequency"),
                                                  "duration": t("duration"), "instructions": t("instructions")}),
                                 height=42 + 35 * len(items) + 4)
                else:
                    ui.empty_state(t("no_data"), "", "pill")
                if rx.get("notes"):
                    st.markdown(f"**{t('notes')}:** {ui.esc(rx['notes'])}")
                if rx.get("follow_up_date"):
                    st.markdown(f"**{t('follow_up_date')}:** {fmt_date(rx['follow_up_date'])}")
                if editable:
                    c1, c2, _ = st.columns([1, 1.4, 2])
                    if ui.icon_button(t("edit"), "pencil", "rx_edit_btn", use_container_width=True):
                        st.session_state.rx_edit = True
                        st.rerun()
                    if ui.icon_button(t("sign_prescription"), "pen-line", "rx_sign_btn", type="primary", use_container_width=True):
                        try:
                            repo.sign_prescription(rx_id, actor=user)
                            st.toast(t("signed"))
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                elif rx["status"] != "Signed":
                    ui.notice("Only the prescribing doctor can edit or sign this prescription." if st.session_state.lang != "ur"
                              else "صرف تجویز کرنے والا ڈاکٹر اس نسخے میں ترمیم یا دستخط کر سکتا ہے۔", "info", "lock")
        if rx.get("consultation_id") and st.button(f"{t('view')} · {t('consultations')}", key="rx_open_cons"):
            st.session_state.cons_view_id = rx["consultation_id"]
            st.session_state.page = "consultations"
            st.rerun()


def render(user: dict) -> None:
    if st.session_state.get("rx_view_id"):
        rx_detail(user, st.session_state.rx_view_id)
        return
    ui.page_header(t("prescriptions"), t("visit_history"), "file-text")
    is_doc = auth.is_doctor(user)
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1.3, 1, 1.6])
        start = c1.date_input(t("from"), value=today() - timedelta(days=30), key="rx_from", format="DD/MM/YYYY")
        end = c2.date_input(t("to"), value=today(), key="rx_to", format="DD/MM/YYYY")
        opts = {0: t("all"), **repo.doctor_options()}
        did = user["doctor_id"] if is_doc else c3.selectbox(t("doctor"), list(opts.keys()), format_func=lambda i: opts[i], key="rx_doc")
        status = c4.selectbox(t("status"), ["", "Draft", "Signed"], format_func=lambda s: t("all") if not s else ui.status_label(s), key="rx_status")
        search = c5.text_input(t("search"), key="rx_search", placeholder="RX-2026-00001 / name / ID")
    df = repo.prescriptions_list(start, end, did or None, search, status or None)
    counts = df["status"].value_counts() if not df.empty else {}
    ui.kpi_row([
        (t("prescriptions"), len(df), "file-text", "primary", f"{fmt_date(start)} - {fmt_date(end)}"),
        (t("signed"), int(counts.get("Signed", 0)), "badge-check", "success"),
        (t("draft"), int(counts.get("Draft", 0)), "square-pen", "warning"),
    ], min_width=170)
    if df.empty:
        ui.empty_state(t("no_data"), "", "file-text")
        return
    view = pd.DataFrame({"Rx": df["rx_number"], t("date"): df["created_at"].map(fmt_datetime), t("patient"): df["patient"],
                         t("patient_id"): df["patient_code"], t("doctor"): df["doctor"], t("medicine"): df["items"].astype(int),
                         t("diagnosis"): df["diagnosis"].fillna("-"), t("status"): df["status"].map(ui.status_label)})
    st.caption(t("select_row"))
    ev = st.dataframe(view, hide_index=True, width="stretch", height=min(520, 42 + 35 * len(view)), on_select="rerun",
                      selection_mode="single-row", key=f"rx_table_{st.session_state.get('rx_table_nonce', 0)}")
    if ev and ev.selection and ev.selection.rows:
        st.session_state.rx_view_id = int(df.iloc[ev.selection.rows[0]]["id"])
        st.session_state.rx_table_nonce = st.session_state.get("rx_table_nonce", 0) + 1
        st.rerun()
