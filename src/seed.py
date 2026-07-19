"""
seed.py
---------
Populates the database with realistic demo data so you can launch the
app and explore a working hospital without clicking through 50 forms.

Run with:  python3 src/seed.py [--reset]
  --reset  Truncates all tables before seeding (safe for dev/demo only).
"""

import sys
import os
from datetime import date, timedelta
import random

sys.path.insert(0, os.path.dirname(__file__))

from db_connection import get_cursor
import patient_module   as pm
import doctor_module    as dm
import visit_module     as vm
import prescription_module as rxm
import billing_module   as bm


# ── helpers ──────────────────────────────────────────────────────────

def reset_all():
    tables = ["billing","prescriptions","visits","token_counters",
              "medicines","doctors","patients"]
    with get_cursor(commit=True) as (conn, cur):
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for t in tables:
            cur.execute(f"TRUNCATE TABLE {t}")
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
    print("  ✓ Tables cleared")


def section(title):
    print(f"\n── {title} ──")


# ── master data ───────────────────────────────────────────────────────

DOCTORS = [
    ("Dr. Priya Menon",      "General Medicine",  "9800000001", 300),
    ("Dr. Arjun Nair",       "Pediatrics",        "9800000002", 350),
    ("Dr. Kavitha Rao",      "Cardiology",        "9800000003", 500),
    ("Dr. Suresh Babu",      "Orthopedics",       "9800000004", 450),
    ("Dr. Deepa Krishnan",   "Dermatology",       "9800000005", 400),
]

PATIENTS = [
    ("Anitha Sharma",  "Female", "1985-03-14", "9700000001", "12 MG Road, Coimbatore", "O+"),
    ("Ravi Kumar",     "Male",   "1978-11-22", "9700000002", "45 RS Puram, Coimbatore","B+"),
    ("Meena Devi",     "Female", "1992-07-05", "9700000003", "7 Saibaba Colony",       "A+"),
    ("Karthik Raj",    "Male",   "2001-01-30", "9700000004", "23 Peelamedu, CBE",      "AB+"),
    ("Sundari Nathan", "Female", "1967-09-09", "9700000005", "88 Gandhipuram",         "O-"),
    ("Vijay Anand",    "Male",   "1990-06-18", "9700000006", "5 Race Course Rd",       "B-"),
    ("Lakshmi Priya",  "Female", "2005-12-01", "9700000007", "14 Hopes College Rd",    "A-"),
    ("Murugan S",      "Male",   "1955-04-25", "9700000008", "3 Town Hall Rd",         "O+"),
]

MEDICINES = [
    ("Paracetamol 500mg",    5.00,  500),
    ("Amoxicillin 250mg",   12.50,  200),
    ("Cough Syrup 100ml",   45.00,   80),
    ("Omeprazole 20mg",     18.00,  150),
    ("Azithromycin 500mg",  55.00,  100),
    ("Ibuprofen 400mg",      8.00,  300),
    ("Cetirizine 10mg",      6.00,  250),
    ("Vitamin C 500mg",      4.50,  400),
    ("Metformin 500mg",     10.00,  180),
    ("Atorvastatin 10mg",   22.00,  120),
    ("Salbutamol Inhaler",  95.00,   40),
    ("Pantoprazole 40mg",   20.00,  160),
]

DIAGNOSES = [
    ("Seasonal viral fever",           "Advised rest, plenty of fluids"),
    ("Upper respiratory tract infection", "Steam inhalation, avoid cold food"),
    ("Gastroenteritis",                "ORS, light diet for 2 days"),
    ("Hypertension – mild",           "Low salt diet, morning walk"),
    ("Type 2 Diabetes – follow-up",   "HbA1c satisfactory, continue medication"),
    ("Allergic rhinitis",              "Avoid dust and pollen"),
    ("Knee pain – osteoarthritis",    "Physiotherapy referral given"),
    ("Skin rash – contact dermatitis","Topical cream prescribed"),
    ("Migraine",                       "Avoid bright lights, caffeine trigger noted"),
    ("Anaemia – mild",                "Iron-rich diet, supplement prescribed"),
]

PRESCRIPTIONS_POOL = [
    # (medicine_index, dosage, duration_days, quantity)
    (0, "1 tab twice daily",    5, 10),
    (1, "1 cap thrice daily",   7, 21),
    (2, "10 ml thrice daily",   5,  1),
    (3, "1 tab before meals",  14, 14),
    (5, "1 tab twice daily",    5, 10),
    (6, "1 tab at night",       7,  7),
    (7, "1 tab daily",         30, 30),
    (8, "1 tab twice daily",   30, 60),
    (9, "1 tab at night",      30, 30),
]


def main():
    reset = "--reset" in sys.argv
    if reset:
        section("Resetting all tables")
        reset_all()

    section("Seeding doctors")
    doc_ids = []
    for name, spec, phone, fee in DOCTORS:
        did = dm.register_doctor(name, spec, phone, fee)
        doc_ids.append(did)
        print(f"  Doctor #{did}: {name} – {spec}")

    section("Seeding medicines")
    med_ids = []
    for name, price, stock in MEDICINES:
        mid = rxm.add_medicine(name, price, stock)
        med_ids.append(mid)
        print(f"  Medicine #{mid}: {name}  ₹{price}  stock={stock}")

    section("Seeding patients")
    pat_ids = []
    for name, gender, dob, phone, address, bg in PATIENTS:
        pid = pm.register_patient(name, gender, dob, phone, address, bg)
        pat_ids.append(pid)
        print(f"  Patient #{pid}: {name}")

    section("Seeding visits, diagnoses, prescriptions, and bills")
    today = date.today()
    random.seed(42)

    visit_count = 0
    for day_offset in range(7, 0, -1):          # last 7 days
        visit_date = today - timedelta(days=day_offset)
        patients_today = random.sample(pat_ids, k=random.randint(3, 6))
        for pid in patients_today:
            did = random.choice(doc_ids)
            visit = vm.create_visit(pid, did, visit_date=visit_date)
            vid   = visit["visit_id"]

            diag, notes = random.choice(DIAGNOSES)
            dm.record_diagnosis(vid, diag, notes)

            # 2-3 prescriptions per visit
            chosen_rxs = random.sample(PRESCRIPTIONS_POOL,
                                       k=random.randint(1, 3))
            for med_idx, dosage, duration, qty in chosen_rxs:
                mid = med_ids[med_idx]
                stock = rxm.get_medicine(mid)["stock_quantity"]
                if stock >= qty:
                    try:
                        rxm.add_prescription(vid, mid, dosage, duration, qty)
                    except Exception:
                        pass  # skip if stock ran out mid-seed

            bill = bm.generate_bill(vid)
            # 80% of historical visits already paid
            if random.random() < 0.8:
                bm.mark_paid(bill["bill_id"])

            visit_count += 1

    # Also create a few visits for today (still open/waiting)
    todays_patients = random.sample(pat_ids, k=min(4, len(pat_ids)))
    for pid in todays_patients:
        did = random.choice(doc_ids)
        vm.create_visit(pid, did)
        visit_count += 1

    section("Seed complete")
    print(f"  Doctors  : {len(doc_ids)}")
    print(f"  Medicines: {len(med_ids)}")
    print(f"  Patients : {len(pat_ids)}")
    print(f"  Visits   : {visit_count}")
    print("\n  You can now launch the app:  cd src && python3 main.py")


if __name__ == "__main__":
    main()
