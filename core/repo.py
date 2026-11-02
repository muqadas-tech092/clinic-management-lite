"""Domain layer: all business rules and queries, independent of Streamlit so they can be unit-tested."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

import pandas as pd

from core import audit, config, db
from core.utils import (DATE_FMT, TIME_FMT, now, now_str, parse_time, time_slots, to_date, today, today_str,
                        normalize_phone, clean_text)


class SlotTakenError(ValueError):
    pass


def _d(value) -> str:
    d = to_date(value)
    return d.strftime(DATE_FMT) if d else ""


# ===================================================================== doctors
def doctors(active_only: bool = True) -> list[dict]:
    sql = "SELECT * FROM doctors"
    if active_only:
        sql += " WHERE is_active = 1"
    return db.query(sql + " ORDER BY name")


def doctor(doctor_id) -> dict | None:
    return db.query_one("SELECT * FROM doctors WHERE id = ?", (doctor_id,))


def doctor_options(active_only: bool = True) -> dict[int, str]:
    return {d["id"]: d["name"] for d in doctors(active_only)}


def save_doctor(data: dict, doctor_id: int | None = None, actor=None) -> int:
    name = clean_text(data.get("name"), 100)
    if len(name) < 2:
        raise ValueError("Doctor name is required")
    fee = float(data.get("consultation_fee") or 0)
    if fee < 0:
        raise ValueError("Fee cannot be negative")
    fields = dict(
        name=name, specialization=clean_text(data.get("specialization"), 100),
        qualification=clean_text(data.get("qualification"), 150),
        registration_no=clean_text(data.get("registration_no"), 60), phone=clean_text(data.get("phone"), 30),
        email=clean_text(data.get("email"), 100), consultation_fee=fee,
        photo_path=data.get("photo_path") or "", is_active=1 if data.get("is_active", True) else 0,
        updated_at=now_str(),
    )
    with db.transaction() as conn:
        if doctor_id:
            sets = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(f"UPDATE doctors SET {sets} WHERE id = ?", (*fields.values(), doctor_id))
            audit.log("update", "doctor", doctor_id, {"name": name}, user=actor, conn=conn)
            return doctor_id
        fields["created_at"] = now_str()
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        cur = conn.execute(f"INSERT INTO doctors({cols}) VALUES ({marks})", tuple(fields.values()))
        new_id = cur.lastrowid
        for wd in range(7):
            conn.execute(
                "INSERT INTO doctor_schedule(doctor_id, weekday, is_working, start_time, end_time, break_start, break_end) "
                "VALUES (?,?,?,?,?,?,?)",
                (new_id, wd, 0 if wd == 6 else 1, "09:00", "17:00", "13:00", "14:00"),
            )
        audit.log("create", "doctor", new_id, {"name": name}, user=actor, conn=conn)
        return new_id


def doctor_schedule(doctor_id) -> list[dict]:
    rows = db.query("SELECT * FROM doctor_schedule WHERE doctor_id = ? ORDER BY weekday", (doctor_id,))
    if len(rows) < 7:
        existing = {r["weekday"] for r in rows}
        with db.transaction() as conn:
            for wd in range(7):
                if wd not in existing:
                    conn.execute(
                        "INSERT INTO doctor_schedule(doctor_id, weekday, is_working, start_time, end_time, break_start, break_end) "
                        "VALUES (?,?,?,?,?,?,?)", (doctor_id, wd, 0 if wd == 6 else 1, "09:00", "17:00", "", ""))
        rows = db.query("SELECT * FROM doctor_schedule WHERE doctor_id = ? ORDER BY weekday", (doctor_id,))
    return rows


def save_schedule(doctor_id, rows: list[dict], actor=None) -> None:
    with db.transaction() as conn:
        for r in rows:
            if r.get("is_working"):
                s, e = parse_time(r["start_time"]), parse_time(r["end_time"])
                if not s or not e or s >= e:
                    raise ValueError(f"Invalid working hours for weekday {r['weekday']}")
                bs, be = parse_time(r.get("break_start") or ""), parse_time(r.get("break_end") or "")
                if (bs and not be) or (be and not bs) or (bs and be and bs >= be):
                    raise ValueError(f"Invalid break for weekday {r['weekday']}")
            conn.execute(
                "UPDATE doctor_schedule SET is_working=?, start_time=?, end_time=?, break_start=?, break_end=? "
                "WHERE doctor_id=? AND weekday=?",
                (1 if r.get("is_working") else 0, r["start_time"], r["end_time"], r.get("break_start") or "",
                 r.get("break_end") or "", doctor_id, r["weekday"]),
            )
        audit.log("update", "doctor_schedule", doctor_id, user=actor, conn=conn)


def holidays(doctor_id, from_date=None) -> list[dict]:
    sql = "SELECT * FROM doctor_holidays WHERE doctor_id = ?"
    params = [doctor_id]
    if from_date:
        sql += " AND holiday_date >= ?"
        params.append(_d(from_date))
    return db.query(sql + " ORDER BY holiday_date", params)


def add_holiday(doctor_id, holiday_date, reason: str = "", actor=None) -> None:
    with db.transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO doctor_holidays(doctor_id, holiday_date, reason) VALUES (?,?,?)",
                     (doctor_id, _d(holiday_date), clean_text(reason, 120)))
        audit.log("create", "holiday", doctor_id, {"date": _d(holiday_date)}, user=actor, conn=conn)


def remove_holiday(holiday_id, actor=None) -> None:
    with db.transaction() as conn:
        conn.execute("DELETE FROM doctor_holidays WHERE id = ?", (holiday_id,))
        audit.log("delete", "holiday", holiday_id, user=actor, conn=conn)


def is_holiday(doctor_id, d) -> dict | None:
    return db.query_one("SELECT * FROM doctor_holidays WHERE doctor_id = ? AND holiday_date = ?", (doctor_id, _d(d)))


def doctor_day(doctor_id, d) -> dict | None:
    """Working-hours row for the doctor on that date's weekday."""
    wd = to_date(d).weekday()
    rows = [r for r in doctor_schedule(doctor_id) if r["weekday"] == wd]
    return rows[0] if rows else None


def doctor_status(doctor_id, d) -> tuple[str, str]:
    """Returns (status_key, hours_text) for the dashboard availability card."""
    hol = is_holiday(doctor_id, d)
    if hol:
        return "on_leave", hol.get("reason") or ""
    day = doctor_day(doctor_id, d)
    if not day or not day["is_working"]:
        return "off_today", ""
    hours = f"{day['start_time']} - {day['end_time']}"
    busy = db.query_one("SELECT id FROM tokens WHERE doctor_id=? AND token_date=? AND status='In Consultation'",
                        (doctor_id, _d(d)))
    if busy:
        return "in_consultation", hours
    return "available", hours


# ==================================================================== patients
def patient(patient_id) -> dict | None:
    return db.query_one("SELECT * FROM patients WHERE id = ?", (patient_id,))


def patient_by_code(code: str) -> dict | None:
    return db.query_one("SELECT * FROM patients WHERE patient_code = ?", (code.strip().upper(),))


