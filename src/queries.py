"""
queries.py — Data query functions for the IASC Donor Analytics tool.
"""

import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# Resolve DB path relative to this file
DB_PATH = Path(__file__).parent.parent / "data" / "donors.db"

def get_db_connection() -> sqlite3.Connection:
    """Open a read-only connection to the donor database."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def _rows_to_dicts(rows: list) -> list[dict]:
    """Convert sqlite3.Row objects to plain dicts."""
    return [dict(row) for row in rows]

def search_donors(
    state: Optional[str] = None,
    city: Optional[str] = None,
    donor_status: Optional[str] = None,
    sort_by: str = "total_gifts",
    sort_order: str = "desc",
    limit: int = 20,
) -> dict:
    """Search and filter the donor database. Returns matching contacts."""
    allowed_sort_columns = {"total_gifts", "last_name", "wealth_score"}
    if sort_by not in allowed_sort_columns:
        sort_by = "total_gifts"
    
    sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
    limit = min(int(limit), 50)

    conditions, params = [], []
    if state:
        conditions.append("state = ?")
        params.append(state.upper())
    if donor_status:
        conditions.append("donor_status = ?")
        params.append(donor_status)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"SELECT * FROM contacts {where_clause} ORDER BY {sort_by} {sort_order} LIMIT ?"
    params.append(limit)

    with get_db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    results = _rows_to_dicts(rows)
    return {"results": results, "count": len(results), "summary": f"Found {len(results)} donors."}

# Required stubs for the other imports in llm.py
def get_donor_detail(contact_id: str): return {"results": []}
def get_summary_statistics(group_by: str = None): return {"results": []}
def get_geographic_distribution(): return {"results": []}
def get_lapsed_donors(): return {"results": []}
def get_prospects_by_potential(): return {"results": []}
def plan_fundraising_trip(target_state: str): return {"results": []}
