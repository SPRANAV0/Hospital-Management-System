"""
main.py
---------
Command-line front end for the Hospital Management System.
Run with: python3 main.py
"""

import sys
from datetime import date

import db_connection
import patient_module as pm
import doctor_module as dm
import visit_module as vm
import prescription_module as rxm
import billing_module as bm


def pause():
    input("\nPress Enter to continue...")


def menu_patients():
    while True:
        print("\n--- Patient Management ---")
        print("1. Register new patient")
        print("2. Search patients")
        print("3. View patient visit history")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice == "1":
            full_name = input("Full name: ")
            gender = input("Gender (Male/Female/Other): ")
            dob = input("DOB (YYYY-MM-DD): ")
            phone = input("Phone (10 digits): ")
            address = input("Address: ")
            blood_group = input("Blood group (optional): ")
            try:
                pid = pm.register_patient(full_name, gender, dob, phone, address, blood_group)
                print(f"Patient registered with ID {pid}")
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "2":
            name = input("Search by name (blank to skip): ")
            phone = input("Search by phone (blank to skip): ")
            results = pm.search_patients(name or None, phone or None)
            for r in results:
                print(r)
            pause()

        elif choice == "3":
            pid = input("Patient ID: ")
            try:
                history = pm.get_visit_history(int(pid))
                for h in history:
                    print(h)
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "0":
            return
        else:
            print("Invalid choice.")


def menu_doctors():
    while True:
        print("\n--- Doctor Module ---")
        print("1. Register new doctor")
        print("2. List doctors")
        print("3. View today's assigned patients")
        print("4. Record diagnosis for a visit")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice == "1":
            full_name = input("Doctor name: ")
            specialization = input("Specialization: ")
            phone = input("Phone (10 digits): ")
            fee = input("Consultation fee: ")
            try:
                did = dm.register_doctor(full_name, specialization, phone, fee)
                print(f"Doctor registered with ID {did}")
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "2":
            for d in dm.list_doctors():
                print(d)
            pause()

        elif choice == "3":
            did = input("Doctor ID: ")
            try:
                for row in dm.get_assigned_patients(int(did)):
                    print(row)
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "4":
            vid = input("Visit ID: ")
            diagnosis = input("Diagnosis: ")
            notes = input("Notes: ")
            try:
                dm.record_diagnosis(int(vid), diagnosis, notes)
                print("Diagnosis recorded and visit marked Completed.")
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "0":
            return
        else:
            print("Invalid choice.")


def menu_visits():
    while True:
        print("\n--- Visit / OPD Management ---")
        print("1. Create new visit (assign token)")
        print("2. View doctor's queue")
        print("3. Update visit status")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice == "1":
            pid = input("Patient ID: ")
            did = input("Doctor ID: ")
            try:
                result = vm.create_visit(int(pid), int(did))
                print(f"Visit created: ID={result['visit_id']}, Token #{result['token_number']}")
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "2":
            did = input("Doctor ID: ")
            try:
                for row in vm.get_queue(int(did)):
                    print(row)
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "3":
            vid = input("Visit ID: ")
            status = input("New status (Waiting/In Consultation/Completed/Cancelled): ")
            try:
                vm.update_status(int(vid), status)
                print("Status updated.")
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "0":
            return
        else:
            print("Invalid choice.")


def menu_pharmacy():
    while True:
        print("\n--- Pharmacy / Prescription ---")
        print("1. Add medicine to inventory")
        print("2. List medicines")
        print("3. Prescribe medicine for a visit")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice == "1":
            name = input("Medicine name: ")
            price = input("Unit price: ")
            stock = input("Initial stock quantity: ")
            try:
                mid = rxm.add_medicine(name, price, int(stock))
                print(f"Medicine added with ID {mid}")
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "2":
            for m in rxm.list_medicines():
                print(m)
            pause()

        elif choice == "3":
            vid = input("Visit ID: ")
            mid = input("Medicine ID: ")
            dosage = input("Dosage (e.g. '1 tab twice daily'): ")
            duration = input("Duration (days): ")
            qty = input("Quantity: ")
            try:
                pid = rxm.add_prescription(int(vid), int(mid), dosage, int(duration), int(qty))
                print(f"Prescription recorded with ID {pid}")
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "0":
            return
        else:
            print("Invalid choice.")


def menu_billing():
    while True:
        print("\n--- Billing ---")
        print("1. Generate / refresh bill for a visit")
        print("2. Mark bill as paid")
        print("3. Print receipt")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice == "1":
            vid = input("Visit ID: ")
            try:
                bill = bm.generate_bill(int(vid))
                print(bill)
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "2":
            bid = input("Bill ID: ")
            try:
                bm.mark_paid(int(bid))
                print("Bill marked as paid.")
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "3":
            bid = input("Bill ID: ")
            try:
                print(bm.print_receipt(int(bid)))
            except Exception as e:
                print(f"Error: {e}")
            pause()

        elif choice == "0":
            return
        else:
            print("Invalid choice.")


def main():
    if not db_connection.test_connection():
        print("ERROR: Could not connect to the database. Check your DB settings / that MySQL is running.")
        sys.exit(1)

    while True:
        print("\n========================================")
        print(" HOSPITAL MANAGEMENT SYSTEM")
        print("========================================")
        print("1. Patient Management")
        print("2. Doctor Module")
        print("3. Visit / OPD Management")
        print("4. Pharmacy / Prescription")
        print("5. Billing")
        print("0. Exit")
        choice = input("Choose: ").strip()

        if choice == "1":
            menu_patients()
        elif choice == "2":
            menu_doctors()
        elif choice == "3":
            menu_visits()
        elif choice == "4":
            menu_pharmacy()
        elif choice == "5":
            menu_billing()
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
