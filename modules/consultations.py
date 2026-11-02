"""Consultations: clinical documentation by the treating doctor (no clinical suggestions of any kind)."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from core import auth, db, repo, ui
from core.i18n import t
from core.utils import age_from_dob, fmt_date, fmt_datetime, fmt_time, today
from modules.appointments import patient_picker

RX_COLS = {
    "medicine_name": st.column_config.TextColumn("Medicine *", width="large", max_chars=150),
    "dosage": st.column_config.TextColumn("Dosage", width="small", max_chars=80),
    "frequency": st.column_config.TextColumn("Frequency", width="medium", max_chars=80),
    "duration": st.column_config.TextColumn("Duration", width="small", max_chars=80),
    "instructions": st.column_config.TextColumn("Instructions", width="medium", max_chars=300),
}
EMPTY_RX = pd.DataFrame([{"medicine_name": "", "dosage": "", "frequency": "", "duration": "", "instructions": ""}] * 3)


def rx_editor(key: str, initial: list[dict] | None = None) -> list[dict]:
    if initial:
        df = pd.DataFrame(initial)[list(RX_COLS.keys())]
    else:
        df = EMPTY_RX.copy()
    edited = st.data_editor(df, num_rows="dynamic", width="stretch", hide_index=True, column_config=RX_COLS, key=key)
    return [r for r in edited.fillna("").to_dict("records") if str(r.get("medicine_name", "")).strip()]


def patient_summary(p: dict, clinical: bool = True) -> None:
    allergy = ui.badge(p["allergies"], "danger") if p.get("allergies") else ui.badge(t("none"), "neutral")
    body = ui.kv([(t("patient_id"), p["patient_code"]), (t("age"), age_from_dob(p["dob"])), (t("gender"), t(p["gender"].lower())),
                  (t("phone"), p["phone"]), (t("blood_group"), p.get("blood_group") or "-"), (t("allergies"), allergy, True)])
    if clinical and p.get("medical_history"):
        body += f'<div style="margin-top:.5rem;font-size:.84rem"><span style="color:var(--muted)">{t("medical_history")}:</span> {ui.esc(p["medical_history"])}</div>'
    ui.card(p["full_name"], body, "user")


def previous_visits(patient_id: int, exclude_id=None) -> None:
    visits = [v for v in repo.consultations_for_patient(patient_id, 6) if v["id"] != exclude_id]
    ui.section(t("previous_visits"), "history", len(visits))
    if not visits:
        ui.empty_state(t("no_data"), "", "history")
        return
    for v in visits:
        with st.expander(f"{fmt_date(v['visit_date'])} · {v['doctor_name']} · {v['diagnosis'] or '-'}"):
            st.markdown(ui.kv([(t("symptoms"), v["symptoms"] or "-"), (t("diagnosis"), v["diagnosis"] or "-"),
                               ("BP", f"{v['bp_systolic'] or '-'}/{v['bp_diastolic'] or '-'}"), (t("clinical_notes"), v["clinical_notes"] or "-")]),
                        unsafe_allow_html=True)
            if v.get("prescription_id"):
                for it in repo.prescription_items(v["prescription_id"]):
                    st.caption(f"{it['medicine_name']} · {it['dosage']} · {it['frequency']} · {it['duration']}")


def consultation_form(user: dict, patient: dict, token: dict | None, existing: dict | None = None) -> None:
    ex = existing or {}
    rx_items = repo.prescription_items(ex["prescription_id"]) if ex.get("prescription_id") else None
    rx = repo.prescription(ex["prescription_id"]) if ex.get("prescription_id") else None
    nonce = st.session_state.get("cons_form_nonce", 0)
    with st.form(f"cons_form_{nonce}", border=True):
        ui.section(t("consultations") + (f" · {t('edit')}" if existing else ""), "stethoscope")
        symptoms = st.text_area(t("symptoms"), value=ex.get("symptoms", ""), height=90, max_chars=4000)
        st.markdown(f"**{t('vitals')}**")
        v = st.columns(7)
        bps = v[0].number_input("BP sys", min_value=50, max_value=300, value=ex.get("bp_systolic"), step=1, placeholder="120")
        bpd = v[1].number_input("BP dia", min_value=30, max_value=200, value=ex.get("bp_diastolic"), step=1, placeholder="80")
        pulse = v[2].number_input("Pulse", min_value=20, max_value=250, value=ex.get("pulse"), step=1, placeholder="72")
        temp = v[3].number_input("Temp F", min_value=90.0, max_value=110.0, value=ex.get("temperature"), step=0.1, placeholder="98.6", format="%.1f")
        weight = v[4].number_input("Wt kg", min_value=0.5, max_value=400.0, value=ex.get("weight"), step=0.5, placeholder="70", format="%.1f")
        height = v[5].number_input("Ht cm", min_value=20.0, max_value=260.0, value=ex.get("height"), step=0.5, placeholder="170", format="%.1f")
        spo2 = v[6].number_input("SpO2 %", min_value=50, max_value=100, value=ex.get("spo2"), step=1, placeholder="98")
        c1, c2 = st.columns(2)
        notes = c1.text_area(t("clinical_notes"), value=ex.get("clinical_notes", ""), height=110, max_chars=8000)
        diagnosis = c2.text_area(t("diagnosis"), value=ex.get("diagnosis", ""), height=110, max_chars=2000)
        c1, c2, c3 = st.columns([1.4, 1.2, 1.4])
        fu_on = c1.checkbox(t("follow_up_date"), value=bool(ex.get("follow_up_date")))
        fu_date = c2.date_input(t("date"), value=repo.to_date(ex.get("follow_up_date")) or today() + timedelta(days=7),
                                min_value=today(), format="DD/MM/YYYY", label_visibility="collapsed")
        st.markdown(f"**{t('prescriptions')}**")
        st.caption("Enter each medicine exactly as you prescribe it. Nothing is pre-filled or suggested." if st.session_state.lang != "ur"
                   else "ہر دوا ویسے ہی درج کریں جیسے آپ تجویز کرتے ہیں۔ کچھ بھی پہلے سے بھرا یا تجویز نہیں کیا جاتا۔")
        items = rx_editor(f"rx_editor_{nonce}", rx_items)
        rx_notes = st.text_input(f"{t('notes')} ({t('prescriptions').lower()}, {t('optional')})", value=(rx or {}).get("notes", ""), max_chars=500)
        b1, b2 = st.columns([1, 1.2])
        save = b1.form_submit_button(t("save_consultation"), type="primary", width="stretch")
        save_sign = b2.form_submit_button(t("save") + " + " + t("sign_prescription"), width="stretch") if not existing or (rx and rx["status"] != "Signed") else False
    if save or save_sign:
        data = dict(symptoms=symptoms, bp_systolic=bps, bp_diastolic=bpd, pulse=pulse, temperature=temp, weight=weight,
                    height=height, spo2=spo2, clinical_notes=notes, diagnosis=diagnosis, follow_up_date=fu_date if fu_on else None)
        try:
            if existing:
                rx_id = repo.update_consultation(existing["id"], data, items, rx_notes, actor=user)
                cons_id = existing["id"]
            else:
                cons_id, rx_id = repo.create_consultation(
                    patient["id"], user.get("doctor_id") or (token or {}).get("doctor_id"), data, items, rx_notes,
                    appointment_id=(token or {}).get("appointment_id"), token_id=(token or {}).get("id"), actor=user)
            if save_sign and rx_id:
                repo.sign_prescription(rx_id, actor=user)
            st.session_state.cons_form_nonce = nonce + 1
            st.session_state.pop("cons_token_id", None)
            st.session_state.pop("cons_patient_id", None)
            st.session_state.pop("cons_edit_id", None)
            st.session_state.cons_view_id = cons_id
            st.toast(t("saved"))
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def consultation_detail(user: dict, cons_id: int) -> None:
    c = repo.consultation(cons_id)
    if not c:
        st.session_state.pop("cons_view_id", None)
        st.rerun()
    rx = repo.prescription(c["prescription_id"]) if c.get("prescription_id") else None
    top = st.columns([0.9, 4, 1.2])
    if top[0].button(t("back"), key="cons_back"):
        st.session_state.pop("cons_view_id", None)
        st.rerun()
    with top[1]:
        ui.page_header(f"{c['patient_name']} · {fmt_date(c['visit_date'])}", f"{c['doctor_name']} · {t('consultations')}", "stethoscope")
    can_edit = auth.is_doctor(user) and user.get("doctor_id") == c["doctor_id"] and (not rx or rx["status"] != "Signed")
    with top[2]:
        if can_edit and ui.icon_button(t("edit"), "pencil", "cons_edit_btn", use_container_width=True):
            st.session_state.cons_edit_id = cons_id
            st.rerun()
    if st.session_state.get("cons_edit_id") == cons_id and can_edit:
        patient = repo.patient(c["patient_id"])
        consultation_form(user, patient, None, existing=c)
        if st.button(t("cancel"), key="cons_edit_cancel"):
            st.session_state.pop("cons_edit_id", None)
            st.rerun()
        return
    left, right = st.columns([1, 1.6])
    with left:
        patient_summary(repo.patient(c["patient_id"]))
    with right:
        with st.container(border=True):
            st.markdown(ui.kv([
                (t("symptoms"), c["symptoms"] or "-"), (t("diagnosis"), c["diagnosis"] or "-"),
                ("BP", f"{c['bp_systolic'] or '-'}/{c['bp_diastolic'] or '-'} mmHg"), ("Pulse", f"{c['pulse'] or '-'} /min"),
                ("Temp", f"{c['temperature'] or '-'} F"), ("Weight", f"{c['weight'] or '-'} kg"),
                ("Height", f"{c['height'] or '-'} cm"), ("SpO2", f"{c['spo2'] or '-'} %"),
                (t("clinical_notes"), c["clinical_notes"] or "-"), (t("follow_up_date"), fmt_date(c["follow_up_date"])),
                ("Recorded", fmt_datetime(c["created_at"])),
            ]), unsafe_allow_html=True)
        with st.container(border=True):
            ui.section(t("prescriptions"), "file-text")
            if not rx:
                ui.empty_state(t("no_data"), "", "file-text")
            else:
                st.markdown(f"**{rx['rx_number']}** {ui.status_badge(rx['status'])}", unsafe_allow_html=True)
                items = repo.prescription_items(rx["id"])
                if items:
                    ui.dataframe(pd.DataFrame(items)[["medicine_name", "dosage", "frequency", "duration", "instructions"]]
                                 .rename(columns={"medicine_name": t("medicine"), "dosage": t("dosage"), "frequency": t("frequency"),
                                                  "duration": t("duration"), "instructions": t("instructions")}))
                if rx.get("notes"):
                    st.caption(rx["notes"])
                if st.button(f"{t('view')} · {t('prescriptions')}", key="cons_open_rx"):
                    st.session_state.rx_view_id = rx["id"]
                    st.session_state.page = "prescriptions"
                    st.rerun()
    previous_visits(c["patient_id"], exclude_id=cons_id)


def render(user: dict) -> None:
    ui.notice(t("clinical_notice"), "info", "shield")
    if st.session_state.get("cons_view_id"):
        consultation_detail(user, st.session_state.cons_view_id)
        return
    is_doc = auth.is_doctor(user) and auth.can_edit(user, "consultations")
    ui.page_header(t("consultations"), user.get("doctor_name") or t("all"), "stethoscope")

    if is_doc:
        did = user["doctor_id"]
        q = repo.queue_for_date(today(), did, statuses=("In Consultation", "Waiting"))
        with st.container(border=True):
            ui.section(f"{t('live_queue')} · {t('today')}", "ticket", len(q))
            token = None
            patient = None
            pre_tok = st.session_state.get("cons_token_id")
            tok_ids = [int(x) for x in q["id"].tolist()] if not q.empty else []
            labels = {int(r.id): f"{t('token')} {int(r.token_no)} · {r.patient} ({r.patient_code}) · {ui.status_label(r.status)}" for r in q.itertuples()} if not q.empty else {}
            mode_opts = ["queue", "patient"]
            mode = st.radio("mode", mode_opts, horizontal=True, label_visibility="collapsed", key="cons_mode",
                            format_func=lambda m: {"queue": t("from_queue"), "patient": t("any_patient")}[m],
                            index=0 if tok_ids or pre_tok else 1)
            if mode == "queue":
                if not tok_ids:
                    ui.empty_state(t("queue_empty"), "", "ticket")
                else:
                    idx = tok_ids.index(pre_tok) if pre_tok in tok_ids else 0
                    sel = st.selectbox(t("token"), tok_ids, index=idx, format_func=lambda i: labels[i], key="cons_tok_sel")
                    token = repo.token(sel)
                    patient = repo.patient(token["patient_id"])
            else:
                pid = patient_picker("cons_pat")
                patient = repo.patient(pid) if pid else None
        if patient:
            left, right = st.columns([1, 2])
            with left:
                patient_summary(patient)
                previous_visits(patient["id"])
            with right:
                consultation_form(user, patient, token)
        st.divider()

    # history / list
    with st.container(border=True):
        ui.section(t("visit_history"), "history")
        c1, c2, c3, c4 = st.columns([1, 1, 1.4, 1.6])
        start = c1.date_input(t("from"), value=today() - timedelta(days=30), key="cons_from", format="DD/MM/YYYY")
        end = c2.date_input(t("to"), value=today(), key="cons_to", format="DD/MM/YYYY")
        opts = {0: t("all"), **repo.doctor_options()}
        did_f = user["doctor_id"] if is_doc else c3.selectbox(t("doctor"), list(opts.keys()), format_func=lambda i: opts[i], key="cons_doc_f")
        search = c4.text_input(t("search"), key="cons_search", placeholder=t("search_patients_hint"))
        df = repo.consultations_list(start, end, did_f or None, search)
        if df.empty:
            ui.empty_state(t("no_data"), "", "stethoscope")
        else:
            view = pd.DataFrame({t("date"): df["visit_date"].map(fmt_date), t("patient"): df["patient"], t("patient_id"): df["patient_code"],
                                 t("doctor"): df["doctor"], t("diagnosis"): df["diagnosis"], "Rx": df["rx_number"].fillna("-"),
                                 t("follow_up_date"): df["follow_up_date"].map(lambda x: fmt_date(x) if x else "-")})
            st.caption(t("select_row"))
            ev = st.dataframe(view, hide_index=True, width="stretch", height=min(480, 42 + 35 * len(view)), on_select="rerun",
                              selection_mode="single-row", key=f"cons_table_{st.session_state.get('cons_table_nonce', 0)}")
            if ev and ev.selection and ev.selection.rows:
                st.session_state.cons_view_id = int(df.iloc[ev.selection.rows[0]]["id"])
                st.session_state.cons_table_nonce = st.session_state.get("cons_table_nonce", 0) + 1
                st.rerun()