def search_patients(q: str = "", limit: int = 50, active_only: bool = True) -> pd.DataFrame:
    sql = ("SELECT *, (SELECT MAX(visit_date) FROM consultations c WHERE c.patient_id = patients.id) AS last_visit, "
           "(SELECT COUNT(*) FROM appointments a WHERE a.patient_id = patients.id AND a.status != 'Cancelled') AS visits "
           "FROM patients WHERE 1=1")
    params: list = []
    if active_only:
        sql += " AND is_active = 1"
    q = (q or "").strip()
    if q:
        sql += " AND (full_name LIKE ? OR phone LIKE ? OR patient_code LIKE ?)"
        like = f"%{q}%"
        params += [like, f"%{normalize_phone(q) or q}%", f"%{q.upper()}%"]
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return db.df(sql, params)


def patient_options(q: str = "", limit: int = 300) -> dict[int, str]:
    d = search_patients(q, limit)
    return {int(r.id): f"{r.full_name} ({r.patient_code}, {r.phone})" for r in d.itertuples()}


def find_duplicates(full_name: str, phone: str, dob=None, exclude_id=None) -> list[dict]:
    phone_n = normalize_phone(phone)
    sql = ("SELECT id, patient_code, full_name, phone, dob FROM patients WHERE is_active = 1 AND "
           "(phone = ? OR (lower(full_name) = lower(?) AND (dob = ? OR ? = '')))")
    params = [phone_n, full_name.strip(), _d(dob), _d(dob)]
    if exclude_id:
        sql += " AND id != ?"
        params.append(exclude_id)
    return db.query(sql, params)


def _patient_fields(data: dict) -> dict:
    name = clean_text(data.get("full_name"), 100)
    phone = normalize_phone(data.get("phone", ""))
    if len(name) < 2:
        raise ValueError("Patient name is required")
    if not phone or len(phone) < 10:
        raise ValueError("A valid phone number is required (e.g. 03001234567)")
    if data.get("gender") not in config.GENDERS:
        raise ValueError("Gender is required")
    dob = _d(data.get("dob")) or None
    if dob and to_date(dob) > today():
        raise ValueError("Date of birth cannot be in the future")
    return dict(
        full_name=name, dob=dob, gender=data["gender"], phone=phone,
        address=clean_text(data.get("address"), 300), blood_group=data.get("blood_group") or "",
        emergency_contact=clean_text(data.get("emergency_contact"), 120),
        allergies=clean_text(data.get("allergies"), 1000), medical_history=clean_text(data.get("medical_history"), 4000),
    )


def create_patient(data: dict, actor=None) -> dict:
    fields = _patient_fields(data)
    with db.transaction() as conn:
        n = db.next_seq(conn, "patient")
        code = f"P-{n:05d}"
        fields.update(patient_code=code, created_at=now_str(), updated_at=now_str())
        cols = ", ".join(fields)
        cur = conn.execute(f"INSERT INTO patients({cols}) VALUES ({', '.join('?' for _ in fields)})",
                           tuple(fields.values()))
        audit.log("create", "patient", code, {"name": fields["full_name"]}, user=actor, conn=conn)
        return {"id": cur.lastrowid, "patient_code": code, **fields}


def update_patient(patient_id, data: dict, actor=None) -> None:
    fields = _patient_fields(data)
    fields["updated_at"] = now_str()
    with db.transaction() as conn:
        sets = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE patients SET {sets} WHERE id = ?", (*fields.values(), patient_id))
        audit.log("update", "patient", patient_id, {"name": fields["full_name"]}, user=actor, conn=conn)


def deactivate_patient(patient_id, actor=None) -> None:
    with db.transaction() as conn:
        conn.execute("UPDATE patients SET is_active = 0, updated_at = ? WHERE id = ?", (now_str(), patient_id))
        audit.log("deactivate", "patient", patient_id, user=actor, conn=conn)


def recent_patients(limit: int = 6) -> pd.DataFrame:
    return db.df("SELECT * FROM patients WHERE is_active = 1 ORDER BY created_at DESC LIMIT ?", (limit,))


def patient_history(patient_id) -> dict[str, pd.DataFrame]:
    return {
        "appointments": db.df(
            "SELECT a.id, a.appt_date, a.appt_time, d.name AS doctor, a.visit_type, a.status, a.notes "
            "FROM appointments a JOIN doctors d ON d.id = a.doctor_id WHERE a.patient_id = ? "
            "ORDER BY a.appt_date DESC, a.appt_time DESC", (patient_id,)),
        "consultations": db.df(
            "SELECT c.id, c.visit_date, d.name AS doctor, c.symptoms, c.diagnosis, c.follow_up_date "
            "FROM consultations c JOIN doctors d ON d.id = c.doctor_id WHERE c.patient_id = ? ORDER BY c.visit_date DESC, c.id DESC",
            (patient_id,)),
        "prescriptions": db.df(
            "SELECT p.id, p.rx_number, p.created_at, d.name AS doctor, p.status, "
            "(SELECT COUNT(*) FROM prescription_items i WHERE i.prescription_id = p.id) AS items "
            "FROM prescriptions p JOIN doctors d ON d.id = p.doctor_id WHERE p.patient_id = ? ORDER BY p.id DESC",
            (patient_id,)),
        "invoices": db.df(
            "SELECT i.id, i.invoice_no, i.invoice_date, i.total, "
            "COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id = i.id), 0) AS paid, i.status "
            "FROM invoices i WHERE i.patient_id = ? ORDER BY i.id DESC", (patient_id,)),
    }


# ================================================================ appointments
def booked_times(doctor_id, d, exclude_appt_id=None) -> set[str]:
    sql = "SELECT appt_time FROM appointments WHERE doctor_id=? AND appt_date=? AND status NOT IN ('Cancelled','No Show')"
    params = [doctor_id, _d(d)]
    if exclude_appt_id:
        sql += " AND id != ?"
        params.append(exclude_appt_id)
    return {r["appt_time"] for r in db.query(sql, params)}


def available_slots(doctor_id, d, exclude_appt_id=None, include_past: bool = False) -> list[str]:
    if is_holiday(doctor_id, d):
        return []
    day = doctor_day(doctor_id, d)
    if not day or not day["is_working"]:
        return []
    step = int(db.get_setting("appointment_duration", "15") or 15)
    slots = time_slots(day["start_time"], day["end_time"], step, day["break_start"], day["break_end"])
    taken = booked_times(doctor_id, d, exclude_appt_id)
    dd = to_date(d)
    cutoff = now().strftime(TIME_FMT) if (dd == today() and not include_past) else None
    out = []
    for s in slots:
        if s in taken:
            continue
        if cutoff and s < cutoff:
            continue
        out.append(s)
    return out


def appointment(appt_id) -> dict | None:
    return db.query_one(
        "SELECT a.*, p.full_name AS patient_name, p.patient_code, p.phone AS patient_phone, p.dob, p.gender, "
        "d.name AS doctor_name FROM appointments a JOIN patients p ON p.id = a.patient_id "
        "JOIN doctors d ON d.id = a.doctor_id WHERE a.id = ?", (appt_id,))


