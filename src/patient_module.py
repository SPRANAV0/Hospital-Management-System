"""
patient_module.py
------------------
Patient registration and lookup.
"""

import re
from datetime import date
from db_connection import fetch_all, fetch_one, execute

VALID_GENDERS = {"Male", "Female", "Other"}
VALID_BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", ""}


class ValidationError(Exception):
    pass


def _validate_patient_input(full_name, gender, dob, phone, blood_group):
    if not full_name or not full_name.strip():
        raise ValidationError("Full name is required.")

    if gender not in VALID_GENDERS:
        raise ValidationError(f"Gender must be one of {VALID_GENDERS}.")

    if not re.fullmatch(r"\d{10}", phone or ""):
        raise ValidationError("Phone number must be exactly 10 digits.")

    if dob is None:
        raise ValidationError("Date of birth is required.")

    if isinstance(dob, str):
        try:
            dob = date.fromisoformat(dob)
        except ValueError:
            raise ValidationError("Date of birth must be in YYYY-MM-DD format.")
    elif not isinstance(dob, date):
        raise ValidationError("Date of birth must be a date or a YYYY-MM-DD string.")

    if dob > date.today():
        raise ValidationError("Date of birth cannot be in the future.")

    if blood_group and blood_group not in VALID_BLOOD_GROUPS:
        raise ValidationError(f"Blood group must be one of {VALID_BLOOD_GROUPS}.")

    return dob


def register_patient(full_name, gender, dob, phone, address="", blood_group=""):
    """
    Register a new patient. dob can be a date object or 'YYYY-MM-DD' string.
    Returns the new patient_id.
    """
    dob = _validate_patient_input(full_name, gender, dob, phone, blood_group)

    result = execute(
        """
        INSERT INTO patients (full_name, gender, dob, phone, address, blood_group)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (full_name.strip(), gender, dob, phone, address, blood_group or None),
    )
    return result["lastrowid"]


def get_patient(patient_id):
    return fetch_one("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))


def search_patients(name=None, phone=None):
    """Search patients by partial name and/or exact phone number."""
    clauses = []
    params = []

    if name:
        clauses.append("full_name LIKE %s")
        params.append(f"%{name}%")
    if phone:
        clauses.append("phone = %s")
        params.append(phone)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return fetch_all(f"SELECT * FROM patients {where_sql} ORDER BY patient_id", params)


def update_patient(patient_id, **fields):
    """Update arbitrary patient fields. e.g. update_patient(5, phone='9876543210')"""
    if not fields:
        return 0

    allowed = {"full_name", "gender", "dob", "phone", "address", "blood_group"}
    bad_fields = set(fields) - allowed
    if bad_fields:
        raise ValidationError(f"Cannot update fields: {bad_fields}")

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    params = list(fields.values()) + [patient_id]
    result = execute(f"UPDATE patients SET {set_clause} WHERE patient_id = %s", params)
    return result["rowcount"]


def get_visit_history(patient_id):
    """One patient -> multiple visits: full visit history with doctor names."""
    return fetch_all(
        """
        SELECT v.visit_id, v.visit_date, v.visit_time, v.status,
               v.diagnosis, d.full_name AS doctor_name, d.specialization
        FROM visits v
        JOIN doctors d ON d.doctor_id = v.doctor_id
        WHERE v.patient_id = %s
        ORDER BY v.visit_date DESC, v.visit_time DESC
        """,
        (patient_id,),
    )
