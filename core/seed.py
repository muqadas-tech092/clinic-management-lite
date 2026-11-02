"""Synthetic demo data. Every name, phone and record here is fictional.

Run:  python -m core.seed            (seeds only if the database has no users)
      python -m core.seed --reset    (deletes data/clinic.db and reseeds)
"""
from __future__ import annotations

import random
import sys
from datetime import timedelta

from core import auth, config, db, repo
from core.utils import DATE_FMT, now_str, today

DEMO_USERS = [
    ("admin", "Admin@123", "Clinic Administrator", "admin", None),
    ("reception", "Reception@123", "Hina Baig", "receptionist", None),
    ("dr.ayesha", "Doctor@123", "Dr. Ayesha Khan", "doctor", "Dr. Ayesha Khan"),
    ("dr.imran", "Doctor@123", "Dr. Imran Malik", "doctor", "Dr. Imran Malik"),
]

DOCTORS = [
    dict(name="Dr. Ayesha Khan", specialization="General Physician", qualification="MBBS, FCPS (Medicine)",
         registration_no="PMDC-45120-P", phone="0300-1234567", email="ayesha@citycareclinic.pk", consultation_fee=1500),
    dict(name="Dr. Imran Malik", specialization="Paediatrician", qualification="MBBS, MCPS (Paeds)",
         registration_no="PMDC-51877-P", phone="0321-7654321", email="imran@citycareclinic.pk", consultation_fee=1800),
    dict(name="Dr. Sana Tariq", specialization="Gynaecologist", qualification="MBBS, FCPS (Gynae)",
         registration_no="PMDC-60233-P", phone="0333-1122334", email="sana@citycareclinic.pk", consultation_fee=2000),
]

FIRST_M = ["Ahmed", "Bilal", "Usman", "Hamza", "Ali", "Fahad", "Zain", "Saad", "Umar", "Tariq", "Kamran", "Waqas",
           "Noman", "Shahid", "Adeel", "Faisal", "Junaid", "Rizwan", "Asad", "Danish"]
FIRST_F = ["Ayesha", "Fatima", "Zainab", "Maryam", "Sana", "Hira", "Iqra", "Mehwish", "Nida", "Rabia", "Sadia",
           "Amna", "Bushra", "Kiran", "Laiba", "Madiha", "Nimra", "Saba", "Uzma", "Zara"]
LAST = ["Khan", "Ahmed", "Malik", "Butt", "Sheikh", "Chaudhry", "Raza", "Hussain", "Qureshi", "Siddiqui", "Baig",
        "Mirza", "Iqbal", "Rehman", "Shah", "Javed", "Akhtar", "Farooq", "Nawaz", "Aslam"]
AREAS = ["Gulberg III", "Johar Town", "Model Town", "DHA Phase 5", "Faisal Town", "Wapda Town", "Iqbal Town",
         "Cantt", "Garden Town", "Township", "Shadman", "Samanabad"]

SERVICES = [("ECG", 800), ("Blood Sugar Test", 200), ("Nebulization", 500), ("Dressing", 600),
            ("Injection Administration", 150), ("Ultrasound", 1500), ("Blood Pressure Check", 100)]

