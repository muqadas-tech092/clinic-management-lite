# Clinic Management Lite

A local prototype of a clinic management system for small and medium clinics in Pakistan.
Built with **Python, Streamlit, SQLite, Pandas, Plotly and ReportLab**. English and Urdu (RTL) interface,
PKR currency, Asia/Karachi time zone, printable prescriptions, receipts, token slips and reports.

> **Important notice.** This is a prototype for evaluation and demonstration. It ships with **synthetic demo data only**.
> Before any use with real patient data it needs a security, privacy, backup and regulatory review
> (data protection, PMDC/PMC and provincial healthcare rules, pharmacy regulations). See [Limitations](#limitations-and-review-items).

---

## Contents

1. [Quick start (Windows)](#quick-start-windows)
2. [Demo accounts](#demo-accounts)
3. [Project structure](#project-structure)
4. [Modules](#modules)
5. [Roles and permissions](#roles-and-permissions)
6. [Security design](#security-design)
7. [Backup and restore](#backup-and-restore)
8. [Testing](#testing)
9. [Customisation / white-label](#customisation--white-label)
10. [Urdu printing](#urdu-printing)
11. [Limitations and review items](#limitations-and-review-items)

---

## Quick start (Windows)

Requirements: Python 3.10 or newer (tested on 3.13), Windows 10/11.

```bat
cd clinic-management-lite
setup.bat
run.bat
```

`setup.bat` creates a virtual environment, installs `requirements.txt`, creates the SQLite database and seeds demo data.
`run.bat` starts the app at <http://localhost:8501>.

Manual equivalent:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m core.seed
streamlit run app.py
```

Useful commands:

| Task | Command |
|---|---|
| Start the app | `streamlit run app.py` |
| Re-create the database with fresh demo data | `python -m core.seed --reset` |
| Run unit tests | `python -m unittest tests.test_core -v` |
| Create a backup from the command line | `python -c "from core import backup; print(backup.create_backup())"` |

The database file is `data/clinic.db`. Uploaded logos and photos live in `data/uploads/`. Backups go to `backups/`.
On first start the app initialises the schema automatically and seeds demo data if the database has no users.

## Demo accounts

| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `Admin@123` |
| Receptionist | `reception` | `Reception@123` |
| Doctor (Dr. Ayesha Khan) | `dr.ayesha` | `Doctor@123` |
| Doctor (Dr. Imran Malik) | `dr.imran` | `Doctor@123` |

Change these in **Settings > Users** before showing the app to anyone outside your team. The login page lists the demo
accounts only while the `demo_mode` setting is `1` (set by the seeder).

## Project structure

```
clinic-management-lite/
  app.py                 entry point: page config, bootstrap, login, sidebar, router
  requirements.txt
  setup.bat / run.bat    Windows helpers
  .streamlit/config.toml theme (teal / navy / light background) and server settings
  core/
    config.py            paths, palette, role matrix, constants, default settings
    db.py                SQLite schema, connections, transactions, sequences
    repo.py              all business rules and queries (framework independent)
    auth.py              bcrypt passwords, login, lockout, sessions, permissions
    audit.py             audit trail
    backup.py            backup / restore via SQLite online backup API
    seed.py              synthetic demo data (python -m core.seed)
    i18n.py              English / Urdu strings
    icons.py             Lucide icon SVG set (embedded)
    ui.py                CSS, icon buttons, cards, KPI tiles, badges, chart styling
    utils.py             dates (Asia/Karachi), money (PKR), validation, uploads
  modules/               one file per sidebar module (dashboard, patients, ... settings)
  pdf/                   ReportLab templates: base (letterhead, Urdu shaping), prescription, receipt, token_slip, report
  tests/test_core.py     unit tests on a temporary database
  assets/fonts/          drop a Nastaliq .ttf here for nicer Urdu PDFs (optional)
  data/                  clinic.db + uploads (created at runtime)
  backups/               database backups
```

All statistics and lists are computed from the SQLite records at render time. There are no hard-coded numbers.

## Modules

### Dashboard
KPI tiles (appointments, waiting, completed, collection, pending payments), the day's schedule with token numbers,
live token queue, 14-day collection chart, doctor availability (working hours, holidays, in consultation), recent
registrations and follow-up reminders (overdue / due / booked). A date picker re-computes everything for any day.
Doctors see only their own schedule and queue.

### Patients
Auto IDs (`P-00001`), registration with validation (name, Pakistani phone format, gender, DOB not in the future),
duplicate detection by phone or name+DOB with an explicit "register anyway" step, search by name / phone / ID, edit,
admin-only deactivation, and a full profile with appointment, consultation, prescription and billing history.
CSV export per tab; clinical tabs are visible to doctors and administrators only.
Quick actions jump to a new appointment, walk-in or invoice with the patient pre-selected.

### Appointments
Booking with patient search, doctor, date and **only free slots** (generated from the doctor's working hours and break,
minus booked slots, minus past times for today; empty on holidays). Double booking is blocked twice: in code and by a
partial unique index on `(doctor, date, time)` for non-cancelled rows. Daily list with Arrive / Reschedule / Cancel /
No-show actions and a weekly calendar. Working hours, breaks and holidays are managed in Settings > Doctors.

### Token Queue
Tokens are numbered per doctor per day. "Mark arrived" issues a token for a booked appointment; walk-ins create an
appointment plus token in one step (existing or new patient, with duplicate check). Statuses: Waiting, In Consultation,
Completed, Cancelled, with Start / Complete / Back to waiting / Cancel actions and a printable A6 token slip.
Doctors act only on their own queue and can jump straight into the consultation.

### Consultations
Patient summary with allergies, previous visits, symptoms, vitals (validated ranges), clinical notes, diagnosis,
follow-up date and a prescription editor (medicine, dosage, frequency, duration, instructions). Saving completes the
token and appointment in the same transaction. **Documentation only: the software never suggests, auto-fills or
auto-generates diagnoses, medicines or doses.** Consultations can be edited until the prescription is signed.

### Prescriptions
Numbered `RX-YYYY-NNNNN`, Draft until the prescribing doctor signs, editable only while Draft, history with filters,
and PDF in English, Urdu or bilingual with clinic letterhead, doctor registration number and signature area.

### Billing & Payments
Invoices `INV-YYYY-NNNNN` with consultation fee, catalogue services, an ad-hoc charge, discount (reason required and
**administrator authorization** unless within the configured no-auth limit), received amount and method
(Cash, Bank Transfer, JazzCash, Easypaisa, Other). Partial payments, payment history, invoice cancellation (only when
nothing has been paid), printable receipt, daily collection by method, outstanding list. Status is derived from
payments: Unpaid / Partial / Paid.

### Medicine Inventory
Name, category, SKU, quantity, reorder level, purchase/selling price, expiry, supplier. Stock changes only through
audited adjustments (purchase, dispensed, expired, correction...). Warnings for low stock, expiring within the
configured window, and expired items. Includes the note that this is not a substitute for pharmacy regulatory compliance.

### Reports & Analytics
Date presets and custom ranges, doctor filter, daily/weekly/monthly grouping. Appointments (completed vs cancelled),
registrations, doctor-wise visits and collection, collection by method and monthly revenue, outstanding payments with
ageing, stock. Every report has CSV and PDF export (landscape A4 with letterhead).

### Settings (administrator)
Clinic profile and logo, doctors (profile, photo, registration number, fee, weekly hours and breaks, holidays), users
(create, role, linked doctor, deactivate, reset password, revoke sessions), service catalogue, print settings (paper
size, footers in both languages, diagnosis on prescription), default language, backup / restore, audit log and
password change. Non-admin users see only the password change section.

## Roles and permissions

| Module | Administrator | Receptionist | Doctor |
|---|---|---|---|
| Dashboard | full | view | own data |
| Appointments | edit | edit | view own |
| Patients | edit | edit | edit |
| Token Queue | edit | edit | own queue |
| Consultations | view | no access | edit own |
| Prescriptions | view / print | no access | edit, sign own |
| Billing | edit | edit | view |
| Inventory | edit | edit | view |
| Reports | all | operational + collection | own |
| Settings | all | password only | password only |

The matrix is in `core/config.py` (`PERMISSIONS`) and enforced in `app.py` (routing) and inside modules (actions).

## Security design

- Passwords hashed with **bcrypt** (12 rounds); minimum 8 characters mixing letters and numbers.
- Server-side sessions table with random tokens, 8-hour lifetime and 30-minute idle timeout; "sign out everywhere".
- Account lockout for 15 minutes after 5 failed logins; identical error for unknown user and wrong password.
- Role-based access on every route and every write action; doctors can only sign their own prescriptions.
- Input validation and length limits on all forms; parameterised SQL everywhere; `BEGIN IMMEDIATE` transactions for
  multi-table writes; foreign keys enabled; WAL journal.
- Audit log for logins, failed logins, every create/update/status change, payments, discounts, stock movements,
  settings changes, backups and restores (Settings > Audit log, exportable).
- Uploads restricted to PNG/JPG/WEBP up to 2 MB, verified with Pillow, stored under `data/uploads` and read back only
  from that folder (path traversal is refused).
- No patient data leaves the machine. The only outbound request is the optional Google Fonts stylesheet for the UI
  typeface; the app falls back to system fonts offline.
- Streamlit's XSRF protection is on; error details are hidden from the browser.

## Backup and restore

- **In the app:** Settings > Backup & restore > *Create backup now*. Backups are consistent snapshots made with the
  SQLite online backup API and saved as `backups/clinic_YYYYMMDD_HHMMSS.db`. They can be downloaded, restored or deleted
  there. Restoring first writes a safety copy (`..._pre_restore.db`), validates the file (SQLite header, clinic tables,
  integrity check) and then replaces the live data. All users are signed out afterwards.
- **Manual:** copy `data/clinic.db` (while the app is stopped) together with `data/uploads/`. To restore, stop the app and
  copy the files back.
- **Recommended routine:** daily backup to an external drive or encrypted cloud folder, weekly restore test on a spare
  machine. Keep the `uploads` folder with the database.

## Testing

Automated tests (`tests/test_core.py`, 14 cases) cover: phone/date/money helpers, slot generation with breaks,
password hashing, login, lockout, permissions, patient codes and duplicate detection, slot availability and
double-booking prevention (including the database-level index), holidays, token numbering and state transitions,
consultation + prescription creation, signing rules, vitals validation, invoice arithmetic, discount authorization,
partial payments and status derivation, invoice cancellation rules, inventory SKU uniqueness and stock alerts,
audit trail presence, and backup/restore round-trip.

```bat
python -m unittest tests.test_core -v
```

Manual smoke test after each change (what was done while building each stage):

1. `streamlit run app.py`, sign in as each demo role, confirm the sidebar shows only permitted modules.
2. Dashboard: change the date, confirm KPIs and lists change; empty state on a date with no data.
3. Patients: register (try a duplicate phone), search by name / phone / ID, open profile, edit, export CSV.
4. Appointments: book tomorrow's slot, try the same slot again (blocked), reschedule, cancel, weekly view.
5. Queue: mark arrived, walk-in with a new patient, Start / Complete, print the token slip.
6. Consultations (doctor): pick a token, enter vitals and medicines, save + sign, open the PDF in all three languages.
7. Billing: invoice with a service and a discount (admin authorization prompt as receptionist), partial payment, receipt.
8. Inventory: add medicine, adjust stock below reorder level, see the warning.
9. Reports: every tab with a preset range, CSV and PDF export.
10. Settings: change working hours and confirm slots change; create a user; backup and restore.
11. Switch to Urdu: layout flips to RTL, labels translate, PDFs still generate.
12. Narrow the browser window: tiles wrap, tables scroll, sidebar collapses.

## Customisation / white-label

- Clinic name, tagline, address, phone, email, logo, currency symbol, token prefix, fee and language: Settings > Clinic profile.
- Colours: `core/config.py` (`COLORS`) and `.streamlit/config.toml`.
- Translations: `core/i18n.py` (add keys or a third language).
- Permissions: `core/config.py` (`PERMISSIONS`).
- Print templates: `pdf/*.py`; footers and paper size in Settings > Prints.
- Demo data: `core/seed.py`.

## Urdu printing

ReportLab has no built-in bidi/shaping, so Urdu text is shaped with `arabic-reshaper` and reordered with `python-bidi`.
The PDF layer looks for a TrueType font in this order: any `.ttf` in `assets/fonts/` (for example Noto Nastaliq Urdu or
Jameel Noori Nastaleeq, if you are licensed to use it), then Windows `tahoma.ttf` / `arial.ttf`. Nastaliq fonts give the
most natural result; Tahoma renders readable Naskh. The screen UI uses the Noto Nastaliq Urdu web font when online.

## Limitations and review items

- Prototype, single clinic, single machine. Multi-user access over a LAN works but has no TLS; put it behind a
  reverse proxy with HTTPS or keep it on one PC.
- Refreshing the browser tab requires signing in again (Streamlit session state is per tab by design).
- No encryption at rest for `clinic.db`; use disk encryption (BitLocker) and restrict folder permissions.
- No SMS / WhatsApp reminders, no lab module, no e-prescription transmission.
- Inventory is a convenience stock list and not a licensed pharmacy system.
- Clinical content is entered entirely by the clinician; the software provides no decision support by design.
- Before production: penetration test, data-protection assessment, consent and retention policy, role review,
  off-site backups, and confirmation of applicable PMDC/PMC, provincial health department and pharmacy rules.
