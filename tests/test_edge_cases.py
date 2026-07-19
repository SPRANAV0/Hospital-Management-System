"""
test_edge_cases.py
---------------------
Probes additional edge cases beyond the main functional suite:
  - None / missing inputs that aren't strings (so the regex/string
    guards in the validators might not catch them)
  - creating a visit with an explicitly unavailable doctor
  - regenerating a bill after it has already been marked Paid
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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
        print(f"  [FAIL] {label} -- {detail}")


def main():
    reset_db()
    print("\n=== Edge case: dob=None ===")
    try:
        pm.register_patient("None DOB Patient", "Male", None, "9888800001")
        check("register_patient(dob=None) raises a clean ValidationError", False,
              "no exception raised at all")
    except pm.ValidationError as e:
        check("register_patient(dob=None) raises a clean ValidationError", True, str(e))
    except Exception as e:
        check("register_patient(dob=None) raises a clean ValidationError", False,
              f"raised {type(e).__name__} instead: {e}")

    print("\n=== Edge case: phone=None ===")
    try:
        pm.register_patient("None Phone Patient", "Male", "1990-01-01", None)
        check("register_patient(phone=None) raises a clean ValidationError", False,
              "no exception raised at all")
    except pm.ValidationError as e:
        check("register_patient(phone=None) raises a clean ValidationError", True, str(e))
    except Exception as e:
        check("register_patient(phone=None) raises a clean ValidationError", False,
              f"raised {type(e).__name__} instead: {e}")

    print("\n=== Edge case: visit with unavailable doctor ===")
    doc_id = dm.register_doctor("Dr. On Leave", "Dermatology", "9888800002", "250")
    dm.set_availability(doc_id, False)
    patient_id = pm.register_patient("Edge Case Patient", "Female", "1992-05-05", "9888800003")
    try:
        vm.create_visit(patient_id, doc_id)
        check("create_visit rejects an unavailable doctor", False, "no exception raised")
    except vm.ValidationError as e:
        check("create_visit rejects an unavailable doctor", True, str(e))
    except Exception as e:
        check("create_visit rejects an unavailable doctor", False,
              f"raised {type(e).__name__} instead: {e}")

    print("\n=== Edge case: regenerate bill after marking it Paid ===")
    dm.set_availability(doc_id, True)
    visit = vm.create_visit(patient_id, doc_id)
    med_id = rxm.add_medicine("Edge Case Tablet", "10.00", 50)
    rxm.add_prescription(visit["visit_id"], med_id, "1 tab", 1, 2)  # 20.00
    bill = bm.generate_bill(visit["visit_id"])
    bm.mark_paid(bill["bill_id"])

    # Now sneak in another prescription after payment and try to regenerate
    rxm.add_prescription(visit["visit_id"], med_id, "extra", 1, 5)  # +50.00
    try:
        bm.generate_bill(visit["visit_id"])
        check("generate_bill refuses to alter an already-Paid bill", False,
              "no exception raised -- the paid total was silently changed")
    except bm.ValidationError as e:
        check("generate_bill refuses to alter an already-Paid bill", True, str(e))
    except Exception as e:
        check("generate_bill refuses to alter an already-Paid bill", False,
              f"raised {type(e).__name__} instead: {e}")

    print(f"\nPASSED: {len(PASS)}  FAILED: {len(FAIL)}")
    return FAIL


if __name__ == "__main__":
    fails = main()
    sys.exit(1 if fails else 0)
