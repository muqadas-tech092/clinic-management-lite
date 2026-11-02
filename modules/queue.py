"""Token queue: walk-ins, arrivals, live status board and printable token slips."""
from __future__ import annotations

import streamlit as st

from core import auth, config, db, repo, ui
from core.i18n import t
from core.utils import fmt_date, fmt_time, fmt_datetime, today
from modules.appointments import doctor_picker, patient_picker


def _slip_button(token_id: int, key: str, settings: dict) -> None:
    from pdf import token_slip
    tk = repo.token(token_id)
    if tk:
        pdf_bytes = token_slip.build(tk, settings, st.session_state.lang)
        ui.icon_download(t("token_slip"), "printer", key, pdf_bytes, f"token_{tk['token_date']}_{tk['token_no']}.pdf",
                         "application/pdf", use_container_width=True)


def walk_in_panel(user: dict, settings: dict) -> None:
    with st.container(border=True):
        ui.section(t("register_walk_in"), "ticket")
        mode = st.radio("Patient", ["existing", "new"], horizontal=True, key="walkin_mode", label_visibility="collapsed",
                        format_func=lambda m: {"existing": t("existing_patient"), "new": t("register_patient")}[m])
        pid = None
        new_data = None
        if mode == "existing":
            pid = patient_picker("walkin_pat")
        else:
            c1, c2, c3 = st.columns([2, 1.2, 1])
            name = c1.text_input(f"{t('full_name')} *", key="walkin_name", max_chars=80)
            phone = c2.text_input(f"{t('phone')} *", key="walkin_phone", placeholder="03001234567")
            gender = c3.selectbox(f"{t('gender')} *", config.GENDERS, key="walkin_gender", format_func=lambda g: t(g.lower()))
            new_data = dict(full_name=name, phone=phone, gender=gender)
        c1, c2 = st.columns([1.4, 2])
        with c1:
            did = doctor_picker("walkin_doc", user)
        with c2:
            notes = st.text_input(f"{t('notes')} ({t('optional')})", key="walkin_notes", max_chars=300)
        if did:
            status, hours = repo.doctor_status(did, today())
            if status in ("on_leave", "off_today"):
                ui.notice(f"{repo.doctor(did)['name']}: {t(status)}", "warning", "triangle-alert")
        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button(t("register_walk_in"), type="primary", key="walkin_go", disabled=not did):
            try:
                if mode == "new":
                    dups = repo.find_duplicates(new_data["full_name"], new_data["phone"])
                    if dups and not st.session_state.get("walkin_dup_ok"):
                        st.session_state.walkin_dups = dups
                        st.rerun()
                    pid = repo.create_patient(new_data, actor=user)["id"]
                    st.session_state.pop("walkin_dup_ok", None)
                if not pid:
                    raise ValueError("Select a patient")
                aid, tid = repo.register_walk_in(pid, did, notes, actor=user)
                st.session_state.queue_last_token = tid
                st.session_state.queue_show_walkin = False
                st.session_state.pop("walkin_dups", None)
                st.toast(f"{t('token')} #{repo.token(tid)['token_no']}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if b2.button(t("cancel"), key="walkin_cancel"):
            st.session_state.queue_show_walkin = False
            st.session_state.pop("walkin_dups", None)
            st.rerun()
        dups = st.session_state.get("walkin_dups")
        if dups and mode == "new":
            ui.notice(t("possible_duplicates"), "warning", "triangle-alert")
            ui.rows([ui.row_item(f"{d['full_name']} · {d['patient_code']}", d["phone"], left_html=ui.avatar_html(None, d["full_name"], 32)) for d in dups])
            st.checkbox("Register as a new patient anyway", key="walkin_dup_ok")


def _token_card(r, user: dict, can_edit: bool, settings: dict, prefix: str) -> None:
    own = (not auth.is_doctor(user)) or user.get("doctor_id") == r.doctor_id
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([0.8, 2.4, 1.3, 1.5])
        c1.markdown(f"<div class='tok' style='width:48px;height:48px;border-radius:12px;background:var(--primary-soft);color:var(--primary-dark);"
                    f"font-weight:700;display:flex;align-items:center;justify-content:center;font-size:1.1rem'>{prefix}{int(r.token_no)}</div>", unsafe_allow_html=True)
        when = fmt_time(r.appt_time) if r.appt_time else fmt_datetime(r.created_at)
        c2.markdown(f"<div style='padding-top:.15rem'><b>{ui.esc(r.patient)}</b> <span style='color:var(--muted);font-size:.8rem'>{r.patient_code}</span>"
                    f"<div style='font-size:.8rem;color:var(--muted)'>{ui.esc(r.doctor)} · {ui.status_label(r.visit_type or 'Walk-in')} · {when}</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='padding-top:.4rem'>{ui.status_badge(r.status)}</div>", unsafe_allow_html=True)
        with c4:
            if can_edit and own and r.status == "Waiting":
                if ui.icon_button(t("start"), "play", f"tk_start_{r.id}", type="primary", use_container_width=True):
                    _do(repo.token_action, r.id, "start", user)
            if can_edit and own and r.status == "In Consultation":
                if auth.is_doctor(user) and auth.can_edit(user, "consultations"):
                    if ui.icon_button(t("consultations"), "stethoscope", f"tk_cons_{r.id}", type="primary", use_container_width=True):
                        st.session_state.cons_token_id = int(r.id)
                        st.session_state.page = "consultations"
                        st.rerun()
                if ui.icon_button(t("complete"), "circle-check", f"tk_done_{r.id}", use_container_width=True):
                    _do(repo.token_action, r.id, "complete", user)
            if can_edit and own and r.status in ("Waiting", "In Consultation"):
                with st.popover(t("actions"), width="stretch"):
                    if r.status == "In Consultation" and ui.icon_button("Back to waiting", "rotate-ccw", f"tk_rq_{r.id}", use_container_width=True):
                        _do(repo.token_action, r.id, "requeue", user)
                    if ui.icon_button(t("cancel"), "circle-x", f"tk_cancel_{r.id}", use_container_width=True):
                        _do(repo.token_action, r.id, "cancel", user)
                    _slip_button(int(r.id), f"tk_slip_{r.id}", settings)
            elif r.status in ("Completed",):
                _slip_button(int(r.id), f"tk_slip_{r.id}", settings)


def _do(fn, *args):
    try:
        fn(*args)
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))