def create_appointment(patient_id, doctor_id, appt_date, appt_time, visit_type="New Visit", notes="",
                       actor=None, status="Scheduled", enforce_slots: bool = True) -> int:
    d = _d(appt_date)
    if not d:
        raise ValueError("Appointment date is required")
    if visit_type not in config.VISIT_TYPES:
        raise ValueError("Invalid visit type")
    if enforce_slots:
        if to_date(d) < today():
            raise ValueError("Cannot book an appointment in the past")
        if appt_time not in available_slots(doctor_id, d):
            raise SlotTakenError("That slot is not available")
    step = int(db.get_setting("appointment_duration", "15") or 15)
    uid = actor.get("id") if actor else None
    try:
        with db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO appointments(patient_id, doctor_id, appt_date, appt_time, duration_min, visit_type, status, "
                "notes, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (patient_id, doctor_id, d, appt_time, step, visit_type, status, clean_text(notes, 500), uid,
                 now_str(), now_str()))
            audit.log("create", "appointment", cur.lastrowid,
                      {"patient_id": patient_id, "doctor_id": doctor_id, "date": d, "time": appt_time},
                      user=actor, conn=conn)
            return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise SlotTakenError("That slot was just taken") from exc


def reschedule_appointment(appt_id, new_date, new_time, actor=None) -> None:
    a = appointment(appt_id)
    if not a:
        raise ValueError("Appointment not found")
    if a["status"] in ("Completed", "Cancelled", "In Consultation"):
        raise ValueError(f"Cannot reschedule a {a['status'].lower()} appointment")
    if new_time not in available_slots(a["doctor_id"], new_date, exclude_appt_id=appt_id):
        raise SlotTakenError("That slot is not available")
    try:
        with db.transaction() as conn:
            conn.execute("UPDATE appointments SET appt_date=?, appt_time=?, status='Scheduled', updated_at=? WHERE id=?",
                         (_d(new_date), new_time, now_str(), appt_id))
            conn.execute("UPDATE tokens SET status='Cancelled' WHERE appointment_id=? AND status='Waiting'", (appt_id,))
            audit.log("reschedule", "appointment", appt_id,
                      {"from": f"{a['appt_date']} {a['appt_time']}", "to": f"{_d(new_date)} {new_time}"},
                      user=actor, conn=conn)
    except sqlite3.IntegrityError as exc:
        raise SlotTakenError("That slot was just taken") from exc


def set_appointment_status(appt_id, status, actor=None, conn: sqlite3.Connection | None = None) -> None:
    if status not in config.APPOINTMENT_STATUSES:
        raise ValueError("Invalid status")

    def _run(c):
        c.execute("UPDATE appointments SET status=?, updated_at=? WHERE id=?", (status, now_str(), appt_id))
        if status in ("Cancelled", "No Show"):
            c.execute("UPDATE tokens SET status='Cancelled' WHERE appointment_id=? AND status IN ('Waiting')", (appt_id,))
        audit.log("status", "appointment", appt_id, {"status": status}, user=actor, conn=c)

    if conn is not None:
        _run(conn)
    else:
        with db.transaction() as c:
            _run(c)


def appointments_for_date(d, doctor_id=None, statuses: tuple | None = None) -> pd.DataFrame:
    sql = ("SELECT a.id, a.appt_time, a.appt_date, p.full_name AS patient, p.patient_code, p.phone, d.name AS doctor, "
           "a.doctor_id, a.patient_id, a.visit_type, a.status, a.notes, "
           "(SELECT token_no FROM tokens t WHERE t.appointment_id = a.id AND t.status != 'Cancelled' LIMIT 1) AS token_no "
           "FROM appointments a JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id "
           "WHERE a.appt_date = ?")
    params: list = [_d(d)]
    if doctor_id:
        sql += " AND a.doctor_id = ?"
        params.append(doctor_id)
    if statuses:
        sql += f" AND a.status IN ({','.join('?' for _ in statuses)})"
        params += list(statuses)
    return db.df(sql + " ORDER BY a.appt_time", params)


def appointments_between(start, end, doctor_id=None) -> pd.DataFrame:
    sql = ("SELECT a.id, a.appt_date, a.appt_time, p.full_name AS patient, p.patient_code, d.name AS doctor, a.doctor_id, "
           "a.patient_id, a.visit_type, a.status FROM appointments a JOIN patients p ON p.id = a.patient_id "
           "JOIN doctors d ON d.id = a.doctor_id WHERE a.appt_date BETWEEN ? AND ?")
    params: list = [_d(start), _d(end)]
    if doctor_id:
        sql += " AND a.doctor_id = ?"
        params.append(doctor_id)
    return db.df(sql + " ORDER BY a.appt_date, a.appt_time", params)


def upcoming_follow_ups(start, end, doctor_id=None) -> pd.DataFrame:
    sql = ("SELECT c.id, c.follow_up_date, p.full_name AS patient, p.patient_code, p.phone, p.id AS patient_id, "
           "d.name AS doctor, c.doctor_id, c.diagnosis, "
           "(SELECT COUNT(*) FROM appointments a WHERE a.patient_id = c.patient_id AND a.appt_date = c.follow_up_date "
           " AND a.status NOT IN ('Cancelled')) AS booked "
           "FROM consultations c JOIN patients p ON p.id = c.patient_id JOIN doctors d ON d.id = c.doctor_id "
           "WHERE c.follow_up_date IS NOT NULL AND c.follow_up_date BETWEEN ? AND ?")
    params: list = [_d(start), _d(end)]
    if doctor_id:
        sql += " AND c.doctor_id = ?"
        params.append(doctor_id)
    return db.df(sql + " ORDER BY c.follow_up_date", params)


# ====================================================================== tokens
def token(token_id) -> dict | None:
    return db.query_one(
        "SELECT t.*, p.full_name AS patient_name, p.patient_code, p.phone, d.name AS doctor_name, "
        "d.specialization, a.appt_time, a.visit_type FROM tokens t JOIN patients p ON p.id = t.patient_id "
        "JOIN doctors d ON d.id = t.doctor_id LEFT JOIN appointments a ON a.id = t.appointment_id WHERE t.id = ?",
        (token_id,))


def _issue_token(conn, patient_id, doctor_id, appointment_id, d) -> int:
    existing = conn.execute(
        "SELECT id FROM tokens WHERE appointment_id = ? AND status != 'Cancelled'", (appointment_id,)).fetchone() \
        if appointment_id else None
    if existing:
        return existing["id"]
    n = conn.execute("SELECT COALESCE(MAX(token_no), 0) + 1 FROM tokens WHERE token_date=? AND doctor_id=?",
                     (d, doctor_id)).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO tokens(token_no, token_date, doctor_id, patient_id, appointment_id, status, created_at) "
        "VALUES (?,?,?,?,?,'Waiting',?)", (n, d, doctor_id, patient_id, appointment_id, now_str()))
    return cur.lastrowid


