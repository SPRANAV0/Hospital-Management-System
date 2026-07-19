"""
app.py
--------
Flask web interface for the Hospital Management System.

Run:  cd src && python3 app.py
Then open:  http://localhost:5000
"""

import os
import sys
from datetime import date, timedelta

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort)

sys.path.insert(0, os.path.dirname(__file__))

import patient_module      as pm
import doctor_module       as dm
import visit_module        as vm
import prescription_module as rxm
import billing_module      as bm
import reports_module      as rm
from db_connection import fetch_all, fetch_one

app = Flask(__name__)
app.secret_key = os.environ.get("HMS_SECRET_KEY", "hms-dev-secret-change-in-prod")


# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────

@app.route("/")
def dashboard():
    today = date.today()
    summary     = rm.daily_opd_summary(today)
    low_stock   = rm.low_stock_medicines(threshold=10)
    outstanding = rm.outstanding_bills()

    # Full queue (all statuses) for today's display
    queue = fetch_all(
        """
        SELECT v.visit_id, v.token_number, v.status,
               p.full_name AS patient_name, d.full_name AS doctor_name
        FROM visits v
        JOIN patients p ON p.patient_id = v.patient_id
        JOIN doctors  d ON d.doctor_id  = v.doctor_id
        WHERE v.visit_date = %s
        ORDER BY v.token_number
        """,
        (today,),
    )
    return render_template("dashboard.html", today=today, summary=summary,
                           queue=queue, low_stock=low_stock, outstanding=outstanding)


# ──────────────────────────────────────────────
# PATIENTS
# ──────────────────────────────────────────────

@app.route("/patients")
def patients_list():
    q     = request.args.get("q", "").strip()
    phone = request.args.get("phone", "").strip()
    patients = pm.search_patients(q or None, phone or None)
    return render_template("patients_list.html", patients=patients, q=q, phone=phone)


@app.route("/patients/new", methods=["GET", "POST"])
def patient_new():
    form = {}
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            pid = pm.register_patient(
                form.get("full_name", ""),
                form.get("gender", ""),
                form.get("dob", ""),
                form.get("phone", ""),
                form.get("address", ""),
                form.get("blood_group", ""),
            )
            flash(f"Patient registered successfully (ID #{pid}).", "success")
            return redirect(url_for("patient_detail", patient_id=pid))
        except pm.ValidationError as e:
            flash(str(e), "error")
    return render_template("patient_form.html", form=form)


@app.route("/patients/<int:patient_id>")
def patient_detail(patient_id):
    patient = pm.get_patient(patient_id)
    if not patient:
        abort(404)
    visits = pm.get_visit_history(patient_id)
    return render_template("patient_detail.html", patient=patient, visits=visits)


# ──────────────────────────────────────────────
# DOCTORS
# ──────────────────────────────────────────────

@app.route("/doctors")
def doctors_list():
    doctors = dm.list_doctors()
    return render_template("doctors_list.html", doctors=doctors)


@app.route("/doctors/new", methods=["GET", "POST"])
def doctor_new():
    form = {}
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            did = dm.register_doctor(
                form.get("full_name", ""),
                form.get("specialization", ""),
                form.get("phone", ""),
                form.get("consultation_fee", 0),
            )
            flash(f"Doctor registered successfully (ID #{did}).", "success")
            return redirect(url_for("doctors_list"))
        except dm.ValidationError as e:
            flash(str(e), "error")
    return render_template("doctor_form.html", form=form)


@app.route("/doctors/<int:doctor_id>/toggle")
def doctor_toggle(doctor_id):
    doc = dm.get_doctor(doctor_id)
    if not doc:
        abort(404)
    dm.set_availability(doctor_id, not doc["is_available"])
    status = "available" if not doc["is_available"] else "unavailable"
    flash(f"{doc['full_name']} marked as {status}.", "info")
    return redirect(url_for("doctors_list"))


