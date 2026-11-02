"""Audit trail for important changes."""
from __future__ import annotations

import json
import sqlite3

from core import db
from core.utils import now_str


def log(action: str, entity: str, entity_id=None, details=None, user: dict | None = None,
        conn: sqlite3.Connection | None = None) -> None:
    """Record an audited action. Pass `conn` to include it in a running transaction."""
    if user is None:
        try:
            import streamlit as st
            user = st.session_state.get("user")
        except Exception:
            user = None
    uid = user.get("id") if user else None
    uname = user.get("username") if user else "system"
    if isinstance(details, (dict, list)):
        details = json.dumps(details, ensure_ascii=False, default=str)
    params = (uid, uname, action, entity, str(entity_id) if entity_id is not None else None,
              details or "", now_str())
    sql = ("INSERT INTO audit_log(user_id, username, action, entity, entity_id, details, created_at) "
           "VALUES (?,?,?,?,?,?,?)")
    if conn is not None:
        conn.execute(sql, params)
    else:
        db.execute(sql, params)


def recent(limit: int = 200, entity: str | None = None, search: str = ""):
    sql = "SELECT * FROM audit_log WHERE 1=1"
    params: list = []
    if entity:
        sql += " AND entity = ?"
        params.append(entity)
    if search:
        sql += " AND (username LIKE ? OR action LIKE ? OR details LIKE ? OR entity_id LIKE ?)"
        params += [f"%{search}%"] * 4
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return db.df(sql, params)
