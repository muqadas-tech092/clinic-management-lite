"""Patients: registration, search, duplicate detection, profile with full history, export."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core import auth, config, repo, ui
from core.i18n import t
from core.utils import age_from_dob, fmt_date, fmt_datetime, fmt_time, money, to_date, today

FORM_KEYS = ("full_name", "phone", "gender", "dob", "blood_group", "address", "emergency_contact", "allergies",
             "medical_history")


def _patient_form(prefix: str, initial: dict | None = None) -> dict | None:
    """Render the registration/edit form. Returns the submitted data dict or None."""
    init = initial or {}
    with st.form(f"{prefix}_form", border=True):
        c1, c2, c3 = st.columns([2, 1.2, 1])
        full_name = c1.text_input(f"{t('full_name')} *", value=init.get("full_name", ""), max_chars=80)
        phone = c2.text_input(f"{t('phone')} *", value=init.get("phone", ""), placeholder="03001234567", max_chars=15)
        gender = c3.selectbox(f"{t('gender')} *", config.GENDERS,
                              index=config.GENDERS.index(init["gender"]) if init.get("gender") in config.GENDERS else 0,
                              format_func=lambda g: t(g.lower()))
        c1, c2, c3 = st.columns([1.2, 1, 1.8])
        dob_val = to_date(init.get("dob"))
        has_dob = c1.checkbox(f"{t('dob')} known", value=bool(dob_val), key=f"{prefix}_has_dob")
        dob = c1.date_input(t("dob"), value=dob_val or date(1990, 1, 1), min_value=date(1900, 1, 1),
                            max_value=today(), format="DD/MM/YYYY", disabled=not has_dob)
        blood = c2.selectbox(t("blood_group"), config.BLOOD_GROUPS,
                             index=config.BLOOD_GROUPS.index(init.get("blood_group", "")) if init.get("blood_group", "") in config.BLOOD_GROUPS else 0,
                             format_func=lambda b: b or "-")
        emergency = c3.text_input(f"{t('emergency_contact')} ({t('optional')})", value=init.get("emergency_contact", ""), max_chars=120)
        address = st.text_input(t("address"), value=init.get("address", ""), max_chars=300)
        c1, c2 = st.columns(2)
        allergies = c1.text_area(f"{t('allergies')} ({t('optional')})", value=init.get("allergies", ""), height=90, max_chars=1000)
        history = c2.text_area(f"{t('medical_history')} ({t('optional')})", value=init.get("medical_history", ""), height=90, max_chars=4000)
        st.caption(t("required_fields"))
        submitted = st.form_submit_button(t("save"), type="primary")
    if not submitted:
        return None
    return dict(full_name=full_name, phone=phone, gender=gender, dob=dob if has_dob else None, blood_group=blood,
                address=address, emergency_contact=emergency, allergies=allergies, medical_history=history)


def _dup_table(dups: list[dict]) -> None:
    rows = [ui.row_item(f"{d['full_name']} · {d['patient_code']}", f"{d['phone']} · {t('dob')}: {fmt_date(d['dob'])}",
                        left_html=ui.avatar_html(None, d["full_name"], 34)) for d in dups]
    ui.rows(rows)


def _open_profile(pid: int) -> None:
    st.session_state.patient_view_id = int(pid)
    st.session_state.patient_edit = False
    st.session_state.patients_table_nonce = st.session_state.get("patients_table_nonce", 0) + 1
    st.rerun()


# ------------------------------------------------------------------ list
def render_list(user: dict) -> None:
    can_edit = auth.can_edit(user, "patients")
    head, act = st.columns([3, 1.2])
    with head:
        total = repo.search_patients("", limit=100000).shape[0]
        ui.page_header(t("patients"), f"{total} {t('patients').lower()}", "users")
    with act:
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        if can_edit and ui.icon_button(t("register_patient"), "user-plus", "pat_new", type="primary", use_container_width=True):
            st.session_state.patient_show_form = not st.session_state.get("patient_show_form", False)
            st.session_state.pop("patient_pending", None)

    if can_edit and st.session_state.get("patient_show_form"):
        ui.section(t("register_patient"), "user-plus")
        pending = st.session_state.get("patient_pending")
        if pending:
            ui.notice(t("possible_duplicates") + ". " + ("Review before saving." if not st.session_state.lang == "ur" else "محفوظ کرنے سے پہلے جانچ لیں۔"),
                      "warning", "triangle-alert")
            _dup_table(pending["dups"])
            c1, c2, _ = st.columns([1, 1, 3])
            if c1.button("Register anyway", key="pat_force", type="primary"):
                try:
                    p = repo.create_patient(pending["data"], actor=user)
                    st.session_state.pop("patient_pending", None)
                    st.session_state.patient_show_form = False
                    st.toast(f"{t('saved')} {p['patient_code']}")
                    _open_profile(p["id"])
                except ValueError as exc:
                    st.error(str(exc))
            if c2.button(t("cancel"), key="pat_force_cancel"):
                st.session_state.pop("patient_pending", None)
                st.rerun()
        else:
            data = _patient_form("pat_reg")
            if data:
                try:
                    repo._patient_fields(data)  # validation only
                    dups = repo.find_duplicates(data["full_name"], data["phone"], data["dob"])
                    if dups:
                        st.session_state.patient_pending = {"data": data, "dups": dups}
                        st.rerun()
                    p = repo.create_patient(data, actor=user)
                    st.session_state.patient_show_form = False
                    st.toast(f"{t('saved')} {p['patient_code']}")
                    _open_profile(p["id"])
                except ValueError as exc:
                    st.error(str(exc))

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        q = c1.text_input(t("search"), placeholder=t("search_patients_hint"), key="pat_search", label_visibility="collapsed")
        show_inactive = c2.checkbox(t("include_inactive"), value=False, key="pat_inactive") if auth.is_admin(user) else False
        df = repo.search_patients(q, limit=500, active_only=not show_inactive)
        if df.empty:
            ui.empty_state(t("no_patients") if not q else t("no_data"), "", "users")
            return
        view = pd.DataFrame({
            t("patient_id"): df["patient_code"],
            t("name"): df["full_name"],
            t("age"): df["dob"].map(age_from_dob),
            t("gender"): df["gender"].map(lambda g: t(g.lower())),
            t("phone"): df["phone"],
            t("visits"): df["visits"].astype(int),
            t("last_visit"): df["last_visit"].map(lambda v: fmt_date(v) if v else "-"),
            t("registered"): df["created_at"].map(fmt_date),
        })
        if show_inactive:
            view[t("status")] = df["is_active"].map(lambda a: "Active" if a else "Inactive")
        st.caption(t("select_row"))
        event = st.dataframe(view, hide_index=True, width="stretch", height=min(520, 42 + 35 * len(view)),
                             on_select="rerun", selection_mode="single-row",
                             key=f"patients_table_{st.session_state.get('patients_table_nonce', 0)}")
        rows = event.selection.rows if event and event.selection else []
        if rows:
            _open_profile(int(df.iloc[rows[0]]["id"]))


# --------------------------------------------------------------- profile
def render_profile(user: dict, pid: int) -> None:
    p = repo.patient(pid)
    if not p:
        st.session_state.pop("patient_view_id", None)
        st.rerun()
    can_edit = auth.can_edit(user, "patients")
    clinical = user["role"] in ("admin", "doctor")

    top = st.columns([0.8, 4, 1.4])
    with top[0]:
        if ui.icon_button(t("back"), "arrow-left", "pat_back", use_container_width=True):
            st.session_state.pop("patient_view_id", None)
            st.session_state.patient_edit = False
            st.rerun()
    with top[1]:
        ui.page_header(p["full_name"], f"{p['patient_code']} · {t('patient_profile')}", "user")
    with top[2]:
        if can_edit and ui.icon_button(t("edit"), "pencil", "pat_edit", use_container_width=True):
            st.session_state.patient_edit = not st.session_state.get("patient_edit", False)

    if st.session_state.get("patient_edit") and can_edit:
        ui.section(f"{t('edit')} · {p['full_name']}", "pencil")
        data = _patient_form("pat_edit", p)
        if data:
            try:
                repo.update_patient(pid, data, actor=user)
                st.session_state.patient_edit = False
                st.toast(t("saved"))
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        return

    left, right = st.columns([1.1, 2])
    with left:
        allergy_html = ui.badge(p["allergies"], "danger") if p.get("allergies") else ui.badge(t("none"), "neutral")
        body = (
            f'<div style="display:flex;gap:.9rem;align-items:center;margin-bottom:.8rem">{ui.avatar_html(None, p["full_name"], 56)}'
            f'<div><div style="font-weight:700;font-size:1.05rem">{ui.esc(p["full_name"])}</div>'
            f'<div style="color:var(--muted);font-size:.82rem">{ui.esc(p["patient_code"])} · {t(p["gender"].lower())} · {age_from_dob(p["dob"])}</div></div></div>'
            + ui.kv([
                (t("phone"), p["phone"]), (t("dob"), fmt_date(p["dob"])), (t("blood_group"), p["blood_group"] or "-"),
                (t("emergency_contact"), p["emergency_contact"] or "-"), (t("address"), p["address"] or "-"),
                ("Registered", fmt_date(p["created_at"])),
            ])
            + f'<div style="margin-top:.8rem"><div class="k" style="color:var(--muted);font-size:.8rem">{t("allergies")}</div>{allergy_html}</div>'
        )
        if clinical and p.get("medical_history"):
            body += f'<div style="margin-top:.6rem"><div style="color:var(--muted);font-size:.8rem">{t("medical_history")}</div><div style="font-size:.86rem">{ui.esc(p["medical_history"])}</div></div>'
        ui.card(t("patient_profile"), body, "clipboard-list")

        # quick actions
        if auth.can_edit(user, "appointments"):
            if ui.icon_button(t("new_appointment"), "calendar-plus", "pat_go_appt", use_container_width=True):
                st.session_state.prefill_patient_id = pid
                st.session_state.page = "appointments"
                st.session_state.appt_show_form = True
                st.rerun()
        if auth.can_edit(user, "queue"):
            if ui.icon_button(t("register_walk_in"), "ticket", "pat_go_walkin", use_container_width=True):
                st.session_state.prefill_patient_id = pid
                st.session_state.page = "queue"
                st.rerun()
        if auth.can_edit(user, "billing"):
            if ui.icon_button(t("new_invoice"), "receipt", "pat_go_inv", use_container_width=True):
                st.session_state.prefill_patient_id = pid
                st.session_state.page = "billing"
                st.session_state.billing_show_form = True
                st.rerun()
        if auth.is_admin(user) and p["is_active"]:
            with st.expander("Deactivate record"):
                st.caption("The record is hidden from searches but kept for history and audit.")
                if st.checkbox("I understand", key="pat_deact_ok") and st.button("Deactivate", key="pat_deact", type="primary"):
                    repo.deactivate_patient(pid, actor=user)
                    st.session_state.pop("patient_view_id", None)
                    st.rerun()

    with right:
        hist = repo.patient_history(pid)
        tabs = [t("appointments")]
        if clinical:
            tabs += [t("consultations"), t("prescriptions")]
        if auth.can_view(user, "billing"):
            tabs.append(t("billing"))
        panes = st.tabs(tabs)
        i = 0
        with panes[i]:
            d = hist["appointments"]
            if d.empty:
                ui.empty_state(t("no_data"), "", "calendar")
            else:
                v = pd.DataFrame({t("date"): d["appt_date"].map(fmt_date), t("time"): d["appt_time"].map(fmt_time),
                                  t("doctor"): d["doctor"], t("visit_type"): d["visit_type"].map(ui.status_label),
                                  t("status"): d["status"].map(ui.status_label), t("notes"): d["notes"]})
                ui.dataframe(v, height=min(400, 42 + 35 * len(v)))
                ui.icon_download(t("download_csv"), "file-spreadsheet", "pat_csv_appts", v.to_csv(index=False).encode("utf-8-sig"),
                                 f"{p['patient_code']}_appointments.csv", "text/csv")
        if clinical:
            i += 1
            with panes[i]:
                d = hist["consultations"]
                if d.empty:
                    ui.empty_state(t("no_data"), "", "stethoscope")
                else:
                    for r in d.itertuples():
                        with st.expander(f"{fmt_date(r.visit_date)} · {r.doctor} · {r.diagnosis or '-'}"):
                            c = repo.consultation(r.id)
                            st.markdown(ui.kv([
                                (t("symptoms"), c["symptoms"] or "-"), (t("diagnosis"), c["diagnosis"] or "-"),
                                ("BP", f"{c['bp_systolic'] or '-'}/{c['bp_diastolic'] or '-'}"), ("Pulse", c["pulse"] or "-"),
                                ("Temp (F)", c["temperature"] or "-"), ("Weight (kg)", c["weight"] or "-"),
                                (t("clinical_notes"), c["clinical_notes"] or "-"), (t("follow_up_date"), fmt_date(c["follow_up_date"])),
                            ]), unsafe_allow_html=True)
                            if c.get("prescription_id"):
                                if st.button(f"{t('view')} {t('prescriptions').lower()}", key=f"pat_rx_{r.id}"):
                                    st.session_state.rx_view_id = c["prescription_id"]
                                    st.session_state.page = "prescriptions"
                                    st.rerun()
                    v = d.copy()
                    v["visit_date"] = v["visit_date"].map(fmt_date)
                    ui.icon_download(t("download_csv"), "file-spreadsheet", "pat_csv_cons", v.to_csv(index=False).encode("utf-8-sig"),
                                     f"{p['patient_code']}_consultations.csv", "text/csv")
            i += 1
            with panes[i]:
                d = hist["prescriptions"]
                if d.empty:
                    ui.empty_state(t("no_data"), "", "file-text")
                else:
                    for r in d.itertuples():
                        c1, c2, c3 = st.columns([3, 1.2, 1])
                        c1.markdown(f"**{r.rx_number}** · {fmt_datetime(r.created_at)} · {r.doctor} · {int(r.items)} {t('medicine').lower()}(s)")
                        c2.markdown(ui.status_badge(r.status), unsafe_allow_html=True)
                        if c3.button(t("view"), key=f"pat_rxv_{r.id}"):
                            st.session_state.rx_view_id = int(r.id)
                            st.session_state.page = "prescriptions"
                            st.rerun()
        if auth.can_view(user, "billing"):
            i += 1
            with panes[i]:
                d = hist["invoices"]
                if d.empty:
                    ui.empty_state(t("no_data"), "", "receipt")
                else:
                    v = pd.DataFrame({t("invoice"): d["invoice_no"], t("date"): d["invoice_date"].map(fmt_date),
                                      t("total"): d["total"].map(money), t("received"): d["paid"].map(money),
                                      t("outstanding"): (d["total"] - d["paid"]).map(money), t("status"): d["status"].map(ui.status_label)})
                    ui.dataframe(v, height=min(400, 42 + 35 * len(v)))
                    tot_out = float((d["total"] - d["paid"]).sum())
                    if tot_out > 0:
                        ui.notice(f"{t('outstanding')}: {money(tot_out)}", "warning", "credit-card")
                    ui.icon_download(t("download_csv"), "file-spreadsheet", "pat_csv_inv", v.to_csv(index=False).encode("utf-8-sig"),
                                     f"{p['patient_code']}_invoices.csv", "text/csv")


def render(user: dict) -> None:
    pid = st.session_state.get("patient_view_id")
    if pid:
        render_profile(user, pid)
    else:
        render_list(user)
