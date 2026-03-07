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
    return [dict(row) for row in rows]


def _get_contact_columns() -> set[str]:
    with get_db_connection() as conn:
        rows = conn.execute("PRAGMA table_info(contacts)").fetchall()
    return {row["name"] for row in rows}


def _pick_column(columns: set[str], *candidates: str) -> Optional[str]:
    normalized = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]
    return None


def _require_column(columns: set[str], *candidates: str) -> str:
    col = _pick_column(columns, *candidates)
    if not col:
        raise RuntimeError(f"Missing expected column. Tried: {', '.join(candidates)}")
    return col


def search_donors(
    state: Optional[str] = None,
    city: Optional[str] = None,
    donor_status: Optional[str] = None,
    sort_by: str = "total_gifts",
    sort_order: str = "desc",
    limit: int = 20,
) -> dict:
    columns = _get_contact_columns()

    state_col = _pick_column(columns, "state", "state_code", "province", "region")
    city_col = _pick_column(columns, "city", "town")
    donor_status_col = _pick_column(columns, "donor_status", "status", "donorstatus")

    sort_map = {
        "total_gifts": _pick_column(columns, "total_gifts", "totalgifts", "lifetime_giving"),
        "last_name": _pick_column(columns, "last_name", "lastname", "surname"),
        "wealth_score": _pick_column(columns, "wealth_score", "wealthscore"),
    }

    actual_sort_col = sort_map.get(sort_by) or sort_map["total_gifts"]
    if not actual_sort_col:
        raise RuntimeError("Could not find a valid sort column in contacts table.")

    sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
    limit = max(1, min(int(limit), 50))

    conditions = []
    params = []

    if state and state_col:
        conditions.append(f"{state_col} = ?")
        params.append(state.upper())

    if city and city_col:
        conditions.append(f"LOWER({city_col}) = LOWER(?)")
        params.append(city)

    if donor_status and donor_status_col:
        conditions.append(f"{donor_status_col} = ?")
        params.append(donor_status)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT *
        FROM contacts
        {where_clause}
        ORDER BY {actual_sort_col} {sort_order}
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
    columns = _get_contact_columns()
    contact_id_col = _require_column(columns, "contact_id", "contactid", "id")

    with get_db_connection() as conn:
        row = conn.execute(
            f"SELECT * FROM contacts WHERE {contact_id_col} = ?",
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
    columns = _get_contact_columns()

    allowed_group_by = {
        "state": _pick_column(columns, "state", "state_code", "province", "region"),
        "donor_status": _pick_column(columns, "donor_status", "status", "donorstatus"),
        "giving_vehicle": _pick_column(columns, "giving_vehicle", "givingvehicle"),
        "subscription_status": _pick_column(columns, "subscription_status", "subscriptionstatus"),
    }

    total_gifts_col = _require_column(columns, "total_gifts", "totalgifts", "lifetime_giving")
    average_gift_col = _pick_column(columns, "average_gift", "averagegift")

    with get_db_connection() as conn:
        group_col = allowed_group_by.get(group_by)
        if group_col:
            rows = conn.execute(
                f"""
                SELECT
                    {group_col} AS group_value,
                    COUNT(*) AS donor_count,
                    COALESCE(SUM({total_gifts_col}), 0) AS total_giving
                FROM contacts
                GROUP BY {group_col}
                ORDER BY donor_count DESC
                """
            ).fetchall()
        else:
            avg_gift_sql = f"COALESCE(AVG({average_gift_col}), 0) AS avg_gift" if average_gift_col else "0 AS avg_gift"
            rows = conn.execute(
                f"""
                SELECT
                    COUNT(*) AS donor_count,
                    COALESCE(SUM({total_gifts_col}), 0) AS total_giving,
                    COALESCE(AVG({total_gifts_col}), 0) AS avg_total_giving,
                    {avg_gift_sql}
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
    columns = _get_contact_columns()
    state_col = _require_column(columns, "state", "state_code", "province", "region")
    total_gifts_col = _require_column(columns, "total_gifts", "totalgifts", "lifetime_giving")
    limit = max(1, min(int(limit), 100))

    with get_db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                {state_col} AS state,
                COUNT(*) AS donor_count,
                COALESCE(SUM({total_gifts_col}), 0) AS total_giving
            FROM contacts
            GROUP BY {state_col}
            ORDER BY donor_count DESC, total_giving DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    results = _rows_to_dicts(rows)
    return {"results": results, "count": len(results), "summary": "Geographic distribution generated."}


def get_lapsed_donors(limit: int = 50) -> dict:
    columns = _get_contact_columns()
    donor_status_col = _require_column(columns, "donor_status", "status", "donorstatus")
    total_gifts_col = _require_column(columns, "total_gifts", "totalgifts", "lifetime_giving")
    limit = max(1, min(int(limit), 100))

    with get_db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM contacts
            WHERE {donor_status_col} = 'lapsed'
            ORDER BY {total_gifts_col} DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    results = _rows_to_dicts(rows)
    return {"results": results, "count": len(results), "summary": f"Found {len(results)} lapsed donors."}


def get_prospects_by_potential(limit: int = 50) -> dict:
    columns = _get_contact_columns()
    donor_status_col = _require_column(columns, "donor_status", "status", "donorstatus")
    wealth_score_col = _require_column(columns, "wealth_score", "wealthscore")
    event_col = _pick_column(columns, "event_attendance_count", "eventattendancecount")
    limit = max(1, min(int(limit), 100))

    order_sql = wealth_score_col
    if event_col:
        order_sql = f"{wealth_score_col} DESC, {event_col} DESC"
    else:
        order_sql = f"{wealth_score_col} DESC"

    with get_db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM contacts
            WHERE {donor_status_col} = 'prospect'
            ORDER BY {order_sql}
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    results = _rows_to_dicts(rows)
    return {"results": results, "count": len(results), "summary": f"Found {len(results)} prospects."}


def plan_fundraising_trip(target_state: str, limit: int = 20) -> dict:
    columns = _get_contact_columns()
    state_col = _require_column(columns, "state", "state_code", "province", "region")
    total_gifts_col = _require_column(columns, "total_gifts", "totalgifts", "lifetime_giving")
    wealth_score_col = _pick_column(columns, "wealth_score", "wealthscore")
    limit = max(1, min(int(limit), 100))

    if wealth_score_col:
        order_sql = f"{total_gifts_col} DESC, {wealth_score_col} DESC"
    else:
        order_sql = f"{total_gifts_col} DESC"

    with get_db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM contacts
            WHERE {state_col} = ?
            ORDER BY {order_sql}
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