def render(user: dict) -> None:
    settings = db.get_settings()
    prefix = settings.get("token_prefix", "") or ""
    can_edit = auth.can_edit(user, "queue")
    doctor_lock = user.get("doctor_id") if auth.is_doctor(user) else None
    d = st.session_state.get("queue_date", today())

    head, act = st.columns([3, 1.2])
    with head:
        ui.page_header(t("queue"), ui.date_label(d), "ticket")
    with act:
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        if can_edit and not auth.is_doctor(user):
            if ui.icon_button(t("register_walk_in"), "user-plus", "queue_walkin", type="primary", use_container_width=True):
                st.session_state.queue_show_walkin = not st.session_state.get("queue_show_walkin", False)
                st.session_state.pop("queue_last_token", None)
    if st.session_state.get("prefill_patient_id") and can_edit and not auth.is_doctor(user):
        st.session_state.queue_show_walkin = True

    if can_edit and st.session_state.get("queue_show_walkin") and not auth.is_doctor(user):
        walk_in_panel(user, settings)

    last = st.session_state.get("queue_last_token")
    if last:
        tk = repo.token(last)
        if tk:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1.2])
                c1.markdown(f"<div style='display:flex;gap:.8rem;align-items:center'><div class='tok' style='width:54px;height:54px;border-radius:12px;background:var(--primary);color:#fff;"
                            f"font-weight:700;display:flex;align-items:center;justify-content:center;font-size:1.3rem'>{prefix}{tk['token_no']}</div>"
                            f"<div><b>{ui.esc(tk['patient_name'])}</b><div style='font-size:.8rem;color:var(--muted)'>{ui.esc(tk['doctor_name'])} · {t('token')} issued</div></div></div>",
                            unsafe_allow_html=True)
                with c2:
                    _slip_button(last, "queue_last_slip", settings)
                    if st.button(t("close"), key="queue_last_close", width="stretch"):
                        st.session_state.pop("queue_last_token", None)
                        st.rerun()

    with st.container(border=True):
        c1, c2, c3 = st.columns([1.6, 1.4, 1])
        with c1:
            did = doctor_lock or doctor_picker("queue_doc", user, allow_all=True)
        with c2:
            picked = st.date_input(t("date"), value=d, max_value=today(), key="queue_date_pick", format="DD/MM/YYYY")
            if picked != d:
                st.session_state.queue_date = picked
                st.rerun()
        with c3:
            st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
            if ui.icon_button(t("refresh"), "refresh-cw", "queue_refresh", use_container_width=True):
                st.rerun()

    q = repo.queue_for_date(d, did)
    counts = q["status"].value_counts() if not q.empty else {}
    ui.kpi_row([
        (t("waiting"), int(counts.get("Waiting", 0)), "hourglass", "warning"),
        (t("in_consultation"), int(counts.get("In Consultation", 0)), "stethoscope", "primary"),
        (t("completed_visits"), int(counts.get("Completed", 0)), "circle-check", "success"),
        (t("cancel"), int(counts.get("Cancelled", 0)), "circle-x", "neutral"),
    ], min_width=150)

    # arrivals: scheduled appointments today with no token yet
    if can_edit and d == today() and not auth.is_doctor(user):
        sched = repo.appointments_for_date(d, did, statuses=("Scheduled",))
        if not sched.empty:
            with st.expander(f"{t('mark_arrived')} · {len(sched)} {t('appointments').lower()}", expanded=False):
                for r in sched.itertuples():
                    c1, c2, c3 = st.columns([1, 3, 1.3])
                    c1.markdown(f"**{fmt_time(r.appt_time)}**")
                    c2.markdown(f"{ui.esc(r.patient)} · <span style='color:var(--muted)'>{ui.esc(r.doctor)}</span>", unsafe_allow_html=True)
                    if ui.icon_button(t("mark_arrived"), "user-round-check", f"arrive_{r.id}", use_container_width=True):
                        try:
                            tid = repo.mark_arrived(r.id, actor=user)
                            st.session_state.queue_last_token = tid
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

    if q.empty:
        ui.empty_state(t("queue_empty"), "", "ticket")
        return

    active = q[q["status"].isin(["Waiting", "In Consultation"])]
    done = q[~q["status"].isin(["Waiting", "In Consultation"])]
    ui.section(t("live_queue"), "ticket", len(active))
    if active.empty:
        ui.empty_state(t("queue_empty"), "", "ticket")
    for r in active.itertuples():
        _token_card(r, user, can_edit, settings, prefix)
    if not done.empty:
        with st.expander(f"{t('completed_visits')} / {t('cancel')} · {len(done)}"):
            for r in done.itertuples():
                _token_card(r, user, can_edit, settings, prefix)
