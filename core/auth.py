"""Authentication, sessions and role-based permissions."""
from __future__ import annotations

import secrets
from datetime import timedelta

import bcrypt

from core import audit, config, db
from core.utils import now, now_str, to_datetime, DT_FMT


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def password_policy_error(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if password.isdigit() or password.isalpha():
        return "Password must mix letters and numbers."
    return None


# ------------------------------------------------------------------- users
def get_user(user_id: int) -> dict | None:
    return db.query_one(
        "SELECT u.*, d.name AS doctor_name FROM users u LEFT JOIN doctors d ON d.id = u.doctor_id WHERE u.id = ?",
        (user_id,),
    )


def get_user_by_username(username: str) -> dict | None:
    return db.query_one(
        "SELECT u.*, d.name AS doctor_name FROM users u LEFT JOIN doctors d ON d.id = u.doctor_id WHERE u.username = ?",
        (username.strip(),),
    )


def create_user(username: str, password: str, full_name: str, role: str, doctor_id=None, actor=None) -> int:
    if role not in config.ROLES:
        raise ValueError("Invalid role")
    err = password_policy_error(password)
    if err:
        raise ValueError(err)
    if get_user_by_username(username):
        raise ValueError("Username already exists")
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, full_name, role, doctor_id, created_at) VALUES (?,?,?,?,?,?)",
            (username.strip(), hash_password(password), full_name.strip(), role, doctor_id, now_str()),
        )
        audit.log("create", "user", cur.lastrowid, {"username": username, "role": role}, user=actor, conn=conn)
        return cur.lastrowid


def set_password(user_id: int, new_password: str, actor=None) -> None:
    err = password_policy_error(new_password)
    if err:
        raise ValueError(err)
    with db.transaction() as conn:
        conn.execute("UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
                     (hash_password(new_password), user_id))
        conn.execute("UPDATE sessions SET revoked = 1 WHERE user_id = ?", (user_id,))
        audit.log("password_reset", "user", user_id, user=actor, conn=conn)


def change_own_password(user: dict, current: str, new_password: str) -> None:
    row = get_user(user["id"])
    if not row or not verify_password(current, row["password_hash"]):
        raise ValueError("Current password is incorrect")
    err = password_policy_error(new_password)
    if err:
        raise ValueError(err)
    with db.transaction() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), user["id"]))
        audit.log("password_change", "user", user["id"], user=user, conn=conn)


# ---------------------------------------------------------------- sessions
def login(username: str, password: str) -> tuple[dict | None, str | None]:
    """Returns (user, error). Applies lockout after repeated failures."""
    username = (username or "").strip()
    if not username or not password:
        return None, "Enter your username and password."
    user = get_user_by_username(username)
    if not user or not user["is_active"]:
        # Same error as a wrong password to avoid user enumeration
        return None, "Invalid username or password."
    locked_until = to_datetime(user.get("locked_until"))
    if locked_until and locked_until > now().replace(tzinfo=None):
        mins = int((locked_until - now().replace(tzinfo=None)).total_seconds() // 60) + 1
        return None, f"Account locked. Try again in {mins} minute(s)."
    if not verify_password(password, user["password_hash"]):
        attempts = int(user.get("failed_attempts") or 0) + 1
        lock = None
        if attempts >= config.MAX_FAILED_LOGINS:
            lock = (now() + timedelta(minutes=config.LOCKOUT_MINUTES)).strftime(DT_FMT)
            attempts = 0
        db.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?", (attempts, lock, user["id"]))
        audit.log("login_failed", "user", user["id"], {"username": username}, user={"id": None, "username": username})
        if lock:
            return None, f"Too many failed attempts. Account locked for {config.LOCKOUT_MINUTES} minutes."
        return None, "Invalid username or password."

    token = secrets.token_urlsafe(32)
    ts = now()
    with db.transaction() as conn:
        conn.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?",
                     (ts.strftime(DT_FMT), user["id"]))
        conn.execute(
            "INSERT INTO sessions(token, user_id, created_at, last_seen, expires_at) VALUES (?,?,?,?,?)",
            (token, user["id"], ts.strftime(DT_FMT), ts.strftime(DT_FMT),
             (ts + timedelta(hours=config.SESSION_HOURS)).strftime(DT_FMT)),
        )
        audit.log("login", "user", user["id"], {"username": username}, user=user, conn=conn)
    user = dict(user)
    user.pop("password_hash", None)
    user["session_token"] = token
    return user, None


def validate_session(token: str) -> dict | None:
    """Return the user for a live session, refreshing last_seen; None if expired/revoked."""
    if not token:
        return None
    row = db.query_one("SELECT * FROM sessions WHERE token = ? AND revoked = 0", (token,))
    if not row:
        return None
    current = now().replace(tzinfo=None)
    if to_datetime(row["expires_at"]) < current:
        return None
    if (current - to_datetime(row["last_seen"])) > timedelta(minutes=config.IDLE_TIMEOUT_MIN):
        db.execute("UPDATE sessions SET revoked = 1 WHERE token = ?", (token,))
        return None
    db.execute("UPDATE sessions SET last_seen = ? WHERE token = ?", (current.strftime(DT_FMT), token))
    user = get_user(row["user_id"])
    if not user or not user["is_active"]:
        return None
    user.pop("password_hash", None)
    user["session_token"] = token
    return user


def logout(token: str, user: dict | None = None) -> None:
    if token:
        with db.transaction() as conn:
            conn.execute("UPDATE sessions SET revoked = 1 WHERE token = ?", (token,))
            audit.log("logout", "user", user.get("id") if user else None, user=user, conn=conn)


def revoke_all_sessions(user_id: int, actor=None) -> None:
    with db.transaction() as conn:
        conn.execute("UPDATE sessions SET revoked = 1 WHERE user_id = ?", (user_id,))
        audit.log("revoke_sessions", "user", user_id, user=actor, conn=conn)


def cleanup_sessions() -> None:
    db.execute("DELETE FROM sessions WHERE revoked = 1 OR expires_at < ?", (now_str(),))


# ------------------------------------------------------------- permissions
def permission(user: dict | None, module: str) -> str | None:
    if not user:
        return None
    return config.PERMISSIONS.get(module, {}).get(user.get("role"))


def can_view(user: dict | None, module: str) -> bool:
    return permission(user, module) in ("view", "edit")


def can_edit(user: dict | None, module: str) -> bool:
    return permission(user, module) == "edit"


def is_admin(user: dict | None) -> bool:
    return bool(user) and user.get("role") == "admin"


def is_doctor(user: dict | None) -> bool:
    return bool(user) and user.get("role") == "doctor"


def authorize_admin(username: str, password: str) -> dict | None:
    """Verify an administrator's credentials for an in-place authorization (e.g. discounts)."""
    user = get_user_by_username(username or "")
    if user and user["is_active"] and user["role"] == "admin" and verify_password(password or "", user["password_hash"]):
        return {"id": user["id"], "username": user["username"], "full_name": user["full_name"]}
    return None
