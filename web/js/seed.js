/* Synthetic demo data (core/seed.py). Every name, phone and record here is fictional.
   Runs on first launch when the database has no users, and from Settings > Backup > Reset to demo data. */
import { store, todayISO, addDays, nowISO, BLOOD_GROUPS, PAYMENT_METHODS } from "./store.js";
import * as repo from "./repo.js";
import { createUser, getUserByUsername } from "./auth.js";

export const DEMO_USERS = [
  ["admin", "Admin@123", "Clinic Administrator", "admin", null],
  ["reception", "Reception@123", "Hina Baig", "receptionist", null],
  ["dr.ayesha", "Doctor@123", "Dr. Ayesha Khan", "doctor", "Dr. Ayesha Khan"],
  ["dr.imran", "Doctor@123", "Dr. Imran Malik", "doctor", "Dr. Imran Malik"],
];
const DOCTORS = [
  { name: "Dr. Ayesha Khan", specialization: "General Physician", qualification: "MBBS, FCPS (Medicine)", registration_no: "PMDC-45120-P", phone: "0300-1234567", email: "ayesha@citycareclinic.pk", consultation_fee: 1500 },
  { name: "Dr. Imran Malik", specialization: "Paediatrician", qualification: "MBBS, MCPS (Paeds)", registration_no: "PMDC-51877-P", phone: "0321-7654321", email: "imran@citycareclinic.pk", consultation_fee: 1800 },
  { name: "Dr. Sana Tariq", specialization: "Gynaecologist", qualification: "MBBS, FCPS (Gynae)", registration_no: "PMDC-60233-P", phone: "0333-1122334", email: "sana@citycareclinic.pk", consultation_fee: 2000 },
];
const FIRST_M = ["Ahmed", "Bilal", "Usman", "Hamza", "Ali", "Fahad", "Zain", "Saad", "Umar", "Tariq", "Kamran", "Waqas", "Noman", "Shahid", "Adeel", "Faisal", "Junaid", "Rizwan", "Asad", "Danish"];
const FIRST_F = ["Ayesha", "Fatima", "Zainab", "Maryam", "Sana", "Hira", "Iqra", "Mehwish", "Nida", "Rabia", "Sadia", "Amna", "Bushra", "Kiran", "Laiba", "Madiha", "Nimra", "Saba", "Uzma", "Zara"];
const LAST = ["Khan", "Ahmed", "Malik", "Butt", "Sheikh", "Chaudhry", "Raza", "Hussain", "Qureshi", "Siddiqui", "Baig", "Mirza", "Iqbal", "Rehman", "Shah", "Javed", "Akhtar", "Farooq", "Nawaz", "Aslam"];
const AREAS = ["Gulberg III", "Johar Town", "Model Town", "DHA Phase 5", "Faisal Town", "Wapda Town", "Iqbal Town", "Cantt", "Garden Town", "Township", "Shadman", "Samanabad"];
const SERVICES = [["ECG", 800], ["Blood Sugar Test", 200], ["Nebulization", 500], ["Dressing", 600], ["Injection Administration", 150], ["Ultrasound", 1500], ["Blood Pressure Check", 100]];
const MEDICINES = [
  ["Panadol 500mg", "Tablet", "MED-001", 240, 50, 1.5, 2.5, 540, "GSK Pakistan"], ["Brufen 400mg", "Tablet", "MED-002", 120, 40, 4.0, 6.0, 400, "Abbott"],
  ["Augmentin 625mg", "Tablet", "MED-003", 36, 30, 38.0, 48.0, 300, "GSK Pakistan"], ["Amoxil 250mg Syrup", "Syrup", "MED-004", 18, 10, 95.0, 130.0, 240, "GSK Pakistan"],
  ["Flagyl 400mg", "Tablet", "MED-005", 200, 40, 2.0, 3.5, 500, "Sanofi"], ["Risek 20mg", "Capsule", "MED-006", 90, 30, 8.0, 12.0, 350, "Getz Pharma"],
  ["Motilium 10mg", "Tablet", "MED-007", 8, 20, 5.0, 8.0, 420, "Janssen"], ["Cefspan 400mg", "Capsule", "MED-008", 44, 20, 55.0, 75.0, 60, "Barrett Hodgson"],
  ["Ventolin Inhaler", "Inhaler", "MED-009", 6, 5, 280.0, 350.0, 380, "GSK Pakistan"], ["Calpol Syrup 120mg", "Syrup", "MED-010", 25, 15, 85.0, 110.0, 25, "GSK Pakistan"],
  ["Arinac Forte", "Tablet", "MED-011", 150, 40, 3.0, 5.0, 300, "Abbott"], ["Gaviscon Syrup", "Syrup", "MED-012", 12, 10, 240.0, 300.0, 200, "Reckitt"],
  ["Disprin 300mg", "Tablet", "MED-013", 300, 60, 1.0, 2.0, 700, "Reckitt"], ["ORS Sachet", "Other", "MED-014", 80, 50, 12.0, 20.0, 450, "Searle"],
  ["Cetrizine 10mg", "Tablet", "MED-015", 160, 40, 2.0, 3.0, 390, "Getz Pharma"], ["Lexotanil 3mg", "Tablet", "MED-016", 0, 10, 6.0, 9.0, 410, "Roche"],
  ["Entamizole DS", "Tablet", "MED-017", 60, 20, 7.0, 10.0, -20, "Abbott"], ["Zyrtec Drops", "Drops", "MED-018", 9, 8, 150.0, 190.0, 150, "GSK Pakistan"],
  ["Polyfax Ointment", "Cream", "MED-019", 22, 10, 95.0, 125.0, 330, "GSK Pakistan"], ["Insulin Mixtard 30", "Injection", "MED-020", 14, 6, 850.0, 980.0, 110, "Novo Nordisk"],
  ["Metformin 500mg", "Tablet", "MED-021", 180, 50, 2.5, 4.0, 480, "Merck"], ["Amlodipine 5mg", "Tablet", "MED-022", 140, 40, 3.0, 5.0, 460, "Pfizer"],
  ["Folic Acid 5mg", "Tablet", "MED-023", 210, 40, 1.0, 2.0, 600, "Searle"], ["Iron Syrup", "Syrup", "MED-024", 16, 10, 160.0, 210.0, 90, "Hilton"],
];
const SYMPTOMS = ["Fever and body aches for 3 days", "Cough with sore throat", "Abdominal pain and loose motions", "Headache and dizziness", "Follow-up for blood pressure", "Chest congestion", "Skin rash on arms", "Routine check-up", "Vomiting since last night", "Joint pain in knees", "Burning micturition", "Shortness of breath on exertion"];
const DIAGNOSES = ["Viral fever", "Acute pharyngitis", "Acute gastroenteritis", "Tension headache", "Essential hypertension", "Acute bronchitis", "Contact dermatitis", "Normal examination", "Gastritis", "Osteoarthritis", "Urinary tract infection", "Bronchial asthma"];
const RX_SETS = [
  [["Panadol 500mg", "1 tablet", "Three times a day", "5 days", "After meals"], ["Cetrizine 10mg", "1 tablet", "Once at night", "5 days", ""]],
  [["Augmentin 625mg", "1 tablet", "Twice a day", "7 days", "After meals"], ["Brufen 400mg", "1 tablet", "Twice a day", "3 days", "With food"]],
  [["Flagyl 400mg", "1 tablet", "Three times a day", "5 days", "After meals"], ["ORS Sachet", "1 sachet in 1 litre water", "After each loose motion", "3 days", ""]],
  [["Risek 20mg", "1 capsule", "Once daily before breakfast", "14 days", "Empty stomach"]],
  [["Amlodipine 5mg", "1 tablet", "Once daily", "30 days", "Same time every morning"]],
  [["Ventolin Inhaler", "2 puffs", "As needed up to 4 times a day", "30 days", "Rinse mouth after use"]],
];
const NOTES = ["Patient advised rest and fluids.", "Advised to monitor temperature.", "Reviewed previous reports.", "Diet counselling given.", "Advised follow-up if symptoms persist."];