# ──────────────────────────────────────────────
# VISITS / OPD
# ──────────────────────────────────────────────

@app.route("/visits")
def visits_list():
    filter_date = request.args.get("date", str(date.today()))
    visits = fetch_all(
        """
        SELECT v.visit_id, v.token_number, v.visit_date, v.status, v.diagnosis,
               p.full_name AS patient_name, d.full_name AS doctor_name
        FROM visits v
        JOIN patients p ON p.patient_id = v.patient_id
        JOIN doctors  d ON d.doctor_id  = v.doctor_id
        WHERE v.visit_date = %s
        ORDER BY v.token_number
        """,
        (filter_date,),
    )
    return render_template("visits_list.html", visits=visits, filter_date=filter_date)


@app.route("/visits/new", methods=["GET", "POST"])
def visit_new():
    if request.method == "POST":
        try:
            patient_id = int(request.form["patient_id"])
            doctor_id  = int(request.form["doctor_id"])
            visit_date_str = request.form.get("visit_date", "")
            vdate = date.fromisoformat(visit_date_str) if visit_date_str else date.today()
            result = vm.create_visit(patient_id, doctor_id, vdate)
            flash(f"Visit created — Token #{result['token_number']} assigned.", "success")
            return redirect(url_for("visit_detail", visit_id=result["visit_id"]))
        except vm.ValidationError as e:
            flash(str(e), "error")
        except Exception as e:
            flash(f"Unexpected error: {e}", "error")

    patients = pm.search_patients()
    doctors  = dm.list_doctors(available_only=False)
    preselect_patient = request.args.get("patient_id", "")
    return render_template("visit_form.html", patients=patients, doctors=doctors,
                           today=str(date.today()), preselect_patient=preselect_patient)


@app.route("/visits/<int:visit_id>")
def visit_detail(visit_id):
    visit = vm.get_visit(visit_id)
    if not visit:
        abort(404)
    prescriptions = rxm.get_prescriptions_for_visit(visit_id)
    medicines     = rxm.list_medicines()
    bill          = bm.get_bill_for_visit(visit_id)
    return render_template("visit_detail.html", visit=visit, prescriptions=prescriptions,
                           medicines=medicines, bill=bill)


@app.route("/visits/<int:visit_id>/status/<status>")
def visit_status(visit_id, status):
    try:
        vm.update_status(visit_id, status)
        flash(f"Visit status updated to '{status}'.", "success")
    except vm.ValidationError as e:
        flash(str(e), "error")
    return redirect(url_for("visit_detail", visit_id=visit_id))


@app.route("/visits/<int:visit_id>/diagnose", methods=["POST"])
def visit_diagnose(visit_id):
    diagnosis = request.form.get("diagnosis", "").strip()
    notes     = request.form.get("notes", "").strip()
    try:
        dm.record_diagnosis(visit_id, diagnosis, notes)
        flash("Diagnosis saved and visit marked Completed.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("visit_detail", visit_id=visit_id))


@app.route("/visits/<int:visit_id>/prescribe", methods=["POST"])
def visit_prescribe(visit_id):
    try:
        medicine_id   = int(request.form["medicine_id"])
        dosage        = request.form.get("dosage", "")
        duration_days = int(request.form["duration_days"])
        quantity      = int(request.form["quantity"])
        rxm.add_prescription(visit_id, medicine_id, dosage, duration_days, quantity)
        flash("Prescription added.", "success")
    except rxm.ValidationError as e:
        flash(str(e), "error")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("visit_detail", visit_id=visit_id))


@app.route("/visits/<int:visit_id>/bill")
def visit_generate_bill(visit_id):
    try:
        bill = bm.generate_bill(visit_id)
        flash(f"Bill generated — Total ₹{bill['total_amount']}.", "success")
    except bm.ValidationError as e:
        flash(str(e), "error")
    return redirect(url_for("visit_detail", visit_id=visit_id))


# ──────────────────────────────────────────────
# PHARMACY
# ──────────────────────────────────────────────

