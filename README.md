# 🏥 Hospital Management System

A full-stack Python + MySQL hospital management system implementing a
**visit-based OPD workflow** — the same model used in real outpatient clinics.

> **One Patient → Multiple Visits → Multiple Treatments & Bills**

---

## ✨ Features

| Module | Capabilities |
|---|---|
| **Patients** | Register, search, view full visit history |
| **Doctors** | Register, toggle availability, per-doctor queue |
| **OPD / Visits** | Token-based queue, concurrent-safe token assignment |
| **Pharmacy** | Inventory, stock-safe prescription dispensing |
| **Billing** | Auto-calculated bills, mark-paid, Paid bill integrity |
| **Reports** | Daily OPD summary, doctor workload, revenue, low-stock alerts |
| **Web UI** | Full Flask interface (all modules) |
| **CLI** | Text-based menu (no browser required) |

---

## 🛠️ Technology Stack

- **Python 3.12**
- **MySQL / MariaDB** (InnoDB with FK constraints)
- **mysql-connector-python** 9.x
- **Flask** 3.x (web interface)

---

## 🚀 Quick Start

### 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### 2 — Start MySQL and create the database
```bash
mysql -u root -e "
  CREATE DATABASE hospital_management CHARACTER SET utf8mb4;
  CREATE USER 'hms_user'@'localhost' IDENTIFIED BY 'HmsPass123!';
  GRANT ALL ON hospital_management.* TO 'hms_user'@'localhost';
  FLUSH PRIVILEGES;
"
mysql -u hms_user -pHmsPass123! hospital_management < database/schema.sql
```

### 3 — Seed demo data (optional but recommended)
```bash
python3 src/seed.py --reset
# Seeds 5 doctors, 12 medicines, 8 patients, ~34 historical visits
```

### 4a — Launch the web interface
```bash
cd src && python3 app.py
# Open http://localhost:5000
```

### 4b — Or use the CLI
```bash
cd src && python3 main.py
```

---

## 🗄️ Database Schema

```
patients ──< visits >── doctors
               │
               ├──< prescriptions >── medicines
               │
               └──< billing

token_counters  (doctor_id, visit_date) → atomic OPD token generator
```

### Key design decisions
- **`token_counters` table** — per-doctor/day token uses an atomic
  `INSERT … ON DUPLICATE KEY UPDATE` counter, not `SELECT MAX() FOR UPDATE`,
  which deadlocks under concurrent receptionist requests (see DEFECT-002).
- **`billing.payment_status`** — once `Paid`, `generate_bill()` raises rather
  than silently mutating the settled total (DEFECT-004).
- **Stock deduction** uses `SELECT … FOR UPDATE` within a transaction so
  pharmacy stock can never go below zero under concurrent prescribing.

---

## 🧪 Running the Test Suite

```bash
# Full functional suite (34 checks)
python3 tests/test_system.py

# Input validation edge cases (4 checks)
python3 tests/test_edge_cases.py

# Token-assignment concurrency (25 threads)
python3 tests/test_concurrency.py

# Pharmacy stock-deduction concurrency (30 threads, 20-unit stock cap)
python3 tests/test_pharmacy_concurrency.py
```

Each test resets the database at startup so runs are fully independent.

---

## 🐛 Defects Found & Fixed

See `docs/DEFECTS.md` for full detail. Summary:

| # | Where | Severity | Issue |
|---|---|---|---|
| 001 | `db_connection.py` | Medium | DB errors mislabeled as connection failures |
| 002 | `visit_module.py` | **Critical** | Token assignment deadlocked under concurrency |
| 003 | `patient_module.py` | Medium | `dob=None` crashed with unhandled TypeError |
| 004 | `billing_module.py` | **High** | Paid bill total could be silently overwritten |
| 005 | `prescription_module.py` | Low | Duplicate medicine name crashed with IntegrityError |

---

## 📁 Project Structure

```
Hospital_Management/
├── database/
│   └── schema.sql          # Full relational schema (6 tables + indexes)
├── docs/
│   └── DEFECTS.md          # Bug log with root causes and fixes
├── src/
│   ├── db_connection.py    # Connection management, retry helper
│   ├── patient_module.py   # Patient CRUD + validation
│   ├── doctor_module.py    # Doctor management + consultation
│   ├── visit_module.py     # OPD visit + token queue
│   ├── prescription_module.py  # Pharmacy + stock-safe dispensing
│   ├── billing_module.py   # Bill generation + receipt printer
│   ├── reports_module.py   # Analytics queries
│   ├── seed.py             # Demo data seeder
│   ├── main.py             # CLI application
│   ├── app.py              # Flask web application
│   └── templates/          # Jinja2 HTML templates (10 files)
├── tests/
│   ├── test_helpers.py          # Shared DB reset utility
│   ├── test_system.py           # Functional end-to-end suite (34 checks)
│   ├── test_edge_cases.py       # Validation + business-logic probes
│   ├── test_concurrency.py      # Token-assignment race-condition test
│   └── test_pharmacy_concurrency.py  # Stock-deduction race-condition test
└── requirements.txt
```

---

## 🔮 Future Enhancements

- Role-based login (Admin / Doctor / Receptionist)
- PDF bill / receipt generation
- Online appointment booking
- Dashboard charts (Chart.js)
- REST API with JWT authentication
- Docker + docker-compose for one-command setup