def mark_arrived(appt_id, actor=None) -> int:
    a = appointment(appt_id)
    if not a:
        raise ValueError("Appointment not found")
    if a["status"] in ("Cancelled", "Completed"):
        raise ValueError(f"Appointment is {a['status'].lower()}")
    with db.transaction() as conn:
        tid = _issue_token(conn, a["patient_id"], a["doctor_id"], appt_id, a["appt_date"])
        conn.execute("UPDATE appointments SET status='Arrived', updated_at=? WHERE id=? AND status='Scheduled'",
                     (now_str(), appt_id))
        audit.log("arrived", "appointment", appt_id, {"token_id": tid}, user=actor, conn=conn)
        return tid


def register_walk_in(patient_id, doctor_id, notes: str = "", actor=None) -> tuple[int, int]:
    """Create a walk-in appointment for now (or next free slot) and issue a token. Returns (appt_id, token_id)."""
    d = today_str()
    free = available_slots(doctor_id, d)
    t = free[0] if free else now().strftime(TIME_FMT)
    uid = actor.get("id") if actor else None
    step = int(db.get_setting("appointment_duration", "15") or 15)
    for attempt in range(60):
        try:
            with db.transaction() as conn:
                cur = conn.execute(
                    "INSERT INTO appointments(patient_id, doctor_id, appt_date, appt_time, duration_min, visit_type, status, "
                    "notes, created_by, created_at, updated_at) VALUES (?,?,?,?,?,'Walk-in','Arrived',?,?,?,?)",
                    (patient_id, doctor_id, d, t, step, clean_text(notes, 500), uid, now_str(), now_str()))
                appt_id = cur.lastrowid
                tid = _issue_token(conn, patient_id, doctor_id, appt_id, d)
                audit.log("walk_in", "appointment", appt_id, {"token_id": tid}, user=actor, conn=conn)
                return appt_id, tid
        except sqlite3.IntegrityError:
            base = datetime.strptime(t, TIME_FMT) + timedelta(minutes=1)
            t = base.strftime(TIME_FMT)
    raise SlotTakenError("Could not find a free time for the walk-in")


def queue_for_date(d, doctor_id=None, statuses: tuple | None = None) -> pd.DataFrame:
    sql = ("SELECT t.id, t.token_no, t.status, t.created_at, t.started_at, t.completed_at, t.doctor_id, t.patient_id, "
           "t.appointment_id, p.full_name AS patient, p.patient_code, p.phone, d.name AS doctor, a.appt_time, a.visit_type "
           "FROM tokens t JOIN patients p ON p.id = t.patient_id JOIN doctors d ON d.id = t.doctor_id "
           "LEFT JOIN appointments a ON a.id = t.appointment_id WHERE t.token_date = ?")
    params: list = [_d(d)]
    if doctor_id:
        sql += " AND t.doctor_id = ?"
        params.append(doctor_id)
    if statuses:
        sql += f" AND t.status IN ({','.join('?' for _ in statuses)})"
        params += list(statuses)
    return db.df(sql + " ORDER BY CASE t.status WHEN 'In Consultation' THEN 0 WHEN 'Waiting' THEN 1 WHEN 'Completed' THEN 2 ELSE 3 END, t.token_no", params)


def token_action(token_id, action: str, actor=None, conn: sqlite3.Connection | None = None) -> None:
    tk = token(token_id)
    if not tk:
        raise ValueError("Token not found")
    transitions = {
        "start": ("Waiting", "In Consultation", "started_at", "In Consultation"),
        "complete": ("In Consultation", "Completed", "completed_at", "Completed"),
        "cancel": (None, "Cancelled", None, "Cancelled"),
        "requeue": ("In Consultation", "Waiting", None, "Arrived"),
    }
    if action not in transitions:
        raise ValueError("Unknown action")
    required, new_status, stamp_col, appt_status = transitions[action]
    if required and tk["status"] != required:
        raise ValueError(f"Token is {tk['status']}, cannot {action}")
    if action == "cancel" and tk["status"] in ("Completed", "Cancelled"):
        raise ValueError(f"Token is already {tk['status'].lower()}")

    def _run(c):
        if stamp_col:
            c.execute(f"UPDATE tokens SET status=?, {stamp_col}=? WHERE id=?", (new_status, now_str(), token_id))
        else:
            c.execute("UPDATE tokens SET status=? WHERE id=?", (new_status, token_id))
        if tk["appointment_id"]:
            c.execute("UPDATE appointments SET status=?, updated_at=? WHERE id=?",
                      (appt_status, now_str(), tk["appointment_id"]))
        audit.log(action, "token", token_id, {"status": new_status}, user=actor, conn=c)

    if conn is not None:
        _run(conn)
    else:
        with db.transaction() as c:
            _run(c)


# =============================================================== consultations
def consultation(cons_id) -> dict | None:
    return db.query_one(
        "SELECT c.*, p.full_name AS patient_name, p.patient_code, p.dob, p.gender, p.phone, p.allergies, "
        "d.name AS doctor_name, d.specialization, d.qualification, d.registration_no, "
        "(SELECT id FROM prescriptions x WHERE x.consultation_id = c.id LIMIT 1) AS prescription_id "
        "FROM consultations c JOIN patients p ON p.id = c.patient_id JOIN doctors d ON d.id = c.doctor_id WHERE c.id = ?",
        (cons_id,))


def consultations_for_patient(patient_id, limit: int = 20) -> list[dict]:
    return db.query(
        "SELECT c.*, d.name AS doctor_name, (SELECT id FROM prescriptions x WHERE x.consultation_id = c.id LIMIT 1) AS prescription_id "
        "FROM consultations c JOIN doctors d ON d.id = c.doctor_id WHERE c.patient_id = ? ORDER BY c.visit_date DESC, c.id DESC LIMIT ?",
        (patient_id, limit))


def consultations_list(start, end, doctor_id=None, search: str = "") -> pd.DataFrame:
    sql = ("SELECT c.id, c.visit_date, p.full_name AS patient, p.patient_code, d.name AS doctor, c.diagnosis, "
           "c.follow_up_date, c.status, (SELECT rx_number FROM prescriptions x WHERE x.consultation_id = c.id LIMIT 1) AS rx_number "
           "FROM consultations c JOIN patients p ON p.id = c.patient_id JOIN doctors d ON d.id = c.doctor_id "
           "WHERE c.visit_date BETWEEN ? AND ?")
    params: list = [_d(start), _d(end)]
    if doctor_id:
        sql += " AND c.doctor_id = ?"
        params.append(doctor_id)
    if search:
        sql += " AND (p.full_name LIKE ? OR p.patient_code LIKE ? OR c.diagnosis LIKE ?)"
        params += [f"%{search}%"] * 3
    return db.df(sql + " ORDER BY c.visit_date DESC, c.id DESC", params)


def _clean_items(items: list[dict]) -> list[dict]:
    out = []
    for i, it in enumerate(items or []):
        name = clean_text(it.get("medicine_name"), 150)
        if not name:
            continue
        out.append(dict(medicine_name=name, dosage=clean_text(it.get("dosage"), 80),
                        frequency=clean_text(it.get("frequency"), 80), duration=clean_text(it.get("duration"), 80),
                        instructions=clean_text(it.get("instructions"), 300), sort_order=i))
    return out


