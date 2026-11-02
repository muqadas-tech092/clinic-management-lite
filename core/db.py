"""SQLite data layer: connections, transactions, schema and sequence helpers."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

import pandas as pd

from core import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sequences (
    name TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    specialization TEXT DEFAULT '',
    qualification TEXT DEFAULT '',
    registration_no TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    consultation_fee REAL NOT NULL DEFAULT 0,
    photo_path TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doctor_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    is_working INTEGER NOT NULL DEFAULT 1,
    start_time TEXT NOT NULL DEFAULT '09:00',
    end_time TEXT NOT NULL DEFAULT '17:00',
    break_start TEXT DEFAULT '',
    break_end TEXT DEFAULT '',
    UNIQUE (doctor_id, weekday)
);

CREATE TABLE IF NOT EXISTS doctor_holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    holiday_date TEXT NOT NULL,
    reason TEXT DEFAULT '',
    UNIQUE (doctor_id, holiday_date)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','receptionist','doctor')),
    doctor_id INTEGER REFERENCES doctors(id) ON DELETE SET NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    last_login TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    dob TEXT,
    gender TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT DEFAULT '',
    blood_group TEXT DEFAULT '',
    emergency_contact TEXT DEFAULT '',
    allergies TEXT DEFAULT '',
    medical_history TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_patients_phone ON patients(phone);
CREATE INDEX IF NOT EXISTS ix_patients_name ON patients(full_name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER NOT NULL REFERENCES doctors(id),
    appt_date TEXT NOT NULL,
    appt_time TEXT NOT NULL,
    duration_min INTEGER NOT NULL DEFAULT 15,
    visit_type TEXT NOT NULL DEFAULT 'New Visit',
    status TEXT NOT NULL DEFAULT 'Scheduled',
    notes TEXT DEFAULT '',
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_appt_slot
    ON appointments(doctor_id, appt_date, appt_time)
    WHERE status NOT IN ('Cancelled', 'No Show');
CREATE INDEX IF NOT EXISTS ix_appt_date ON appointments(appt_date);
CREATE INDEX IF NOT EXISTS ix_appt_patient ON appointments(patient_id);

CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_no INTEGER NOT NULL,
    token_date TEXT NOT NULL,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id),
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    appointment_id INTEGER REFERENCES appointments(id),
    status TEXT NOT NULL DEFAULT 'Waiting',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    UNIQUE (token_date, doctor_id, token_no)
);
CREATE INDEX IF NOT EXISTS ix_tokens_date ON tokens(token_date);

CREATE TABLE IF NOT EXISTS consultations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER NOT NULL REFERENCES doctors(id),
    appointment_id INTEGER REFERENCES appointments(id),
    token_id INTEGER REFERENCES tokens(id),
    visit_date TEXT NOT NULL,
    symptoms TEXT DEFAULT '',
    bp_systolic INTEGER,
    bp_diastolic INTEGER,
    pulse INTEGER,
    temperature REAL,
    weight REAL,
    height REAL,
    spo2 INTEGER,
    clinical_notes TEXT DEFAULT '',
    diagnosis TEXT DEFAULT '',
    follow_up_date TEXT,
    status TEXT NOT NULL DEFAULT 'Completed',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_cons_patient ON consultations(patient_id);
CREATE INDEX IF NOT EXISTS ix_cons_date ON consultations(visit_date);

CREATE TABLE IF NOT EXISTS prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rx_number TEXT NOT NULL UNIQUE,
    consultation_id INTEGER REFERENCES consultations(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER NOT NULL REFERENCES doctors(id),
    notes TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Draft',
    signed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prescription_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id INTEGER NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    medicine_name TEXT NOT NULL,
    dosage TEXT DEFAULT '',
    frequency TEXT DEFAULT '',
    duration TEXT DEFAULT '',
    instructions TEXT DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    price REAL NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT NOT NULL UNIQUE,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER REFERENCES doctors(id),
    appointment_id INTEGER REFERENCES appointments(id),
    consultation_id INTEGER REFERENCES consultations(id),
    invoice_date TEXT NOT NULL,
    consultation_fee REAL NOT NULL DEFAULT 0,
    services_total REAL NOT NULL DEFAULT 0,
    discount_amount REAL NOT NULL DEFAULT 0,
    discount_reason TEXT DEFAULT '',
    discount_authorized_by TEXT DEFAULT '',
    total REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Unpaid',
    notes TEXT DEFAULT '',
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_inv_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS ix_inv_patient ON invoices(patient_id);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    qty REAL NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL DEFAULT 0,
    amount REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    amount REAL NOT NULL,
    method TEXT NOT NULL,
    reference TEXT DEFAULT '',
    paid_at TEXT NOT NULL,
    received_by INTEGER REFERENCES users(id),
    notes TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_pay_date ON payments(paid_at);

CREATE TABLE IF NOT EXISTS medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'Tablet',
    sku TEXT NOT NULL UNIQUE,
    quantity INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 10,
    purchase_price REAL NOT NULL DEFAULT 0,
    selling_price REAL NOT NULL DEFAULT 0,
    expiry_date TEXT,
    supplier TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL REFERENCES medicines(id) ON DELETE CASCADE,
    change_qty INTEGER NOT NULL,
    reason TEXT NOT NULL,
    reference TEXT DEFAULT '',
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id TEXT,
    details TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_created ON audit_log(created_at);
"""

