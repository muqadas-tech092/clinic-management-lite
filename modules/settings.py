"""Settings: clinic profile, doctors & schedules, users, services, prints, language, backup, audit log, security."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import audit, auth, backup, config, db, repo, ui
from core.i18n import LANGS, t
from core.utils import fmt_date, fmt_datetime, money, save_upload, resolve_upload, today


# ------------------------------------------------------------ clinic profile
def clinic_tab(user: dict, settings: dict) -> None:
    with st.form("clinic_form", border=True):
        ui.section(t("clinic_profile"), "hospital")
        c1, c2 = st.columns(2)
        name = c1.text_input("Clinic name *", value=settings["clinic_name"], max_chars=80)
        tagline = c2.text_input("Tagline", value=settings.get("clinic_tagline", ""), max_chars=100)
        address = st.text_input(t("address"), value=settings.get("clinic_address", ""), max_chars=200)
        c1, c2, c3 = st.columns(3)
        phone = c1.text_input(t("phone"), value=settings.get("clinic_phone", ""), max_chars=40)
        email = c2.text_input("Email", value=settings.get("clinic_email", ""), max_chars=80)
        currency = c3.text_input("Currency symbol", value=settings.get("currency_symbol", "Rs."), max_chars=6)
        c1, c2, c3 = st.columns(3)
        fee = c1.number_input(f"Default {t('consultation_fee').lower()}", min_value=0.0, value=float(settings.get("default_consultation_fee", 0) or 0), step=50.0)
        dur = c2.number_input("Appointment duration (minutes)", min_value=5, max_value=120, value=int(settings.get("appointment_duration", 15) or 15), step=5)
        prefix = c3.text_input("Token prefix", value=settings.get("token_prefix", "T"), max_chars=3)
        c1, c2, c3 = st.columns(3)
        lang = c1.selectbox("Default language", list(LANGS.keys()), index=list(LANGS.keys()).index(settings.get("default_language", "en")), format_func=lambda k: LANGS[k])
        fu = c2.number_input("Follow-up reminder window (days)", min_value=1, max_value=60, value=int(settings.get("follow_up_window_days", 7) or 7))
        max_disc = c3.number_input("Max discount without admin authorization", min_value=0.0, value=float(settings.get("max_discount_without_auth", 0) or 0), step=50.0)
        if st.form_submit_button(t("save"), type="primary"):
            if len(name.strip()) < 2:
                st.error("Clinic name is required")
            else:
                with db.transaction() as conn:
                    for k, v in dict(clinic_name=name.strip(), clinic_tagline=tagline.strip(), clinic_address=address.strip(), clinic_phone=phone.strip(),
                                     clinic_email=email.strip(), currency_symbol=currency.strip() or "Rs.", default_consultation_fee=fee,
                                     appointment_duration=int(dur), token_prefix=prefix.strip(), default_language=lang,
                                     follow_up_window_days=int(fu), max_discount_without_auth=max_disc).items():
                        db.set_setting(k, v, conn)
                    audit.log("update", "settings", "clinic", user=user, conn=conn)
                st.toast(t("saved"))
                st.rerun()
    with st.container(border=True):
        ui.section("Clinic logo", "image")
        c1, c2 = st.columns([1, 2])
        with c1:
            p = resolve_upload(settings.get("clinic_logo", ""))
            if p:
                st.image(str(p), width=120)
            else:
                ui.empty_state("No logo", "PNG or JPG, up to 2 MB", "image")
        with c2:
            up = st.file_uploader("Upload logo", type=["png", "jpg", "jpeg", "webp"], key="logo_upload")
            if up and st.button("Save logo", key="logo_save", type="primary"):
                try:
                    rel = save_upload(up, "clinic", "logo")
                    db.set_setting("clinic_logo", rel)
                    audit.log("update", "settings", "clinic_logo", user=user)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if p and st.button("Remove logo", key="logo_remove"):
                db.set_setting("clinic_logo", "")
                st.rerun()


# ------------------------------------------------------------------- doctors
def doctor_editor(user: dict, doc: dict | None) -> None:
    init = doc or {}
    with st.form(f"doc_form_{init.get('id', 'new')}", border=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name *", value=init.get("name", ""), max_chars=100, placeholder="Dr. ...")
        spec = c2.text_input("Specialization", value=init.get("specialization", ""), max_chars=100)
        c1, c2 = st.columns(2)
        qual = c1.text_input("Qualifications", value=init.get("qualification", ""), max_chars=150, placeholder="MBBS, FCPS")
        reg = c2.text_input("Registration number (PMDC / PMC)", value=init.get("registration_no", ""), max_chars=60)
        c1, c2, c3 = st.columns(3)
        phone = c1.text_input(t("phone"), value=init.get("phone", ""), max_chars=30)
        email = c2.text_input("Email", value=init.get("email", ""), max_chars=100)
        fee = c3.number_input(t("consultation_fee"), min_value=0.0, value=float(init.get("consultation_fee", 0) or 0), step=50.0)
        active = st.checkbox("Active", value=bool(init.get("is_active", 1)))
        if st.form_submit_button(t("save"), type="primary"):
            try:
                did = repo.save_doctor(dict(name=name, specialization=spec, qualification=qual, registration_no=reg, phone=phone, email=email,
                                            consultation_fee=fee, photo_path=init.get("photo_path", ""), is_active=active),
                                       doctor_id=init.get("id"), actor=user)
                st.session_state.settings_doc_id = did
                st.toast(t("saved"))
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def doctors_tab(user: dict) -> None:
    docs = repo.doctors(active_only=False)
    c1, c2 = st.columns([1, 2.2])
    with c1:
        ui.section(t("doctors"), "stethoscope", len(docs))
        opts = {0: f"+ {t('add')}", **{d["id"]: d["name"] + ("" if d["is_active"] else " (inactive)") for d in docs}}
        cur = st.session_state.get("settings_doc_id", docs[0]["id"] if docs else 0)
        if cur not in opts:
            cur = 0
        sel = st.radio("Doctor", list(opts.keys()), index=list(opts.keys()).index(cur), format_func=lambda i: opts[i], key="settings_doc_radio",
                       label_visibility="collapsed")
        st.session_state.settings_doc_id = sel
    with c2:
        doc = repo.doctor(sel) if sel else None
        if doc:
            st.markdown(f"<div style='display:flex;gap:1rem;align-items:center;margin-bottom:.6rem'>{ui.avatar_html(doc.get('photo_path'), doc['name'], 64)}"
                        f"<div><div style='font-weight:700;font-size:1.05rem'>{ui.esc(doc['name'])}</div><div style='color:var(--muted);font-size:.84rem'>"
                        f"{ui.esc(doc['specialization'])} · {ui.esc(doc['qualification'])} · {ui.esc(doc['registration_no'])}</div></div></div>", unsafe_allow_html=True)
        sub = st.tabs(["Profile", "Photo", t("working_hours"), t("holidays")]) if doc else [st.container()]
        with sub[0]:
            doctor_editor(user, doc)
        if doc:
            with sub[1]:
                up = st.file_uploader("Profile photo (PNG/JPG, up to 2 MB)", type=["png", "jpg", "jpeg", "webp"], key=f"doc_photo_{doc['id']}")
                if up and st.button("Save photo", key=f"doc_photo_save_{doc['id']}", type="primary"):
                    try:
                        rel = save_upload(up, "doctors", f"doctor_{doc['id']}")
                        db.execute("UPDATE doctors SET photo_path = ? WHERE id = ?", (rel, doc["id"]))
                        audit.log("update", "doctor", doc["id"], {"photo": rel}, user=user)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                if doc.get("photo_path") and st.button("Remove photo", key=f"doc_photo_rm_{doc['id']}"):
                    db.execute("UPDATE doctors SET photo_path = '' WHERE id = ?", (doc["id"],))
                    st.rerun()
            with sub[2]:
                sched = repo.doctor_schedule(doc["id"])
                with st.form(f"sched_form_{doc['id']}", border=True):
                    rows = []
                    hdr = st.columns([1.2, 0.8, 1, 1, 1, 1])
                    for h, label in zip(hdr, ["Day", "Working", "Start", "End", "Break start", "Break end"]):
                        h.caption(label)
                    for r in sched:
                        c = st.columns([1.2, 0.8, 1, 1, 1, 1])
                        c[0].markdown(f"**{config.WEEKDAYS[r['weekday']]}**")
                        w = c[1].checkbox("on", value=bool(r["is_working"]), key=f"wd_on_{doc['id']}_{r['weekday']}", label_visibility="collapsed")
                        s_ = c[2].text_input("start", value=r["start_time"], key=f"wd_s_{doc['id']}_{r['weekday']}", label_visibility="collapsed")
                        e_ = c[3].text_input("end", value=r["end_time"], key=f"wd_e_{doc['id']}_{r['weekday']}", label_visibility="collapsed")
                        bs = c[4].text_input("bs", value=r["break_start"] or "", key=f"wd_bs_{doc['id']}_{r['weekday']}", label_visibility="collapsed", placeholder="13:00")
                        be = c[5].text_input("be", value=r["break_end"] or "", key=f"wd_be_{doc['id']}_{r['weekday']}", label_visibility="collapsed", placeholder="14:00")
                        rows.append(dict(weekday=r["weekday"], is_working=w, start_time=s_.strip(), end_time=e_.strip(), break_start=bs.strip(), break_end=be.strip()))
                    st.caption("24-hour times, e.g. 09:00 and 17:30. Slots are generated from these hours using the appointment duration.")
                    if st.form_submit_button(t("save"), type="primary"):
                        try:
                            repo.save_schedule(doc["id"], rows, actor=user)
                            st.toast(t("saved"))
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
            with sub[3]:
                hols = repo.holidays(doc["id"], from_date=today())
                c1, c2, c3 = st.columns([1, 2, 1])
                hd = c1.date_input(t("date"), value=today(), min_value=today(), key=f"hol_date_{doc['id']}", format="DD/MM/YYYY")
                hr = c2.text_input("Reason", key=f"hol_reason_{doc['id']}", max_chars=100)
                c3.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
                if c3.button(t("add"), key=f"hol_add_{doc['id']}", type="primary", width="stretch"):
                    repo.add_holiday(doc["id"], hd, hr, actor=user)
                    st.rerun()
                if not hols:
                    ui.empty_state("No upcoming holidays", "", "calendar")
                for h in hols:
                    a, b = st.columns([4, 1])
                    a.markdown(f"**{fmt_date(h['holiday_date'], long=True)}** · {ui.esc(h['reason'] or '-')}", unsafe_allow_html=True)
                    if b.button(t("remove"), key=f"hol_rm_{h['id']}"):
                        repo.remove_holiday(h["id"], actor=user)
                        st.rerun()


# --------------------------------------------------------------------- users
def users_tab(user: dict) -> None:
    users = repo.users_list()
    ui.section(t("users"), "users", len(users))
    v = pd.DataFrame({t("username"): users["username"], t("name"): users["full_name"], "Role": users["role"].map(t),
                      t("doctor"): users["doctor"].fillna("-"), t("status"): users["is_active"].map(lambda a: "Active" if a else "Inactive"),
                      "Last login": users["last_login"].map(lambda x: fmt_datetime(x) if x else "-")})
    ui.dataframe(v, height=42 + 35 * len(v) + 4)
    c1, c2 = st.columns(2)
    with c1:
        with st.form("user_new", border=True):
            ui.section("Add user", "user-plus")
            uname = st.text_input("Username *", max_chars=40)
            full = st.text_input("Full name *", max_chars=100)
            role = st.selectbox("Role", config.ROLES, format_func=t)
            docs = repo.doctor_options()
            did = st.selectbox("Linked doctor (for Doctor role)", [0] + list(docs.keys()), format_func=lambda i: "-" if i == 0 else docs[i])
            pw = st.text_input("Temporary password *", type="password", help="At least 8 characters with letters and numbers")
            if st.form_submit_button("Create user", type="primary"):
                try:
                    if role == "doctor" and not did:
                        raise ValueError("Select the linked doctor for a Doctor account")
                    auth.create_user(uname, pw, full, role, did or None, actor=user)
                    st.toast(t("saved"))
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    with c2:
        with st.container(border=True):
            ui.section("Manage user", "key-round")
            opts = {int(r.id): f"{r.username} ({r.full_name})" for r in users.itertuples()}
            uid = st.selectbox("User", list(opts.keys()), format_func=lambda i: opts[i], key="mng_user")
            target = auth.get_user(uid)
            if target:
                new_role = st.selectbox("Role", config.ROLES, index=config.ROLES.index(target["role"]), format_func=t, key="mng_role")
                docs = repo.doctor_options()
                d_ids = [0] + list(docs.keys())
                new_doc = st.selectbox("Linked doctor", d_ids, index=d_ids.index(target["doctor_id"]) if target.get("doctor_id") in d_ids else 0,
                                       format_func=lambda i: "-" if i == 0 else docs[i], key="mng_doc")
                new_name = st.text_input("Full name", value=target["full_name"], key="mng_name")
                a, b, c = st.columns(3)
                if a.button(t("save"), key="mng_save", type="primary"):
                    try:
                        repo.update_user(uid, new_name, new_role, new_doc or None, actor=user)
                        st.toast(t("saved"))
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                if uid != user["id"]:
                    if b.button("Deactivate" if target["is_active"] else "Activate", key="mng_toggle"):
                        repo.set_user_active(uid, not target["is_active"], actor=user)
                        st.rerun()
                if c.button("Sign out everywhere", key="mng_revoke"):
                    auth.revoke_all_sessions(uid, actor=user)
                    st.toast("Sessions revoked")
                npw = st.text_input("Reset password", type="password", key="mng_pw")
                if st.button("Set new password", key="mng_pw_btn", disabled=not npw):
                    try:
                        auth.set_password(uid, npw, actor=user)
                        st.toast("Password updated")
                    except ValueError as exc:
                        st.error(str(exc))


# ------------------------------------------------------------------ services
def services_tab(user: dict, settings: dict) -> None:
    sym = settings.get("currency_symbol", "Rs.")
    svcs = repo.services(active_only=False)
    ui.section(t("services"), "briefcase-medical", len(svcs))
    c1, c2 = st.columns([1.4, 1])
    with c1:
        for s in svcs:
            a, b, c, d = st.columns([2.5, 1.2, 1, 1])
            a.markdown(f"**{ui.esc(s['name'])}**" + ("" if s["is_active"] else " · inactive"), unsafe_allow_html=True)
            price = b.number_input("price", min_value=0.0, value=float(s["price"]), step=50.0, key=f"svc_p_{s['id']}", label_visibility="collapsed")
            if c.button(t("save"), key=f"svc_save_{s['id']}"):
                repo.save_service(s["name"], price, s["id"], bool(s["is_active"]), actor=user)
                st.rerun()
            if d.button("Disable" if s["is_active"] else "Enable", key=f"svc_tg_{s['id']}"):
                repo.save_service(s["name"], s["price"], s["id"], not s["is_active"], actor=user)
                st.rerun()
    with c2:
        with st.form("svc_new", border=True):
            ui.section("Add service", "plus")
            name = st.text_input("Service name *", max_chars=100)
            price = st.number_input(f"Price ({sym})", min_value=0.0, value=0.0, step=50.0)
            if st.form_submit_button(t("add"), type="primary"):
                try:
                    repo.save_service(name, price, actor=user)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


# -------------------------------------------------------------------- prints
def prints_tab(user: dict, settings: dict) -> None:
    with st.form("prints_form", border=True):
        ui.section("Prescription & receipt", "printer")
        c1, c2, c3 = st.columns(3)
        paper = c1.selectbox("Paper size", ["A5", "A4", "A6"], index=["A5", "A4", "A6"].index(settings.get("paper_size", "A5")))
        show_dx = c2.checkbox("Print diagnosis on prescription", value=settings.get("rx_show_diagnosis", "1") == "1")
        urdu = c3.checkbox("Offer Urdu prints", value=settings.get("show_urdu_on_prints", "1") == "1")
        c1, c2 = st.columns(2)
        rx_en = c1.text_area("Prescription footer (English)", value=settings.get("rx_footer_en", ""), height=80)
        rx_ur = c2.text_area("Prescription footer (Urdu)", value=settings.get("rx_footer_ur", ""), height=80)
        rc_en = c1.text_area("Receipt footer (English)", value=settings.get("receipt_footer_en", ""), height=80)
        rc_ur = c2.text_area("Receipt footer (Urdu)", value=settings.get("receipt_footer_ur", ""), height=80)
        c1, c2 = st.columns(2)
        low = c1.number_input("Default low-stock threshold", min_value=0, value=int(settings.get("low_stock_threshold", 10) or 10))
        expd = c2.number_input("Expiry warning (days ahead)", min_value=7, max_value=365, value=int(settings.get("expiry_warning_days", 90) or 90))
        if st.form_submit_button(t("save"), type="primary"):
            with db.transaction() as conn:
                for k, v in dict(paper_size=paper, rx_show_diagnosis="1" if show_dx else "0", show_urdu_on_prints="1" if urdu else "0",
                                 rx_footer_en=rx_en.strip(), rx_footer_ur=rx_ur.strip(), receipt_footer_en=rc_en.strip(), receipt_footer_ur=rc_ur.strip(),
                                 low_stock_threshold=int(low), expiry_warning_days=int(expd)).items():
                    db.set_setting(k, v, conn)
                audit.log("update", "settings", "prints", user=user, conn=conn)
            st.toast(t("saved"))
            st.rerun()
    st.caption("Urdu PDFs use a Nastaliq font if one is placed in assets/fonts (any .ttf), otherwise the Windows Tahoma/Arial Naskh glyphs.")


# -------------------------------------------------------------------- backup
def backup_tab(user: dict) -> None:
    c1, c2 = st.columns([1, 1.4])
    with c1:
        with st.container(border=True):
            ui.section(t("backup"), "database")
            counts = db.table_counts()
            st.caption(f"{counts.get('patients', 0)} patients · {counts.get('appointments', 0)} appointments · {counts.get('invoices', 0)} invoices · "
                       f"{counts.get('audit_log', 0)} audit entries")
            if ui.icon_button("Create backup now", "save", "bk_create", type="primary", use_container_width=True):
                p = backup.create_backup(actor=user)
                st.toast(f"Backup created: {p.name}")
                st.rerun()
            st.caption(f"Backups are stored in {config.BACKUP_DIR}")
        with st.container(border=True):
            ui.section("Restore from file", "upload")
            up = st.file_uploader("Upload a .db backup", type=["db"], key="bk_upload")
            ok = st.checkbox("I understand the current data will be replaced (a safety copy is taken first).", key="bk_restore_ok")
            if up and ok and st.button("Restore uploaded backup", key="bk_restore_up", type="primary"):
                try:
                    path = backup.save_uploaded_backup(up.getvalue())
                    safety = backup.restore_backup(path, actor=user)
                    st.success(f"Restored. Safety copy: {safety.name}. Please sign in again.")
                    st.session_state.pop("user", None)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Restore failed: {exc}")
    with c2:
        with st.container(border=True):
            items = backup.list_backups()
            ui.section("Available backups", "archive", len(items))
            if not items:
                ui.empty_state("No backups yet", "", "archive")
            for b in items[:20]:
                a, bcol, c, d = st.columns([2.6, 1, 1, 1])
                a.markdown(f"**{b['name']}**<br><span style='color:var(--muted);font-size:.78rem'>{b['modified']} · {b['size_kb']} KB</span>", unsafe_allow_html=True)
                p = backup.backup_path(b["name"])
                bcol.download_button(t("download_pdf").replace("PDF", "DB"), data=p.read_bytes(), file_name=b["name"], mime="application/octet-stream",
                                     key=f"bk_dl_{b['name']}", width="stretch")
                if c.button("Restore", key=f"bk_rs_{b['name']}", width="stretch"):
                    st.session_state.bk_confirm = b["name"]
                if d.button(t("delete"), key=f"bk_del_{b['name']}", width="stretch"):
                    backup.delete_backup(b["name"])
                    st.rerun()
            if st.session_state.get("bk_confirm"):
                name = st.session_state.bk_confirm
                ui.notice(f"Restore {name}? Current data will be replaced; a safety copy is created first.", "warning", "triangle-alert")
                a, b_ = st.columns(2)
                if a.button(t("confirm"), key="bk_confirm_yes", type="primary"):
                    try:
                        safety = backup.restore_backup(backup.backup_path(name), actor=user)
                        st.session_state.pop("bk_confirm", None)
                        st.success(f"Restored {name}. Safety copy: {safety.name}. Please sign in again.")
                        st.session_state.pop("user", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Restore failed: {exc}")
                if b_.button(t("cancel"), key="bk_confirm_no"):
                    st.session_state.pop("bk_confirm", None)
                    st.rerun()


# ----------------------------------------------------------------- audit log
def audit_tab() -> None:
    c1, c2, c3 = st.columns([1.5, 1, 0.8])
    search = c1.text_input(t("search"), key="audit_q", placeholder="username / action / details")
    entities = [""] + [r["entity"] for r in db.query("SELECT DISTINCT entity FROM audit_log ORDER BY entity")]
    ent = c2.selectbox("Entity", entities, format_func=lambda e: e or t("all"), key="audit_entity")
    limit = c3.selectbox("Rows", [100, 250, 500, 1000], key="audit_limit")
    df = audit.recent(limit, ent or None, search)
    if df.empty:
        ui.empty_state(t("no_data"), "", "shield")
        return
    v = pd.DataFrame({"Time": df["created_at"].map(fmt_datetime), "User": df["username"], "Action": df["action"], "Entity": df["entity"],
                      "ID": df["entity_id"], "Details": df["details"]})
    ui.dataframe(v, height=min(560, 42 + 35 * len(v)))
    ui.icon_download(t("download_csv"), "file-spreadsheet", "audit_csv", v.to_csv(index=False).encode("utf-8-sig"), f"audit_{today()}.csv", "text/csv")


# ------------------------------------------------------------------ security
def security_tab(user: dict) -> None:
    c1, c2 = st.columns(2)
    with c1:
        with st.form("pw_form", border=True):
            ui.section("Change my password", "lock")
            cur = st.text_input("Current password", type="password")
            new = st.text_input("New password", type="password")
            rep = st.text_input("Repeat new password", type="password")
            if st.form_submit_button("Update password", type="primary"):
                if new != rep:
                    st.error("New passwords do not match")
                else:
                    try:
                        auth.change_own_password(user, cur, new)
                        st.success("Password changed")
                    except ValueError as exc:
                        st.error(str(exc))
    with c2:
        with st.container(border=True):
            ui.section("Session & policy", "shield-check")
            st.markdown(ui.kv([
                ("Signed in as", f"{user['full_name']} ({user['username']})"), ("Role", t(user["role"])),
                ("Idle timeout", f"{config.IDLE_TIMEOUT_MIN} minutes"), ("Session lifetime", f"{config.SESSION_HOURS} hours"),
                ("Lockout", f"{config.MAX_FAILED_LOGINS} failed attempts → {config.LOCKOUT_MINUTES} min"),
                ("Password hashing", "bcrypt (12 rounds)"),
            ]), unsafe_allow_html=True)
            if st.button("Sign out of my other sessions", key="sec_revoke"):
                auth.revoke_all_sessions(user["id"], actor=user)
                # keep the current session alive
                db.execute("UPDATE sessions SET revoked = 0 WHERE token = ?", (user["session_token"],))
                st.toast("Other sessions revoked")
        ui.notice(t("prototype_notice"), "warning", "triangle-alert")


def render(user: dict) -> None:
    settings = db.get_settings()
    ui.page_header(t("settings"), f"{config.APP_NAME} v{config.APP_VERSION}", "settings")
    if not auth.is_admin(user):
        ui.notice(t("read_only") + " You can change your own password below.", "info", "info")
        security_tab(user)
        return
    tabs = st.tabs([t("clinic_profile"), t("doctors"), t("users"), t("services"), t("prints"), t("backup"), t("audit_log"), t("security")])
    with tabs[0]:
        clinic_tab(user, settings)
    with tabs[1]:
        doctors_tab(user)
    with tabs[2]:
        users_tab(user)
    with tabs[3]:
        services_tab(user, settings)
    with tabs[4]:
        prints_tab(user, settings)
    with tabs[5]:
        backup_tab(user)
    with tabs[6]:
        audit_tab()
    with tabs[7]:
        security_tab(user)
