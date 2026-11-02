"""Dashboard: live KPIs, schedule, queue, collection chart, availability and reminders."""
from __future__ import annotations

from datetime import timedelta

import streamlit as st

from core import auth, db, icons, repo, ui
from core.i18n import t
from core.utils import fmt_date, fmt_time, money, today


def render(user: dict) -> None:
    settings = db.get_settings()
    sym = settings.get("currency_symbol", "Rs.")
    doctor_id = user.get("doctor_id") if auth.is_doctor(user) else None

    head, ctl = st.columns([3, 1.2])
    with head:
        ui.page_header(t("dashboard"), f"{settings['clinic_name']} · {fmt_date(today(), long=True)}", "layout-dashboard")
    with ctl:
        d = st.date_input(t("date"), value=today(), key="dash_date", format="DD/MM/YYYY")

    stats = repo.dashboard_stats(d, doctor_id)
    label_day = t("today") if d == today() else fmt_date(d)
    ui.kpi_row([
        (t("todays_appointments") if d == today() else t("appointments"), stats["appointments"], "calendar", "primary",
         f"{stats['completed']} {t('completed_visits').lower()} · {stats['cancelled']} {t('cancel').lower()}"),
        (t("patients_waiting"), stats["waiting"], "hourglass", "warning", f"{stats['in_consultation']} {t('in_consultation').lower()}"),
        (t("completed_visits"), stats["completed"], "circle-check", "success", label_day),
        (t("todays_collection") if d == today() else t("daily_collection"), money(stats["collection"], sym), "wallet", "primary", label_day),
        (t("pending_payments"), money(stats["pending"], sym), "credit-card", "danger", t("all")),
    ])
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.6, 1])
    with left:
        with st.container(border=True):
            appts = repo.appointments_for_date(d, doctor_id)
            ui.section(f"{t('todays_schedule')} · {label_day}", "calendar", len(appts))
            if appts.empty:
                ui.empty_state(t("no_appointments_today"), "", "calendar")
            else:
                items = []
                for r in appts.itertuples():
                    has_token = r.token_no is not None and r.token_no == r.token_no
                    tok = f'<div class="tok">{int(r.token_no)}</div>' if has_token else                         f'<div class="tok" style="background:#EEF2F4;color:#9AAAB2">{icons.svg("user", 16)}</div>'
                    items.append(ui.row_item(
                        f"{r.patient} · {r.patient_code}", f"{r.doctor} · {ui.status_label(r.visit_type)}",
                        left_html=f'<div class="time">{fmt_time(r.appt_time)}</div>{tok}',
                        right_html=ui.status_badge(r.status)))
                ui.rows(items)
    with right:
        with st.container(border=True):
            q = repo.queue_for_date(d, doctor_id, statuses=("Waiting", "In Consultation"))
            ui.section(t("live_queue"), "ticket", len(q))
            if q.empty:
                ui.empty_state(t("queue_empty"), "", "ticket")
            else:
                items = [ui.row_item(r.patient, r.doctor, left_html=f'<div class="tok">{int(r.token_no)}</div>',
                                     right_html=ui.status_badge(r.status)) for r in q.itertuples()]
                ui.rows(items)
            if auth.can_edit(user, "queue") and not q.empty:
                if ui.icon_button(t("queue"), "arrow-right", "dash_go_queue", use_container_width=True):
                    st.session_state.page = "queue"
                    st.rerun()

    left, right = st.columns([1.6, 1])
    with left:
        with st.container(border=True):
            days = 14
            start = d - timedelta(days=days - 1)
            ui.section(f"{t('daily_collection')} · {t('last_days', n=days)}", "trending-up")
            coll = repo.daily_collection(start, d, doctor_id)
            if coll["amount"].sum() == 0:
                ui.empty_state(t("no_data"), "", "trending-up")
            else:
                coll["label"] = coll["day"].map(lambda s: fmt_date(s)[:6])
                fig = ui.bar_chart(coll["label"], coll["amount"], hover_fmt=f"{sym} %{{y:,.0f}}", height=260)
                ui.plot(fig)
    with right:
        with st.container(border=True):
            ui.section(t("doctor_availability"), "stethoscope")
            docs = repo.doctors()
            if doctor_id:
                docs = [x for x in docs if x["id"] == doctor_id]
            items = []
            for doc in docs:
                status, hours = repo.doctor_status(doc["id"], d)
                tone = {"available": "success", "on_leave": "danger", "off_today": "neutral", "in_consultation": "warning"}[status]
                sub = f"{doc['specialization']} · {hours}" if hours else doc["specialization"]
                items.append(ui.row_item(doc["name"], sub, left_html=ui.avatar_html(doc.get("photo_path"), doc["name"], 36),
                                         right_html=ui.badge(t(status), tone)))
            if items:
                ui.rows(items)
            else:
                ui.empty_state(t("no_data"), "", "stethoscope")

    left, right = st.columns([1, 1])
    with left:
        with st.container(border=True):
            ui.section(t("recent_registrations"), "user-plus")
            recent = repo.recent_patients(6)
            if recent.empty:
                ui.empty_state(t("no_patients"), "", "users")
            else:
                items = [ui.row_item(f"{r.full_name} · {r.patient_code}", f"{r.phone} · {fmt_date(r.created_at)}",
                                     left_html=ui.avatar_html(None, r.full_name, 36)) for r in recent.itertuples()]
                ui.rows(items)
    with right:
        with st.container(border=True):
            window = int(settings.get("follow_up_window_days", "7") or 7)
            ui.section(f"{t('follow_up_reminders')} · {t('next_days', n=window)}", "bell")
            fus = repo.upcoming_follow_ups(d - timedelta(days=3), d + timedelta(days=window), doctor_id)
            if fus.empty:
                ui.empty_state(t("no_follow_ups"), "", "bell")
            else:
                items = []
                for r in fus.head(8).itertuples():
                    overdue = str(r.follow_up_date) < d.strftime("%Y-%m-%d")
                    badge = ui.badge(t("booked") if r.booked else (t("overdue") if overdue else t("due")),
                                     "success" if r.booked else ("danger" if overdue else "warning"))
                    items.append(ui.row_item(f"{r.patient} · {r.patient_code}", f"{r.doctor} · {r.phone}",
                                             left_html=f'<div class="time">{fmt_date(r.follow_up_date)}</div>', right_html=badge))
                ui.rows(items)
                if len(fus) > 8:
                    st.caption(f"+{len(fus) - 8} more")
