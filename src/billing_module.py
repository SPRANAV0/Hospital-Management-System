"""
billing_module.py
--------------------
Automatic bill generation: consultation fee (from the assigned doctor)
plus medicine charges (sum of all prescriptions for the visit).
"""

from decimal import Decimal
from db_connection import fetch_all, fetch_one, get_cursor
from visit_module import get_visit
from prescription_module import get_prescriptions_for_visit


class ValidationError(Exception):
    pass


def generate_bill(visit_id):
    """
    Generate (or regenerate) the bill for a visit:
    total = doctor's consultation_fee + sum(medicine unit_price * quantity)

    Safe to call again after a new prescription is added to the same visit;
    it recalculates and updates the existing bill rather than duplicating it.

    Once a bill has been marked Paid it is treated as closed: this raises
    ValidationError rather than silently changing the amount on a receipt
    the patient has already been given and paid against. Use a fresh visit
    (or a dedicated refund/adjustment workflow) for any post-payment changes.
    """
    visit = get_visit(visit_id)
    if not visit:
        raise ValidationError(f"No visit found with id {visit_id}.")

    existing_bill = get_bill_for_visit(visit_id)
    if existing_bill and existing_bill["payment_status"] == "Paid":
        raise ValidationError(
            f"Bill {existing_bill['bill_id']} for visit {visit_id} is already Paid "
            f"and cannot be regenerated. Start a new visit for further charges."
        )

    consultation_fee = Decimal(str(visit["consultation_fee"]))

    prescriptions = get_prescriptions_for_visit(visit_id)
    medicine_charges = sum(
        (Decimal(str(p["line_total"])) for p in prescriptions), Decimal("0.00")
    )

    total_amount = consultation_fee + medicine_charges

    with get_cursor(commit=True) as (conn, cursor):
        cursor.execute("SELECT bill_id FROM billing WHERE visit_id = %s", (visit_id,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                """
                UPDATE billing
                SET consultation_fee = %s, medicine_charges = %s, total_amount = %s
                WHERE visit_id = %s
                """,
                (consultation_fee, medicine_charges, total_amount, visit_id),
            )
            bill_id = existing["bill_id"]
        else:
            cursor.execute(
                """
                INSERT INTO billing (visit_id, consultation_fee, medicine_charges, total_amount)
                VALUES (%s, %s, %s, %s)
                """,
                (visit_id, consultation_fee, medicine_charges, total_amount),
            )
            bill_id = cursor.lastrowid

    return get_bill(bill_id)


def get_bill(bill_id):
    return fetch_one("SELECT * FROM billing WHERE bill_id = %s", (bill_id,))


def get_bill_for_visit(visit_id):
    return fetch_one("SELECT * FROM billing WHERE visit_id = %s", (visit_id,))


def mark_paid(bill_id):
    with get_cursor(commit=True) as (conn, cursor):
        cursor.execute(
            "UPDATE billing SET payment_status = 'Paid' WHERE bill_id = %s", (bill_id,)
        )
        if cursor.rowcount == 0:
            raise ValidationError(f"No bill found with id {bill_id}.")
    return True


def print_receipt(bill_id):
    """Return a formatted text receipt for a given bill (also used by the CLI)."""
    bill = get_bill(bill_id)
    if not bill:
        raise ValidationError(f"No bill found with id {bill_id}.")

    visit = get_visit(bill["visit_id"])
    prescriptions = get_prescriptions_for_visit(bill["visit_id"])

    lines = []
    lines.append("=" * 50)
    lines.append("           HOSPITAL OPD RECEIPT")
    lines.append("=" * 50)
    lines.append(f"Bill ID        : {bill['bill_id']}")
    lines.append(f"Visit ID       : {visit['visit_id']}  (Token #{visit['token_number']})")
    lines.append(f"Patient        : {visit['patient_name']}")
    lines.append(f"Doctor         : {visit['doctor_name']}")
    lines.append(f"Visit Date     : {visit['visit_date']}")
    lines.append("-" * 50)
    lines.append(f"Consultation Fee        : {bill['consultation_fee']:>10}")
    if prescriptions:
        lines.append("Medicines:")
        for p in prescriptions:
            lines.append(
                f"  - {p['medicine_name']:<20} x{p['quantity']:<3} "
                f"@ {p['unit_price']:>8} = {p['line_total']:>10}"
            )
    lines.append(f"Medicine Charges        : {bill['medicine_charges']:>10}")
    lines.append("-" * 50)
    lines.append(f"TOTAL AMOUNT             : {bill['total_amount']:>10}")
    lines.append(f"Payment Status           : {bill['payment_status']}")
    lines.append("=" * 50)
    return "\n".join(lines)
