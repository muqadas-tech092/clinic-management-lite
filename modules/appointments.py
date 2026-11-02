"""Appointments: booking with slot availability, daily/weekly calendar, reschedule, cancel, arrivals."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from core import auth, config, repo, ui
from core.i18n import t
from core.utils import fmt_date, fmt_time, today, week_bounds


def patient_picker(key: str, label: str | None = None) -> int | None:
    """Search box + select. Honours st.session_state.prefill_patient_id once."""
    prefill = st.session_state.pop("prefill_patient_id", None)
    if prefill:
        st.session_state[f"{key}_sel"] = int(prefill)
        p = repo.patient(prefill)
        if p:
            st.session_state[f"{key}_q"] = p["patient_code"]
    c1, c2 = st.columns([1, 2])
    q = c1.text_input(t("search"), key=f"{key}_q", placeholder=t("search_patients_hint"))
    opts = repo.patient_options(q, limit=200)
    if not opts:
        c2.selectbox(label or t("patient"), ["-"], key=f"{key}_none", disabled=True)
        c2.caption(t("no_data"))
        return None
    ids = list(opts.keys())
    cur = st.session_state.get(f"{key}_sel")
    idx = ids.index(cur) if cur in ids else 0
    sel = c2.selectbox(label or f"{t('patient')} *", ids, index=idx, format_func=lambda i: opts[i], key=f"{key}_box")
    st.session_state[f"{key}_sel"] = sel
    return sel


def doctor_picker(key: str, user: dict, allow_all: bool = False, label: str | None = None):
    opts = repo.doctor_options()
    if auth.is_doctor(user) and user.get("doctor_id") in opts:
        st.selectbox(label or t("doctor"), [user["doctor_id"]], format_func=lambda i: opts[i], key=key, disabled=True)
        return user["doctor_id"]
    ids = list(opts.keys())
    if allow_all:
        ids = [0] + ids
        opts = {0: t("all"), **opts}
    if not ids:
        return None
    sel = st.selectbox(label or t("doctor"), ids, format_func=lambda i: opts[i], key=key)
    return sel or None


# ------------------------------------------------------------ booking form
def booking_form(user: dict) -> None:
    with st.container(border=True):
        ui.section(t("new_appointment"), "calendar-plus")
        pid = patient_picker("appt_pat")
        c1, c2, c3 = st.columns([1.4, 1, 1])
        with c1:
            did = doctor_picker("appt_doc", user)
        with c2:
            d = st.date_input(t("date"), value=max(today(), st.session_state.get("appt_date", today())),
                              min_value=today(), max_value=today() + timedelta(days=120), key="appt_form_date", format="DD/MM/YYYY")
        with c3:
            vtype = st.selectbox(t("visit_type"), [v for v in config.VISIT_TYPES if v != "Walk-in"], format_func=ui.status_label, key="appt_vtype")
        slots = repo.available_slots(did, d) if did else []
        hol = repo.is_holiday(did, d) if did else None
        c1, c2 = st.columns([1, 2])
        with c1:
            if hol:
                ui.notice(f"{t('on_leave')}: {hol.get('reason') or ''}", "warning", "triangle-alert")
                slot = None
            elif not slots:
                ui.notice(t("no_slots"), "warning", "clock")
                slot = None
            else:
                slot = st.selectbox(f"{t('slot')} *", slots, format_func=fmt_time, key="appt_slot")
                st.caption(f"{len(slots)} free")
        with c2:
            notes = st.text_input(f"{t('notes')} ({t('optional')})", key="appt_notes", max_chars=300)
        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button(t("save"), type="primary", key="appt_save", disabled=not (pid and did and slot)):
            try:
                aid = repo.create_appointment(pid, did, d, slot, vtype, notes, actor=user)
                st.session_state.appt_show_form = False
                st.session_state.appt_date = d
                st.toast(f"{t('saved')} #{aid}")
                st.rerun()
            except repo.SlotTakenError:
                st.error(t("slot_taken"))
            except ValueError as exc:
                st.error(str(exc))
        if b2.button(t("cancel"), key="appt_form_cancel"):
            st.session_state.appt_show_form = False
            st.rerun()


def reschedule_panel(user: dict) -> None:
    aid = st.session_state.get("appt_resched_id")
    a = repo.appointment(aid) if aid else None
    if not a:
        st.session_state.pop("appt_resched_id", None)
        return
    with st.container(border=True):
        ui.section(f"{t('reschedule')} · {a['patient_name']} · {a['doctor_name']}", "rotate-ccw")
        st.caption(f"{t('from')}: {fmt_date(a['appt_date'])} {fmt_time(a['appt_time'])}")
        c1, c2, c3 = st.columns([1, 1, 2])
        nd = c1.date_input(t("date"), value=max(today(), repo.to_date(a["appt_date"])), min_value=today(),
                           key="resched_date", format="DD/MM/YYYY")
        slots = repo.available_slots(a["doctor_id"], nd, exclude_appt_id=aid)
        ns = c2.selectbox(t("slot"), slots, format_func=fmt_time, key="resched_slot") if slots else None
        if not slots:
            c2.caption(t("no_slots"))
        b1, b2 = c3.columns(2)
        if b1.button(t("confirm"), type="primary", key="resched_ok", disabled=ns is None):
            try:
                repo.reschedule_appointment(aid, nd, ns, actor=user)
                st.session_state.pop("appt_resched_id", None)
                st.session_state.appt_date = nd
                st.toast(t("saved"))
                st.rerun()
            except repo.SlotTakenError:
                st.error(t("slot_taken"))
            except ValueError as exc:
                st.error(str(exc))
        if b2.button(t("cancel"), key="resched_cancel"):
            st.session_state.pop("appt_resched_id", None)
            st.rerun()


# ---------------------------------------------------------------- daily
def _action(fn, *args, ok: str | None = None):
    try:
        fn(*args)
        st.toast(ok or t("saved"))
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))


def daily_view(user: dict, d, doctor_id, can_edit: bool) -> None:
    appts = repo.appointments_for_date(d, doctor_id)
    ui.section(f"{ui.date_label(d)}", "calendar", len(appts))
    if appts.empty:
        ui.empty_state(t("no_appointments_today"), "", "calendar")
        return
    is_today_or_future = d >= today()
    for r in appts.itertuples():
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([0.9, 2.6, 1.8, 1.2, 1.1])
            c1.markdown(f"<div style='font-weight:700;font-size:.95rem;padding-top:.3rem;white-space:nowrap'>{fmt_time(r.appt_time)}</div>", unsafe_allow_html=True)
            tok = f" · {t('token')} {int(r.token_no)}" if r.token_no == r.token_no and r.token_no is not None else ""
            c2.markdown(f"<div style='padding-top:.2rem'><b>{ui.esc(r.patient)}</b> <span style='color:var(--muted);font-size:.8rem'>{r.patient_code} · {r.phone}</span>"
                        f"<div style='font-size:.8rem;color:var(--muted)'>{ui.esc(r.doctor)} · {ui.status_label(r.visit_type)}{tok}</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div style='padding-top:.35rem'>{ui.status_badge(r.status)}</div>" +
                        (f"<div style='font-size:.76rem;color:var(--muted)'>{ui.esc(r.notes)}</div>" if r.notes else ""), unsafe_allow_html=True)
            if c4.button(t("view"), key=f"appt_pat_{r.id}", help=t("patient_profile")):
                st.session_state.patient_view_id = int(r.patient_id)
                st.session_state.page = "patients"
                st.rerun()
            if can_edit and r.status not in ("Completed", "Cancelled", "No Show"):
                with c5.popover(t("actions"), width="stretch"):
                    if r.status == "Scheduled" and d == today():
                        if ui.icon_button(t("mark_arrived"), "user-round-check", f"arr_{r.id}", use_container_width=True):
                            _action(repo.mark_arrived, r.id, user, ok=t("mark_arrived"))
                    if r.status in ("Scheduled", "Arrived") and is_today_or_future:
                        if ui.icon_button(t("reschedule"), "rotate-ccw", f"res_{r.id}", use_container_width=True):
                            st.session_state.appt_resched_id = int(r.id)
                            st.rerun()
                    if r.status in ("Scheduled", "Arrived"):
                        if ui.icon_button(t("cancel"), "circle-x", f"can_{r.id}", use_container_width=True):
                            _action(repo.set_appointment_status, r.id, "Cancelled", user, ok=t("cancel"))
                        if d <= today() and ui.icon_button("No show", "x", f"ns_{r.id}", use_container_width=True):
                            _action(repo.set_appointment_status, r.id, "No Show", user, ok="No show")


# --------------------------------------------------------------- weekly
def weekly_view(user: dict, d, doctor_id) -> None:
    start, end = week_bounds(d)
    appts = repo.appointments_between(start, end, doctor_id)
    ui.section(f"{t('weekly_view')} · {fmt_date(start)} - {fmt_date(end)}", "calendar", len(appts))
    cols = st.columns(7)
    for i in range(7):
        day = start + timedelta(days=i)
        day_s = day.strftime("%Y-%m-%d")
        sub = appts[appts["appt_date"] == day_s] if not appts.empty else appts
        with cols[i]:
            is_today = day == today()
            head = f"<div style='font-weight:700;color:{'var(--primary)' if is_today else 'var(--navy)'}'>{config.WEEKDAYS[i][:3]}</div>" \
                   f"<div style='font-size:.78rem;color:var(--muted)'>{day.strftime('%d %b')}</div>"
            chips = ""
            for r in sub.head(8).itertuples():
                bg, fg = ui.TONES.get(ui.STATUS_TONES.get(r.status, "neutral"), ui.TONES["neutral"])
                chips += (f"<div style='background:{bg};color:{fg};border-radius:8px;padding:.25rem .45rem;margin:.25rem 0;"
                          f"font-size:.72rem;line-height:1.3'><b>{fmt_time(r.appt_time)}</b><br>{ui.esc(r.patient)}"
                          f"<br><span style='opacity:.8'>{ui.esc(r.doctor.replace('Dr. ', ''))}</span></div>")
            if len(sub) > 8:
                chips += f"<div style='font-size:.72rem;color:var(--muted);padding:.2rem 0'>+{len(sub) - 8} more</div>"
            if not chips:
                chips = "<div style='font-size:.74rem;color:#B6C6CC;padding:.5rem 0'>-</div>"
            st.markdown(f"<div class='cml-card' style='padding:.6rem .6rem;min-height:120px'>{head}"
                        f"<div style='font-size:.72rem;color:var(--muted)'>{len(sub)} appt(s)</div>{chips}</div>", unsafe_allow_html=True)
            if st.button(t("view"), key=f"wk_open_{i}", width="stretch"):
                st.session_state.appt_date = day
                st.session_state.appt_view = "daily"
                st.rerun()


# ----------------------------------------------------------------- page
def render(user: dict) -> None:
    can_edit = auth.can_edit(user, "appointments")
    doctor_lock = user.get("doctor_id") if auth.is_doctor(user) else None

    head, act = st.columns([3, 1.2])
    with head:
        ui.page_header(t("appointments"), t("daily_view") + " / " + t("weekly_view"), "calendar")
    with act:
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        if can_edit and ui.icon_button(t("new_appointment"), "calendar-plus", "appt_new", type="primary", use_container_width=True):
            st.session_state.appt_show_form = not st.session_state.get("appt_show_form", False)

    if can_edit and st.session_state.get("appt_show_form"):
        booking_form(user)
    if can_edit and st.session_state.get("appt_resched_id"):
        reschedule_panel(user)

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([0.5, 1.6, 0.5, 1.8, 1.6])
        if "appt_date" not in st.session_state:
            st.session_state.appt_date = today()
        if c1.button("<", key="appt_prev", width="stretch"):
            step = 7 if st.session_state.get("appt_view") == "weekly" else 1
            st.session_state.appt_date = st.session_state.appt_date - timedelta(days=step)
            st.rerun()
        picked = c2.date_input(t("date"), value=st.session_state.appt_date, key="appt_date_pick", format="DD/MM/YYYY",
                               label_visibility="collapsed")
        if picked != st.session_state.appt_date:
            st.session_state.appt_date = picked
            st.rerun()
        if c3.button(">", key="appt_next", width="stretch"):
            step = 7 if st.session_state.get("appt_view") == "weekly" else 1
            st.session_state.appt_date = st.session_state.appt_date + timedelta(days=step)
            st.rerun()
        with c4:
            did = doctor_lock or doctor_picker("appt_filter_doc", user, allow_all=True, label=t("doctor"))
        with c5:
            view = st.segmented_control(t("view"), ["daily", "weekly"], format_func=lambda v: t(f"{v}_view"),
                                        default=st.session_state.get("appt_view", "daily"), key="appt_view_ctl",
                                        label_visibility="collapsed")
            st.session_state.appt_view = view or "daily"
        if st.session_state.appt_date != today():
            if st.button(t("today"), key="appt_today"):
                st.session_state.appt_date = today()
                st.rerun()

    d = st.session_state.appt_date
    if st.session_state.appt_view == "weekly":
        weekly_view(user, d, did)
    else:
        daily_view(user, d, did, can_edit)

    # working hours summary for the selected doctor/date
    if did:
        doc = repo.doctor(did)
        status, hours = repo.doctor_status(did, d)
        day = repo.doctor_day(did, d)
        brk = f" · Break {day['break_start']}-{day['break_end']}" if day and day.get("break_start") else ""
        tone = {"available": "success", "on_leave": "danger", "off_today": "neutral", "in_consultation": "warning"}[status]
        st.markdown(f"<div style='margin-top:.6rem;font-size:.82rem;color:var(--muted)'>{ui.esc(doc['name'])} · {t('working_hours')}: "
                    f"{hours or '-'}{brk} · {ui.badge(t(status), tone)}</div>", unsafe_allow_html=True)
