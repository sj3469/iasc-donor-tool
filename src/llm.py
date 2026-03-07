import os
import re
from types import SimpleNamespace
from typing import List, Dict, Any, Optional, Callable

try:
    from google import genai
except Exception:
    genai = None

from queries import (
    search_donors,
    get_donor_detail,
    get_summary_statistics,
    get_geographic_distribution,
    get_lapsed_donors,
    get_prospects_by_potential,
    plan_fundraising_trip,
)
from prompts import build_system_prompt


def _safe_log_usage(session_tracker: Any, model: str, usage: Any) -> None:
    if not session_tracker:
        return
    if not hasattr(session_tracker, "log_call"):
        return

    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0
    session_tracker.log_call(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _zero_usage() -> Any:
    return SimpleNamespace(prompt_token_count=0, candidates_token_count=0)


def _fmt_currency(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


def _pick(row: dict, *keys, default=None):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def _extract_zip(text: str) -> Optional[str]:
    match = re.search(r"\b\d{5}(?:-\d{4})?\b", text)
    return match.group(0) if match else None


def _extract_contact_id(text: str) -> Optional[str]:
    match = re.search(r"\bC\d{6}\b", text, flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _format_donor_list(title: str, result: dict, max_rows: int = 10) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return f"{title}\n\nNo matching donors found."

    lines = [title]
    for row in rows[:max_rows]:
        contact_id = _pick(row, "contact_id", "Contact ID", default="Unknown ID")
        zip_code = _pick(row, "zip_code", "Mailing Zip/Postal Code", default="N/A")
        total_gifts = _pick(row, "total_gifts", "Total Gifts", default=0)
        last_gift_date = _pick(row, "last_gift_date", "Last Gift Date", default="N/A")
        donor_status = _pick(row, "donor_status", default="N/A")
        wealth_score = _pick(row, "wealth_score", default="N/A")

        lines.append(
            f"{contact_id} | ZIP {zip_code} | "
            f"Total gifts {_fmt_currency(total_gifts)} | "
            f"Last gift {last_gift_date} | "
            f"Status {donor_status} | "
            f"Wealth {wealth_score}"
        )

    return "\n".join(lines)


def _format_donor_detail(result: dict) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return "No donor found."

    row = rows[0]
    contact_id = _pick(row, "contact_id", "Contact ID", default="Unknown ID")
    zip_code = _pick(row, "zip_code", "Mailing Zip/Postal Code", default="N/A")
    first_gift_date = _pick(row, "first_gift_date", "First Gift Date", default="N/A")
    last_gift_date = _pick(row, "last_gift_date", "Last Gift Date", default="N/A")
    average_gift = _pick(row, "average_gift", "Average Gift", default=0)
    total_gifts = _pick(row, "total_gifts", "Total Gifts", default=0)
    total_number_of_gifts = _pick(
        row, "total_number_of_gifts", "Total Number of Gifts", default=0
    )
    donor_status = _pick(row, "donor_status", default="N/A")
    created = _pick(row, "contact_created_date", "contact_created_date", default="N/A")
    subscription_type = _pick(row, "subscription_type", default="N/A")
    subscription_status = _pick(row, "subscription_status", default="N/A")
    email_open_rate = _pick(row, "email_open_rate", default="N/A")
    last_click = _pick(row, "last_email_click_date", default="N/A")
    event_count = _pick(row, "event_attendance_count", default="N/A")
    giving_vehicle = _pick(row, "giving_vehicle", default="N/A")
    wealth_score = _pick(row, "wealth_score", default="N/A")

    return "\n".join([
        f"Donor detail for {contact_id}",
        f"ZIP/postal code: {zip_code}",
        f"First gift date: {first_gift_date}",
        f"Last gift date: {last_gift_date}",
        f"Average gift: {_fmt_currency(average_gift)}",
        f"Total gifts: {_fmt_currency(total_gifts)}",
        f"Total number of gifts: {total_number_of_gifts}",
        f"Donor status: {donor_status}",
        f"Contact created date: {created}",
        f"Subscription type: {subscription_type}",
        f"Subscription status: {subscription_status}",
        f"Email open rate: {email_open_rate}",
        f"Last email click date: {last_click}",
        f"Event attendance count: {event_count}",
        f"Giving vehicle: {giving_vehicle}",
        f"Wealth score: {wealth_score}",
    ])


def _format_summary(result: dict) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return "No summary statistics available."

    row = rows[0]
    donor_count = row.get("donor_count", 0)
    total_giving = row.get("total_giving", 0)
    avg_total_giving = row.get("avg_total_giving", 0)
    avg_gift = row.get("avg_gift", 0)
    avg_wealth_score = row.get("avg_wealth_score", 0)

    return "\n".join([
        "Summary statistics",
        f"Donor count: {donor_count}",
        f"Total giving: {_fmt_currency(total_giving)}",
        f"Average total giving per donor: {_fmt_currency(avg_total_giving)}",
        f"Average gift: {_fmt_currency(avg_gift)}",
        f"Average wealth score: {avg_wealth_score:.2f}" if isinstance(avg_wealth_score, (int, float)) else f"Average wealth score: {avg_wealth_score}",
    ])


def _format_grouped_summary(title: str, result: dict) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return f"{title}\n\nNo grouped statistics available."

    lines = [title]
    for row in rows:
        group_value = row.get("group_value")
        donor_count = row.get("donor_count", 0)
        total_giving = row.get("total_giving", 0)
        label = group_value if group_value not in (None, "") else "Unknown"
        lines.append(
            f"{label} | Donors {donor_count} | Total giving {_fmt_currency(total_giving)}"
        )
    return "\n".join(lines)


def _format_geo_distribution(result: dict, max_rows: int = 10) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return "No geographic distribution available."

    lines = ["Top ZIP/postal codes by donor count"]
    for row in rows[:max_rows]:
        zip_code = row.get("zip_code", "N/A")
        donor_count = row.get("donor_count", 0)
        total_giving = row.get("total_giving", 0)
        lines.append(
            f"ZIP {zip_code} | Donors {donor_count} | Total giving {_fmt_currency(total_giving)}"
        )
    return "\n".join(lines)


def _handle_direct_query(user_message: str) -> Optional[str]:
    text = user_message.lower().strip()
    zip_code = _extract_zip(user_message)
    contact_id = _extract_contact_id(user_message)

    if contact_id:
        return _format_donor_detail(get_donor_detail(contact_id))

    if "state" in text:
        return plan_fundraising_trip("N/A").get("summary", "State-level planning unavailable.")

    if ("top donors" in text or "largest donors" in text) and "overall" in text:
        return _format_donor_list(
            "Top donors overall",
            search_donors(sort_by="total_gifts", sort_order="desc", limit=10),
        )

    if ("top donors" in text or "largest donors" in text) and zip_code:
        return _format_donor_list(
            f"Top donors in ZIP {zip_code}",
            search_donors(
                zip_code=zip_code,
                sort_by="total_gifts",
                sort_order="desc",
                limit=10,
            ),
        )

    if "lapsed" in text:
        return _format_donor_list("Top lapsed donors", get_lapsed_donors(limit=10))

    if "prospect" in text and "wealth" in text:
        return _format_donor_list(
            "Top prospects by wealth score",
            get_prospects_by_potential(limit=10),
        )

    if "geographic" in text or "zip distribution" in text or "postal code distribution" in text:
        return _format_geo_distribution(get_geographic_distribution(limit=10))

    if "summary" in text and "donor status" in text:
        return _format_grouped_summary(
            "Summary by donor status",
            get_summary_statistics(group_by="donor_status"),
        )

    if "summary" in text and "subscription type" in text:
        return _format_grouped_summary(
            "Summary by subscription type",
            get_summary_statistics(group_by="subscription_type"),
        )

    if "summary" in text and "subscription status" in text:
        return _format_grouped_summary(
            "Summary by subscription status",
            get_summary_statistics(group_by="subscription_status"),
        )

    if "summary" in text and "giving vehicle" in text:
        return _format_grouped_summary(
            "Summary by giving vehicle",
            get_summary_statistics(group_by="giving_vehicle"),
        )

    if text in {"summary", "show summary", "overall summary"}:
        return _format_summary(get_summary_statistics())

    if "top donors" in text:
        return _format_donor_list(
            "Top donors overall",
            search_donors(sort_by="total_gifts", sort_order="desc", limit=10),
        )

    return None


def _fallback_help_text() -> str:
    return "\n".join([
        "I can help with donor analytics queries.",
        "Try one of these:",
        "- Show top donors overall",
        "- Show top donors in ZIP 10027",
        "- Show lapsed donors",
        "- Show top prospects by wealth score",
        "- Show donor C000015",
        "- Show summary",
        "- Show geographic distribution",
    ])


def get_response(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    model: str,
    session_tracker: Any,
    progress_callback: Optional[Callable[[str], None]] = None,
    st_session_id: Optional[str] = None,
    attachment: Optional[Any] = None,
) -> tuple[str, Any]:
    direct_answer = _handle_direct_query(user_message)
    if direct_answer is not None:
        usage = _zero_usage()
        _safe_log_usage(session_tracker, model, usage)
        return direct_answer, usage

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or genai is None:
        usage = _zero_usage()
        _safe_log_usage(session_tracker, model, usage)
        return _fallback_help_text(), usage

    try:
        client = genai.Client(api_key=api_key)
        system_instruction_text = str(build_system_prompt())

        response = client.models.generate_content(
            model=model,
            contents=[system_instruction_text, user_message],
        )

        usage = getattr(response, "usage_metadata", None) or _zero_usage()
        _safe_log_usage(session_tracker, model, usage)

        text = getattr(response, "text", None) or _fallback_help_text()
        return text, usage
    except Exception:
        usage = _zero_usage()
        _safe_log_usage(session_tracker, model, usage)
        return _fallback_help_text(), usage

