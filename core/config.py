"""Central configuration: paths, constants and defaults for Clinic Management Lite."""
from __future__ import annotations

from pathlib import Path

APP_NAME = "Clinic Management Lite"
APP_VERSION = "0.7.0"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
BACKUP_DIR = BASE_DIR / "backups"
ASSETS_DIR = BASE_DIR / "assets"
FONT_DIR = ASSETS_DIR / "fonts"
DB_PATH = DATA_DIR / "clinic.db"

for _d in (DATA_DIR, UPLOAD_DIR, BACKUP_DIR, FONT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

TIMEZONE = "Asia/Karachi"
CURRENCY = "PKR"

# Brand palette (premium healthcare SaaS)
COLORS = {
    "primary": "#087F8C",
    "primary_dark": "#066670",
    "primary_soft": "#E3F2F3",
    "navy": "#173B48",
    "bg": "#F3F7F8",
    "card": "#FFFFFF",
    "border": "#E1E9EC",
    "muted": "#5F7A85",
    "success": "#1E8E5A",
    "success_soft": "#E4F4EC",
    "warning": "#B7791F",
    "warning_soft": "#FBF1DC",
    "danger": "#C0392B",
    "danger_soft": "#FBE5E2",
    "info": "#2B6CB0",
    "info_soft": "#E3EDF9",
}

ROLES = ("admin", "receptionist", "doctor")
ROLE_LABELS = {"admin": "Administrator", "receptionist": "Receptionist", "doctor": "Doctor"}

# Module permission matrix. Levels: "edit" > "view" > None.
PERMISSIONS = {
    "dashboard":     {"admin": "edit", "receptionist": "view", "doctor": "view"},
    "appointments":  {"admin": "edit", "receptionist": "edit", "doctor": "view"},
    "patients":      {"admin": "edit", "receptionist": "edit", "doctor": "edit"},
    "queue":         {"admin": "edit", "receptionist": "edit", "doctor": "edit"},
    "consultations": {"admin": "view", "receptionist": None,   "doctor": "edit"},
    "prescriptions": {"admin": "view", "receptionist": None,   "doctor": "edit"},
    "billing":       {"admin": "edit", "receptionist": "edit", "doctor": "view"},
    "inventory":     {"admin": "edit", "receptionist": "edit", "doctor": "view"},
    "reports":       {"admin": "edit", "receptionist": "view", "doctor": "view"},
    "settings":      {"admin": "edit", "receptionist": "view", "doctor": "view"},
}

NAV_ITEMS = [
    ("dashboard", "nav_dashboard", "layout-dashboard"),
    ("appointments", "nav_appointments", "calendar"),
    ("patients", "nav_patients", "users"),
    ("queue", "nav_queue", "ticket"),
    ("consultations", "nav_consultations", "stethoscope"),
    ("prescriptions", "nav_prescriptions", "file-text"),
    ("billing", "nav_billing", "credit-card"),
    ("inventory", "nav_inventory", "package"),
    ("reports", "nav_reports", "bar-chart"),
    ("settings", "nav_settings", "settings"),
]

APPOINTMENT_STATUSES = ("Scheduled", "Arrived", "In Consultation", "Completed", "Cancelled", "No Show")
VISIT_TYPES = ("New Visit", "Follow-up", "Walk-in", "Procedure")
TOKEN_STATUSES = ("Waiting", "In Consultation", "Completed", "Cancelled")
PAYMENT_METHODS = ("Cash", "Bank Transfer", "JazzCash", "Easypaisa", "Other")
INVOICE_STATUSES = ("Unpaid", "Partial", "Paid", "Cancelled")
GENDERS = ("Male", "Female", "Other")
BLOOD_GROUPS = ("", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
MEDICINE_CATEGORIES = ("Tablet", "Capsule", "Syrup", "Injection", "Drops", "Cream", "Inhaler", "Other")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

SESSION_HOURS = 8           # absolute session lifetime
IDLE_TIMEOUT_MIN = 30       # inactivity timeout
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}

DEFAULT_SETTINGS = {
    "clinic_name": "City Care Clinic",
    "clinic_tagline": "Family Medicine and General Practice",
    "clinic_address": "12-B Main Boulevard, Gulberg III, Lahore",
    "clinic_phone": "042-35761234",
    "clinic_email": "info@citycareclinic.pk",
    "clinic_logo": "",
    "default_language": "en",
    "appointment_duration": "15",
    "default_consultation_fee": "1500",
    "token_prefix": "T",
    "currency_symbol": "Rs.",
    "rx_footer_en": "Please bring this prescription on your next visit.",
    "rx_footer_ur": "براہ کرم اگلی ملاقات پر یہ نسخہ ساتھ لائیں۔",
    "receipt_footer_en": "Thank you for choosing our clinic. Fees once paid are non-refundable.",
    "receipt_footer_ur": "ہمارے کلینک کا انتخاب کرنے کا شکریہ۔ ادا شدہ فیس ناقابل واپسی ہے۔",
    "paper_size": "A5",
    "show_urdu_on_prints": "1",
    "low_stock_threshold": "10",
    "expiry_warning_days": "90",
    "max_discount_without_auth": "0",
    "follow_up_window_days": "7",
}
