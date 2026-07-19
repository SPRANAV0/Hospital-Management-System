"""
doctor_module.py
------------------
Doctor registration, availability, and doctor-facing queries
(viewing assigned patients, recording diagnosis/prescriptions).
"""

import re
from decimal import Decimal, InvalidOperation
from db_connection import fetch_all, fetch_one, execute


class ValidationError(Exception):
    pass


def _validate_doctor_input(full_name, specialization, phone, consultation_fee):
    if not full_name or not full_name.strip():
        raise ValidationError("Doctor name is required.")
    if not specialization or not specialization.strip():
        raise ValidationError("Specialization is required.")
    if not re.fullmatch(r"\d{10}", phone or ""):
        raise ValidationError("Phone number must be exactly 10 digits.")
    try:
        fee = Decimal(str(consultation_fee))
    except InvalidOperation:
        raise ValidationError("Consultation fee must be a number.")
    if fee < 0:
        raise ValidationError("Consultation fee cannot be negative.")
    return fee


def register_doctor(full_name, specialization, phone, consultation_fee):
    fee = _validate_doctor_input(full_name, specialization, phone, consultation_fee)
    result = execute(
        """
        INSERT INTO doctors (full_name, specialization, phone, consultation_fee)
        VALUES (%s, %s, %s, %s)
        """,
        (full_name.strip(), specialization.strip(), phone, fee),
    )
    return result["lastrowid"]


def get_doctor(doctor_id):
    return fetch_one("SELECT * FROM doctors WHERE doctor_id = %s", (doctor_id,))


def list_doctors(available_only=False):
    if available_only:
        return fetch_all("SELECT * FROM doctors WHERE is_available = TRUE ORDER BY full_name")
    return fetch_all("SELECT * FROM doctors ORDER BY full_name")


def set_availability(doctor_id, available: bool):
    result = execute(
        "UPDATE doctors SET is_available = %s WHERE doctor_id = %s",
        (available, doctor_id),
    )
    return result["rowcount"]


def get_assigned_patients(doctor_id, visit_date=None):
    """View the doctor's patient queue for a given day (defaults to today)."""
    if visit_date:
        return fetch_all(
            """
            SELECT v.visit_id, v.token_number, v.status, v.visit_time,
                   p.patient_id, p.full_name, p.gender, p.dob
            FROM visits v
            JOIN patients p ON p.patient_id = v.patient_id
            WHERE v.doctor_id = %s AND v.visit_date = %s
            ORDER BY v.token_number
            """,
            (doctor_id, visit_date),
        )
    return fetch_all(
        """
        SELECT v.visit_id, v.token_number, v.status, v.visit_time,
               p.patient_id, p.full_name, p.gender, p.dob
        FROM visits v
        JOIN patients p ON p.patient_id = v.patient_id
        WHERE v.doctor_id = %s AND v.visit_date = CURDATE()
        ORDER BY v.token_number
        """,
        (doctor_id,),
    )


def record_diagnosis(visit_id, diagnosis, notes=""):
    """Doctor records diagnosis/notes for a visit and marks consultation complete."""
    result = execute(
        """
        UPDATE visits
        SET diagnosis = %s, notes = %s, status = 'Completed'
        WHERE visit_id = %s
        """,
        (diagnosis, notes, visit_id),
    )
    if result["rowcount"] == 0:
        raise ValidationError(f"No visit found with id {visit_id}.")
    return result["rowcount"]