def _vital(v, lo, hi, label, as_int=True):
    if v in (None, "", 0) or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        val = int(v) if as_int else float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number")
    if not (lo <= val <= hi):
        raise ValueError(f"{label} must be between {lo} and {hi}")
    return val


def _consultation_fields(data: dict) -> dict:
    fu = _d(data.get("follow_up_date")) or None
    return dict(
        symptoms=clean_text(data.get("symptoms"), 4000),
        bp_systolic=_vital(data.get("bp_systolic"), 50, 300, "Systolic BP"),
        bp_diastolic=_vital(data.get("bp_diastolic"), 30, 200, "Diastolic BP"),
        pulse=_vital(data.get("pulse"), 20, 250, "Pulse"),
        temperature=_vital(data.get("temperature"), 90, 110, "Temperature (F)", as_int=False),
        weight=_vital(data.get("weight"), 0.5, 400, "Weight (kg)", as_int=False),
        height=_vital(data.get("height"), 20, 260, "Height (cm)", as_int=False),
        spo2=_vital(data.get("spo2"), 50, 100, "SpO2"),
        clinical_notes=clean_text(data.get("clinical_notes"), 8000),
        diagnosis=clean_text(data.get("diagnosis"), 2000),
        follow_up_date=fu,
    )


def create_consultation(patient_id, doctor_id, data: dict, items: list[dict], rx_notes: str = "",
                        appointment_id=None, token_id=None, actor=None, visit_date=None) -> tuple[int, int | None]:
    fields = _consultation_fields(data)
    items = _clean_items(items)
    vd = _d(visit_date) or today_str()
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO consultations(patient_id, doctor_id, appointment_id, token_id, visit_date, symptoms, bp_systolic, "
            "bp_diastolic, pulse, temperature, weight, height, spo2, clinical_notes, diagnosis, follow_up_date, status, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Completed',?,?)",
            (patient_id, doctor_id, appointment_id, token_id, vd, fields["symptoms"], fields["bp_systolic"],
             fields["bp_diastolic"], fields["pulse"], fields["temperature"], fields["weight"], fields["height"],
             fields["spo2"], fields["clinical_notes"], fields["diagnosis"], fields["follow_up_date"], now_str(), now_str()))
        cons_id = cur.lastrowid
        rx_id = None
        if items or clean_text(rx_notes):
            rx_id = _create_prescription(conn, cons_id, patient_id, doctor_id, items, rx_notes)
        if token_id:
            conn.execute("UPDATE tokens SET status='Completed', completed_at=? WHERE id=? AND status != 'Cancelled'",
                         (now_str(), token_id))
        if appointment_id:
            conn.execute("UPDATE appointments SET status='Completed', updated_at=? WHERE id=?", (now_str(), appointment_id))
        audit.log("create", "consultation", cons_id, {"patient_id": patient_id, "rx_id": rx_id}, user=actor, conn=conn)
        return cons_id, rx_id


def update_consultation(cons_id, data: dict, items: list[dict], rx_notes: str = "", actor=None) -> int | None:
    c = consultation(cons_id)
    if not c:
        raise ValueError("Consultation not found")
    rx = prescription(c["prescription_id"]) if c["prescription_id"] else None
    if rx and rx["status"] == "Signed":
        raise ValueError("Prescription is signed; it can no longer be edited")
    fields = _consultation_fields(data)
    items = _clean_items(items)
    with db.transaction() as conn:
        sets = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE consultations SET {sets}, updated_at = ? WHERE id = ?", (*fields.values(), now_str(), cons_id))
        rx_id = c["prescription_id"]
        if rx_id:
            conn.execute("DELETE FROM prescription_items WHERE prescription_id = ?", (rx_id,))
            _insert_items(conn, rx_id, items)
            conn.execute("UPDATE prescriptions SET notes=?, updated_at=? WHERE id=?", (clean_text(rx_notes, 2000), now_str(), rx_id))
        elif items or clean_text(rx_notes):
            rx_id = _create_prescription(conn, cons_id, c["patient_id"], c["doctor_id"], items, rx_notes)
        audit.log("update", "consultation", cons_id, user=actor, conn=conn)
        return rx_id


# =============================================================== prescriptions
def _insert_items(conn, rx_id, items):
    for it in items:
        conn.execute(
            "INSERT INTO prescription_items(prescription_id, medicine_name, dosage, frequency, duration, instructions, sort_order) "
            "VALUES (?,?,?,?,?,?,?)",
            (rx_id, it["medicine_name"], it["dosage"], it["frequency"], it["duration"], it["instructions"], it["sort_order"]))


def _create_prescription(conn, cons_id, patient_id, doctor_id, items, notes) -> int:
    n = db.next_seq(conn, f"rx_{today().year}")
    rx_number = f"RX-{today().year}-{n:05d}"
    cur = conn.execute(
        "INSERT INTO prescriptions(rx_number, consultation_id, patient_id, doctor_id, notes, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,'Draft',?,?)", (rx_number, cons_id, patient_id, doctor_id, clean_text(notes, 2000), now_str(), now_str()))
    _insert_items(conn, cur.lastrowid, items)
    return cur.lastrowid


def prescription(rx_id) -> dict | None:
    return db.query_one(
        "SELECT r.*, p.full_name AS patient_name, p.patient_code, p.dob, p.gender, p.phone, p.allergies, "
        "d.name AS doctor_name, d.specialization, d.qualification, d.registration_no, "
        "c.visit_date, c.diagnosis, c.symptoms, c.follow_up_date, c.bp_systolic, c.bp_diastolic, c.pulse, c.temperature, c.weight "
        "FROM prescriptions r JOIN patients p ON p.id = r.patient_id JOIN doctors d ON d.id = r.doctor_id "
        "LEFT JOIN consultations c ON c.id = r.consultation_id WHERE r.id = ?", (rx_id,))


def prescription_items(rx_id) -> list[dict]:
    return db.query("SELECT * FROM prescription_items WHERE prescription_id = ? ORDER BY sort_order, id", (rx_id,))


def prescriptions_list(start, end, doctor_id=None, search: str = "", status: str | None = None) -> pd.DataFrame:
    sql = ("SELECT r.id, r.rx_number, r.created_at, p.full_name AS patient, p.patient_code, d.name AS doctor, r.status, "
           "(SELECT COUNT(*) FROM prescription_items i WHERE i.prescription_id = r.id) AS items, c.diagnosis "
           "FROM prescriptions r JOIN patients p ON p.id = r.patient_id JOIN doctors d ON d.id = r.doctor_id "
           "LEFT JOIN consultations c ON c.id = r.consultation_id WHERE substr(r.created_at,1,10) BETWEEN ? AND ?")
    params: list = [_d(start), _d(end)]
    if doctor_id:
        sql += " AND r.doctor_id = ?"
        params.append(doctor_id)
    if status:
        sql += " AND r.status = ?"
        params.append(status)
    if search:
        sql += " AND (p.full_name LIKE ? OR p.patient_code LIKE ? OR r.rx_number LIKE ?)"
        params += [f"%{search}%"] * 3
    return db.df(sql + " ORDER BY r.id DESC", params)