# Allows tests to point the whole layer at a temporary database.
_DB_OVERRIDE: dict[str, Any] = {"path": None}


def set_db_path(path) -> None:
    _DB_OVERRIDE["path"] = path


def current_db_path():
    return _DB_OVERRIDE["path"] or config.DB_PATH


def get_conn(db_path=None) -> sqlite3.Connection:
    path = str(db_path or current_db_path())
    conn = sqlite3.connect(path, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaction(db_path=None) -> Iterator[sqlite3.Connection]:
    """Run several statements atomically. Rolls back on any exception."""
    conn = get_conn(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def query(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    conn = get_conn()
    try:
        return _rows(conn.execute(sql, tuple(params)))
    finally:
        conn.close()


def query_one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def scalar(sql: str, params: Iterable[Any] = (), default=0):
    row = query_one(sql, params)
    if not row:
        return default
    val = list(row.values())[0]
    return default if val is None else val


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    """Execute a single write statement in its own transaction; returns lastrowid."""
    with transaction() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.lastrowid


def df(sql: str, params: Iterable[Any] = ()) -> pd.DataFrame:
    conn = get_conn()
    try:
        return pd.read_sql_query(sql, conn, params=tuple(params))
    finally:
        conn.close()


def next_seq(conn: sqlite3.Connection, name: str) -> int:
    """Atomically increment and return a named counter (call inside a transaction)."""
    conn.execute(
        "INSERT INTO sequences(name, value) VALUES (?, 0) ON CONFLICT(name) DO NOTHING",
        (name,),
    )
    conn.execute("UPDATE sequences SET value = value + 1 WHERE name = ?", (name,))
    return conn.execute("SELECT value FROM sequences WHERE name = ?", (name,)).fetchone()[0]


def init_db(db_path=None) -> None:
    """Create all tables and default settings. Safe to call on every start."""
    conn = get_conn(db_path)
    try:
        conn.executescript(SCHEMA)
        for key, value in config.DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- settings
def get_setting(key: str, default: str = "") -> str:
    row = query_one("SELECT value FROM settings WHERE key = ?", (key,))
    if row is None:
        return config.DEFAULT_SETTINGS.get(key, default)
    return row["value"]


def get_settings() -> dict[str, str]:
    data = dict(config.DEFAULT_SETTINGS)
    data.update({r["key"]: r["value"] for r in query("SELECT key, value FROM settings")})
    return data


def set_setting(key: str, value: Any, conn: sqlite3.Connection | None = None) -> None:
    sql = "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value"
    if conn is not None:
        conn.execute(sql, (key, str(value)))
    else:
        execute(sql, (key, str(value)))


def table_counts() -> dict[str, int]:
    names = [r["name"] for r in query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {n: scalar(f"SELECT COUNT(*) FROM {n}") for n in names}
