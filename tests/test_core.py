"""Unit tests for the domain layer. Run:  python -m pytest -q   or   python -m unittest -v

Every test runs against a throw-away SQLite file, never the live database.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import auth, config, db, repo  # noqa: E402
from core.utils import today, time_slots, money, normalize_phone, valid_phone, age_years  # noqa: E402


class CoreTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.db_path = Path(cls.tmp) / "test.db"
        db.set_db_path(cls.db_path)
        db.init_db()
        cls.admin_id = auth.create_user("admin", "Admin@123", "Admin", "admin")
        cls.admin = {"id": cls.admin_id, "username": "admin", "role": "admin"}
        cls.doc_id = repo.save_doctor(dict(name="Dr. Test", specialization="GP", consultation_fee=1000), actor=cls.admin)
        cls.doctor_user_id = auth.create_user("doc", "Doctor@123", "Dr. Test", "doctor", cls.doc_id)
        cls.doctor = {"id": cls.doctor_user_id, "username": "doc", "role": "doctor", "doctor_id": cls.doc_id}
        # make the doctor work every day 09:00-17:00 so tests do not depend on weekday
        sched = repo.doctor_schedule(cls.doc_id)
        for r in sched:
            r.update(is_working=1, start_time="09:00", end_time="17:00", break_start="13:00", break_end="14:00")
        repo.save_schedule(cls.doc_id, sched, actor=cls.admin)
        cls.p1 = repo.create_patient(dict(full_name="Ali Khan", phone="03001234567", gender="Male", dob=date(1990, 5, 1)), actor=cls.admin)
        cls.p2 = repo.create_patient(dict(full_name="Sana Malik", phone="0311-7654321", gender="Female"), actor=cls.admin)

    @classmethod
    def tearDownClass(cls):
        db.set_db_path(None)

    # ---------------------------------------------------------------- utils
    def test_utils(self):
        self.assertEqual(normalize_phone("+92 300 1234567"), "03001234567")
        self.assertTrue(valid_phone("0300-1234567"))
        self.assertFalse(valid_phone("12345"))
        self.assertEqual(money(1500), "Rs. 1,500")
        self.assertEqual(money(1500.5, "PKR"), "PKR 1,500.50")
        slots = time_slots("09:00", "11:00", 30, "10:00", "10:30")
        self.assertEqual(slots, ["09:00", "09:30", "10:30"])
        self.assertEqual(age_years(today() - timedelta(days=366 * 10 + 5)), 10)

    # ----------------------------------------------------------------- auth
    def test_password_hash_and_login(self):
        h = auth.hash_password("Secret123")
        self.assertTrue(h.startswith("$2"))
        self.assertTrue(auth.verify_password("Secret123", h))
        self.assertFalse(auth.verify_password("wrong", h))
        user, err = auth.login("admin", "Admin@123")
        self.assertIsNone(err)
        self.assertEqual(user["role"], "admin")
        self.assertNotIn("password_hash", user)
        self.assertIsNotNone(auth.validate_session(user["session_token"]))
        auth.logout(user["session_token"], user)
        self.assertIsNone(auth.validate_session(user["session_token"]))
        _, err = auth.login("admin", "nope")
        self.assertEqual(err, "Invalid username or password.")
        _, err = auth.login("ghost", "nope")
        self.assertEqual(err, "Invalid username or password.")

    def test_lockout(self):
        auth.create_user("locky", "Locky@123", "Lock Me", "receptionist")
        for _ in range(config.MAX_FAILED_LOGINS):
            auth.login("locky", "bad")
        _, err = auth.login("locky", "Locky@123")
        self.assertIn("locked", err.lower())

    def test_permissions(self):
        recep = {"role": "receptionist"}
        self.assertTrue(auth.can_edit(self.admin, "settings"))
        self.assertFalse(auth.can_view(recep, "consultations"))
        self.assertTrue(auth.can_edit(recep, "billing"))
        self.assertFalse(auth.can_edit(self.doctor, "billing"))
        self.assertTrue(auth.can_view(self.doctor, "billing"))
        self.assertIsNotNone(auth.authorize_admin("admin", "Admin@123"))
        self.assertIsNone(auth.authorize_admin("doc", "Doctor@123"))
        with self.assertRaises(ValueError):
            auth.create_user("weak", "short", "Weak", "doctor")

    # ------------------------------------------------------------- patients
    def test_patient_codes_and_duplicates(self):
        self.assertEqual(self.p1["patient_code"], "P-00001")
        self.assertEqual(self.p2["patient_code"], "P-00002")
        self.assertEqual(repo.patient(self.p2["id"])["phone"], "03117654321")
        dups = repo.find_duplicates("ali khan", "0300 1234567")
        self.assertEqual(len(dups), 1)
        self.assertFalse(repo.find_duplicates("Nobody", "03009999999"))
        self.assertEqual(len(repo.search_patients("P-00001")), 1)
        self.assertEqual(len(repo.search_patients("Malik")), 1)
        with self.assertRaises(ValueError):
            repo.create_patient(dict(full_name="X", phone="123", gender="Male"))
        with self.assertRaises(ValueError):
            repo.create_patient(dict(full_name="Future Kid", phone="03001112222", gender="Male", dob=today() + timedelta(days=1)))

    # --------------------------------------------------------- appointments
    def test_slots_and_double_booking(self):
        d = today() + timedelta(days=1)
        slots = repo.available_slots(self.doc_id, d)
        self.assertIn("09:00", slots)
        self.assertNotIn("13:00", slots)  # break
        a1 = repo.create_appointment(self.p1["id"], self.doc_id, d, "09:00", "New Visit", actor=self.admin)
        self.assertNotIn("09:00", repo.available_slots(self.doc_id, d))
        with self.assertRaises(repo.SlotTakenError):
            repo.create_appointment(self.p2["id"], self.doc_id, d, "09:00", "New Visit", actor=self.admin)
        # direct insert bypassing slot check still blocked by the unique index
        with self.assertRaises(repo.SlotTakenError):
            repo.create_appointment(self.p2["id"], self.doc_id, d, "09:00", "New Visit", actor=self.admin, enforce_slots=False)
        # cancelling frees the slot
        repo.set_appointment_status(a1, "Cancelled", actor=self.admin)
        self.assertIn("09:00", repo.available_slots(self.doc_id, d))
        a2 = repo.create_appointment(self.p2["id"], self.doc_id, d, "09:00", "Follow-up", actor=self.admin)
        repo.reschedule_appointment(a2, d, "09:15", actor=self.admin)
        self.assertEqual(repo.appointment(a2)["appt_time"], "09:15")
        with self.assertRaises(ValueError):
            repo.create_appointment(self.p1["id"], self.doc_id, today() - timedelta(days=1), "09:00", actor=self.admin)

    def test_holiday_blocks_slots(self):
        d = today() + timedelta(days=10)
        repo.add_holiday(self.doc_id, d, "Eid", actor=self.admin)
        self.assertEqual(repo.available_slots(self.doc_id, d), [])
        self.assertEqual(repo.doctor_status(self.doc_id, d)[0], "on_leave")
        hol = repo.is_holiday(self.doc_id, d)
        repo.remove_holiday(hol["id"], actor=self.admin)
        self.assertTrue(repo.available_slots(self.doc_id, d))

    # --------------------------------------------------------------- tokens
    def test_token_flow(self):
        d = today()
        a = repo.create_appointment(self.p1["id"], self.doc_id, d, "16:45", "New Visit", actor=self.admin, enforce_slots=False)
        tid = repo.mark_arrived(a, actor=self.admin)
        tk = repo.token(tid)
        self.assertEqual(tk["status"], "Waiting")
        self.assertEqual(repo.appointment(a)["status"], "Arrived")
        # arriving twice does not create a second token
        self.assertEqual(repo.mark_arrived(a, actor=self.admin), tid)
        wa, wt = repo.register_walk_in(self.p2["id"], self.doc_id, actor=self.admin)
        self.assertEqual(repo.token(wt)["token_no"], tk["token_no"] + 1)
        with self.assertRaises(ValueError):
            repo.token_action(tid, "complete", actor=self.admin)  # not started
        repo.token_action(tid, "start", actor=self.admin)
        self.assertEqual(repo.token(tid)["status"], "In Consultation")
        self.assertEqual(repo.doctor_status(self.doc_id, d)[0], "in_consultation")
        repo.token_action(tid, "complete", actor=self.admin)
        self.assertEqual(repo.token(tid)["status"], "Completed")
        self.assertEqual(repo.appointment(a)["status"], "Completed")
        repo.token_action(wt, "cancel", actor=self.admin)
        self.assertEqual(repo.token(wt)["status"], "Cancelled")

    # -------------------------------------------- consultations / prescriptions
    def test_consultation_and_prescription(self):
        a = repo.create_appointment(self.p1["id"], self.doc_id, today(), "16:30", "New Visit", actor=self.admin, enforce_slots=False)
        tid = repo.mark_arrived(a, actor=self.admin)
        repo.token_action(tid, "start", actor=self.doctor)
        cons_id, rx_id = repo.create_consultation(
            self.p1["id"], self.doc_id, dict(symptoms="Fever", bp_systolic=120, bp_diastolic=80, temperature=99.1, diagnosis="Viral fever",
                                              follow_up_date=today() + timedelta(days=7)),
            [dict(medicine_name="Panadol 500mg", dosage="1 tab", frequency="TDS", duration="5 days"), dict(medicine_name="  ")],
            appointment_id=a, token_id=tid, actor=self.doctor)
        self.assertIsNotNone(rx_id)
        self.assertEqual(repo.token(tid)["status"], "Completed")
        rx = repo.prescription(rx_id)
        self.assertTrue(rx["rx_number"].startswith(f"RX-{today().year}-"))
        self.assertEqual(rx["status"], "Draft")
        self.assertEqual(len(repo.prescription_items(rx_id)), 1)  # blank row dropped
        repo.update_prescription(rx_id, [dict(medicine_name="Brufen 400mg", dosage="1", frequency="BD", duration="3 days")], "After food", actor=self.doctor)
        self.assertEqual(repo.prescription_items(rx_id)[0]["medicine_name"], "Brufen 400mg")
        other_doc = {"id": 99, "username": "x", "role": "doctor", "doctor_id": 999}
        with self.assertRaises(ValueError):
            repo.sign_prescription(rx_id, actor=other_doc)
        repo.sign_prescription(rx_id, actor=self.doctor)
        self.assertEqual(repo.prescription(rx_id)["status"], "Signed")
        with self.assertRaises(ValueError):
            repo.update_prescription(rx_id, [], "", actor=self.doctor)
        with self.assertRaises(ValueError):
            repo.update_consultation(cons_id, dict(symptoms="x"), [], actor=self.doctor)
        with self.assertRaises(ValueError):
            repo.create_consultation(self.p1["id"], self.doc_id, dict(bp_systolic=999), [], actor=self.doctor)
        fus = repo.upcoming_follow_ups(today(), today() + timedelta(days=10))
        self.assertEqual(len(fus), 1)

    # -------------------------------------------------------------- billing
    def test_invoice_math_and_payments(self):
        inv_id = repo.create_invoice(self.p1["id"], self.doc_id, 1000, [dict(description="ECG", qty=2, unit_price=400)],
                                     discount=300, discount_reason="Staff", authorized_by="admin",
                                     payment=dict(amount=500, method="JazzCash", reference="TX1"), actor=self.admin)
        inv = repo.invoice(inv_id)
        self.assertEqual(inv["services_total"], 800)
        self.assertEqual(inv["total"], 1500)
        self.assertEqual(inv["paid"], 500)
        self.assertEqual(inv["outstanding"], 1000)
        self.assertEqual(inv["status"], "Partial")
        self.assertTrue(inv["invoice_no"].startswith(f"INV-{today().year}-"))
        with self.assertRaises(ValueError):
            repo.record_payment(inv_id, 2000, "Cash", actor=self.admin)
        with self.assertRaises(ValueError):
            repo.record_payment(inv_id, 100, "Bitcoin", actor=self.admin)
        repo.record_payment(inv_id, 1000, "Cash", actor=self.admin)
        inv = repo.invoice(inv_id)
        self.assertEqual(inv["status"], "Paid")
        self.assertEqual(inv["outstanding"], 0)
        with self.assertRaises(ValueError):
            repo.cancel_invoice(inv_id, "oops", actor=self.admin)  # has payments
        # discount requires authorization
        with self.assertRaises(ValueError):
            repo.create_invoice(self.p1["id"], self.doc_id, 1000, [], discount=100, actor=self.admin)
        with self.assertRaises(ValueError):
            repo.create_invoice(self.p1["id"], self.doc_id, 1000, [], discount=5000, authorized_by="admin", actor=self.admin)
        unpaid = repo.create_invoice(self.p2["id"], self.doc_id, 1000, [], actor=self.admin)
        self.assertEqual(repo.invoice(unpaid)["status"], "Unpaid")
        self.assertGreaterEqual(repo.pending_total(), 1000)
        repo.cancel_invoice(unpaid, "duplicate", actor=self.admin)
        self.assertEqual(repo.invoice(unpaid)["status"], "Cancelled")
        self.assertEqual(repo.collection_on(today()), 1500)
        dc = repo.daily_collection(today() - timedelta(days=2), today())
        self.assertEqual(len(dc), 3)
        self.assertEqual(float(dc["amount"].iloc[-1]), 1500)

    # ------------------------------------------------------------ inventory
    def test_inventory(self):
        mid = repo.save_medicine(dict(name="Panadol", category="Tablet", sku="t-001", quantity=20, reorder_level=25, purchase_price=1, selling_price=2,
                                      expiry_date=today() + timedelta(days=30)), actor=self.admin)
        self.assertEqual(repo.medicine(mid)["sku"], "T-001")
        with self.assertRaises(ValueError):
            repo.save_medicine(dict(name="Dup", sku="T-001", quantity=1), actor=self.admin)
        self.assertEqual(repo.adjust_stock(mid, -5, "Dispensed", actor=self.admin), 15)
        with self.assertRaises(ValueError):
            repo.adjust_stock(mid, -100, "Dispensed", actor=self.admin)
        alerts = repo.stock_alerts()
        row = alerts[alerts["id"] == mid].iloc[0]
        self.assertIn("Low stock", row["alert"])
        self.assertIn("Expiring soon", row["alert"])
        self.assertEqual(len(repo.stock_movements(mid)), 2)

    # --------------------------------------------------------------- audit
    def test_audit_and_dashboard(self):
        n = db.scalar("SELECT COUNT(*) FROM audit_log")
        self.assertGreaterEqual(n, 5)  # setUpClass alone writes user/doctor/patient entries
        repo.create_patient(dict(full_name="Audit Person", phone="03459998877", gender="Male"), actor=self.admin)
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM audit_log"), n + 1)
        last = db.query_one("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1")
        self.assertEqual((last["action"], last["entity"], last["username"]), ("create", "patient", "admin"))
        stats = repo.dashboard_stats(today())
        for key in ("appointments", "waiting", "completed", "collection", "pending", "new_patients"):
            self.assertIn(key, stats)
        self.assertGreaterEqual(stats["new_patients"], 1)

    def test_backup_restore(self):
        from core import backup
        p = backup.create_backup("test", actor=self.admin)
        self.assertTrue(p.exists())
        before = db.scalar("SELECT COUNT(*) FROM patients")
        repo.create_patient(dict(full_name="Temp Person", phone="03451234567", gender="Female"), actor=self.admin)
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM patients"), before + 1)
        backup.restore_backup(p, actor=self.admin)
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM patients"), before)
        p.unlink()
        for f in config.BACKUP_DIR.glob("clinic_*_pre_restore.db"):
            f.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