def sign_prescription(rx_id, actor=None) -> None:
    rx = prescription(rx_id)
    if not rx:
        raise ValueError("Prescription not found")
    if rx["status"] == "Signed":
        return
    if actor and actor.get("role") == "doctor" and actor.get("doctor_id") != rx["doctor_id"]:
        raise ValueError("Only the prescribing doctor can sign this prescription")
    if not prescription_items(rx_id) and not rx["notes"]:
        raise ValueError("Add at least one medicine or a note before signing")
    with db.transaction() as conn:
        conn.execute("UPDATE prescriptions SET status='Signed', signed_at=?, updated_at=? WHERE id=?",
                     (now_str(), now_str(), rx_id))
        audit.log("sign", "prescription", rx["rx_number"], user=actor, conn=conn)


def update_prescription(rx_id, items: list[dict], notes: str, actor=None) -> None:
    rx = prescription(rx_id)
    if not rx:
        raise ValueError("Prescription not found")
    if rx["status"] == "Signed":
        raise ValueError("Signed prescriptions cannot be edited")
    items = _clean_items(items)
    with db.transaction() as conn:
        conn.execute("DELETE FROM prescription_items WHERE prescription_id = ?", (rx_id,))
        _insert_items(conn, rx_id, items)
        conn.execute("UPDATE prescriptions SET notes=?, updated_at=? WHERE id=?", (clean_text(notes, 2000), now_str(), rx_id))
        audit.log("update", "prescription", rx["rx_number"], user=actor, conn=conn)


# ===================================================================== billing
def services(active_only: bool = True) -> list[dict]:
    sql = "SELECT * FROM services" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY name"
    return db.query(sql)


def save_service(name: str, price: float, service_id=None, is_active: bool = True, actor=None) -> int:
    name = clean_text(name, 100)
    if not name:
        raise ValueError("Service name is required")
    if price < 0:
        raise ValueError("Price cannot be negative")
    with db.transaction() as conn:
        if service_id:
            conn.execute("UPDATE services SET name=?, price=?, is_active=? WHERE id=?", (name, price, 1 if is_active else 0, service_id))
            audit.log("update", "service", service_id, {"name": name, "price": price}, user=actor, conn=conn)
            return service_id
        cur = conn.execute("INSERT INTO services(name, price, is_active) VALUES (?,?,?)", (name, price, 1 if is_active else 0))
        audit.log("create", "service", cur.lastrowid, {"name": name, "price": price}, user=actor, conn=conn)
        return cur.lastrowid


def invoice_status_for(total: float, paid: float) -> str:
    if total <= 0 or paid >= total - 0.005:
        return "Paid"
    if paid > 0:
        return "Partial"
    return "Unpaid"


def create_invoice(patient_id, doctor_id=None, consultation_fee: float = 0, items: list[dict] | None = None,
                   discount: float = 0, discount_reason: str = "", authorized_by: str = "", consultation_id=None,
                   appointment_id=None, notes: str = "", payment: dict | None = None, actor=None, invoice_date=None) -> int:
    items = [it for it in (items or []) if clean_text(it.get("description"))]
    fee = round(float(consultation_fee or 0), 2)
    if fee < 0:
        raise ValueError("Consultation fee cannot be negative")
    services_total = 0.0
    clean_items = []
    for it in items:
        qty = float(it.get("qty") or 1)
        price = float(it.get("unit_price") or 0)
        if qty <= 0 or price < 0:
            raise ValueError("Service quantity must be positive and price non-negative")
        amount = round(qty * price, 2)
        services_total += amount
        clean_items.append((clean_text(it["description"], 150), qty, price, amount))
    discount = round(float(discount or 0), 2)
    subtotal = round(fee + services_total, 2)
    if discount < 0 or discount > subtotal:
        raise ValueError("Discount must be between 0 and the subtotal")
    if discount > 0 and not authorized_by:
        raise ValueError("Discounts require administrator authorization")
    total = round(subtotal - discount, 2)
    if payment:
        amt = round(float(payment.get("amount") or 0), 2)
        if amt < 0 or amt > total + 0.005:
            raise ValueError("Received amount cannot exceed the invoice total")
        if amt > 0 and payment.get("method") not in config.PAYMENT_METHODS:
            raise ValueError("Select a payment method")
    uid = actor.get("id") if actor else None
    inv_date = _d(invoice_date) or today_str()
    with db.transaction() as conn:
        n = db.next_seq(conn, f"inv_{inv_date[:4]}")
        inv_no = f"INV-{inv_date[:4]}-{n:05d}"
        paid = round(float(payment.get("amount") or 0), 2) if payment else 0.0
        cur = conn.execute(
            "INSERT INTO invoices(invoice_no, patient_id, doctor_id, appointment_id, consultation_id, invoice_date, consultation_fee, "
            "services_total, discount_amount, discount_reason, discount_authorized_by, total, status, notes, created_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (inv_no, patient_id, doctor_id, appointment_id, consultation_id, inv_date, fee, round(services_total, 2), discount,
             clean_text(discount_reason, 200), authorized_by, total, invoice_status_for(total, paid), clean_text(notes, 500),
             uid, now_str(), now_str()))
        inv_id = cur.lastrowid
        for desc, qty, price, amount in clean_items:
            conn.execute("INSERT INTO invoice_items(invoice_id, description, qty, unit_price, amount) VALUES (?,?,?,?,?)",
                         (inv_id, desc, qty, price, amount))
        if paid > 0:
            conn.execute("INSERT INTO payments(invoice_id, amount, method, reference, paid_at, received_by, notes) VALUES (?,?,?,?,?,?,?)",
                         (inv_id, paid, payment["method"], clean_text(payment.get("reference"), 100),
                          payment.get("paid_at") or now_str(), uid, clean_text(payment.get("notes"), 200)))
        audit.log("create", "invoice", inv_no, {"total": total, "paid": paid, "discount": discount,
                                                 "authorized_by": authorized_by}, user=actor, conn=conn)
        return inv_id


def invoice(inv_id) -> dict | None:
    row = db.query_one(
        "SELECT i.*, p.full_name AS patient_name, p.patient_code, p.phone, d.name AS doctor_name, u.full_name AS created_by_name, "
        "COALESCE((SELECT SUM(amount) FROM payments x WHERE x.invoice_id = i.id), 0) AS paid "
        "FROM invoices i JOIN patients p ON p.id = i.patient_id LEFT JOIN doctors d ON d.id = i.doctor_id "
        "LEFT JOIN users u ON u.id = i.created_by WHERE i.id = ?", (inv_id,))
    if row:
        row["outstanding"] = round(row["total"] - row["paid"], 2)
        row["items"] = db.query("SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id", (inv_id,))
        row["payments"] = db.query(
            "SELECT p.*, u.full_name AS received_by_name FROM payments p LEFT JOIN users u ON u.id = p.received_by "
            "WHERE p.invoice_id = ? ORDER BY p.paid_at", (inv_id,))
    return row


