"""
visit_module.py
------------------
Visit / OPD management: creating new visits, assigning token numbers,
tracking the patient queue, and updating visit status.

Core concept: One Patient -> Multiple Visits.
"""

from datetime import date
from db_connection import fetch_all, fetch_one, get_cursor, run_with_retry
from patient_module import get_patient
from doctor_module import get_doctor


class ValidationError(Exception):
    pass


def _create_visit_txn(patient_id, doctor_id, visit_date):
    """
    Atomically assigns the next token for (doctor_id, visit_date) using a
    single-row counter (INSERT ... ON DUPLICATE KEY UPDATE) and inserts
    the visit in the same transaction.

    This single-row PK update is far less prone to InnoDB deadlocks than
    scanning visits with SELECT MAX() ... FOR UPDATE, which takes a gap
    lock across the whole (doctor_id, visit_date) range and deadlocks
    under concurrent inserts (see docs/DEFECTS.md, Defect #2).
    """
    with get_cursor(commit=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO token_counters (doctor_id, visit_date, last_token)
            VALUES (%s, %s, 1)
            ON DUPLICATE KEY UPDATE last_token = last_token + 1
            """,
            (doctor_id, visit_date),
        )
        cursor.execute(
            "SELECT last_token FROM token_counters WHERE doctor_id = %s AND visit_date = %s",
            (doctor_id, visit_date),
        )
        next_token = cursor.fetchone()["last_token"]

        cursor.execute(
            """
            INSERT INTO visits (patient_id, doctor_id, token_number, visit_date, status)
            VALUES (%s, %s, %s, %s, 'Waiting')
            """,
            (patient_id, doctor_id, next_token, visit_date),
        )
        visit_id = cursor.lastrowid

    return {"visit_id": visit_id, "token_number": next_token}


def create_visit(patient_id, doctor_id, visit_date=None):
    """
    Create a new OPD visit for a patient with a given doctor.
    Assigns the next token number for that doctor on that day.
    """
    visit_date = visit_date or date.today()

    if not get_patient(patient_id):
        raise ValidationError(f"No patient found with id {patient_id}.")

    doctor = get_doctor(doctor_id)
    if not doctor:
        raise ValidationError(f"No doctor found with id {doctor_id}.")
    if not doctor["is_available"]:
        raise ValidationError(f"Doctor {doctor['full_name']} is not available today.")

    return run_with_retry(_create_visit_txn, patient_id, doctor_id, visit_date)


def get_visit(visit_id):
    return fetch_one(
        """
        SELECT v.*, p.full_name AS patient_name, d.full_name AS doctor_name,
               d.consultation_fee
        FROM visits v
        JOIN patients p ON p.patient_id = v.patient_id
        JOIN doctors d ON d.doctor_id = v.doctor_id
        WHERE v.visit_id = %s
        """,
        (visit_id,),
    )


def get_queue(doctor_id, visit_date=None):
    """Patients currently waiting/in-consultation for a doctor, ordered by token."""
    visit_date = visit_date or date.today()
    return fetch_all(
        """
        SELECT v.visit_id, v.token_number, v.status, p.full_name
        FROM visits v
        JOIN patients p ON p.patient_id = v.patient_id
        WHERE v.doctor_id = %s AND v.visit_date = %s
              AND v.status IN ('Waiting', 'In Consultation')
        ORDER BY v.token_number
        """,
        (doctor_id, visit_date),
    )


def update_status(visit_id, status):
    valid = {"Waiting", "In Consultation", "Completed", "Cancelled"}
    if status not in valid:
        raise ValidationError(f"Status must be one of {valid}.")

    with get_cursor(commit=True) as (conn, cursor):
        cursor.execute(
            "UPDATE visits SET status = %s WHERE visit_id = %s", (status, visit_id)
        )
        if cursor.rowcount == 0:
            raise ValidationError(f"No visit found with id {visit_id}.")
    return True
