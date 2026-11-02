"""Date, time, currency, validation and file helpers (Asia/Karachi, PKR)."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from core import config

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(config.TIMEZONE)
except Exception:  # pragma: no cover - fallback when tzdata is missing
    TZ = timezone(timedelta(hours=5), "PKT")

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M"
DT_FMT = "%Y-%m-%d %H:%M:%S"


# ------------------------------------------------------------------ time
def now() -> datetime:
    return datetime.now(TZ)


def now_str() -> str:
    return now().strftime(DT_FMT)


def today() -> date:
    return now().date()


def today_str() -> str:
    return today().strftime(DATE_FMT)


def to_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], DATE_FMT).date()
    except ValueError:
        return None


def to_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in (DT_FMT, "%Y-%m-%d %H:%M", DATE_FMT):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


def fmt_date(value, long: bool = False) -> str:
    d = to_date(value)
    if not d:
        return "-"
    return d.strftime("%d %b %Y") if not long else d.strftime("%A, %d %B %Y")


def fmt_time(value) -> str:
    """Render 'HH:MM' (24h) as 'hh:mm AM/PM'."""
    if not value:
        return "-"
    try:
        t = datetime.strptime(str(value)[:5], TIME_FMT)
        return t.strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return str(value)


def fmt_datetime(value) -> str:
    dt = to_datetime(value)
    if not dt:
        return "-"
    return dt.strftime("%d %b %Y, %I:%M %p").replace(", 0", ", ")


def parse_time(value: str) -> time | None:
    try:
        return datetime.strptime(value.strip(), TIME_FMT).time()
    except (ValueError, AttributeError):
        return None


def time_slots(start: str, end: str, step_min: int, break_start: str = "", break_end: str = "") -> list[str]:
    """All 'HH:MM' slot starts between start and end, skipping the break window."""
    s, e = parse_time(start), parse_time(end)
    if not s or not e or step_min <= 0:
        return []
    bs, be = parse_time(break_start or ""), parse_time(break_end or "")
    slots = []
    cur = datetime.combine(date.today(), s)
    end_dt = datetime.combine(date.today(), e)
    step = timedelta(minutes=step_min)
    while cur + step <= end_dt:
        t = cur.time()
        in_break = bs and be and bs <= t < be
        if not in_break:
            slots.append(cur.strftime(TIME_FMT))
        cur += step
    return slots


def age_from_dob(dob) -> str:
    d = to_date(dob)
    if not d:
        return "-"
    t = today()
    years = t.year - d.year - ((t.month, t.day) < (d.month, d.day))
    if years >= 2:
        return f"{years} y"
    months = (t.year - d.year) * 12 + t.month - d.month - (t.day < d.day)
    return f"{max(months, 0)} m"


def age_years(dob) -> int | None:
    d = to_date(dob)
    if not d:
        return None
    t = today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def week_bounds(d: date) -> tuple[date, date]:
    start = d - timedelta(days=d.weekday())
    return start, start + timedelta(days=6)


def month_bounds(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start, nxt - timedelta(days=1)


# -------------------------------------------------------------- currency
def money(value, symbol: str | None = None) -> str:
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0.0
    sym = symbol if symbol is not None else "Rs."
    neg = v < 0
    s = f"{abs(v):,.0f}" if abs(v - round(v)) < 0.005 else f"{abs(v):,.2f}"
    return f"{'-' if neg else ''}{sym} {s}"


def to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------ validation
PHONE_RE = re.compile(r"^(\+92|0)?3\d{2}-?\d{7}$|^(\+92|0)?\d{2,3}-?\d{7,8}$")


def normalize_phone(phone: str) -> str:
    p = re.sub(r"[^\d+]", "", phone or "")
    if p.startswith("+92"):
        p = "0" + p[3:]
    elif p.startswith("92") and len(p) == 12:
        p = "0" + p[2:]
    return p


def valid_phone(phone: str) -> bool:
    p = normalize_phone(phone)
    return bool(re.fullmatch(r"0\d{9,10}", p))


def valid_name(name: str) -> bool:
    return bool(name) and 2 <= len(name.strip()) <= 80 and not re.search(r"[<>{}\[\]]", name)


def clean_text(value, max_len: int = 2000) -> str:
    s = (value or "").strip()
    return s[:max_len]


# ------------------------------------------------------------------ files
def safe_filename(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._")
    return base[:80] or "file"


def save_upload(uploaded, subdir: str, prefix: str) -> str:
    """Validate and store an uploaded image under data/uploads/<subdir>; returns relative path."""
    if uploaded is None:
        raise ValueError("No file provided")
    ext = Path(uploaded.name).suffix.lower()
    if ext not in config.ALLOWED_IMAGE_EXT:
        raise ValueError("Only PNG, JPG or WEBP images are allowed")
    data = uploaded.getvalue()
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise ValueError("Image must be 2 MB or smaller")
    # Verify it really is an image
    from io import BytesIO
    from PIL import Image
    try:
        img = Image.open(BytesIO(data))
        img.verify()
    except Exception as exc:
        raise ValueError("File is not a valid image") from exc
    folder = config.UPLOAD_DIR / safe_filename(subdir)
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{safe_filename(prefix)}_{int(now().timestamp())}{ext}"
    path = folder / fname
    path.write_bytes(data)
    return str(path.relative_to(config.DATA_DIR)).replace("\\", "/")


def resolve_upload(rel_path: str) -> Path | None:
    """Return an absolute path for a stored upload, refusing anything outside the uploads dir."""
    if not rel_path:
        return None
    candidate = (config.DATA_DIR / rel_path).resolve()
    try:
        candidate.relative_to(config.UPLOAD_DIR.resolve())
    except ValueError:
        return None
    return candidate if candidate.exists() else None
