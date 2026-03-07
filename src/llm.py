import os
import re
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

try:
    from google import genai
except Exception:
    genai = None

from prompts import build_system_prompt, needs_knowledge_base
from queries import (
    get_donor_detail,
    get_geographic_distribution,
    get_lapsed_donors,
    get_prospects_by_potential,
    get_summary_statistics,
    plan_fundraising_trip,
    search_donors,
)


STATE_NAME_TO_ABBR = {
    "virginia": "VA",
    "new york": "NY",
    "district of columbia": "DC",
    "washington dc": "DC",
    "washington d.c.": "DC",
    "maryland": "MD",
    "massachusetts": "MA",
    "illinois": "IL",
    "california": "CA",
    "texas": "TX",
    "florida": "FL",
    "pennsylvania": "PA",
    "ohio": "OH",
    "georgia": "GA",
    "north carolina": "NC",
    "washington state": "WA",
    "colorado": "CO",
    "minnesota": "MN",
    "missouri": "MO",
    "arizona": "AZ",
    "tennessee": "TN",
    "new jersey": "NJ",
}

VALID_STATE_ABBRS = {
    "VA", "NY", "DC", "MD", "MA", "IL", "CA", "TX", "FL", "PA",
    "OH", "GA", "NC", "WA", "CO", "MN", "MO", "AZ", "TN", "NJ"
}


def _zero_usage() -> Any:
    return SimpleNamespace(prompt_token_count=0, candidates_token_count=0)


