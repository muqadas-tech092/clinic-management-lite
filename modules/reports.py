"""Reports & analytics: operational, financial and stock reports with charts, CSV and PDF export."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from core import auth, db, repo, ui
from core.i18n import t
from core.utils import DATE_FMT, fmt_date, money, month_bounds, today, week_bounds


def _export(df: pd.DataFrame, title: str, subtitle: str, key: str, settings: dict, summary=None, numeric=()) -> None:
    from pdf import report
    c1, c2, _ = st.columns([1, 1, 3])
    with c1:
        ui.icon_download(t("download_csv"), "file-spreadsheet", f"{key}_csv", df.to_csv(index=False).encode("utf-8-sig"),
                         f"{key}_{today()}.csv", "text/csv", use_container_width=True)
    with c2:
        ui.icon_download(t("download_pdf"), "file-down", f"{key}_pdf", report.build(title, subtitle, df, settings, summary, numeric),
                         f"{key}_{today()}.pdf", "application/pdf", use_container_width=True)


def _period_frame(df: pd.DataFrame, date_col: str, granularity: str) -> pd.DataFrame:
    d = df.copy()
    d["_dt"] = pd.to_datetime(d[date_col])
    if granularity == "Daily":
        d["Period"] = d["_dt"].dt.strftime("%d %b")
        d["_key"] = d["_dt"].dt.strftime(DATE_FMT)
    elif granularity == "Weekly":
        d["_key"] = d["_dt"].dt.to_period("W-SUN").dt.start_time.dt.strftime(DATE_FMT)
        d["Period"] = "Wk " + pd.to_datetime(d["_key"]).dt.strftime("%d %b")
    else:
        d["_key"] = d["_dt"].dt.strftime("%Y-%m")
        d["Period"] = d["_dt"].dt.strftime("%b %Y")
    return d


def render(user: dict) -> None:
    settings = db.get_settings()
    sym = settings.get("currency_symbol", "Rs.")
    doctor_lock = user.get("doctor_id") if auth.is_doctor(user) else None
    ui.page_header(t("reports"), f"{settings['clinic_name']}", "bar-chart")

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1.3, 1, 1, 1.4, 1])
        preset = c1.selectbox(t("range"), ["This month", "Last 7 days", "Last 30 days", "This week", "Last month", "Custom"], key="rep_preset")
        tdy = today()
        if preset == "This month":
            s0, e0 = month_bounds(tdy)
        elif preset == "Last 7 days":
            s0, e0 = tdy - timedelta(days=6), tdy
        elif preset == "Last 30 days":
            s0, e0 = tdy - timedelta(days=29), tdy
        elif preset == "This week":
            s0, e0 = week_bounds(tdy)
        elif preset == "Last month":
            s0, e0 = month_bounds(month_bounds(tdy)[0] - timedelta(days=1))
        else:
            s0, e0 = tdy - timedelta(days=29), tdy
        start = c2.date_input(t("from"), value=s0, key=f"rep_from_{preset}", format="DD/MM/YYYY", disabled=preset != "Custom")
        end = c3.date_input(t("to"), value=e0, key=f"rep_to_{preset}", format="DD/MM/YYYY", disabled=preset != "Custom")
        if preset != "Custom":
            start, end = s0, e0
        opts = {0: t("all"), **repo.doctor_options()}
        did = doctor_lock or c4.selectbox(t("doctor"), list(opts.keys()), format_func=lambda i: opts[i], key="rep_doc") or None
        gran = c5.selectbox(t("group_by"), ["Daily", "Weekly", "Monthly"], key="rep_gran")
    if start > end:
        st.error("Start date must be before end date.")
        return
    sub = f"{fmt_date(start)} - {fmt_date(end)}" + (f" · {opts.get(did, '')}" if did else "")

    tab_names = [t("report_appointments"), t("report_registrations"), t("report_doctors")]
    if auth.can_view(user, "billing"):
        tab_names += [t("report_collection"), t("report_outstanding")]
    if auth.can_view(user, "inventory"):
        tab_names.append(t("report_stock"))
    tabs = st.tabs(tab_names)
    ti = 0

    # ---------------- appointments
    with tabs[ti]:
        appts = repo.appointments_between(start, end, did)
        if appts.empty:
            ui.empty_state(t("no_data"), "", "calendar")
        else:
            total = len(appts)
            comp = int((appts["status"] == "Completed").sum())
            canc = int(appts["status"].isin(["Cancelled", "No Show"]).sum())
            ui.kpi_row([
                (t("appointments"), total, "calendar", "primary", sub),
                (t("completed_visits"), comp, "circle-check", "success", f"{comp / total:.0%}" if total else ""),
                ("Cancelled / No show", canc, "circle-x", "danger", f"{canc / total:.0%}" if total else ""),
                ("Walk-ins", int((appts["visit_type"] == "Walk-in").sum()), "ticket", "neutral"),
            ], min_width=160)
            pf = _period_frame(appts, "appt_date", gran)
            grp = pf.groupby(["_key", "Period"]).agg(
                Appointments=("id", "count"), Completed=("status", lambda s: int((s == "Completed").sum())),
                Cancelled=("status", lambda s: int(s.isin(["Cancelled", "No Show"]).sum()))).reset_index().sort_values("_key")
            fig = ui.grouped_bar(grp, "Period", ["Completed", "Cancelled"], height=300)
            ui.plot(fig)
            by_type = appts.groupby("visit_type").size().reset_index(name="count").sort_values("count", ascending=False)
            c1, c2 = st.columns([1, 1.4])
            with c1:
                ui.section(t("visit_type"), "list")
                ui.plot(ui.hbar_chart(by_type["visit_type"], by_type["count"], height=220))
            with c2:
                ui.section(t("status"), "list")
                by_status = appts.groupby("status").size().reset_index(name="count")
                ui.plot(ui.hbar_chart(by_status["status"], by_status["count"], height=220, color=ui.CHART_COLORS[4]))
            out = grp[["Period", "Appointments", "Completed", "Cancelled"]]
            ui.dataframe(out, height=min(360, 42 + 35 * len(out)))
            _export(out, "Appointments report", sub, "appointments", settings,
                    [("Appointments", total), ("Completed", comp), ("Cancelled / No show", canc)], ("Appointments", "Completed", "Cancelled"))
    ti += 1

    # ---------------- registrations
    with tabs[ti]:
        regs = db.df("SELECT id, patient_code, full_name, gender, dob, phone, created_at FROM patients WHERE substr(created_at,1,10) BETWEEN ? AND ? ORDER BY created_at",
                     (start.strftime(DATE_FMT), end.strftime(DATE_FMT)))
        if regs.empty:
            ui.empty_state(t("no_data"), "", "user-plus")
        else:
            by_g = regs.groupby("gender").size()
            ui.kpi_row([(t("recent_registrations"), len(regs), "user-plus", "primary", sub)] +
                       [(t(g.lower()), int(n), "user", "neutral") for g, n in by_g.items()], min_width=150)
            pf = _period_frame(regs, "created_at", gran)
            grp = pf.groupby(["_key", "Period"]).size().reset_index(name="Registrations").sort_values("_key")
            ui.plot(ui.bar_chart(grp["Period"], grp["Registrations"], height=280))
            out = pd.DataFrame({t("patient_id"): regs["patient_code"], t("name"): regs["full_name"], t("gender"): regs["gender"],
                                t("phone"): regs["phone"], "Registered": regs["created_at"].map(fmt_date)})
            ui.dataframe(out, height=min(360, 42 + 35 * len(out)))
            _export(out, "Patient registrations", sub, "registrations", settings, [("Registrations", len(regs))])
    ti += 1

    # ---------------- doctor-wise
    with tabs[ti]:
        dw = db.df(
            "SELECT d.name AS Doctor, COUNT(a.id) AS Appointments, SUM(a.status='Completed') AS Completed, "
            "SUM(a.status IN ('Cancelled','No Show')) AS Cancelled, "
            "(SELECT COUNT(*) FROM consultations c WHERE c.doctor_id = d.id AND c.visit_date BETWEEN ? AND ?) AS Consultations, "
            "(SELECT COALESCE(SUM(p.amount),0) FROM payments p JOIN invoices i ON i.id = p.invoice_id WHERE i.doctor_id = d.id AND substr(p.paid_at,1,10) BETWEEN ? AND ?) AS Collection "
            "FROM doctors d LEFT JOIN appointments a ON a.doctor_id = d.id AND a.appt_date BETWEEN ? AND ? "
            + ("WHERE d.id = ? " if did else "") + "GROUP BY d.id ORDER BY Appointments DESC",
            [start.strftime(DATE_FMT), end.strftime(DATE_FMT)] * 3 + ([did] if did else []))
        if dw.empty:
            ui.empty_state(t("no_data"), "", "stethoscope")
        else:
            c1, c2 = st.columns(2)
            with c1:
                ui.section("Visits by doctor", "stethoscope")
                ui.plot(ui.hbar_chart(dw["Doctor"], dw["Completed"], height=240))
            with c2:
                if auth.can_view(user, "billing"):
                    ui.section("Collection by doctor", "wallet")
                    ui.plot(ui.hbar_chart(dw["Doctor"], dw["Collection"], height=240, color=ui.CHART_COLORS[1], hover_fmt=f"{sym} %{{x:,.0f}}"))
            out = dw.copy()
            if not auth.can_view(user, "billing"):
                out = out.drop(columns=["Collection"])
            else:
                out["Collection"] = out["Collection"].map(lambda v: money(v, sym))
            ui.dataframe(out, height=min(300, 42 + 35 * len(out)))
            _export(out, "Doctor-wise report", sub, "doctor_wise", settings, numeric=("Appointments", "Completed", "Cancelled", "Consultations", "Collection"))
    ti += 1

    # ---------------- collection & revenue
    if auth.can_view(user, "billing"):
        with tabs[ti]:
            daily = repo.daily_collection(start, end, did)
            by_method = repo.collection_by_method(start, end, did)
            inv = repo.invoices_list(start, end, None, "", did)
            billed = float(inv["total"].sum()) if not inv.empty else 0.0
            disc = float(inv["discount_amount"].sum()) if not inv.empty else 0.0
            collected = float(daily["amount"].sum())
            ui.kpi_row([
                (t("report_collection"), money(collected, sym), "wallet", "primary", sub),
                ("Billed", money(billed, sym), "receipt", "neutral", f"{len(inv)} invoice(s)"),
                (t("discount"), money(disc, sym), "percent", "warning"),
                ("Avg / day", money(collected / max(len(daily), 1), sym), "trending-up", "neutral"),
            ], min_width=160)
            pf = _period_frame(daily, "day", gran)
            grp = pf.groupby(["_key", "Period"])["amount"].sum().reset_index().sort_values("_key")
            ui.plot(ui.bar_chart(grp["Period"], grp["amount"], height=300, hover_fmt=f"{sym} %{{y:,.0f}}"))
            c1, c2 = st.columns([1, 1.4])
            with c1:
                ui.section(t("payment_method"), "credit-card")
                if by_method.empty:
                    ui.empty_state(t("no_data"), "", "credit-card")
                else:
                    ui.plot(ui.hbar_chart(by_method["method"], by_method["amount"], height=220, hover_fmt=f"{sym} %{{x:,.0f}}"))
            with c2:
                ui.section("Monthly revenue", "trending-up")
                monthly = db.df("SELECT substr(p.paid_at,1,7) AS month, SUM(p.amount) AS amount FROM payments p JOIN invoices i ON i.id = p.invoice_id "
                                "WHERE substr(p.paid_at,1,10) >= ? " + ("AND i.doctor_id = ? " if did else "") + "GROUP BY month ORDER BY month",
                                [(today() - timedelta(days=365)).strftime(DATE_FMT)] + ([did] if did else []))
                if monthly.empty:
                    ui.empty_state(t("no_data"), "", "trending-up")
                else:
                    monthly["label"] = pd.to_datetime(monthly["month"]).dt.strftime("%b %Y")
                    ui.plot(ui.line_chart(monthly["label"], monthly["amount"], height=220, hover_fmt=f"{sym} %{{y:,.0f}}"))
            out = grp.rename(columns={"amount": "Collection"})[["Period", "Collection"]]
            out["Collection"] = out["Collection"].round(0)
            ui.dataframe(out.assign(Collection=out["Collection"].map(lambda v: money(v, sym))), height=min(360, 42 + 35 * len(out)))
            _export(out.assign(Collection=out["Collection"].map(lambda v: money(v, sym))), "Collection report", sub, "collection", settings,
                    [("Collected", money(collected, sym)), ("Billed", money(billed, sym)), ("Discounts", money(disc, sym))], ("Collection",))
        ti += 1
        with tabs[ti]:
            out = repo.outstanding_invoices()
            if did and not out.empty:
                ids = set(db.df("SELECT invoice_no FROM invoices WHERE doctor_id = ?", (did,))["invoice_no"])
                out = out[out["invoice_no"].isin(ids)]
            if out.empty:
                ui.empty_state("No outstanding payments", "", "circle-check")
            else:
                aging = out.copy()
                aging["days"] = (pd.Timestamp(today()) - pd.to_datetime(aging["invoice_date"])).dt.days
                bins = pd.cut(aging["days"], [-1, 7, 30, 90, 10000], labels=["0-7 days", "8-30 days", "31-90 days", "90+ days"])
                age_sum = aging.groupby(bins, observed=False)["outstanding"].sum().reset_index()
                ui.kpi_row([(t("outstanding"), money(out["outstanding"].sum(), sym), "credit-card", "danger", f"{len(out)} invoice(s)")] +
                           [(str(r.days), money(r.outstanding, sym), "clock", "neutral") for r in age_sum.itertuples()], min_width=150)
                v = pd.DataFrame({t("invoice"): out["invoice_no"], t("date"): out["invoice_date"].map(fmt_date), t("patient"): out["patient"],
                                  t("patient_id"): out["patient_code"], t("phone"): out["phone"], t("total"): out["total"].map(lambda x: money(x, sym)),
                                  t("received"): out["paid"].map(lambda x: money(x, sym)), t("outstanding"): out["outstanding"].map(lambda x: money(x, sym)),
                                  "Days": aging["days"].values})
                ui.dataframe(v, height=min(420, 42 + 35 * len(v)))
                _export(v, "Outstanding payments", "As of " + fmt_date(today()), "outstanding", settings,
                        [("Outstanding", money(out["outstanding"].sum(), sym)), ("Invoices", len(out))], (t("total"), t("received"), t("outstanding"), "Days"))
        ti += 1

    # ---------------- stock
    if auth.can_view(user, "inventory"):
        with tabs[ti]:
            meds = repo.medicines()
            alerts = repo.stock_alerts()
            if meds.empty:
                ui.empty_state(t("no_data"), "", "package")
            else:
                flags = alerts.set_index("id")["alert"] if not alerts.empty else pd.Series(dtype=str)
                by_cat = meds.groupby("category")["quantity"].sum().reset_index().sort_values("quantity", ascending=False)
                c1, c2 = st.columns([1, 1.4])
                with c1:
                    ui.section("Units by category", "package")
                    ui.plot(ui.hbar_chart(by_cat["category"], by_cat["quantity"], height=240))
                with c2:
                    ui.section("Warnings", "triangle-alert")
                    if alerts.empty:
                        ui.empty_state("No warnings", "", "circle-check")
                    else:
                        ui.rows([ui.row_item(r.name, f"{r.sku} · {int(r.quantity)} units", right_html=" ".join(
                            ui.badge(a.strip(), ui.STATUS_TONES.get(a.strip(), "neutral")) for a in r.alert.split(","))) for r in alerts.head(8).itertuples()])
                v = pd.DataFrame({"SKU": meds["sku"], t("name"): meds["name"], t("category"): meds["category"], t("quantity"): meds["quantity"].astype(int),
                                  "Reorder": meds["reorder_level"].astype(int), t("expiry"): meds["expiry_date"].map(lambda x: fmt_date(x) if x else "-"),
                                  "Value": (meds["quantity"] * meds["purchase_price"]).map(lambda x: money(x, sym)), "Alert": meds["id"].map(lambda i: flags.get(i, ""))})
                ui.dataframe(v, height=min(420, 42 + 35 * len(v)))
                _export(v, "Stock report", "As of " + fmt_date(today()), "stock", settings,
                        [("Items", len(meds)), ("Units", int(meds["quantity"].sum())), ("Warnings", len(alerts))], (t("quantity"), "Reorder", "Value"))
