"""
db_connection.py
-----------------
Centralized MySQL connection handling for the Hospital Management System.

Reads connection settings from environment variables when available,
falling back to sensible local defaults. Exposes a context manager so
callers never forget to close connections / cursors, and a small helper
to run a query and get back rows as dictionaries.
"""

import os
import time
import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager

DB_CONFIG = {
    "host": os.environ.get("HMS_DB_HOST", "localhost"),
    "user": os.environ.get("HMS_DB_USER", "hms_user"),
    "password": os.environ.get("HMS_DB_PASSWORD", "HmsPass123!"),
    "database": os.environ.get("HMS_DB_NAME", "hospital_management"),
    "autocommit": False,
}

# MySQL/MariaDB error numbers for transient lock contention that are
# safe to retry: 1213 = deadlock, 1205 = lock wait timeout exceeded.
RETRYABLE_ERRNOS = {1213, 1205}


class DatabaseError(Exception):
    """Raised when the database connection itself cannot be established."""
    pass


@contextmanager
def get_connection():
    """
    Context manager that yields a live MySQL connection and guarantees
    it is closed afterwards, even if an exception is raised.

    NOTE: only errors raised while *establishing* the connection are
    translated into DatabaseError here. Errors raised by the caller's
    queries (e.g. deadlocks, constraint violations) are intentionally
    left alone so they propagate with their real type/message instead
    of being mislabeled as a connection failure.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        raise DatabaseError(f"Could not connect to database: {e}")

    try:
        yield conn
    finally:
        if conn.is_connected():
            conn.close()


@contextmanager
def get_cursor(commit=False, dictionary=True):
    """
    Context manager that yields (connection, cursor). If commit=True,
    commits on successful exit and rolls back on exception.
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=dictionary)
        try:
            yield conn, cursor
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def fetch_all(query, params=None):
    """Run a SELECT query and return a list of dict rows."""
    with get_cursor(commit=False) as (conn, cursor):
        cursor.execute(query, params or ())
        return cursor.fetchall()


def fetch_one(query, params=None):
    """Run a SELECT query and return a single dict row (or None)."""
    with get_cursor(commit=False) as (conn, cursor):
        cursor.execute(query, params or ())
        return cursor.fetchone()


def execute(query, params=None):
    """
    Run an INSERT/UPDATE/DELETE statement, commit it, and return the
    cursor's lastrowid (useful for INSERTs) and rowcount.
    """
    with get_cursor(commit=True) as (conn, cursor):
        cursor.execute(query, params or ())
        return {"lastrowid": cursor.lastrowid, "rowcount": cursor.rowcount}


def run_with_retry(func, *args, max_attempts=3, base_delay=0.05, **kwargs):
    """
    Run func(*args, **kwargs) and automatically retry it if MySQL reports
    a transient lock-contention error (deadlock 1213 / lock wait timeout
    1205). Any other error is raised immediately without retrying.

    Useful for write operations that take row locks (e.g. token
    assignment, stock deduction) where brief contention under concurrent
    requests is expected and should be retried rather than surfaced to
    the end user as a hard failure.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return func(*args, **kwargs)
        except Error as e:
            if getattr(e, "errno", None) in RETRYABLE_ERRNOS and attempt < max_attempts:
                time.sleep(base_delay * attempt)
                continue
            raise


def test_connection():
    """Quick utility to verify DB connectivity from the CLI."""
    try:
        with get_connection() as conn:
            return conn.is_connected()
    except DatabaseError:
        return False