def _safe_log_usage(session_tracker: Any, model: str, usage: Any, question: str = "") -> None:
    if not session_tracker or not hasattr(session_tracker, "log_call"):
        return

    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0

    try:
        session_tracker.log_call(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            question=question,
        )
    except TypeError:
        session_tracker.log_call(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


def _fmt_currency(value: Any) -> str:
    try:
        if value is None:
            return "N/A"
        return f"${float(value):,.2f}"
    except Exception:
        return "N/A"


def _fmt_pct(value: Any) -> str:
    try:
        if value is None:
            return "N/A"
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "N/A"


def _pick(row: dict, *keys, default=None):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def _extract_zip(text: str) -> Optional[str]:
    match = re.search(r"\b\d{5}(?:-\d{4})?\b", text)
    return match.group(0) if match else None


def _extract_contact_id(text: str) -> Optional[str]:
    match = re.search(r"\b003[A-Za-z0-9]{15}\b", text)
    return match.group(0) if match else None


def _extract_state(text: str) -> Optional[str]:
    lower_text = text.lower()
    upper_text = text.upper()

    for name, abbr in sorted(STATE_NAME_TO_ABBR.items(), key=lambda x: -len(x[0])):
        if name in lower_text:
            return abbr

    for abbr in VALID_STATE_ABBRS:
        if re.search(rf"\b{abbr}\b", upper_text):
            return abbr

    return None


def _extract_city(text: str) -> Optional[str]:
    patterns = [
        r"\bin\s+([A-Za-z.\- ]+?),\s*[A-Z]{2}\b",
        r"\bin\s+([A-Za-z.\- ]+)\b",
    ]
    blocked = {
        "zip", "state", "va", "ny", "dc", "md", "ma", "il", "ca", "tx", "fl",
        "pa", "oh", "ga", "nc", "wa", "co", "mn", "mo", "az", "tn", "nj"
    }

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            if city and city.lower() not in blocked:
                return city
    return None


def _person_label(row: dict) -> str:
    first_name = _pick(row, "first_name", default="")
    last_name = _pick(row, "last_name", default="")
    full_name = f"{first_name} {last_name}".strip()
    return full_name or _pick(row, "contact_id", default="Unknown donor")


def _location_label(row: dict) -> str:
    city = _pick(row, "city", default=None)
    state = _pick(row, "state", default=None)
    zip_code = _pick(row, "zip_code", default=None)

    if city and state:
        return f"{city}, {state}"
    if state and zip_code:
        return f"{state} {zip_code}"
    if state:
        return state
    if zip_code:
        return f"ZIP {zip_code}"
    return "N/A"


def _format_donor_list(title: str, result: dict, max_rows: int = 10) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return f"{title}\n\nNo matching donors found."

    lines = [title]
    for row in rows[:max_rows]:
        lines.append(
            f"- {_person_label(row)} | {_location_label(row)} | "
            f"Total gifts {_fmt_currency(_pick(row, 'total_gifts'))} | "
            f"Last gift {_pick(row, 'last_gift_date', default='N/A')} | "
            f"Status {_pick(row, 'donor_status', default='N/A')} | "
            f"Wealth {_pick(row, 'wealth_score', default='N/A')}"
        )
    return "\n".join(lines)


def _format_donor_detail(result: dict) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return "No donor found."

    row = rows[0]
    return "\n".join([
        f"Donor detail for {_person_label(row)}",
        f"Contact ID: {_pick(row, 'contact_id', default='N/A')}",
        f"Email: {_pick(row, 'email', default='N/A')}",
        f"Location: {_pick(row, 'city', default='N/A')}, {_pick(row, 'state', default='N/A')} {_pick(row, 'zip_code', default='')}".strip(),
        f"Donor status: {_pick(row, 'donor_status', default='N/A')}",
        f"Contact created: {_pick(row, 'contact_created_date', default='N/A')}",
        f"First gift date: {_pick(row, 'first_gift_date', default='N/A')}",
        f"Last gift date: {_pick(row, 'last_gift_date', default='N/A')}",
        f"Total gifts: {_fmt_currency(_pick(row, 'total_gifts'))}",
        f"Number of gifts: {_pick(row, 'total_number_of_gifts', default='N/A')}",
        f"Average gift: {_fmt_currency(_pick(row, 'average_gift'))}",
        f"Giving vehicle: {_pick(row, 'giving_vehicle', default='N/A')}",
        f"Subscription: {_pick(row, 'subscription_type', default='N/A')} / {_pick(row, 'subscription_status', default='N/A')}",
        f"Email open rate: {_fmt_pct(_pick(row, 'email_open_rate'))}",
        f"Last email click: {_pick(row, 'last_email_click_date', default='N/A')}",
        f"Event attendance count: {_pick(row, 'event_attendance_count', default='N/A')}",
        f"Wealth score: {_pick(row, 'wealth_score', default='N/A')}",
        f"Notes: {_pick(row, 'notes', default='N/A')}",
    ])


def _format_summary(result: dict) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return "No summary statistics available."

    row = rows[0]
    return "\n".join([
        "Summary statistics",
        f"- Donor count: {row.get('donor_count', 0)}",
        f"- Total giving: {_fmt_currency(row.get('total_giving', 0))}",
        f"- Average total giving per donor: {_fmt_currency(row.get('avg_total_giving', 0))}",
        f"- Average gift: {_fmt_currency(row.get('avg_gift', 0))}",
        f"- Average wealth score: {row.get('avg_wealth_score', 0):.2f}" if isinstance(row.get('avg_wealth_score', 0), (int, float)) else f"- Average wealth score: {row.get('avg_wealth_score', 'N/A')}",
    ])


def _format_grouped_summary(title: str, result: dict) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return f"{title}\n\nNo grouped statistics available."

    lines = [title]
    for row in rows:
        label = row.get("group_value") or "Unknown"
        lines.append(
            f"- {label} | Donors {row.get('donor_count', 0)} | Total giving {_fmt_currency(row.get('total_giving', 0))}"
        )
    return "\n".join(lines)


def _format_geo_distribution(result: dict, max_rows: int = 10) -> str:
    rows = result.get("results", []) or []
    if not rows:
        return "No geographic distribution available."

    lines = ["Top geographic segments"]
    for row in rows[:max_rows]:
        lines.append(
            f"- {row.get('city', 'N/A')}, {row.get('state', 'N/A')} {row.get('zip_code', 'N/A')} | "
            f"Donors {row.get('donor_count', 0)} | Total giving {_fmt_currency(row.get('total_giving', 0))}"
        )
    return "\n".join(lines)


def _help_text() -> str:
    return "\n".join([
        "I can help with donor analytics questions.",
        "",
        "Try one of these:",
        "- Show top donors overall",
        "- Show top donors in VA",
        "- Show top donors in New York",
        "- Show top donors in ZIP 10027",
        "- Show lapsed donors",
        "- Show top prospects by wealth score",
        "- Show summary",
        "- Show summary by state",
        "- Show geographic distribution",
        "- Plan a fundraising trip in DC",
    ])


def _handle_direct_query(user_message: str) -> Optional[str]:
    text = user_message.lower().strip()
    zip_code = _extract_zip(user_message)
    contact_id = _extract_contact_id(user_message)
    state = _extract_state(user_message)
    city = _extract_city(user_message)

    if contact_id:
        return _format_donor_detail(get_donor_detail(contact_id))

    if "trip" in text and state:
        return _format_donor_list(
            f"Fundraising trip candidates in {state}",
            plan_fundraising_trip(state, limit=10),
        )

    if ("top donors" in text or "largest donors" in text) and state:
        return _format_donor_list(
            f"Top donors in {state}",
            search_donors(state=state, sort_by="total_gifts", sort_order="desc", limit=10),
        )

    if ("top donors" in text or "largest donors" in text) and zip_code:
        return _format_donor_list(
            f"Top donors in ZIP {zip_code}",
            search_donors(zip_code=zip_code, sort_by="total_gifts", sort_order="desc", limit=10),
        )

    if ("top donors" in text or "largest donors" in text) and city:
        return _format_donor_list(
            f"Top donors in {city}",
            search_donors(city=city, sort_by="total_gifts", sort_order="desc", limit=10),
        )

    if "lapsed" in text and state:
        return _format_donor_list(
            f"Lapsed donors in {state}",
            search_donors(state=state, donor_status="lapsed", sort_by="total_gifts", sort_order="desc", limit=10),
        )

    if "lapsed" in text:
        return _format_donor_list("Top lapsed donors", get_lapsed_donors(limit=10))

    if "prospect" in text and "wealth" in text:
        return _format_donor_list(
            "Top prospects by wealth score",
            get_prospects_by_potential(limit=10),
        )

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

    if "summary" in text and "state" in text:
        return _format_grouped_summary(
            "Summary by state",
            get_summary_statistics(group_by="state"),
        )

    if "geographic" in text or "distribution" in text:
        return _format_geo_distribution(get_geographic_distribution(limit=10))

    if text in {"summary", "show summary", "overall summary"}:
        return _format_summary(get_summary_statistics())

    if "top donors" in text or "largest donors" in text:
        return _format_donor_list(
            "Top donors overall",
            search_donors(sort_by="total_gifts", sort_order="desc", limit=10),
        )

    return None


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
        _safe_log_usage(session_tracker, model, usage, question=user_message)
        return direct_answer, usage

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or genai is None:
        usage = _zero_usage()
        _safe_log_usage(session_tracker, model, usage, question=user_message)
        return _help_text(), usage

    attachment_note = ""
    if attachment:
        try:
            names = [f.name for f in attachment if getattr(f, "name", None)]
            if names:
                attachment_note = "\n\nUploaded files:\n- " + "\n- ".join(names)
        except Exception:
            attachment_note = ""

    history_text = ""
    if conversation_history:
        trimmed = conversation_history[-6:]
        lines = []
        for msg in trimmed:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        history_text = "\n\nRecent conversation:\n" + "\n".join(lines)

    include_knowledge = needs_knowledge_base(user_message)
    system_prompt = build_system_prompt(include_knowledge=include_knowledge)

    final_prompt = (
        system_prompt
        + history_text
        + attachment_note
        + "\n\nUser request:\n"
        + user_message
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=final_prompt,
        )

        usage = getattr(response, "usage_metadata", None) or _zero_usage()
        text = getattr(response, "text", None) or _help_text()

        _safe_log_usage(session_tracker, model, usage, question=user_message)
        return text, usage

    except Exception:
        usage = _zero_usage()
        _safe_log_usage(session_tracker, model, usage, question=user_message)
        return _help_text(), usage
