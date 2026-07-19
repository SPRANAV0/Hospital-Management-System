# HMS — Defect Log

All defects were found by automated testing during development.
Each entry records: symptom, root cause, fix, and test that now covers it.

---

## DEFECT-001 — Connection errors masking real DB errors

**Severity:** Medium  
**Found by:** `test_concurrency.py` — deadlock errors reported as "Could not connect"  
**File:** `src/db_connection.py`

### Symptom
When a thread hit a MySQL deadlock (errno 1213), the error was reported as:
```
DatabaseError: Could not connect to database: 1213 (40001): Deadlock found…
```
This completely hid the real cause — the `try/except Error` in `get_connection()`
wrapped the `yield`, so *any* exception from the caller's queries was caught and
relabeled as a connection failure.

### Root Cause
```python
# BEFORE (buggy)
try:
    conn = mysql.connector.connect(...)
    yield conn          # ← exceptions from callers caught here too
except Error as e:
    raise DatabaseError(...)
```

### Fix
Separated the connection-establishment try/except from the yield so that
post-connection query errors propagate with their real type:
```python
# AFTER (fixed)
try:
    conn = mysql.connector.connect(...)
except Error as e:
    raise DatabaseError(...)  # only connection failures land here

try:
    yield conn          # ← query errors now propagate unmodified
finally:
    conn.close()
```

**Also added:** `run_with_retry()` helper that auto-retries on transient
lock errors (errno 1213 / 1205) with exponential backoff.

**Covered by:** `test_concurrency.py`

---

## DEFECT-002 — Concurrent token assignment deadlocks under load

**Severity:** Critical  
**Found by:** `test_concurrency.py` (25 threads, 22 failures)  
**File:** `src/visit_module.py`

### Symptom
Under concurrent visit creation (simulating multiple receptionists),
`SELECT MAX(token_number) … FOR UPDATE` on the visits table caused InnoDB
deadlocks:
```
1213 (40001): Deadlock found when trying to get lock; try restarting transaction
```
Only 3 of 25 concurrent requests succeeded; 22 died with deadlock errors.

### Root Cause
`SELECT MAX() … FOR UPDATE` takes a **gap lock** across the entire
`(doctor_id, visit_date)` range in the visits table. Two concurrent
transactions each hold a gap lock on the same range and each need to
insert into it — classic deadlock.

### Fix
Introduced a dedicated `token_counters` table:
```sql
CREATE TABLE token_counters (
    doctor_id  INT, visit_date DATE,
    last_token INT DEFAULT 0,
    PRIMARY KEY (doctor_id, visit_date)
) ENGINE=InnoDB;
```
Token generation now uses a single-row atomic increment:
```sql
INSERT INTO token_counters (doctor_id, visit_date, last_token) VALUES (%s, %s, 1)
ON DUPLICATE KEY UPDATE last_token = last_token + 1;
```
This locks only a **single primary key row** (not a range), eliminating
the gap lock deadlock. `run_with_retry()` is applied as a safety net.

**Result after fix:** 25/25 threads succeed, tokens form a clean 1–25 sequence.

**Covered by:** `test_concurrency.py`

---

## DEFECT-003 — `dob=None` raises unhandled TypeError instead of ValidationError

**Severity:** Medium  
**Found by:** `test_edge_cases.py`  
**File:** `src/patient_module.py`

### Symptom
```python
pm.register_patient("Test", "Male", None, "9999999999")
# Raises: TypeError: '>' not supported between instances of 'NoneType' and 'datetime.date'
```
The comparison `dob > date.today()` was reached before any None check.

### Root Cause
The validator checked `isinstance(dob, str)` before doing `dob > date.today()`,
but skipped the None case — `None` is not a str so neither branch ran,
and the comparison on the raw `None` crashed with a TypeError.

### Fix
Added an explicit `None` guard at the top of dob validation:
```python
if dob is None:
    raise ValidationError("Date of birth is required.")
```
Also added a type check for non-string, non-date objects.

**Covered by:** `test_edge_cases.py`

---

## DEFECT-004 — Paid bills could be silently overwritten by `generate_bill()`

**Severity:** High (financial integrity)  
**Found by:** `test_edge_cases.py`  
**File:** `src/billing_module.py`

### Symptom
After marking a bill `Paid`, adding another prescription and calling
`generate_bill()` again silently updated the total amount on the same bill row.
The payment status remained `Paid` but the total changed — meaning the hospital
held a receipt for one amount and the DB showed another.

### Root Cause
`generate_bill()` used `INSERT ... ON DUPLICATE KEY UPDATE` logic to update
the existing bill regardless of its payment status, with no guard against
already-paid bills.

### Fix
Added an early-exit guard:
```python
existing_bill = get_bill_for_visit(visit_id)
if existing_bill and existing_bill["payment_status"] == "Paid":
    raise ValidationError(
        f"Bill {existing_bill['bill_id']} is already Paid and cannot be regenerated…"
    )
```
Post-payment charges must now go through a new visit.

**Covered by:** `test_edge_cases.py`

---

## DEFECT-005 — Medicine duplicate key crash in `add_medicine()`

**Severity:** Low (UX / idempotency)  
**Found by:** Running `test_edge_cases.py` a second time without resetting the DB  
**File:** `src/prescription_module.py`

### Symptom
Running any test that calls `add_medicine()` twice with the same name (e.g.,
on repeated test runs without a DB reset) raised:
```
IntegrityError: 1062 Duplicate entry 'Edge Case Tablet' for key 'medicine_name'
```

### Root Cause
The original `INSERT` had no handling for duplicate medicine names.

### Fix
Changed to `INSERT … ON DUPLICATE KEY UPDATE` — idempotent upsert that
updates price/stock on re-insertion instead of crashing. Returns the
existing `medicine_id` when the row already exists.

**Covered by:** Running any test suite multiple times; `test_system.py` handles this via `reset_db()`.

---

## Test Data Isolation (Process Defect)

**Found by:** Running `test_edge_cases.py` on a non-fresh database  
**Resolution:** Added `test_helpers.reset_db()` called at the start of every
test file's `main()`. This truncates all tables in FK-safe order before
each run, ensuring fully repeatable results.
