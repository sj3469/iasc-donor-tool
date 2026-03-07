"""
System prompts and prompt templates for the IASC donor analytics assistant.
"""

from knowledge import load_knowledge_base


DB_SCHEMA_SUMMARY = """
## Database schema summary

contacts table (one row per person):
- contact_id, first_name, last_name, email, city, state, zip_code
- donor_status: active, lapsed, prospect, new_donor
- contact_created_date, first_gift_date, last_gift_date
- total_gifts, total_number_of_gifts, average_gift
- giving_vehicle
- subscription_type, subscription_status, subscription_start_date
- email_open_rate, last_email_click_date
- event_attendance_count, wealth_score, notes

gifts table:
- gift_id, contact_id, gift_date, amount, gift_type, campaign

interactions table:
- interaction_id, contact_id, interaction_date, interaction_type, details

Prospects typically have null gift history fields.
"""


BASE_SYSTEM_PROMPT = """
You are a donor analytics assistant for the Institute for Advanced Studies in Culture (IASC),
a nonprofit research center and publisher at the University of Virginia.

You help IASC's development team analyze donor data and make informed decisions
about fundraising outreach.

Rules:
1. Use actual donor database results whenever possible.
2. Never invent donor names, amounts, or engagement details.
3. Be concise, practical, and actionable.
4. When listing donors, include name, location, total giving, last gift date,
   donor status, and any relevant indicators such as wealth score or engagement.
5. If there are no matches, say so clearly and suggest a broader search.
6. If the user asks about strategy or best practices, use the knowledge base when relevant.
7. Use plain English and clean formatting.
8. This app uses Gemini, not Claude.
"""

KNOWLEDGE_TRIGGER_KEYWORDS = [
    "best practice",
    "strategy",
    "how to",
    "recommend",
    "advice",
    "approach",
    "re-engage",
    "re-engagement",
    "cultivate",
    "cultivation",
    "retention",
    "pipeline",
    "moves management",
    "major gift",
    "prospect research",
    "donor pyramid",
    "rfm",
    "wealth screen",
    "center-out",
    "stewardship",
    "solicitation",
    "annual fund",
    "capital campaign",
    "planned giving",
    "donor lifecycle",
    "engagement strategy",
    "outreach plan",
    "thank",
    "acknowledge",
]


def needs_knowledge_base(user_message: str) -> bool:
    msg_lower = user_message.lower()
    return any(keyword in msg_lower for keyword in KNOWLEDGE_TRIGGER_KEYWORDS)


def build_system_prompt(include_knowledge: bool = False) -> str:
    prompt = BASE_SYSTEM_PROMPT + "\n\n" + DB_SCHEMA_SUMMARY

    if include_knowledge:
        kb = load_knowledge_base()
        if kb:
            prompt += "\n\n" + kb
    else:
        prompt += (
            "\n\nA fundraising knowledge base is available and should be used when the user "
            "asks about strategy, best practices, cultivation, stewardship, or outreach."
        )

    return prompt