function mulberry32(a) { return function () { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
class RNG {
  constructor(seed) { this.r = mulberry32(seed); }
  random() { return this.r(); }
  randint(a, b) { return a + Math.floor(this.r() * (b - a + 1)); }
  uniform(a, b) { return a + this.r() * (b - a); }
  choice(arr) { return arr[Math.floor(this.r() * arr.length)]; }
  sample(arr, k) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(this.r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a.slice(0, Math.min(k, a.length)); }
  choices(arr, weights) { const total = weights.reduce((s, w) => s + w, 0); let x = this.r() * total; for (let i = 0; i < arr.length; i++) { x -= weights[i]; if (x <= 0) return arr[i]; } return arr[arr.length - 1]; }
}
const items = (set) => set.map(([m, d, f, du, i]) => ({ medicine_name: m, dosage: d, frequency: f, duration: du, instructions: i }));
const randPhone = (rng) => `03${rng.choice(["00", "01", "02", "03", "11", "12", "21", "22", "31", "33", "34", "45"])}${rng.randint(1000000, 9999999)}`;

export const needsSeed = () => store.state.users.length === 0;

export async function seedDemo() {
  const rng = new RNG(42);
  const system = { id: null, username: "seed" };
  const S = store.state;
  await store.batch(async () => {
    const docIds = {};
    for (const d of DOCTORS) docIds[d.name] = repo.saveDoctor(d, null, system);
    // Dr. Sana works evenings only (Mon-Thu and Sat); Dr. Imran not on Friday
    let sched = repo.doctorSchedule(docIds["Dr. Sana Tariq"]).map((r) => ({ ...r, is_working: r.weekday <= 3 || r.weekday === 5 ? 1 : 0, start_time: "16:00", end_time: "21:00", break_start: "", break_end: "" }));
    repo.saveSchedule(docIds["Dr. Sana Tariq"], sched, system);
    sched = repo.doctorSchedule(docIds["Dr. Imran Malik"]).map((r) => ({ ...r, is_working: r.weekday === 4 ? 0 : r.is_working }));
    repo.saveSchedule(docIds["Dr. Imran Malik"], sched, system);
    const t = todayISO();
    repo.addHoliday(docIds["Dr. Imran Malik"], addDays(t, 3), "Conference", system);

    for (const [username, pw, full, role, doc] of DEMO_USERS) await createUser(username, pw, full, role, doc ? docIds[doc] : null, system);
    for (const [name, price] of SERVICES) repo.saveService(name, price, null, true, system);
    for (const [name, cat, sku, qty, reorder, pp, sp, expDays, supplier] of MEDICINES) repo.saveMedicine({ name, category: cat, sku, quantity: qty, reorder_level: reorder, purchase_price: pp, selling_price: sp, expiry_date: addDays(t, expDays), supplier }, null, system);

    // patients
    const patients = []; const used = new Set();
    for (let i = 0; i < 48; i++) {
      const gender = rng.choice(["Male", "Female"]);
      const name = `${rng.choice(gender === "Male" ? FIRST_M : FIRST_F)} ${rng.choice(LAST)}`;
      let phone = randPhone(rng); while (used.has(phone)) phone = randPhone(rng); used.add(phone);
      const p = repo.createPatient({
        full_name: name, dob: addDays(t, -rng.randint(365, 365 * 75)), gender, phone,
        address: `House ${rng.randint(1, 400)}, Street ${rng.randint(1, 40)}, ${rng.choice(AREAS)}, Lahore`,
        blood_group: rng.random() < 0.6 ? rng.choice(BLOOD_GROUPS.slice(1)) : "",
        emergency_contact: rng.random() < 0.5 ? randPhone(rng) : "",
        allergies: rng.choice(["", "", "", "Penicillin", "Sulpha drugs", "Dust", "Peanuts"]),
        medical_history: rng.choice(["", "", "Hypertension", "Type 2 diabetes", "Asthma", "Migraine"]),
      }, system);
      p.created_at = `${addDays(t, -rng.randint(0, 60))} 10:00:00`;
      patients.push(p);
    }
    const doctorList = repo.doctors(); const services = repo.services();
    const receptionist = getUserByUsername("reception"); const actor = { id: receptionist.id, username: "reception" };
    const stamp = (row, s) => { row.created_at = s; row.updated_at = s; };

    // past visits: 30 days back
    for (let off = 30; off > 0; off--) {
      const d = addDays(t, -off);
      for (const doc of doctorList) {
        const day = repo.doctorDay(doc.id, d);
        if (!day || !day.is_working || repo.isHoliday(doc.id, d)) continue;
        const slots = repo.availableSlots(doc.id, d, null, true);
        for (const slot of rng.sample(slots, rng.randint(3, 7))) {
          const pt = rng.choice(patients); const roll = rng.random();
          const status = roll < 0.82 ? "Completed" : roll < 0.92 ? "Cancelled" : "No Show";
          const vtype = rng.choice(["New Visit", "New Visit", "Follow-up", "Walk-in"]);
          const apptId = repo.createAppointment(pt.id, doc.id, d, slot, vtype, "", actor, status, false);
          if (status !== "Completed") continue;
          const idx = rng.randint(0, SYMPTOMS.length - 1);
          const fu = rng.random() < 0.35 ? addDays(d, rng.choice([7, 14, 30])) : null;
          const [consId, rxId] = repo.createConsultation(pt.id, doc.id, {
            symptoms: SYMPTOMS[idx], bp_systolic: rng.randint(105, 150), bp_diastolic: rng.randint(65, 95), pulse: rng.randint(62, 98),
            temperature: Math.round(rng.uniform(97.5, 101.5) * 10) / 10, weight: Math.round(rng.uniform(12, 95) * 10) / 10, spo2: rng.randint(94, 99),
            clinical_notes: rng.choice(NOTES), diagnosis: DIAGNOSES[idx], follow_up_date: fu,
          }, items(rng.choice(RX_SETS)), "", { appointmentId: apptId, actor: { id: null, username: doc.name }, visitDate: d });
          const when = `${d} ${slot}:00`;
          stamp(S.consultations.find((c) => c.id === consId), when);
          if (rxId) { const rx = S.prescriptions.find((r) => r.id === rxId); stamp(rx, when); rx.status = "Signed"; rx.signed_at = when; }
          // invoice
          const extra = [];
          if (rng.random() < 0.4) { const s = rng.choice(services); extra.push({ description: s.name, qty: 1, unit_price: s.price }); }
          const total = doc.consultation_fee + extra.reduce((s, e) => s + e.unit_price, 0);
          const pay = rng.random();
          let amount = pay < 0.8 ? total : pay < 0.93 ? Math.round(total * rng.choice([0.5, 0.6, 0.75]) / 50) * 50 : 0;
          const method = rng.choices(PAYMENT_METHODS, [60, 8, 15, 15, 2]);
          let disc = 0, authBy = "";
          if (rng.random() < 0.1) { disc = 200; authBy = "admin"; amount = Math.min(amount, total - disc); }
          const invId = repo.createInvoice({ patientId: pt.id, doctorId: doc.id, consultationFee: doc.consultation_fee, items: extra, discount: disc, discountReason: disc ? "Regular patient" : "", authorizedBy: authBy,
            consultationId: consId, appointmentId: apptId, payment: amount ? { amount, method, paid_at: when } : null, actor, invoiceDate: d });
          stamp(S.invoices.find((i) => i.id === invId), when);
        }
      }
    }
    // today: a realistic mix of scheduled, arrived (tokens), in consultation, completed
    for (const doc of doctorList) {
      const slots = repo.availableSlots(doc.id, t, null, true);
      if (!slots.length) continue;
      const chosen = rng.sample(slots, 7).sort();
      chosen.forEach((slot, j) => {
        const pt = rng.choice(patients);
        const apptId = repo.createAppointment(pt.id, doc.id, t, slot, rng.choice(["New Visit", "Follow-up"]), "", actor, "Scheduled", false);
        if (j < 2) {
          const tid = repo.markArrived(apptId, actor); repo.tokenAction(tid, "start", actor);
          const idx = rng.randint(0, SYMPTOMS.length - 1);
          const [consId, rxId] = repo.createConsultation(pt.id, doc.id, { symptoms: SYMPTOMS[idx], bp_systolic: 120, bp_diastolic: 80, pulse: 76, temperature: 98.6, clinical_notes: rng.choice(NOTES), diagnosis: DIAGNOSES[idx] },
            items(rng.choice(RX_SETS)), "", { appointmentId: apptId, tokenId: tid, actor });
          if (rxId) repo.signPrescription(rxId, { id: null, username: doc.name, role: "admin" });
          repo.createInvoice({ patientId: pt.id, doctorId: doc.id, consultationFee: doc.consultation_fee, consultationId: consId, appointmentId: apptId, payment: { amount: doc.consultation_fee, method: "Cash" }, actor });
        } else if (j === 2) { const tid = repo.markArrived(apptId, actor); repo.tokenAction(tid, "start", actor); }
        else if (j === 3 || j === 4) repo.markArrived(apptId, actor);
      });
    }
    // future appointments
    for (let off = 1; off <= 7; off++) {
      const d = addDays(t, off);
      for (const doc of doctorList) {
        const slots = repo.availableSlots(doc.id, d);
        for (const slot of rng.sample(slots, rng.randint(1, 4))) repo.createAppointment(rng.choice(patients).id, doc.id, d, slot, rng.choice(["New Visit", "Follow-up"]), "", actor);
      }
    }
    store.setSettings({ demo_mode: "1", seeded_at: nowISO() });
  });
  await store.flush();
}
