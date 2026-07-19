"""
test_system.py
-----------------
End-to-end functional test for the Hospital Management System.
Exercises the full visit-based workflow:

    Register patient -> Register doctor -> Create visit (token) ->
    Doctor diagnosis -> Prescribe medicines -> Generate bill -> Pay bill

Also probes edge cases / invalid input on purpose, to surface defects:
    - duplicate / concurrent token assignment
    - prescribing more medicine than is in stock
    - invalid phone numbers, future DOB, bad gender/blood group
    - billing a visit that doesn't exist
    - re-generating a bill after adding a second prescription
    - multiple visits for the same patient (visit-history check)

Run with: python3 tests/test_system.py
"""

import sys
import os
import traceback
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import db_connection
import patient_module as pm
import doctor_module as dm
import visit_module as vm
import prescription_module as rxm
import billing_module as bm
from test_helpers import reset_db

PASS = []
FAIL = []


def check(label, condition, detail=""):
    if condition:
        PASS.append(label)
        print(f"  [PASS] {label}")
    else:
        FAIL.append((label, detail))
        print(f"  [FAIL] {label}  -- {detail}")


def expect_exception(label, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        FAIL.append((label, "expected an exception, none was raised"))
        print(f"  [FAIL] {label} -- expected an exception, none was raised")
    except Exception as e:
        PASS.append(label)
        print(f"  [PASS] {label} (raised {type(e).__name__}: {e})")


def section(title):
    print(f"\n=== {title} ===")


def main():
    section("0. Connectivity")
    check("DB connection works", db_connection.test_connection())
    reset_db()

    section("1. Patient registration")
    p1 = pm.register_patient("Anjali Sharma", "Female", "1990-04-12", "9876543210",
                              "12 MG Road, Ooty", "O+")
    check("Patient 1 created with valid id", isinstance(p1, int) and p1 > 0, p1)

    p2 = pm.register_patient("Ravi Kumar", "Male", "1985-11-02", "9123456780",
                              "45 Lake View, Ooty", "B+")
    check("Patient 2 created with valid id", isinstance(p2, int) and p2 > 0, p2)

    fetched = pm.get_patient(p1)
    check("Fetched patient matches registered name", fetched["full_name"] == "Anjali Sharma", fetched)

    section("1b. Patient validation edge cases")
    expect_exception("Reject bad phone number (9 digits)",
                      pm.register_patient, "Bad Phone", "Male", "1990-01-01", "123456789")
    expect_exception("Reject future date of birth",
                      pm.register_patient, "Future Baby", "Male", "2099-01-01", "9999999999")
    expect_exception("Reject invalid gender",
                      pm.register_patient, "Weird Gender", "Alien", "1990-01-01", "9999999991")
    expect_exception("Reject invalid blood group",
                      pm.register_patient, "Bad Blood", "Male", "1990-01-01", "9999999992",
                      "", "Z+")

    section("2. Doctor registration")
    doc1 = dm.register_doctor("Dr. Meera Iyer", "General Medicine", "9000000001", "300.00")
    check("Doctor 1 created", isinstance(doc1, int) and doc1 > 0, doc1)

    doc2 = dm.register_doctor("Dr. Suresh Babu", "Pediatrics", "9000000002", "400")
    check("Doctor 2 created", isinstance(doc2, int) and doc2 > 0, doc2)

    expect_exception("Reject negative consultation fee",
                      dm.register_doctor, "Dr. Bad Fee", "Cardiology", "9000000003", "-50")
    expect_exception("Reject bad doctor phone",
                      dm.register_doctor, "Dr. Bad Phone", "Cardiology", "900", "100")

    section("3. Visit creation / token assignment")
    visit1 = vm.create_visit(p1, doc1)
    check("Visit 1 token starts at 1", visit1["token_number"] == 1, visit1)

    visit2 = vm.create_visit(p2, doc1)
    check("Visit 2 token increments to 2", visit2["token_number"] == 2, visit2)

    # Same patient, different doctor, same day -> independent token sequence
    visit3 = vm.create_visit(p1, doc2)
    check("Visit 3 (different doctor) starts its own token at 1",
          visit3["token_number"] == 1, visit3)

    # Patient 1 now has two visits (core "one patient -> many visits" concept)
    history = pm.get_visit_history(p1)
    check("Patient 1 has 2 visits in history", len(history) == 2, history)

    expect_exception("Reject visit creation for nonexistent patient",
                      vm.create_visit, 999999, doc1)
    expect_exception("Reject visit creation for nonexistent doctor",
                      vm.create_visit, p1, 999999)

    section("4. Doctor consultation")
    queue_before = vm.get_queue(doc1)
    check("Doctor 1 queue has 2 waiting patients", len(queue_before) == 2, queue_before)

    dm.record_diagnosis(visit1["visit_id"], "Seasonal flu", "Advised rest and fluids")
    v1_after = vm.get_visit(visit1["visit_id"])
    check("Visit 1 status becomes Completed", v1_after["status"] == "Completed", v1_after)

    queue_after = vm.get_queue(doc1)
    check("Doctor 1 queue drops to 1 after consultation completed",
          len(queue_after) == 1, queue_after)

    expect_exception("Reject diagnosis for nonexistent visit",
                      dm.record_diagnosis, 999999, "x", "y")

    section("5. Pharmacy / prescriptions")
    med1 = rxm.add_medicine("Paracetamol 500mg", "5.00", 100)
    med2 = rxm.add_medicine("Cough Syrup 100ml", "45.50", 20)
    check("Medicine 1 created", isinstance(med1, int), med1)
    check("Medicine 2 created", isinstance(med2, int), med2)

    rxm.add_prescription(visit1["visit_id"], med1, "1 tab twice daily", 5, 10)
    rxm.add_prescription(visit1["visit_id"], med2, "10ml thrice daily", 5, 1)

    stock_after = rxm.get_medicine(med1)
    check("Stock deducted correctly after prescription (100 - 10 = 90)",
          stock_after["stock_quantity"] == 90, stock_after)

    expect_exception("Reject prescription exceeding available stock",
                      rxm.add_prescription, visit1["visit_id"], med2, "overdose", 1, 9999)

    expect_exception("Reject prescription with zero quantity",
                      rxm.add_prescription, visit1["visit_id"], med1, "x", 1, 0)

    section("6. Billing")
    bill1 = bm.generate_bill(visit1["visit_id"])
    expected_total = 300.00 + (5.00 * 10) + (45.50 * 1)
    check(f"Bill total correct (expected {expected_total})",
          float(bill1["total_amount"]) == expected_total, bill1)

    # Add another prescription, then regenerate the bill -> should update, not duplicate
    rxm.add_prescription(visit1["visit_id"], med1, "extra dose", 2, 5)
    bill1_updated = bm.generate_bill(visit1["visit_id"])
    check("Regenerating bill updates same bill_id (no duplicate row)",
          bill1_updated["bill_id"] == bill1["bill_id"], (bill1, bill1_updated))

    new_expected_total = expected_total + (5.00 * 5)
    check(f"Updated bill total reflects new prescription (expected {new_expected_total})",
          float(bill1_updated["total_amount"]) == new_expected_total, bill1_updated)

    bm.mark_paid(bill1_updated["bill_id"])
    paid_bill = bm.get_bill(bill1_updated["bill_id"])
    check("Bill marked Paid", paid_bill["payment_status"] == "Paid", paid_bill)

    receipt_text = bm.print_receipt(bill1_updated["bill_id"])
    check("Receipt text generation does not crash and contains patient name",
          "Anjali Sharma" in receipt_text, receipt_text[:200])

    expect_exception("Reject billing a nonexistent visit",
                      bm.generate_bill, 999999)

    section("7. Cross-cutting: patient visit history after billing")
    full_history = pm.get_visit_history(p1)
    check("Visit history still shows 2 visits after billing flow", len(full_history) == 2, full_history)

    section("RESULTS SUMMARY")
    print(f"\nPASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailed checks:")
        for label, detail in FAIL:
            print(f"  - {label}: {detail}")
    return len(FAIL) == 0


if __name__ == "__main__":
    try:
        ok = main()
        sys.exit(0 if ok else 1)
    except Exception:
        print("\n!!! UNHANDLED EXCEPTION DURING TEST RUN !!!")
        traceback.print_exc()
        sys.exit(2)
