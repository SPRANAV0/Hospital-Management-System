"""
test_pharmacy_concurrency.py
-------------------------------
Stress-tests stock deduction: many threads simultaneously try to
prescribe the SAME medicine, with combined demand that exceeds stock.
Confirms stock never goes negative and the exact right number of
requests succeed/fail.
"""

import sys
import os
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import patient_module as pm
import doctor_module as dm
import visit_module as vm
import prescription_module as rxm
from test_helpers import reset_db

NUM_THREADS = 30
STOCK = 20          # only enough for 20 of the 30 requests (qty 1 each)

success = []
failure = []
lock = threading.Lock()


def worker(visit_id, medicine_id):
    try:
        rxm.add_prescription(visit_id, medicine_id, "1 tab", 1, 1)
        with lock:
            success.append(1)
    except Exception as e:
        with lock:
            failure.append(str(e))


def main():
    reset_db()
    doc_id = dm.register_doctor("Dr. Stock Test", "Pharmacology", "9222222222", "100")
    patient_id = pm.register_patient("Stock Test Patient", "Other", "1990-01-01", "9333333333")
    visit = vm.create_visit(patient_id, doc_id)

    medicine_id = rxm.add_medicine("Stress Test Tablet", "2.00", STOCK)

    threads = [
        threading.Thread(target=worker, args=(visit["visit_id"], medicine_id))
        for _ in range(NUM_THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final_stock = rxm.get_medicine(medicine_id)["stock_quantity"]

    print(f"Requests fired      : {NUM_THREADS}")
    print(f"Succeeded           : {len(success)} (expected {STOCK})")
    print(f"Failed (no stock)   : {len(failure)} (expected {NUM_THREADS - STOCK})")
    print(f"Final stock in DB   : {final_stock} (expected 0)")

    ok = (
        len(success) == STOCK
        and len(failure) == NUM_THREADS - STOCK
        and final_stock == 0
    )
    print("\nRESULT:", "PASS - stock deduction is race-free" if ok else "FAIL - overselling / stock corruption detected")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
