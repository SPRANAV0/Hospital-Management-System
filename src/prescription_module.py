"""
prescription_module.py
------------------------
Pharmacy inventory (medicines) and prescription recording for a visit.
"""

from decimal import Decimal, InvalidOperation
from db_connection import fetch_all, fetch_one, execute, get_cursor


class ValidationError(Exception):
    pass


def add_medicine(medicine_name, unit_price, stock_quantity=0):
    try:
        price = Decimal(str(unit_price))
    except InvalidOperation:
        raise ValidationError("Unit price must be a number.")
    if price < 0:
        raise ValidationError("Unit price cannot be negative.")
    if stock_quantity < 0:
        raise ValidationError("Stock quantity cannot be negative.")

    with get_cursor(commit=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO medicines (medicine_name, unit_price, stock_quantity)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                unit_price     = VALUES(unit_price),
                stock_quantity = stock_quantity + VALUES(stock_quantity)
            """,
            (medicine_name.strip(), price, stock_quantity),
        )
        # lastrowid == 0 on a no-insert DUK update; look it up in that case
        if cursor.lastrowid:
            return cursor.lastrowid
        cursor.execute(
            "SELECT medicine_id FROM medicines WHERE medicine_name = %s",
            (medicine_name.strip(),),
        )
        return cursor.fetchone()["medicine_id"]


def restock_medicine(medicine_id, additional_quantity):
    if additional_quantity <= 0:
        raise ValidationError("Restock quantity must be positive.")
    result = execute(
        "UPDATE medicines SET stock_quantity = stock_quantity + %s WHERE medicine_id = %s",
        (additional_quantity, medicine_id),
    )
    if result["rowcount"] == 0:
        raise ValidationError(f"No medicine found with id {medicine_id}.")
    return result["rowcount"]


def list_medicines():
    return fetch_all("SELECT * FROM medicines ORDER BY medicine_name")


def get_medicine(medicine_id):
    return fetch_one("SELECT * FROM medicines WHERE medicine_id = %s", (medicine_id,))


def add_prescription(visit_id, medicine_id, dosage, duration_days, quantity):
    """
    Record a prescribed medicine for a visit and deduct it from pharmacy stock.
    Stock check + deduction + insert happen in a single transaction so stock
    can never go negative even under concurrent prescribing.
    """
    if quantity <= 0:
        raise ValidationError("Quantity must be positive.")
    if duration_days <= 0:
        raise ValidationError("Duration (days) must be positive.")

    with get_cursor(commit=True) as (conn, cursor):
        cursor.execute(
            "SELECT stock_quantity, medicine_name FROM medicines WHERE medicine_id = %s FOR UPDATE",
            (medicine_id,),
        )
        med = cursor.fetchone()
        if med is None:
            raise ValidationError(f"No medicine found with id {medicine_id}.")
        if med["stock_quantity"] < quantity:
            raise ValidationError(
                f"Insufficient stock for {med['medicine_name']}: "
                f"requested {quantity}, available {med['stock_quantity']}."
            )

        cursor.execute(
            """
            INSERT INTO prescriptions (visit_id, medicine_id, dosage, duration_days, quantity)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (visit_id, medicine_id, dosage, duration_days, quantity),
        )
        prescription_id = cursor.lastrowid

        cursor.execute(
            "UPDATE medicines SET stock_quantity = stock_quantity - %s WHERE medicine_id = %s",
            (quantity, medicine_id),
        )

    return prescription_id


def get_prescriptions_for_visit(visit_id):
    return fetch_all(
        """
        SELECT pr.prescription_id, pr.dosage, pr.duration_days, pr.quantity,
               m.medicine_id, m.medicine_name, m.unit_price,
               (m.unit_price * pr.quantity) AS line_total
        FROM prescriptions pr
        JOIN medicines m ON m.medicine_id = pr.medicine_id
        WHERE pr.visit_id = %s
        """,
        (visit_id,),
    )