MEDICINES = [
    ("Panadol 500mg", "Tablet", "MED-001", 240, 50, 1.5, 2.5, 540, "GSK Pakistan"),
    ("Brufen 400mg", "Tablet", "MED-002", 120, 40, 4.0, 6.0, 400, "Abbott"),
    ("Augmentin 625mg", "Tablet", "MED-003", 36, 30, 38.0, 48.0, 300, "GSK Pakistan"),
    ("Amoxil 250mg Syrup", "Syrup", "MED-004", 18, 10, 95.0, 130.0, 240, "GSK Pakistan"),
    ("Flagyl 400mg", "Tablet", "MED-005", 200, 40, 2.0, 3.5, 500, "Sanofi"),
    ("Risek 20mg", "Capsule", "MED-006", 90, 30, 8.0, 12.0, 350, "Getz Pharma"),
    ("Motilium 10mg", "Tablet", "MED-007", 8, 20, 5.0, 8.0, 420, "Janssen"),
    ("Cefspan 400mg", "Capsule", "MED-008", 44, 20, 55.0, 75.0, 60, "Barrett Hodgson"),
    ("Ventolin Inhaler", "Inhaler", "MED-009", 6, 5, 280.0, 350.0, 380, "GSK Pakistan"),
    ("Calpol Syrup 120mg", "Syrup", "MED-010", 25, 15, 85.0, 110.0, 25, "GSK Pakistan"),
    ("Arinac Forte", "Tablet", "MED-011", 150, 40, 3.0, 5.0, 300, "Abbott"),
    ("Gaviscon Syrup", "Syrup", "MED-012", 12, 10, 240.0, 300.0, 200, "Reckitt"),
    ("Disprin 300mg", "Tablet", "MED-013", 300, 60, 1.0, 2.0, 700, "Reckitt"),
    ("ORS Sachet", "Other", "MED-014", 80, 50, 12.0, 20.0, 450, "Searle"),
    ("Cetrizine 10mg", "Tablet", "MED-015", 160, 40, 2.0, 3.0, 390, "Getz Pharma"),
    ("Lexotanil 3mg", "Tablet", "MED-016", 0, 10, 6.0, 9.0, 410, "Roche"),
    ("Entamizole DS", "Tablet", "MED-017", 60, 20, 7.0, 10.0, -20, "Abbott"),
    ("Zyrtec Drops", "Drops", "MED-018", 9, 8, 150.0, 190.0, 150, "GSK Pakistan"),
    ("Polyfax Ointment", "Cream", "MED-019", 22, 10, 95.0, 125.0, 330, "GSK Pakistan"),
    ("Insulin Mixtard 30", "Injection", "MED-020", 14, 6, 850.0, 980.0, 110, "Novo Nordisk"),
    ("Metformin 500mg", "Tablet", "MED-021", 180, 50, 2.5, 4.0, 480, "Merck"),
    ("Amlodipine 5mg", "Tablet", "MED-022", 140, 40, 3.0, 5.0, 460, "Pfizer"),
    ("Folic Acid 5mg", "Tablet", "MED-023", 210, 40, 1.0, 2.0, 600, "Searle"),
    ("Iron Syrup", "Syrup", "MED-024", 16, 10, 160.0, 210.0, 90, "Hilton"),
]

SYMPTOMS = ["Fever and body aches for 3 days", "Cough with sore throat", "Abdominal pain and loose motions",
            "Headache and dizziness", "Follow-up for blood pressure", "Chest congestion", "Skin rash on arms",
            "Routine check-up", "Vomiting since last night", "Joint pain in knees", "Burning micturition",
            "Shortness of breath on exertion"]
DIAGNOSES = ["Viral fever", "Acute pharyngitis", "Acute gastroenteritis", "Tension headache", "Essential hypertension",
             "Acute bronchitis", "Contact dermatitis", "Normal examination", "Gastritis", "Osteoarthritis",
             "Urinary tract infection", "Bronchial asthma"]
RX_SETS = [
    [("Panadol 500mg", "1 tablet", "Three times a day", "5 days", "After meals"),
     ("Cetrizine 10mg", "1 tablet", "Once at night", "5 days", "")],
    [("Augmentin 625mg", "1 tablet", "Twice a day", "7 days", "After meals"),
     ("Brufen 400mg", "1 tablet", "Twice a day", "3 days", "With food")],
    [("Flagyl 400mg", "1 tablet", "Three times a day", "5 days", "After meals"),
     ("ORS Sachet", "1 sachet in 1 litre water", "After each loose motion", "3 days", "")],
    [("Risek 20mg", "1 capsule", "Once daily before breakfast", "14 days", "Empty stomach")],
    [("Amlodipine 5mg", "1 tablet", "Once daily", "30 days", "Same time every morning")],
    [("Ventolin Inhaler", "2 puffs", "As needed up to 4 times a day", "30 days", "Rinse mouth after use")],
]
NOTES = ["Patient advised rest and fluids.", "Advised to monitor temperature.", "Reviewed previous reports.",
         "Diet counselling given.", "Advised follow-up if symptoms persist."]


def _rand_phone(rng):
    return f"03{rng.choice(['00','01','02','03','11','12','21','22','31','33','34','45'])}{rng.randint(1000000, 9999999)}"


