"""Billing & payments: invoices, authorized discounts, partial payments, receipts and daily collection."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from core import auth, config, db, repo, ui
from core.i18n import t
from core.utils import fmt_date, fmt_datetime, fmt_time, money, today
from modules.appointments import patient_picker


def receipt_buttons(inv: dict, settings: dict, key: str) -> None:
    from pdf import receipt
    ui.icon_download(f"{t('receipt')} · English", "printer", f"{key}_en", receipt.build(inv, settings, "en"),
                     f"{inv['invoice_no']}_en.pdf", "application/pdf", use_container_width=True)
    if settings.get("show_urdu_on_prints", "1") == "1":
        ui.icon_download(f"{t('receipt')} · English + اردو", "printer", f"{key}_ur", receipt.build(inv, settings, "both"),
                         f"{inv['invoice_no']}_ur.pdf", "application/pdf", use_container_width=True)


# ------------------------------------------------------------ new invoice
def invoice_form(user: dict, settings: dict) -> None:
    sym = settings.get("currency_symbol", "Rs.")
    services = repo.services()
    with st.container(border=True):
        ui.section(t("new_invoice"), "receipt")
        # quick pick from today's unbilled visits
        unbilled = repo.unbilled_visits(today())
        pre = st.session_state.get("billing_prefill")  # dict from unbilled selection
        if not unbilled.empty:
            labels = {int(r.appointment_id): f"{fmt_time(r.appt_time)} · {r.patient} ({r.patient_code}) · {r.doctor} · {ui.status_label(r.status)}" for r in unbilled.itertuples()}
            opts = [0] + list(labels.keys())
            sel = st.selectbox(t("unbilled_visits"), opts, format_func=lambda i: "-- choose a visit (optional) --" if i == 0 else labels[i], key="bill_unbilled")
            if sel:
                row = unbilled[unbilled["appointment_id"] == sel].iloc[0]
                pre = dict(patient_id=int(row.patient_id), doctor_id=int(row.doctor_id), fee=float(row.consultation_fee),
                           appointment_id=int(row.appointment_id), consultation_id=int(row.consultation_id) if pd.notna(row.consultation_id) else None)
                st.session_state.billing_prefill = pre
            elif pre and st.session_state.get("bill_unbilled_prev") != sel:
                st.session_state.pop("billing_prefill", None)
                pre = None
            st.session_state.bill_unbilled_prev = sel
        if pre and pre.get("patient_id"):
            st.session_state.prefill_patient_id = pre["patient_id"]
        pid = patient_picker("bill_pat")
        c1, c2 = st.columns([1.4, 1])
        docs = repo.doctor_options()
        doc_ids = [0] + list(docs.keys())
        d_idx = doc_ids.index(pre["doctor_id"]) if pre and pre.get("doctor_id") in doc_ids else 0
        did = c1.selectbox(t("doctor"), doc_ids, index=d_idx, format_func=lambda i: "-" if i == 0 else docs[i], key="bill_doc")
        default_fee = (pre or {}).get("fee") if pre else (repo.doctor(did)["consultation_fee"] if did else float(settings.get("default_consultation_fee", 0) or 0))
        fee = c2.number_input(f"{t('consultation_fee')} ({sym})", min_value=0.0, value=float(default_fee or 0), step=50.0, key="bill_fee")

        st.markdown(f"**{t('services')}**")
        svc_names = [s["name"] for s in services]
        chosen = st.multiselect(t("services"), svc_names, key="bill_svcs", label_visibility="collapsed")
        items = []
        svc_total = 0.0
        if chosen:
            cols = st.columns(len(chosen)) if len(chosen) <= 4 else None
            for i, name in enumerate(chosen):
                s = next(x for x in services if x["name"] == name)
                holder = cols[i] if cols else st
                qty = holder.number_input(f"{name} × ({money(s['price'], sym)})", min_value=1, value=1, step=1, key=f"bill_qty_{s['id']}")
                items.append(dict(description=name, qty=qty, unit_price=s["price"]))
                svc_total += qty * s["price"]
        extra = st.text_input("Other charge (description) · optional", key="bill_extra_desc", max_chars=100)
        extra_amt = st.number_input(f"Other charge amount ({sym})", min_value=0.0, value=0.0, step=50.0, key="bill_extra_amt") if extra else 0.0
        if extra and extra_amt > 0:
            items.append(dict(description=extra, qty=1, unit_price=extra_amt))
            svc_total += extra_amt

        subtotal = fee + svc_total
        st.markdown(f"**{t('discount')}**")
        c1, c2 = st.columns([1, 2])
        discount = c1.number_input(f"{t('discount')} ({sym})", min_value=0.0, max_value=float(subtotal) if subtotal else 0.0, value=0.0, step=50.0, key="bill_disc")
        reason = c2.text_input("Reason", key="bill_disc_reason", max_chars=120, disabled=discount <= 0)
        authorized_by = ""
        max_free = float(settings.get("max_discount_without_auth", "0") or 0)
        if discount > 0:
            if auth.is_admin(user) or discount <= max_free:
                authorized_by = user["username"]
                st.caption(f"Authorized by {user['full_name']}")
            else:
                ui.notice(t("discount_auth"), "warning", "lock")
                a1, a2 = st.columns(2)
                au = a1.text_input("Administrator username", key="bill_auth_user", autocomplete="off")
                ap = a2.text_input("Administrator password", type="password", key="bill_auth_pw", autocomplete="off")
                if au and ap:
                    ok = auth.authorize_admin(au, ap)
                    if ok:
                        authorized_by = ok["username"]
                        st.success(f"Authorized by {ok['full_name']}")
                    else:
                        st.error("Authorization failed")
        total = max(subtotal - discount, 0)

        st.markdown(f"**{t('record_payment')}**")
        c1, c2, c3 = st.columns([1, 1, 1.4])
        received = c1.number_input(f"{t('received')} ({sym})", min_value=0.0, max_value=float(total), value=float(total), step=50.0, key="bill_received")
        method = c2.selectbox(t("payment_method"), config.PAYMENT_METHODS, key="bill_method")
        ref = c3.text_input(f"Reference / TID ({t('optional')})", key="bill_ref", max_chars=100)
        notes = st.text_input(f"{t('notes')} ({t('optional')})", key="bill_notes", max_chars=300)

        st.markdown(
            f'<div class="cml-card" style="margin:.4rem 0"><div class="cml-kv">'
            f'<div class="k">{t("consultation_fee")}</div><div class="v">{money(fee, sym)}</div>'
            f'<div class="k">{t("services")}</div><div class="v">{money(svc_total, sym)}</div>'
            f'<div class="k">{t("discount")}</div><div class="v">- {money(discount, sym)}</div>'
            f'<div class="k" style="font-weight:700">{t("total")}</div><div class="v" style="font-weight:700;font-size:1.05rem">{money(total, sym)}</div>'
            f'<div class="k">{t("received")}</div><div class="v">{money(received, sym)}</div>'
            f'<div class="k">{t("outstanding")}</div><div class="v" style="color:var(--danger)">{money(total - received, sym)}</div>'
            f'</div></div>', unsafe_allow_html=True)
        b1, b2, _ = st.columns([1, 1, 3])
        disabled = not pid or (discount > 0 and not authorized_by) or (total <= 0 and not items and fee <= 0)
        if b1.button(t("save"), type="primary", key="bill_save", disabled=disabled):
            try:
                inv_id = repo.create_invoice(
                    pid, did or None, fee, items, discount, reason, authorized_by,
                    consultation_id=(pre or {}).get("consultation_id"), appointment_id=(pre or {}).get("appointment_id"),
                    notes=notes, payment=dict(amount=received, method=method, reference=ref) if received > 0 else None, actor=user)
                st.session_state.billing_show_form = False
                st.session_state.pop("billing_prefill", None)
                st.session_state.inv_view_id = inv_id
                st.toast(t("saved"))
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if b2.button(t("cancel"), key="bill_cancel"):
            st.session_state.billing_show_form = False
            st.session_state.pop("billing_prefill", None)
            st.rerun()


# ----------------------------------------------------------- invoice view
def invoice_detail(user: dict, inv_id: int, settings: dict) -> None:
    sym = settings.get("currency_symbol", "Rs.")
    inv = repo.invoice(inv_id)
    if not inv:
        st.session_state.pop("inv_view_id", None)
        st.rerun()
    can_edit = auth.can_edit(user, "billing")
    top = st.columns([0.9, 4, 1.2])
    if top[0].button(t("back"), key="inv_back"):
        st.session_state.pop("inv_view_id", None)
        st.rerun()
    with top[1]:
        ui.page_header(inv["invoice_no"], f"{inv['patient_name']} · {inv['patient_code']} · {fmt_date(inv['invoice_date'])}", "receipt")
    with top[2]:
        st.markdown(f"<div style='padding-top:.6rem'>{ui.status_badge(inv['status'])}</div>", unsafe_allow_html=True)

    left, right = st.columns([1.3, 1])
    with left:
        rows = []
        if inv["consultation_fee"]:
            rows.append((t("consultation_fee"), 1, inv["consultation_fee"], inv["consultation_fee"]))
        for it in inv["items"]:
            rows.append((it["description"], it["qty"], it["unit_price"], it["amount"]))
        df = pd.DataFrame(rows, columns=["Description", "Qty", "Rate", "Amount"])
        df["Rate"] = df["Rate"].map(lambda v: money(v, sym))
        df["Amount"] = df["Amount"].map(lambda v: money(v, sym))
        with st.container(border=True):
            ui.section(t("invoice"), "receipt")
            ui.dataframe(df, height=42 + 35 * len(df) + 4)
            disc = f'<div class="k">{t("discount")} ({ui.esc(inv["discount_reason"])}, auth: {ui.esc(inv["discount_authorized_by"])})</div><div class="v">- {money(inv["discount_amount"], sym)}</div>' if inv["discount_amount"] else ""
            st.markdown(f'<div class="cml-kv"><div class="k">{t("total")}</div><div class="v" style="font-weight:700">{money(inv["total"], sym)}</div>{disc}'
                        f'<div class="k">{t("received")}</div><div class="v">{money(inv["paid"], sym)}</div>'
                        f'<div class="k">{t("outstanding")}</div><div class="v" style="color:var(--danger);font-weight:600">{money(inv["outstanding"], sym)}</div>'
                        f'<div class="k">{t("doctor")}</div><div class="v">{ui.esc(inv.get("doctor_name") or "-")}</div>'
                        f'<div class="k">Created by</div><div class="v">{ui.esc(inv.get("created_by_name") or "-")} · {fmt_datetime(inv["created_at"])}</div></div>',
                        unsafe_allow_html=True)
            if inv.get("notes"):
                st.caption(inv["notes"])
        with st.container(border=True):
            ui.section(t("payment_history"), "wallet", len(inv["payments"]))
            if inv["payments"]:
                pdf_ = pd.DataFrame([(fmt_datetime(p["paid_at"]), p["method"], p.get("reference") or "-", money(p["amount"], sym), p.get("received_by_name") or "-")
                                     for p in inv["payments"]], columns=[t("date"), t("payment_method"), "Ref", t("amount"), "Received by"])
                ui.dataframe(pdf_, height=42 + 35 * len(pdf_) + 4)
            else:
                ui.empty_state(t("no_data"), "", "wallet")
    with right:
        receipt_buttons(inv, settings, "inv_pdf")
        if can_edit and inv["status"] in ("Unpaid", "Partial"):
            with st.form("pay_form", border=True):
                ui.section(t("record_payment"), "banknote")
                amt = st.number_input(f"{t('amount')} ({sym})", min_value=0.0, max_value=float(inv["outstanding"]), value=float(inv["outstanding"]), step=50.0)
                method = st.selectbox(t("payment_method"), config.PAYMENT_METHODS)
                ref = st.text_input(f"Reference ({t('optional')})", max_chars=100)
                if st.form_submit_button(t("record_payment"), type="primary"):
                    try:
                        repo.record_payment(inv_id, amt, method, ref, actor=user)
                        st.toast(t("saved"))
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        if can_edit and inv["status"] != "Cancelled" and inv["paid"] == 0:
            with st.expander(f"{t('cancel')} {t('invoice').lower()}"):
                reason = st.text_input("Reason", key="inv_cancel_reason")
                if st.button(t("confirm"), key="inv_cancel_btn", disabled=not reason):
                    try:
                        repo.cancel_invoice(inv_id, reason, actor=user)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        if st.button(t("patient_profile"), key="inv_go_patient"):
            st.session_state.patient_view_id = inv["patient_id"]
            st.session_state.page = "patients"
            st.rerun()


# ------------------------------------------------------------------ page
def render(user: dict) -> None:
    settings = db.get_settings()
    sym = settings.get("currency_symbol", "Rs.")
    if st.session_state.get("inv_view_id"):
        invoice_detail(user, st.session_state.inv_view_id, settings)
        return
    can_edit = auth.can_edit(user, "billing")
    doctor_lock = user.get("doctor_id") if auth.is_doctor(user) else None
    head, act = st.columns([3, 1.2])
    with head:
        ui.page_header(t("billing"), t("daily_collection"), "credit-card")
    with act:
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        if can_edit and ui.icon_button(t("new_invoice"), "plus", "bill_new", type="primary", use_container_width=True):
            st.session_state.billing_show_form = not st.session_state.get("billing_show_form", False)
    if st.session_state.get("prefill_patient_id") and can_edit:
        st.session_state.billing_show_form = True
    if can_edit and st.session_state.get("billing_show_form"):
        invoice_form(user, settings)

    tabs = st.tabs([t("invoices"), t("daily_collection"), t("outstanding")])
    with tabs[0]:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 1, 1, 1.6])
            start = c1.date_input(t("from"), value=today() - timedelta(days=7), key="inv_from", format="DD/MM/YYYY")
            end = c2.date_input(t("to"), value=today(), key="inv_to", format="DD/MM/YYYY")
            status = c3.selectbox(t("status"), [""] + list(config.INVOICE_STATUSES), format_func=lambda s: t("all") if not s else ui.status_label(s), key="inv_status")
            search = c4.text_input(t("search"), key="inv_search", placeholder="INV-2026-00001 / name / ID")
        df = repo.invoices_list(start, end, status or None, search, doctor_lock)
        if df.empty:
            ui.empty_state(t("no_data"), "", "receipt")
        else:
            ui.kpi_row([
                (t("invoices"), len(df), "receipt", "primary", f"{fmt_date(start)} - {fmt_date(end)}"),
                (t("total"), money(df["total"].sum(), sym), "banknote", "primary"),
                (t("received"), money(df["paid"].sum(), sym), "wallet", "success"),
                (t("outstanding"), money(df["outstanding"].sum(), sym), "credit-card", "danger"),
            ], min_width=160)
            view = pd.DataFrame({t("invoice"): df["invoice_no"], t("date"): df["invoice_date"].map(fmt_date), t("patient"): df["patient"],
                                 t("patient_id"): df["patient_code"], t("doctor"): df["doctor"].fillna("-"),
                                 t("total"): df["total"].map(lambda v: money(v, sym)), t("received"): df["paid"].map(lambda v: money(v, sym)),
                                 t("outstanding"): df["outstanding"].map(lambda v: money(v, sym)), t("status"): df["status"].map(ui.status_label)})
            st.caption(t("select_row"))
            ev = st.dataframe(view, hide_index=True, width="stretch", height=min(500, 42 + 35 * len(view)), on_select="rerun",
                              selection_mode="single-row", key=f"inv_table_{st.session_state.get('inv_table_nonce', 0)}")
            if ev and ev.selection and ev.selection.rows:
                st.session_state.inv_view_id = int(df.iloc[ev.selection.rows[0]]["id"])
                st.session_state.inv_table_nonce = st.session_state.get("inv_table_nonce", 0) + 1
                st.rerun()
            ui.icon_download(t("download_csv"), "file-spreadsheet", "inv_csv", view.to_csv(index=False).encode("utf-8-sig"),
                             f"invoices_{start}_{end}.csv", "text/csv")
    with tabs[1]:
        c1, c2 = st.columns([1, 3])
        d = c1.date_input(t("date"), value=today(), key="coll_date", format="DD/MM/YYYY")
        by_method = repo.collection_by_method(d, d, doctor_lock)
        total = float(by_method["amount"].sum()) if not by_method.empty else 0.0
        tiles = [(t("daily_collection"), money(total, sym), "wallet", "primary", fmt_date(d))]
        for r in by_method.itertuples():
            tiles.append((r.method, money(r.amount, sym), "banknote", "neutral", f"{int(r.payments)} payment(s)"))
        ui.kpi_row(tiles, min_width=160)
        pays = db.df(
            "SELECT p.paid_at, i.invoice_no, pt.full_name AS patient, pt.patient_code, d.name AS doctor, p.method, p.reference, p.amount, u.full_name AS received_by "
            "FROM payments p JOIN invoices i ON i.id = p.invoice_id JOIN patients pt ON pt.id = i.patient_id LEFT JOIN doctors d ON d.id = i.doctor_id "
            "LEFT JOIN users u ON u.id = p.received_by WHERE substr(p.paid_at,1,10) = ?" + (" AND i.doctor_id = ?" if doctor_lock else "") + " ORDER BY p.paid_at",
            [d.strftime("%Y-%m-%d")] + ([doctor_lock] if doctor_lock else []))
        if pays.empty:
            ui.empty_state(t("no_data"), "", "wallet")
        else:
            v = pays.copy()
            v["paid_at"] = v["paid_at"].map(fmt_datetime)
            v["amount"] = v["amount"].map(lambda x: money(x, sym))
            v.columns = [t("time"), t("invoice"), t("patient"), t("patient_id"), t("doctor"), t("payment_method"), "Ref", t("amount"), "Received by"]
            ui.dataframe(v, height=min(500, 42 + 35 * len(v)))
            ui.icon_download(t("download_csv"), "file-spreadsheet", "coll_csv", v.to_csv(index=False).encode("utf-8-sig"),
                             f"collection_{d}.csv", "text/csv")
    with tabs[2]:
        out = repo.outstanding_invoices()
        if doctor_lock:
            out = out[out["invoice_no"].isin(db.df("SELECT invoice_no FROM invoices WHERE doctor_id = ?", (doctor_lock,))["invoice_no"])] if not out.empty else out
        if out.empty:
            ui.empty_state(t("no_data"), "", "credit-card")
        else:
            ui.kpi_row([(t("outstanding"), money(out["outstanding"].sum(), sym), "credit-card", "danger", f"{len(out)} invoice(s)")], min_width=200)
            v = pd.DataFrame({t("invoice"): out["invoice_no"], t("date"): out["invoice_date"].map(fmt_date), t("patient"): out["patient"],
                              t("patient_id"): out["patient_code"], t("phone"): out["phone"], t("total"): out["total"].map(lambda x: money(x, sym)),
                              t("received"): out["paid"].map(lambda x: money(x, sym)), t("outstanding"): out["outstanding"].map(lambda x: money(x, sym))})
            ev = st.dataframe(v, hide_index=True, width="stretch", height=min(500, 42 + 35 * len(v)), on_select="rerun",
                              selection_mode="single-row", key=f"out_table_{st.session_state.get('inv_table_nonce', 0)}")
            if ev and ev.selection and ev.selection.rows:
                st.session_state.inv_view_id = int(out.iloc[ev.selection.rows[0]]["id"])
                st.session_state.inv_table_nonce = st.session_state.get("inv_table_nonce", 0) + 1
                st.rerun()
