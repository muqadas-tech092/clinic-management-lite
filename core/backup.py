"""Database backup and restore using the SQLite online backup API."""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from core import audit, config, db
from core.utils import now


def create_backup(label: str = "", actor=None) -> Path:
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    target = config.BACKUP_DIR / f"clinic_{stamp}{suffix}.db"
    src = db.get_conn()
    try:
        dest = sqlite3.connect(str(target))
        try:
            src.backup(dest)
        finally:
            dest.close()
    finally:
        src.close()
    try:
        audit.log("backup", "database", target.name, user=actor)
    except Exception:
        pass
    return target


def list_backups() -> list[dict]:
    items = []
    for p in sorted(config.BACKUP_DIR.glob("clinic_*.db"), reverse=True):
        st = p.stat()
        items.append({"name": p.name, "size_kb": round(st.st_size / 1024, 1),
                      "modified": now().fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")})
    return items


def backup_path(name: str) -> Path | None:
    candidate = (config.BACKUP_DIR / Path(name).name).resolve()
    try:
        candidate.relative_to(config.BACKUP_DIR.resolve())
    except ValueError:
        return None
    return candidate if candidate.exists() else None


def _validate_sqlite(path: Path) -> None:
    with open(path, "rb") as fh:
        header = fh.read(16)
    if header != b"SQLite format 3\x00":
        raise ValueError("File is not a valid SQLite database")
    conn = sqlite3.connect(str(path))
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"patients", "users", "appointments"}.issubset(tables):
            raise ValueError("Backup file does not contain clinic tables")
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup file failed integrity check")
    finally:
        conn.close()


def restore_backup(path: Path, actor=None) -> Path:
    """Replace the live database with the given backup. A safety copy is made first."""
    _validate_sqlite(path)
    safety = create_backup("pre_restore", actor=actor)
    src = sqlite3.connect(str(path))
    try:
        dest = db.get_conn()
        try:
            src.backup(dest)
        finally:
            dest.close()
    finally:
        src.close()
    db.init_db()  # make sure any newer tables/settings exist
    try:
        audit.log("restore", "database", path.name, {"safety_copy": safety.name}, user=actor)
    except Exception:
        pass
    return safety


def save_uploaded_backup(data: bytes) -> Path:
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = config.BACKUP_DIR / f"clinic_{now().strftime('%Y%m%d_%H%M%S')}_uploaded.db"
    target.write_bytes(data)
    try:
        _validate_sqlite(target)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


def delete_backup(name: str) -> bool:
    p = backup_path(name)
    if p:
        p.unlink()
        return True
    return False


def copy_uploads_to(folder: Path) -> None:
    if config.UPLOAD_DIR.exists():
        shutil.copytree(config.UPLOAD_DIR, folder / "uploads", dirs_exist_ok=True)