def seed_demo(verbose: bool = True) -> None:
    rng = random.Random(42)
    db.init_db()
    system = {"id": None, "username": "seed"}
    if verbose:
        print("Seeding demo data...")

    doc_ids = {}
    for d in DOCTORS:
        doc_ids[d["name"]] = repo.save_doctor(d, actor=system)
    # Dr. Sana works evenings only, Mon-Thu; Dr. Imran not on Friday
    sched = repo.doctor_schedule(doc_ids["Dr. Sana Tariq"])
    for r in sched:
        r["is_working"] = 1 if r["weekday"] <= 3 or r["weekday"] == 5 else 0
        r["start_time"], r["end_time"], r["break_start"], r["break_end"] = "16:00", "21:00", "", ""
    repo.save_schedule(doc_ids["Dr. Sana Tariq"], sched, actor=system)
    sched = repo.doctor_schedule(doc_ids["Dr. Imran Malik"])
    for r in sched:
        if r["weekday"] == 4:
            r["is_working"] = 0
    repo.save_schedule(doc_ids["Dr. Imran Malik"], sched, actor=system)
    repo.add_holiday(doc_ids["Dr. Imran Malik"], today() + timedelta(days=3), "Conference", actor=system)

    for username, pw, full, role, doc in DEMO_USERS:
        auth.create_user(username, pw, full, role, doc_ids.get(doc), actor=system)

    for name, price in SERVICES:
        repo.save_service(name, price, actor=system)

    t = today()
    for name, cat, sku, qty, reorder, pp, sp, exp_days, supplier in MEDICINES:
        repo.save_medicine(dict(name=name, category=cat, sku=sku, quantity=qty, reorder_level=reorder,
                                purchase_price=pp, selling_price=sp,
                                expiry_date=(t + timedelta(days=exp_days)).strftime(DATE_FMT), supplier=supplier),
                           actor=system)

    # patients
    patients = []
    used_phones = set()
    for i in range(48):
        gender = rng.choice(["Male", "Female"])
        first = rng.choice(FIRST_M if gender == "Male" else FIRST_F)
        name = f"{first} {rng.choice(LAST)}"
        phone = _rand_phone(rng)
        while phone in used_phones:
            phone = _rand_phone(rng)
        used_phones.add(phone)
        dob = t - timedelta(days=rng.randint(365, 365 * 75))
        p = repo.create_patient(dict(
            full_name=name, dob=dob, gender=gender, phone=phone,
            address=f"House {rng.randint(1, 400)}, Street {rng.randint(1, 40)}, {rng.choice(AREAS)}, Lahore",
            blood_group=rng.choice(config.BLOOD_GROUPS[1:]) if rng.random() < 0.6 else "",
            emergency_contact=_rand_phone(rng) if rng.random() < 0.5 else "",
            allergies=rng.choice(["", "", "", "Penicillin", "Sulpha drugs", "Dust", "Peanuts"]),
            medical_history=rng.choice(["", "", "Hypertension", "Type 2 diabetes", "Asthma", "Migraine"]),
        ), actor=system)
        # spread registration dates over the last 60 days
        created = (t - timedelta(days=rng.randint(0, 60))).strftime(DATE_FMT) + " 10:00:00"
        db.execute("UPDATE patients SET created_at = ? WHERE id = ?", (created, p["id"]))
        patients.append(p)

    doctor_list = repo.doctors()
    services = repo.services()
    receptionist = auth.get_user_by_username("reception")
    actor = {"id": receptionist["id"], "username": "reception"}

    # past visits: 30 days back
    for day_offset in range(30, 0, -1):
        d = t - timedelta(days=day_offset)
        for doc in doctor_list:
            day = repo.doctor_day(doc["id"], d)
            if not day or not day["is_working"] or repo.is_holiday(doc["id"], d):
                continue
            slots = repo.available_slots(doc["id"], d, include_past=True)
            n_visits = rng.randint(3, 7)
            for slot in rng.sample(slots, min(n_visits, len(slots))):
                pt = rng.choice(patients)
                status_roll = rng.random()
                status = "Completed" if status_roll < 0.82 else ("Cancelled" if status_roll < 0.92 else "No Show")
                vtype = rng.choice(["New Visit", "New Visit", "Follow-up", "Walk-in"])
                appt_id = repo.create_appointment(pt["id"], doc["id"], d, slot, vtype, actor=actor,
                                                 status=status, enforce_slots=False)
                if status != "Completed":
                    continue
                idx = rng.randrange(len(SYMPTOMS))
                rx = rng.choice(RX_SETS)
                items = [dict(medicine_name=m, dosage=do, frequency=f, duration=du, instructions=ins) for m, do, f, du, ins in rx]
                fu = d + timedelta(days=rng.choice([7, 14, 30])) if rng.random() < 0.35 else None
                cons_id, rx_id = repo.create_consultation(pt["id"], doc["id"], dict(
                    symptoms=SYMPTOMS[idx], bp_systolic=rng.randint(105, 150), bp_diastolic=rng.randint(65, 95),
                    pulse=rng.randint(62, 98), temperature=round(rng.uniform(97.5, 101.5), 1),
                    weight=round(rng.uniform(12, 95), 1), spo2=rng.randint(94, 99),
                    clinical_notes=rng.choice(NOTES), diagnosis=DIAGNOSES[idx], follow_up_date=fu,
                ), items, rx_notes="", appointment_id=appt_id, actor={"id": None, "username": doc["name"]}, visit_date=d)
                db.execute("UPDATE consultations SET created_at=?, updated_at=? WHERE id=?",
                           (f"{d.strftime(DATE_FMT)} {slot}:00",) * 2 + (cons_id,))
                if rx_id:
                    db.execute("UPDATE prescriptions SET created_at=?, updated_at=?, status='Signed', signed_at=? WHERE id=?",
                               (f"{d.strftime(DATE_FMT)} {slot}:00",) * 3 + (rx_id,))
                # invoice
                extra = []
                if rng.random() < 0.4:
                    s = rng.choice(services)
                    extra.append(dict(description=s["name"], qty=1, unit_price=s["price"]))
                total = doc["consultation_fee"] + sum(e["unit_price"] for e in extra)
                pay_roll = rng.random()
                if pay_roll < 0.8:
                    amount = total
                elif pay_roll < 0.93:
                    amount = round(total * rng.choice([0.5, 0.6, 0.75]) / 50) * 50
                else:
                    amount = 0
                method = rng.choices(config.PAYMENT_METHODS, weights=[60, 8, 15, 15, 2])[0]
                disc = 0
                auth_by = ""
                if rng.random() < 0.1:
                    disc = 200
                    auth_by = "admin"
                    amount = min(amount, total - disc)
                inv_id = repo.create_invoice(pt["id"], doc["id"], doc["consultation_fee"], extra, disc,
                                             "Regular patient" if disc else "", auth_by, cons_id, appt_id,
                                             payment=dict(amount=amount, method=method,
                                                          paid_at=f"{d.strftime(DATE_FMT)} {slot}:00") if amount else None,
                                             actor=actor, invoice_date=d)
                db.execute("UPDATE invoices SET created_at=?, updated_at=? WHERE id=?",
                           (f"{d.strftime(DATE_FMT)} {slot}:00",) * 2 + (inv_id,))

    # today: a realistic mix of scheduled, arrived (tokens), in consultation, completed
    for doc in doctor_list:
        slots = repo.available_slots(doc["id"], t, include_past=True)
        if not slots:
            continue
        chosen = sorted(rng.sample(slots, min(7, len(slots))))
        for j, slot in enumerate(chosen):
            pt = rng.choice(patients)
            appt_id = repo.create_appointment(pt["id"], doc["id"], t, slot, rng.choice(["New Visit", "Follow-up"]),
                                             actor=actor, enforce_slots=False)
            if j < 2:
                tid = repo.mark_arrived(appt_id, actor=actor)
                repo.token_action(tid, "start", actor=actor)
                idx = rng.randrange(len(SYMPTOMS))
                cons_id, rx_id = repo.create_consultation(pt["id"], doc["id"], dict(
                    symptoms=SYMPTOMS[idx], bp_systolic=120, bp_diastolic=80, pulse=76, temperature=98.6,
                    clinical_notes=rng.choice(NOTES), diagnosis=DIAGNOSES[idx]),
                    [dict(medicine_name=m, dosage=do, frequency=f, duration=du, instructions=ins) for m, do, f, du, ins in rng.choice(RX_SETS)],
                    appointment_id=appt_id, token_id=tid, actor=actor)
                if rx_id:
                    repo.sign_prescription(rx_id, actor={"id": None, "username": doc["name"], "role": "admin"})
                repo.create_invoice(pt["id"], doc["id"], doc["consultation_fee"], [], 0, "", "", cons_id, appt_id,
                                    payment=dict(amount=doc["consultation_fee"], method="Cash"), actor=actor)
            elif j == 2:
                tid = repo.mark_arrived(appt_id, actor=actor)
                repo.token_action(tid, "start", actor=actor)
            elif j in (3, 4):
                repo.mark_arrived(appt_id, actor=actor)
    # future appointments
    for day_offset in range(1, 8):
        d = t + timedelta(days=day_offset)
        for doc in doctor_list:
            slots = repo.available_slots(doc["id"], d)
            for slot in rng.sample(slots, min(rng.randint(1, 4), len(slots))):
                pt = rng.choice(patients)
                repo.create_appointment(pt["id"], doc["id"], d, slot, rng.choice(["New Visit", "Follow-up"]), actor=actor)

    db.set_setting("demo_mode", "1")
    db.set_setting("seeded_at", now_str())
    if verbose:
        counts = db.table_counts()
        print("Done. Row counts:")
        for k, v in counts.items():
            print(f"  {k:20s} {v}")


def needs_seed() -> bool:
    return db.scalar("SELECT COUNT(*) FROM users") == 0


if __name__ == "__main__":
    if "--reset" in sys.argv:
        for suffix in ("", "-wal", "-shm"):
            p = config.DB_PATH.with_name(config.DB_PATH.name + suffix)
            if p.exists():
                p.unlink()
        print("Removed existing database.")
    db.init_db()
    if needs_seed():
        seed_demo()
    else:
        print("Database already has users; nothing seeded. Use --reset to start over.")