def record_payment(inv_id, amount: float, method: str, reference: str = "", notes: str = "", actor=None) -> int:
    inv = invoice(inv_id)
    if not inv:
        raise ValueError("Invoice not found")
    if inv["status"] == "Cancelled":
        raise ValueError("Invoice is cancelled")
    amount = round(float(amount or 0), 2)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")
    if amount > inv["outstanding"] + 0.005:
        raise ValueError(f"Amount exceeds the outstanding balance ({inv['outstanding']:.0f})")
    if method not in config.PAYMENT_METHODS:
        raise ValueError("Select a payment method")
    uid = actor.get("id") if actor else None
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO payments(invoice_id, amount, method, reference, paid_at, received_by, notes) VALUES (?,?,?,?,?,?,?)",
            (inv_id, amount, method, clean_text(reference, 100), now_str(), uid, clean_text(notes, 200)))
        paid = inv["paid"] + amount
        conn.execute("UPDATE invoices SET status=?, updated_at=? WHERE id=?", (invoice_status_for(inv["total"], paid), now_str(), inv_id))
        audit.log("payment", "invoice", inv["invoice_no"], {"amount": amount, "method": method}, user=actor, conn=conn)
        return cur.lastrowid


def cancel_invoice(inv_id, reason: str = "", actor=None) -> None:
    inv = invoice(inv_id)
    if not inv:
        raise ValueError("Invoice not found")
    if inv["paid"] > 0:
        raise ValueError("Invoices with recorded payments cannot be cancelled")
    with db.transaction() as conn:
        conn.execute("UPDATE invoices SET status='Cancelled', notes=?, updated_at=? WHERE id=?",
                     (clean_text(f"{inv['notes']} Cancelled: {reason}".strip(), 500), now_str(), inv_id))
        audit.log("cancel", "invoice", inv["invoice_no"], {"reason": reason}, user=actor, conn=conn)


def invoices_list(start, end, status: str | None = None, search: str = "", doctor_id=None) -> pd.DataFrame:
    sql = ("SELECT i.id, i.invoice_no, i.invoice_date, p.full_name AS patient, p.patient_code, d.name AS doctor, i.total, "
           "COALESCE((SELECT SUM(amount) FROM payments x WHERE x.invoice_id = i.id), 0) AS paid, i.status, i.discount_amount "
           "FROM invoices i JOIN patients p ON p.id = i.patient_id LEFT JOIN doctors d ON d.id = i.doctor_id "
           "WHERE i.invoice_date BETWEEN ? AND ?")
    params: list = [_d(start), _d(end)]
    if status:
        sql += " AND i.status = ?"
        params.append(status)
    if doctor_id:
        sql += " AND i.doctor_id = ?"
        params.append(doctor_id)
    if search:
        sql += " AND (p.full_name LIKE ? OR p.patient_code LIKE ? OR i.invoice_no LIKE ?)"
        params += [f"%{search}%"] * 3
    d = db.df(sql + " ORDER BY i.id DESC", params)
    if not d.empty:
        d["outstanding"] = (d["total"] - d["paid"]).round(2)
    return d


def outstanding_invoices() -> pd.DataFrame:
    d = db.df(
        "SELECT i.id, i.invoice_no, i.invoice_date, p.full_name AS patient, p.patient_code, p.phone, i.total, "
        "COALESCE((SELECT SUM(amount) FROM payments x WHERE x.invoice_id = i.id), 0) AS paid, i.status "
        "FROM invoices i JOIN patients p ON p.id = i.patient_id WHERE i.status IN ('Unpaid','Partial') ORDER BY i.invoice_date")
    if not d.empty:
        d["outstanding"] = (d["total"] - d["paid"]).round(2)
    return d


def collection_on(d, doctor_id=None) -> float:
    sql = "SELECT COALESCE(SUM(p.amount),0) FROM payments p JOIN invoices i ON i.id = p.invoice_id WHERE substr(p.paid_at,1,10) = ?"
    params: list = [_d(d)]
    if doctor_id:
        sql += " AND i.doctor_id = ?"
        params.append(doctor_id)
    return float(db.scalar(sql, params))


def pending_total(doctor_id=None) -> float:
    sql = ("SELECT COALESCE(SUM(i.total - COALESCE((SELECT SUM(amount) FROM payments x WHERE x.invoice_id = i.id),0)),0) "
           "FROM invoices i WHERE i.status IN ('Unpaid','Partial')")
    params: list = []
    if doctor_id:
        sql += " AND i.doctor_id = ?"
        params.append(doctor_id)
    return float(db.scalar(sql, params))


def daily_collection(start, end, doctor_id=None) -> pd.DataFrame:
    sql = ("SELECT substr(p.paid_at,1,10) AS day, SUM(p.amount) AS amount FROM payments p JOIN invoices i ON i.id = p.invoice_id "
           "WHERE substr(p.paid_at,1,10) BETWEEN ? AND ?")
    params: list = [_d(start), _d(end)]
    if doctor_id:
        sql += " AND i.doctor_id = ?"
        params.append(doctor_id)
    d = db.df(sql + " GROUP BY day ORDER BY day", params)
    days = pd.date_range(to_date(start), to_date(end), freq="D").strftime(DATE_FMT)
    out = pd.DataFrame({"day": days})
    out = out.merge(d, on="day", how="left").fillna({"amount": 0.0})
    return out


def collection_by_method(start, end, doctor_id=None) -> pd.DataFrame:
    sql = ("SELECT p.method, SUM(p.amount) AS amount, COUNT(*) AS payments FROM payments p JOIN invoices i ON i.id = p.invoice_id "
           "WHERE substr(p.paid_at,1,10) BETWEEN ? AND ?")
    params: list = [_d(start), _d(end)]
    if doctor_id:
        sql += " AND i.doctor_id = ?"
        params.append(doctor_id)
    return db.df(sql + " GROUP BY p.method ORDER BY amount DESC", params)


def unbilled_visits(d, doctor_id=None) -> pd.DataFrame:
    """Completed or in-progress visits on a date that have no invoice yet."""
    sql = ("SELECT a.id AS appointment_id, a.appt_time, p.id AS patient_id, p.full_name AS patient, p.patient_code, "
           "d.name AS doctor, a.doctor_id, d.consultation_fee, a.status, "
           "(SELECT c.id FROM consultations c WHERE c.appointment_id = a.id LIMIT 1) AS consultation_id "
           "FROM appointments a JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id "
           "WHERE a.appt_date = ? AND a.status IN ('Arrived','In Consultation','Completed') "
           "AND NOT EXISTS (SELECT 1 FROM invoices i WHERE i.appointment_id = a.id AND i.status != 'Cancelled')")
    params: list = [_d(d)]
    if doctor_id:
        sql += " AND a.doctor_id = ?"
        params.append(doctor_id)
    return db.df(sql + " ORDER BY a.appt_time", params)


# =================================================================== inventory
def medicines(search: str = "", active_only: bool = True, category: str | None = None) -> pd.DataFrame:
    sql = "SELECT * FROM medicines WHERE 1=1"
    params: list = []
    if active_only:
        sql += " AND is_active = 1"
    if search:
        sql += " AND (name LIKE ? OR sku LIKE ? OR supplier LIKE ?)"
        params += [f"%{search}%"] * 3
    if category:
        sql += " AND category = ?"
        params.append(category)
    return db.df(sql + " ORDER BY name", params)