@app.route("/pharmacy")
def pharmacy_list():
    medicines = rxm.list_medicines()
    return render_template("pharmacy_list.html", medicines=medicines)


@app.route("/pharmacy/add", methods=["GET", "POST"])
def pharmacy_add():
    if request.method == "POST":
        try:
            mid = rxm.add_medicine(
                request.form["medicine_name"],
                request.form["unit_price"],
                int(request.form.get("stock_quantity", 0)),
            )
            flash(f"Medicine added (ID #{mid}).", "success")
            return redirect(url_for("pharmacy_list"))
        except rxm.ValidationError as e:
            flash(str(e), "error")
    return render_template("pharmacy_form.html")


@app.route("/pharmacy/<int:medicine_id>/restock", methods=["GET", "POST"])
def pharmacy_restock(medicine_id):
    med = rxm.get_medicine(medicine_id)
    if not med:
        abort(404)
    if request.method == "POST":
        qty = request.form.get("quantity", "0")
        try:
            rxm.restock_medicine(medicine_id, int(qty))
            flash(f"Restocked {med['medicine_name']} by {qty} units.", "success")
            return redirect(url_for("pharmacy_list"))
        except rxm.ValidationError as e:
            flash(str(e), "error")
    # Simple inline form via GET
    return render_template("pharmacy_restock.html", med=med)


# ──────────────────────────────────────────────
# BILLING
# ──────────────────────────────────────────────

@app.route("/billing")
def billing_list():
    filter_status = request.args.get("status", "")
    where = "WHERE b.payment_status = %s" if filter_status else ""
    params = (filter_status,) if filter_status else ()
    bills = fetch_all(
        f"""
        SELECT b.bill_id, b.visit_id, b.consultation_fee, b.medicine_charges,
               b.total_amount, b.payment_status, b.bill_date,
               v.visit_date, p.full_name AS patient_name, d.full_name AS doctor_name
        FROM billing b
        JOIN visits  v ON v.visit_id   = b.visit_id
        JOIN patients p ON p.patient_id = v.patient_id
        JOIN doctors  d ON d.doctor_id  = v.doctor_id
        {where}
        ORDER BY b.bill_date DESC
        """,
        params,
    )
    return render_template("billing_list.html", bills=bills, filter_status=filter_status)


@app.route("/billing/<int:bill_id>/pay")
def bill_pay(bill_id):
    try:
        bm.mark_paid(bill_id)
        flash("Bill marked as Paid.", "success")
    except bm.ValidationError as e:
        flash(str(e), "error")
    # Redirect back to referring page (dashboard or billing list)
    referrer = request.referrer
    if referrer and "visit" in referrer:
        bill = bm.get_bill(bill_id)
        return redirect(url_for("visit_detail", visit_id=bill["visit_id"]))
    return redirect(url_for("billing_list"))


# ──────────────────────────────────────────────
# REPORTS
# ──────────────────────────────────────────────

@app.route("/reports")
def reports():
    end_date   = date.today()
    start_date = end_date - timedelta(days=30)
    try:
        start_date = date.fromisoformat(request.args.get("start", str(start_date)))
        end_date   = date.fromisoformat(request.args.get("end",   str(end_date)))
    except ValueError:
        pass

    return render_template(
        "reports.html",
        start          = str(start_date),
        end            = str(end_date),
        workload       = rm.doctor_workload(start_date, end_date),
        revenue_rows   = rm.revenue_by_day(start_date, end_date),
        med_consumption= rm.medicine_consumption(start_date, end_date),
        top_patients   = rm.top_patients(limit=8),
    )


# ──────────────────────────────────────────────
# ERROR HANDLERS
# ──────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message=str(e)), 500


if __name__ == "__main__":
    port = int(os.environ.get("HMS_PORT", 5000))
    debug = os.environ.get("HMS_DEBUG", "1") == "1"
    print(f"Starting HMS Flask app on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
