"""
queries.py — Data query functions for the IASC Donor Analytics tool.
"""

import sqlite3
from typing import Optional

from config import DB_PATH


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
    limit = max(1, min(int(limit), 50))

    conditions = []
    params = []

    if state:
        conditions.append("state = ?")
        params.append(state.upper())

    if city:
        conditions.append("LOWER(city) = LOWER(?)")
        params.append(city)

    if donor_status:
        conditions.append("donor_status = ?")
        params.append(donor_status)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT *
        FROM contacts
        {where_clause}
        ORDER BY {sort_by} {sort_order}
        LIMIT ?
    """
    params.append(limit)

    with get_db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    results = _rows_to_dicts(rows)
    return {
        "results": results,
        "count": len(results),
        "summary": f"Found {len(results)} donors."
    }


def get_donor_detail(contact_id: str) -> dict:
    """Return one donor record by contact_id."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM contacts WHERE contact_id = ?",
            (contact_id,),
        ).fetchone()

    if row is None:
        return {"results": [], "count": 0, "summary": "No donor found."}

    return {
        "results": [dict(row)],
        "count": 1,
        "summary": "Found donor detail."
    }


def get_summary_statistics(group_by: Optional[str] = None) -> dict:
    """Return overall or grouped donor summary statistics."""
    allowed_group_by = {"state", "donor_status", "giving_vehicle", "subscription_status"}

    with get_db_connection() as conn:
        if group_by in allowed_group_by:
            rows = conn.execute(
                f"""
                SELECT
                    {group_by} AS group_value,
                    COUNT(*) AS donor_count,
                    COALESCE(SUM(total_gifts), 0) AS total_giving
                FROM contacts
                GROUP BY {group_by}
                ORDER BY donor_count DESC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    COUNT(*) AS donor_count,
                    COALESCE(SUM(total_gifts), 0) AS total_giving,
                    COALESCE(AVG(total_gifts), 0) AS avg_total_giving,
                    COALESCE(AVG(average_gift), 0) AS avg_gift
                FROM contacts
                """
            ).fetchall()

    results = _rows_to_dicts(rows)
    return {
        "results": results,
        "count": len(results),
        "summary": "Summary statistics generated."
    }


def get_geographic_distribution(limit: int = 50) -> dict:
    """Return donor distribution by state."""
    limit = max(1, min(int(limit), 100))

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                state,
                COUNT(*) AS donor_count,
                COALESCE(SUM(total_gifts), 0) AS total_giving
            FROM contacts
            GROUP BY state
            ORDER BY donor_count DESC, total_giving DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    results = _rows_to_dicts(rows)
    return {
        "results": results,
        "count": len(results),
        "summary": "Geographic distribution generated."
    }


def get_lapsed_donors(limit: int = 50) -> dict:
    """Return top lapsed donors."""
    limit = max(1, min(int(limit), 100))

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM contacts
            WHERE donor_status = 'lapsed'
            ORDER BY total_gifts DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    results = _rows_to_dicts(rows)
    return {
        "results": results,
        "count": len(results),
        "summary": f"Found {len(results)} lapsed donors."
    }


def get_prospects_by_potential(limit: int = 50) -> dict:
    """Return top prospects ranked by potential."""
    limit = max(1, min(int(limit), 100))

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM contacts
            WHERE donor_status = 'prospect'
            ORDER BY wealth_score DESC, event_attendance_count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    results = _rows_to_dicts(rows)
    return {
        "results": results,
        "count": len(results),
        "summary": f"Found {len(results)} prospects."
    }


def plan_fundraising_trip(target_state: str, limit: int = 20) -> dict:
    """Return top donors in a target state for visit planning."""
    limit = max(1, min(int(limit), 100))

    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM contacts
            WHERE state = ?
            ORDER BY total_gifts DESC, wealth_score DESC
            LIMIT ?
            """,
            (target_state.upper(), limit),
        ).fetchall()

    results = _rows_to_dicts(rows)
    return {
        "results": results,
        "count": len(results),
        "summary": f"Found {len(results)} donors for a {target_state.upper()} trip."
    }