def medicine(med_id) -> dict | None:
    return db.query_one("SELECT * FROM medicines WHERE id = ?", (med_id,))


def save_medicine(data: dict, med_id=None, actor=None) -> int:
    name = clean_text(data.get("name"), 120)
    sku = clean_text(data.get("sku"), 40).upper()
    if not name:
        raise ValueError("Medicine name is required")
    if not sku:
        raise ValueError("SKU is required")
    qty = int(data.get("quantity") or 0)
    reorder = int(data.get("reorder_level") or 0)
    pp, sp = float(data.get("purchase_price") or 0), float(data.get("selling_price") or 0)
    if qty < 0 or reorder < 0 or pp < 0 or sp < 0:
        raise ValueError("Quantities and prices cannot be negative")
    exp = _d(data.get("expiry_date")) or None
    fields = dict(name=name, category=data.get("category") or "Other", sku=sku, reorder_level=reorder,
                  purchase_price=pp, selling_price=sp, expiry_date=exp, supplier=clean_text(data.get("supplier"), 120),
                  is_active=1 if data.get("is_active", True) else 0, updated_at=now_str())
    try:
        with db.transaction() as conn:
            if med_id:
                sets = ", ".join(f"{k} = ?" for k in fields)
                conn.execute(f"UPDATE medicines SET {sets} WHERE id = ?", (*fields.values(), med_id))
                audit.log("update", "medicine", sku, {"name": name}, user=actor, conn=conn)
                return med_id
            fields["quantity"] = qty
            fields["created_at"] = now_str()
            cur = conn.execute(f"INSERT INTO medicines({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                               tuple(fields.values()))
            if qty:
                conn.execute("INSERT INTO stock_movements(medicine_id, change_qty, reason, reference, created_by, created_at) VALUES (?,?,?,?,?,?)",
                             (cur.lastrowid, qty, "Opening stock", "", actor.get("id") if actor else None, now_str()))
            audit.log("create", "medicine", sku, {"name": name, "qty": qty}, user=actor, conn=conn)
            return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError("A medicine with this SKU already exists") from exc


def adjust_stock(med_id, change: int, reason: str, reference: str = "", actor=None) -> int:
    change = int(change)
    if change == 0:
        raise ValueError("Enter a non-zero quantity")
    reason = clean_text(reason, 80)
    if not reason:
        raise ValueError("A reason is required")
    with db.transaction() as conn:
        row = conn.execute("SELECT quantity, sku FROM medicines WHERE id = ?", (med_id,)).fetchone()
        if not row:
            raise ValueError("Medicine not found")
        new_qty = row["quantity"] + change
        if new_qty < 0:
            raise ValueError(f"Stock cannot go below zero (current {row['quantity']})")
        conn.execute("UPDATE medicines SET quantity = ?, updated_at = ? WHERE id = ?", (new_qty, now_str(), med_id))
        conn.execute("INSERT INTO stock_movements(medicine_id, change_qty, reason, reference, created_by, created_at) VALUES (?,?,?,?,?,?)",
                     (med_id, change, reason, clean_text(reference, 100), actor.get("id") if actor else None, now_str()))
        audit.log("stock", "medicine", row["sku"], {"change": change, "reason": reason, "new_qty": new_qty}, user=actor, conn=conn)
        return new_qty


def stock_movements(med_id, limit: int = 50) -> pd.DataFrame:
    return db.df("SELECT m.created_at, m.change_qty, m.reason, m.reference, u.full_name AS by_user FROM stock_movements m "
                 "LEFT JOIN users u ON u.id = m.created_by WHERE m.medicine_id = ? ORDER BY m.id DESC LIMIT ?", (med_id, limit))


def stock_alerts() -> pd.DataFrame:
    """Medicines with a warning flag: Low stock, Expired, Expiring soon."""
    d = medicines()
    if d.empty:
        d["alert"] = []
        return d
    warn_days = int(db.get_setting("expiry_warning_days", "90") or 90)
    t = today()
    horizon = (t + timedelta(days=warn_days)).strftime(DATE_FMT)

    def flag(row):
        flags = []
        exp = row.get("expiry_date")
        if exp and str(exp) < t.strftime(DATE_FMT):
            flags.append("Expired")
        elif exp and str(exp) <= horizon:
            flags.append("Expiring soon")
        if int(row["quantity"]) <= int(row["reorder_level"]):
            flags.append("Low stock")
        return ", ".join(flags)

    d["alert"] = d.apply(flag, axis=1)
    return d[d["alert"] != ""].copy()


# =================================================================== dashboard
def dashboard_stats(d, doctor_id=None) -> dict:
    ds = _d(d)
    doc_sql = " AND doctor_id = ?" if doctor_id else ""
    params = [ds] + ([doctor_id] if doctor_id else [])
    return {
        "appointments": int(db.scalar(f"SELECT COUNT(*) FROM appointments WHERE appt_date = ? AND status != 'Cancelled'{doc_sql}", params)),
        "waiting": int(db.scalar(f"SELECT COUNT(*) FROM tokens WHERE token_date = ? AND status = 'Waiting'{doc_sql}", params)),
        "in_consultation": int(db.scalar(f"SELECT COUNT(*) FROM tokens WHERE token_date = ? AND status = 'In Consultation'{doc_sql}", params)),
        "completed": int(db.scalar(f"SELECT COUNT(*) FROM appointments WHERE appt_date = ? AND status = 'Completed'{doc_sql}", params)),
        "cancelled": int(db.scalar(f"SELECT COUNT(*) FROM appointments WHERE appt_date = ? AND status IN ('Cancelled','No Show'){doc_sql}", params)),
        "collection": collection_on(ds, doctor_id),
        "pending": pending_total(doctor_id),
        "new_patients": int(db.scalar("SELECT COUNT(*) FROM patients WHERE substr(created_at,1,10) = ?", (ds,))),
    }


def users_list() -> pd.DataFrame:
    return db.df("SELECT u.id, u.username, u.full_name, u.role, d.name AS doctor, u.is_active, u.last_login, u.created_at "
                 "FROM users u LEFT JOIN doctors d ON d.id = u.doctor_id ORDER BY u.role, u.username")


def set_user_active(user_id, active: bool, actor=None) -> None:
    with db.transaction() as conn:
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if active else 0, user_id))
        if not active:
            conn.execute("UPDATE sessions SET revoked = 1 WHERE user_id = ?", (user_id,))
        audit.log("activate" if active else "deactivate", "user", user_id, user=actor, conn=conn)


def update_user(user_id, full_name: str, role: str, doctor_id=None, actor=None) -> None:
    if role not in config.ROLES:
        raise ValueError("Invalid role")
    with db.transaction() as conn:
        conn.execute("UPDATE users SET full_name=?, role=?, doctor_id=? WHERE id=?",
                     (clean_text(full_name, 100), role, doctor_id if role == "doctor" else None, user_id))
        audit.log("update", "user", user_id, {"role": role}, user=actor, conn=conn)
