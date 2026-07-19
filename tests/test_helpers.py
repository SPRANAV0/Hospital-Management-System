"""
test_helpers.py
-----------------
Shared utilities for test scripts.
reset_db() truncates all tables in dependency order so each test run
starts from a clean slate regardless of previous runs.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db_connection import get_cursor


def reset_db():
    """Truncate all tables in the correct FK-safe order."""
    tables_in_order = [
        "billing",
        "prescriptions",
        "visits",
        "token_counters",
        "medicines",
        "doctors",
        "patients",
    ]
    with get_cursor(commit=True) as (conn, cursor):
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        for table in tables_in_order:
            cursor.execute(f"TRUNCATE TABLE {table}")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    print("[setup] Database reset to clean state.")
