"""Medicine inventory: stock list, add/edit, adjustments, low-stock and expiry warnings."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from core import auth, config, db, repo, ui
from core.i18n import t
from core.utils import fmt_date, fmt_datetime, money, today


def medicine_form(prefix: str, initial: dict | None = None) -> dict | None:
    init = initial or {}
    with st.form(f"{prefix}_form", border=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        name = c1.text_input(f"{t('name')} *", value=init.get("name", ""), max_chars=120)
        cat = c2.selectbox(t("category"), config.MEDICINE_CATEGORIES,
                           index=config.MEDICINE_CATEGORIES.index(init["category"]) if init.get("category") in config.MEDICINE_CATEGORIES else 0)
        sku = c3.text_input("SKU *", value=init.get("sku", ""), max_chars=40, disabled=bool(initial))
        c1, c2, c3, c4 = st.columns(4)
        qty = c1.number_input(t("quantity"), min_value=0, value=int(init.get("quantity", 0)), step=1, disabled=bool(initial),
                              help="Opening stock. Use stock adjustments after creation." if not initial else "Change stock via adjustments.")
        reorder = c2.number_input("Reorder level", min_value=0, value=int(init.get("reorder_level", 10)), step=1)
        pp = c3.number_input(t("purchase_price"), min_value=0.0, value=float(init.get("purchase_price", 0)), step=1.0)
        sp = c4.number_input(t("selling_price"), min_value=0.0, value=float(init.get("selling_price", 0)), step=1.0)
        c1, c2, c3 = st.columns([1, 1, 2])
        has_exp = c1.checkbox(f"{t('expiry')} known", value=bool(init.get("expiry_date")))
        exp = c2.date_input(t("expiry"), value=repo.to_date(init.get("expiry_date")) or today() + timedelta(days=365),
                            min_value=today() - timedelta(days=3650), format="DD/MM/YYYY", label_visibility="collapsed")
        supplier = c3.text_input(t("supplier"), value=init.get("supplier", ""), max_chars=120)
        active = st.checkbox("Active", value=bool(init.get("is_active", 1))) if initial else True
        if st.form_submit_button(t("save"), type="primary"):
            return dict(name=name, category=cat, sku=sku or init.get("sku"), quantity=qty, reorder_level=reorder, purchase_price=pp,
                        selling_price=sp, expiry_date=exp if has_exp else None, supplier=supplier, is_active=active)
    return None


def render(user: dict) -> None:
    settings = db.get_settings()
    sym = settings.get("currency_symbol", "Rs.")
    can_edit = auth.can_edit(user, "inventory")
    head, act = st.columns([3, 1.2])
    with head:
        ui.page_header(t("inventory"), t("inventory_notice"), "package")
    with act:
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        if can_edit and ui.icon_button(t("add_medicine"), "plus", "inv_add", type="primary", use_container_width=True):
            st.session_state.med_show_form = not st.session_state.get("med_show_form", False)
            st.session_state.pop("med_edit_id", None)

    if can_edit and st.session_state.get("med_show_form"):
        ui.section(t("add_medicine"), "pill")
        data = medicine_form("med_new")
        if data:
            try:
                repo.save_medicine(data, actor=user)
                st.session_state.med_show_form = False
                st.toast(t("saved"))
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    alerts = repo.stock_alerts()
    all_meds = repo.medicines()
    low = int((alerts["alert"].str.contains("Low stock")).sum()) if not alerts.empty else 0
    exp_soon = int((alerts["alert"].str.contains("Expiring soon")).sum()) if not alerts.empty else 0
    expired = int((alerts["alert"].str.contains("Expired")).sum()) if not alerts.empty else 0
    stock_value = float((all_meds["quantity"] * all_meds["purchase_price"]).sum()) if not all_meds.empty else 0.0
    ui.kpi_row([
        (t("items"), len(all_meds), "package", "primary", f"{int(all_meds['quantity'].sum()) if not all_meds.empty else 0} units"),
        (t("low_stock"), low, "triangle-alert", "warning" if low else "success"),
        (t("expiring_soon"), exp_soon, "clock", "warning" if exp_soon else "success", f"{settings.get('expiry_warning_days', 90)} days"),
        (t("expired"), expired, "circle-x", "danger" if expired else "success"),
        (t("stock_value"), money(stock_value, sym), "banknote", "neutral", ""),
    ], min_width=150)

    tabs = st.tabs([t("stock"), t("warnings"), t("adjust_stock") if can_edit else t("movements")])
    with tabs[0]:
        c1, c2, c3 = st.columns([2, 1, 1])
        q = c1.text_input(t("search"), key="med_q", placeholder="name / SKU / supplier", label_visibility="collapsed")
        cat = c2.selectbox(t("category"), ("",) + config.MEDICINE_CATEGORIES, format_func=lambda c: c or t("all"), key="med_cat")
        show_inactive = c3.checkbox(t("include_inactive"), key="med_inactive") if auth.is_admin(user) else False
        meds = repo.medicines(q, active_only=not show_inactive, category=cat or None)
        if meds.empty:
            ui.empty_state(t("no_data"), "", "package")
        else:
            flags = alerts.set_index("id")["alert"] if not alerts.empty else pd.Series(dtype=str)
            view = pd.DataFrame({
                "SKU": meds["sku"], t("name"): meds["name"], t("category"): meds["category"], t("quantity"): meds["quantity"].astype(int),
                "Reorder": meds["reorder_level"].astype(int), t("purchase_price"): meds["purchase_price"].map(lambda v: money(v, sym)),
                t("selling_price"): meds["selling_price"].map(lambda v: money(v, sym)),
                t("expiry"): meds["expiry_date"].map(lambda v: fmt_date(v) if v else "-"), t("supplier"): meds["supplier"],
                "Alert": meds["id"].map(lambda i: flags.get(i, "")),
            })
            if show_inactive:
                view[t("status")] = meds["is_active"].map(lambda a: "Active" if a else "Inactive")
            st.caption(t("select_row") if can_edit else "")
            ev = st.dataframe(view, hide_index=True, width="stretch", height=min(520, 42 + 35 * len(view)),
                              on_select="rerun" if can_edit else "ignore", selection_mode="single-row",
                              key=f"med_table_{st.session_state.get('med_table_nonce', 0)}")
            if can_edit and ev and ev.selection and ev.selection.rows:
                st.session_state.med_edit_id = int(meds.iloc[ev.selection.rows[0]]["id"])
                st.session_state.med_table_nonce = st.session_state.get("med_table_nonce", 0) + 1
                st.session_state.med_show_form = False
                st.rerun()
            ui.icon_download(t("download_csv"), "file-spreadsheet", "med_csv", view.to_csv(index=False).encode("utf-8-sig"),
                             f"stock_{today()}.csv", "text/csv")
        if can_edit and st.session_state.get("med_edit_id"):
            m = repo.medicine(st.session_state.med_edit_id)
            if m:
                ui.section(f"{t('edit')} · {m['name']} ({m['sku']})", "pencil")
                data = medicine_form("med_edit", m)
                if data:
                    try:
                        repo.save_medicine(data, med_id=m["id"], actor=user)
                        st.session_state.pop("med_edit_id", None)
                        st.toast(t("saved"))
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                if st.button(t("close"), key="med_edit_close"):
                    st.session_state.pop("med_edit_id", None)
                    st.rerun()
    with tabs[1]:
        ui.notice(t("inventory_notice"), "info", "shield")
        if alerts.empty:
            ui.empty_state("No warnings", "All stock levels and expiry dates are within limits.", "circle-check")
        else:
            rows = []
            for r in alerts.itertuples():
                badges = " ".join(ui.badge(a.strip(), ui.STATUS_TONES.get(a.strip(), "neutral")) for a in r.alert.split(","))
                sub = f"{r.sku} · {t('quantity')}: {int(r.quantity)} (reorder {int(r.reorder_level)})" + (f" · {t('expiry')}: {fmt_date(r.expiry_date)}" if r.expiry_date else "")
                rows.append(ui.row_item(r.name, sub, right_html=badges))
            ui.rows(rows)
    with tabs[2]:
        if all_meds.empty:
            ui.empty_state(t("no_data"), "", "package")
        else:
            opts = {int(r.id): f"{r.name} ({r.sku}) · {int(r.quantity)} in stock" for r in all_meds.itertuples()}
            mid = st.selectbox(t("medicine"), list(opts.keys()), format_func=lambda i: opts[i], key="adj_med")
            if can_edit:
                with st.form("adj_form", border=True):
                    c1, c2, c3 = st.columns([1, 1.3, 1.6])
                    direction = c1.radio("Type", ["Add", "Remove"], horizontal=True)
                    qty = c2.number_input(t("quantity"), min_value=1, value=1, step=1)
                    reason = c3.selectbox("Reason", ["Purchase", "Dispensed", "Return to supplier", "Expired / disposed", "Damaged", "Count correction", "Other"])
                    ref = st.text_input(f"Reference ({t('optional')})", max_chars=100, placeholder="Invoice / batch / patient ID")
                    if st.form_submit_button(t("save"), type="primary"):
                        try:
                            new_qty = repo.adjust_stock(mid, qty if direction == "Add" else -qty, reason, ref, actor=user)
                            st.toast(f"{t('saved')} · {new_qty} in stock")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
            mv = repo.stock_movements(mid)
            ui.section("Movements", "history", len(mv))
            if mv.empty:
                ui.empty_state(t("no_data"), "", "history")
            else:
                mv["created_at"] = mv["created_at"].map(fmt_datetime)
                mv.columns = [t("date"), "Change", "Reason", "Reference", "By"]
                ui.dataframe(mv, height=min(400, 42 + 35 * len(mv)))
