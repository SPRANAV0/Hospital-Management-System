"""
reports_module.py
--------------------
Analytics and reporting queries for the Hospital Management System.
All queries return plain Python dicts/lists so they can be consumed by
the CLI, Flask views, or a PDF generator equally.
"""

from datetime import date, timedelta
from db_connection import fetch_all, fetch_one


# ─────────────────────────────────────────────
# 1. DAILY OPD SUMMARY
# ─────────────────────────────────────────────

def daily_opd_summary(target_date=None):
    """
    Total visits, completed, waiting, cancelled, and total revenue
    collected for a given date (defaults to today).
    """
    target_date = target_date or date.today()
    row = fetch_one(
        """
        SELECT
            COUNT(v.visit_id)                                         AS total_visits,
            SUM(v.status = 'Completed')                               AS completed,
            SUM(v.status = 'Waiting')                                 AS waiting,
            SUM(v.status = 'In Consultation')                         AS in_consultation,
            SUM(v.status = 'Cancelled')                               AS cancelled,
            COALESCE(SUM(CASE WHEN b.payment_status='Paid'
                              THEN b.total_amount ELSE 0 END), 0)     AS revenue_collected,
            COALESCE(SUM(b.total_amount), 0)                          AS revenue_total
        FROM visits v
        LEFT JOIN billing b ON b.visit_id = v.visit_id
        WHERE v.visit_date = %s
        """,
        (target_date,),
    )
    row["date"] = str(target_date)
    return row


# ─────────────────────────────────────────────
# 2. DOCTOR WORKLOAD REPORT (date range)
# ─────────────────────────────────────────────

def doctor_workload(start_date=None, end_date=None):
    """
    Per-doctor breakdown of visits, completed consultations and
    revenue earned over a date range (defaults to last 30 days).
    """
    end_date   = end_date   or date.today()
    start_date = start_date or (end_date - timedelta(days=30))
    return fetch_all(
        """
        SELECT
            d.doctor_id,
            d.full_name        AS doctor_name,
            d.specialization,
            COUNT(v.visit_id)  AS total_visits,
            SUM(v.status = 'Completed')  AS completed_visits,
            COALESCE(SUM(b.consultation_fee), 0) AS consultation_revenue,
            COALESCE(SUM(b.total_amount),     0) AS total_revenue
        FROM doctors d
        LEFT JOIN visits v ON v.doctor_id = d.doctor_id
                           AND v.visit_date BETWEEN %s AND %s
        LEFT JOIN billing b ON b.visit_id = v.visit_id
        GROUP BY d.doctor_id, d.full_name, d.specialization
        ORDER BY total_visits DESC
        """,
        (start_date, end_date),
    )


# ─────────────────────────────────────────────
# 3. REVENUE REPORT (daily totals, date range)
# ─────────────────────────────────────────────

def revenue_by_day(start_date=None, end_date=None):
    """
    Day-by-day revenue: consultation fees vs medicine charges vs total,
    split by Paid / Pending.
    """
    end_date   = end_date   or date.today()
    start_date = start_date or (end_date - timedelta(days=30))
    return fetch_all(
        """
        SELECT
            v.visit_date,
            COUNT(b.bill_id)                                              AS bills_generated,
            SUM(b.payment_status = 'Paid')                               AS bills_paid,
            COALESCE(SUM(b.consultation_fee), 0)                         AS consultation_fees,
            COALESCE(SUM(b.medicine_charges), 0)                         AS medicine_charges,
            COALESCE(SUM(b.total_amount), 0)                             AS gross_revenue,
            COALESCE(SUM(CASE WHEN b.payment_status='Paid'
                              THEN b.total_amount END), 0)               AS collected_revenue
        FROM billing b
        JOIN visits v ON v.visit_id = b.visit_id
        WHERE v.visit_date BETWEEN %s AND %s
        GROUP BY v.visit_date
        ORDER BY v.visit_date
        """,
        (start_date, end_date),
    )


# ─────────────────────────────────────────────
# 4. MEDICINE CONSUMPTION REPORT
# ─────────────────────────────────────────────

def medicine_consumption(start_date=None, end_date=None):
    """
    Which medicines were prescribed most, total units dispensed,
    and revenue generated, over the given date range.
    """
    end_date   = end_date   or date.today()
    start_date = start_date or (end_date - timedelta(days=30))
    return fetch_all(
        """
        SELECT
            m.medicine_id,
            m.medicine_name,
            m.unit_price,
            m.stock_quantity                    AS current_stock,
            COALESCE(SUM(pr.quantity), 0)       AS units_dispensed,
            COALESCE(SUM(pr.quantity * m.unit_price), 0) AS revenue
        FROM medicines m
        LEFT JOIN prescriptions pr ON pr.medicine_id = m.medicine_id
        LEFT JOIN visits v ON v.visit_id = pr.visit_id
                          AND v.visit_date BETWEEN %s AND %s
        GROUP BY m.medicine_id, m.medicine_name, m.unit_price, m.stock_quantity
        ORDER BY units_dispensed DESC
        """,
        (start_date, end_date),
    )


# ─────────────────────────────────────────────
# 5. LOW-STOCK ALERT
# ─────────────────────────────────────────────

def low_stock_medicines(threshold=10):
    """Medicines whose current stock is at or below the threshold."""
    return fetch_all(
        "SELECT * FROM medicines WHERE stock_quantity <= %s ORDER BY stock_quantity",
        (threshold,),
    )


# ─────────────────────────────────────────────
# 6. PATIENT VISIT FREQUENCY (top N patients)
# ─────────────────────────────────────────────

def top_patients(limit=10):
    """Patients with the most visits — useful for identifying frequent visitors."""
    return fetch_all(
        """
        SELECT
            p.patient_id,
            p.full_name,
            p.phone,
            p.blood_group,
            COUNT(v.visit_id)   AS total_visits,
            MAX(v.visit_date)   AS last_visit
        FROM patients p
        LEFT JOIN visits v ON v.patient_id = p.patient_id
        GROUP BY p.patient_id, p.full_name, p.phone, p.blood_group
        ORDER BY total_visits DESC
        LIMIT %s
        """,
        (limit,),
    )


# ─────────────────────────────────────────────
# 7. OUTSTANDING (UNPAID) BILLS
# ─────────────────────────────────────────────

def outstanding_bills():
    """All bills that remain in Pending status, with patient and doctor context."""
    return fetch_all(
        """
        SELECT
            b.bill_id,
            b.total_amount,
            b.bill_date,
            v.visit_date,
            p.patient_id,
            p.full_name  AS patient_name,
            p.phone,
            d.full_name  AS doctor_name
        FROM billing b
        JOIN visits  v ON v.visit_id   = b.visit_id
        JOIN patients p ON p.patient_id = v.patient_id
        JOIN doctors  d ON d.doctor_id  = v.doctor_id
        WHERE b.payment_status = 'Pending'
        ORDER BY b.bill_date
        """,
    )
