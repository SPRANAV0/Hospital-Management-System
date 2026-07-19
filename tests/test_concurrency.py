"""
test_concurrency.py
----------------------
Stress-tests token assignment: fires many simultaneous create_visit()
calls for the SAME doctor/day from separate threads (separate DB
connections, like separate receptionist terminals) and checks that:
  - every visit gets a token
  - no two visits for the same doctor/day share a token
  - tokens form a clean contiguous sequence (no double-increments)
"""

import sys
import os
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import patient_module as pm
import doctor_module as dm
import visit_module as vm
from test_helpers import reset_db

NUM_THREADS = 25

results = []
errors = []
lock = threading.Lock()


def worker(patient_id, doctor_id):
    try:
        visit = vm.create_visit(patient_id, doctor_id)
        with lock:
            results.append(visit["token_number"])
    except Exception as e:
        with lock:
            errors.append(str(e))


def main():
    reset_db()
    doc_id = dm.register_doctor("Dr. Concurrency Test", "Stress Testing", "9111111111", "200")

    patient_ids = [
        pm.register_patient(f"Load Test Patient {i}", "Other", "1990-01-01", f"90000{i:05d}")
        for i in range(NUM_THREADS)
    ]

    threads = [
        threading.Thread(target=worker, args=(pid, doc_id)) for pid in patient_ids
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"Threads launched : {NUM_THREADS}")
    print(f"Successful visits: {len(results)}")
    print(f"Errors           : {len(errors)}")
    if errors:
        print("Sample errors:", errors[:5])

    tokens_sorted = sorted(results)
    expected = list(range(1, NUM_THREADS + 1))

    has_duplicates = len(set(tokens_sorted)) != len(tokens_sorted)
    matches_expected = tokens_sorted == expected

    print(f"Tokens assigned  : {tokens_sorted}")
    print(f"Has duplicates?  : {has_duplicates}")
    print(f"Clean 1..N seq?  : {matches_expected}")

    ok = (not has_duplicates) and matches_expected and not errors
    print("\nRESULT:", "PASS - no race condition detected" if ok else "FAIL - race condition or error detected")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
