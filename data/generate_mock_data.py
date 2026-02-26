"""
generate_mock_data.py
=====================
Generates a synthetic donor database at data/donors.db for the IASC Donor
Analytics prototype.  All records are fictional; no real PII is used.

Run:
    python data/generate_mock_data.py

Requires: Python 3.11+ standard library only (no third-party packages).
"""

import json
import math
import random
import sqlite3
import statistics
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
random.seed(42)

# ---------------------------------------------------------------------------
# Name lists — diverse first and last names, no faker required
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Barbara", "William", "Elizabeth", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Christopher",
    "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony", "Margaret",
    "Mark", "Sandra", "Donald", "Ashley", "Steven", "Dorothy", "Paul",
    "Kimberly", "Andrew", "Emily", "Kenneth", "Donna", "George", "Michelle",
    "Joshua", "Carol", "Kevin", "Amanda", "Brian", "Melissa", "Edward",
    "Deborah", "Ronald", "Stephanie", "Timothy", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen",
    "Brenda", "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole",
    "Brandon", "Helen", "Raymond", "Samantha", "Frank", "Katherine", "Gregory",
    "Christine", "Benjamin", "Debra", "Samuel", "Rachel", "Carolyn", "Patrick",
    "Janet", "Alexander", "Catherine", "Jack", "Frances", "Dennis", "Ann",
    "Jerry", "Joyce", "Tyler", "Diana", "Aaron", "Alice", "Jose", "Julie",
    "Adam", "Heather", "Nathan", "Teresa", "Henry", "Gloria", "Douglas",
    "Evelyn", "Zachary", "Jean", "Peter", "Cheryl", "Kyle", "Mildred",
    "Walter", "Ethan", "Joan", "Jeremy", "Andrea", "Harold", "Keith",
    "Diane", "Christian", "Rose", "Roger", "Janice", "Terry", "Julia", "Sean",
    "Grace", "Austin", "Judy", "Gerald", "Victoria", "Carl", "Kelly",
    "Arthur", "Christina", "Lawrence", "Dylan", "Ruth", "Jesse", "Lauren",
    "Bryan", "Hazel", "Joe", "Amber", "Jordan", "Marilyn", "Billy",
    "Danielle", "Bruce", "Beverly", "Albert", "Theresa", "Willie", "Denise",
    "Gabriel", "Logan", "Roy", "Crystal", "Alan", "Tammy", "Juan", "Irene",
    "Wayne", "Lori", "Eugene", "Tiffany", "Louis", "Hannah", "Randy",
    "Kathryn", "Vincent", "Peggy", "Russell", "Sara", "Bobby", "Bettye",
    "Philip", "Jacqueline", "Johnny", "Wanda", "Bradley", "Norma", "Sophia",
    "Wei", "Priya", "Aisha", "Marco", "Elena", "Yuki", "Rajesh", "Fatima",
    "Lena", "Carlos", "Mei", "Andre", "Nadia", "Ibrahim", "Sofia", "Hiroshi",
    "Amara", "Diego", "Yuna",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Chen", "Kim", "Patel", "Kumar", "Singh", "Zhang",
    "Wang", "Liu", "Gupta", "Sharma", "Okafor", "Mensah", "Diallo", "Mbeki",
    "Tanaka", "Nakamura", "Yamamoto", "Sato", "Cohen", "Goldstein", "Shapiro",
    "Weinstein", "OBrien", "Murphy", "Walsh", "Kelly", "Sullivan", "McCarthy",
    "Murray", "Fitzgerald", "Burke",
]

# ---------------------------------------------------------------------------
# Geographic configuration
# State weights → cumulative probability used with random.random()
# ---------------------------------------------------------------------------

# Each entry: (state, weight, zip_prefix)
# Zip prefixes chosen for realism (see CLAUDE.md for rationale).
GEO_CONFIG = [
    # (state, weight, [zip_prefixes])
    ("VA", 20, ["229", "220", "230"]),   # Charlottesville / Northern VA
    ("NY", 15, ["100", "101", "112"]),   # NYC metro
    ("DC", 7,  ["200", "202", "203"]),   # Washington DC
    ("MD", 5,  ["207", "208", "209"]),   # Maryland suburbs
    ("MA", 6,  ["021", "022", "024"]),   # Boston
    ("IL", 5,  ["606", "607", "608"]),   # Chicago
    ("CA", 8,  ["900", "941", "945"]),   # LA / SF
    ("TX", 5,  ["770", "782", "787"]),   # Houston / Austin
    ("FL", 4,  ["331", "332", "337"]),   # Miami / Tampa
    ("PA", 4,  ["191", "192", "193"]),   # Philadelphia
    ("OH", 3,  ["432", "440", "441"]),   # Columbus / Cleveland
    ("GA", 3,  ["303", "304", "305"]),   # Atlanta
    ("NC", 3,  ["275", "277", "282"]),   # Raleigh / Charlotte
    ("WA", 3,  ["980", "981", "982"]),   # Seattle
    ("CO", 2,  ["800", "801", "802"]),   # Denver
    ("MN", 2,  ["550", "551", "554"]),   # Minneapolis
    ("MO", 1,  ["631", "641", "647"]),   # St. Louis / KC
    ("AZ", 1,  ["850", "852", "853"]),   # Phoenix
    ("TN", 1,  ["370", "371", "372"]),   # Nashville
    ("NJ", 1,  ["070", "071", "080"]),   # New Jersey
]

# Unpack for weighted selection
_GEO_STATES   = [g[0] for g in GEO_CONFIG]
_GEO_WEIGHTS  = [g[1] for g in GEO_CONFIG]
_GEO_ZIPS     = [g[2] for g in GEO_CONFIG]
_GEO_TOTAL    = sum(_GEO_WEIGHTS)

# ---------------------------------------------------------------------------
# Donor-status weights
# ---------------------------------------------------------------------------
STATUS_CONFIG = [
    ("active",     35),
    ("lapsed",     25),
    ("prospect",   25),
    ("new_donor",  15),
]
_STATUS_CHOICES = [s for s, w in STATUS_CONFIG for _ in range(w)]

# ---------------------------------------------------------------------------
# Notes pool — ~30 % of contacts get one
# ---------------------------------------------------------------------------
NOTES_POOL = [
    "Met at UVA event 2019",
    "Board member referral",
    "Prefers email contact",
    "Alumna of UVA Batten School",
    "Interested in planned giving",
    "Responded to 2022 Year-End Appeal",
    "Former colleague of board member",
    "Strong interest in cultural sociology",
    "Subscriber since inception",
    "Met at Hedgehog Gala 2022",
    "Prefers phone contact",
    "Potential major gift prospect",
    "Works in philanthropic advising",
    "Gave stock gift in 2021",
    "Known DAF holder at Fidelity Charitable",
    "Attended 2023 UVA Homecoming event",
    "Connected through Charlottesville arts community",
    "Interested in naming opportunity",
    "Legacy Society prospect",
    "Annual Fund loyal donor since 2010",
]

# Campaign names used in the gifts table
CAMPAIGNS = [
    "Annual Fund 2020",
    "Annual Fund 2021",
    "Annual Fund 2022",
    "Annual Fund 2023",
    "Year-End Appeal 2021",
    "Year-End Appeal 2022",
    "Year-End Appeal 2023",
    "Year-End Appeal 2024",
    "Hedgehog Gala 2022",
    "Hedgehog Gala 2023",
    "Spring Appeal 2022",
    "Spring Appeal 2023",
    "Spring Appeal 2024",
    "Major Gift Initiative 2022",
    "Planned Giving Society",
    None,  # ungifted / unrestricted
]

GIFT_TYPES = ["one_time", "recurring", "planned_giving", "event"]
# Weights for gift_type — most gifts are one_time or recurring
GIFT_TYPE_WEIGHTS = [55, 30, 5, 10]

GIVING_VEHICLES = ["check", "online", "stock", "DAF", "wire"]
GIVING_VEHICLE_WEIGHTS = [30, 45, 10, 10, 5]

INTERACTION_TYPES = [
    "email_open",
    "email_click",
    "event_attended",
    "meeting",
    "phone_call",
    "mail_sent",
]

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def random_date(start: date, end: date) -> date:
    """Return a uniformly random date in [start, end]."""
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def year_end_biased_date(start: date, end: date) -> date:
    """
    Return a date biased toward November–December (year-end giving season).
    70 % of the time pick a month in [10, 12]; otherwise pick any month.
    """
    year = random.randint(start.year, end.year)
    if random.random() < 0.70:
        month = random.choice([10, 11, 12])
    else:
        month = random.randint(1, 9)
    day = random.randint(1, 28)
    candidate = date(year, month, day)
    # Clamp to [start, end]
    if candidate < start:
        candidate = start
    if candidate > end:
        candidate = end
    return candidate


def weighted_choice(population: list, weights: list):
    """Simple weighted choice without numpy."""
    total = sum(weights)
    r = random.random() * total
    cumulative = 0.0
    for item, w in zip(population, weights):
        cumulative += w
        if r <= cumulative:
            return item
    return population[-1]


def pick_geo():
    """Return (state, zip_code) using configured geographic weights."""
    r = random.random() * _GEO_TOTAL
    cumulative = 0.0
    for state, weight, prefixes in GEO_CONFIG:
        cumulative += weight
        if r <= cumulative:
            prefix = random.choice(prefixes)
            suffix = f"{random.randint(0, 99):02d}"
            zip_code = prefix + suffix
            return state, zip_code
    # Fallback (should not happen)
    return "VA", "22901"


def generate_contact_id() -> str:
    """
    Generate a Salesforce-style 18-character contact ID.
    Format: '003XX00000' + 8 random alphanumeric characters.
    """
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    suffix = "".join(random.choices(chars, k=8))
    return f"003XX00000{suffix}"


def power_law_total_gifts() -> float:
    """
    Draw total gift amount from a power-law-like distribution as specified:
      40 % → $10–$500
      25 % → $500–$5,000
      15 % → $5,000–$50,000
      10 % → $50,000–$500,000
       5 % → $500,000–$8,000,000 (including a few multi-million outliers)
    Within each band, use a log-uniform draw so small amounts are more common.
    """
    r = random.random()
    if r < 0.40:
        lo, hi = 10, 500
    elif r < 0.65:
        lo, hi = 500, 5_000
    elif r < 0.80:
        lo, hi = 5_000, 50_000
    elif r < 0.90:
        lo, hi = 50_000, 500_000
    else:
        lo, hi = 500_000, 8_000_000

    # Log-uniform within band → realistic long tail
    log_amount = random.uniform(math.log(lo), math.log(hi))
    return round(math.exp(log_amount), 2)


def n_gifts_for_total(total: float) -> int:
    """
    Choose number of gifts roughly correlated with total giving level.
    Larger donors tend to have more gifts (more giving history).
    """
    if total < 500:
        return random.randint(1, 5)
    elif total < 5_000:
        return random.randint(2, 15)
    elif total < 50_000:
        return random.randint(5, 30)
    elif total < 500_000:
        return random.randint(10, 50)
    else:
        return random.randint(20, 60)


def wealth_score_for_total(total: float) -> int | None:
    """
    Return a 1–10 wealth score loosely correlated with total gifts.
    Returns None for ~40 % of donors (WealthEngine data not available for all).
    """
    if random.random() < 0.40:
        return None
    if total < 500:
        base = random.randint(1, 4)
    elif total < 5_000:
        base = random.randint(2, 6)
    elif total < 50_000:
        base = random.randint(4, 8)
    elif total < 500_000:
        base = random.randint(6, 10)
    else:
        base = random.randint(8, 10)
    # Add a small random jitter so it's not perfectly correlated
    return max(1, min(10, base + random.randint(-1, 1)))


# ---------------------------------------------------------------------------
# Record generators
# ---------------------------------------------------------------------------

def generate_contacts(n: int = 300) -> list[dict]:
    """
    Generate n synthetic donor contact records.
    Returns a list of dicts matching the contacts table schema.
    """
    contacts = []
    used_ids: set[str] = set()

    today = date(2026, 2, 25)        # "current date" for the prototype
    lapsed_cutoff = date(2024, 2, 25)  # last_gift_date must be before this for lapsed

    for i in range(n):
        # --- Identity ---
        first_name = random.choice(FIRST_NAMES)
        last_name  = random.choice(LAST_NAMES)
        email      = f"{first_name.lower()}.{last_name.lower()}{i}@example.com"

        # Guarantee unique contact_id
        contact_id = generate_contact_id()
        while contact_id in used_ids:
            contact_id = generate_contact_id()
        used_ids.add(contact_id)

        # --- Geography ---
        state, zip_code = pick_geo()
        # City is a loose match to state (not exhaustive — good enough for mock data)
        city = _city_for_state(state)

        # --- Donor status ---
        donor_status = random.choice(_STATUS_CHOICES)

        # --- Dates ---
        # contact_created_date: most records 2005-2020, some older/newer
        created_start = date(1993, 1, 1)
        created_end   = date(2024, 12, 31)
        # Bias creation dates toward 2005-2020
        if random.random() < 0.70:
            created_start = date(2005, 1, 1)
            created_end   = date(2020, 12, 31)
        contact_created_date = random_date(created_start, created_end)

        # --- Gift data (NULL for prospects) ---
        if donor_status == "prospect":
            first_gift_date      = None
            last_gift_date       = None
            total_gifts          = None
            total_number_of_gifts = None
            average_gift         = None
            giving_vehicle       = None
        else:
            # first_gift_date: on or after contact_created_date
            gift_start = max(contact_created_date, date(1993, 1, 1))

            if donor_status == "lapsed":
                # last gift must be before lapsed_cutoff (2024-02-25)
                first_gift_date = random_date(gift_start, date(2022, 12, 31))
                last_gift_date  = random_date(
                    min(first_gift_date + timedelta(days=1), lapsed_cutoff - timedelta(days=1)),
                    lapsed_cutoff - timedelta(days=1),
                )
            elif donor_status == "new_donor":
                # Recent first gift (within ~18 months of today)
                first_gift_date = random_date(date(2024, 9, 1), today)
                last_gift_date  = random_date(first_gift_date, today)
            else:
                # active
                first_gift_date = random_date(gift_start, date(2023, 12, 31))
                last_gift_date  = random_date(
                    first_gift_date,
                    today,
                )

            # Ensure first <= last
            if first_gift_date > last_gift_date:
                first_gift_date, last_gift_date = last_gift_date, first_gift_date

            total_gifts           = power_law_total_gifts()
            total_number_of_gifts = n_gifts_for_total(total_gifts)
            average_gift          = round(total_gifts / total_number_of_gifts, 2)
            giving_vehicle        = weighted_choice(GIVING_VEHICLES, GIVING_VEHICLE_WEIGHTS)

        # --- Subscription ---
        sub_roll = random.random()
        if sub_roll < 0.20:
            subscription_type   = "print"
        elif sub_roll < 0.40:
            subscription_type   = "digital"
        elif sub_roll < 0.60:
            subscription_type   = "both"
        else:
            subscription_type   = "none"

        if subscription_type == "none":
            subscription_status     = "never"
            subscription_start_date = None
        else:
            sub_status_roll = random.random()
            if sub_status_roll < 0.65:
                subscription_status = "active"
            else:
                subscription_status = "expired"
            # Start date: sometime in 2000-2024
            sub_start = random_date(date(2000, 1, 1), date(2024, 12, 31))
            subscription_start_date = sub_start

        # --- Email engagement ---
        if random.random() < 0.15:
            email_open_rate      = None
            last_email_click_date = None
        else:
            # Beta-like distribution centered around 0.25
            email_open_rate = round(random.betavariate(2, 6), 3)
            if email_open_rate > 0.25 and random.random() < 0.60:
                # Clickers exist for engaged subscribers
                last_email_click_date = random_date(date(2022, 1, 1), today)
            else:
                last_email_click_date = None

        # --- Events ---
        event_attendance_count = _draw_event_count()

        # --- Wealth score ---
        wealth_score = (
            wealth_score_for_total(total_gifts) if total_gifts else (
                random.randint(1, 5) if random.random() < 0.30 else None
            )
        )

        # --- Notes (~30 %) ---
        notes = random.choice(NOTES_POOL) if random.random() < 0.30 else None

        contacts.append({
            "contact_id":             contact_id,
            "first_name":             first_name,
            "last_name":              last_name,
            "email":                  email,
            "city":                   city,
            "state":                  state,
            "zip_code":               zip_code,
            "donor_status":           donor_status,
            "contact_created_date":   contact_created_date.isoformat(),
            "first_gift_date":        first_gift_date.isoformat() if first_gift_date else None,
            "last_gift_date":         last_gift_date.isoformat() if last_gift_date else None,
            "total_gifts":            total_gifts,
            "total_number_of_gifts":  total_number_of_gifts,
            "average_gift":           average_gift,
            "giving_vehicle":         giving_vehicle,
            "subscription_type":      subscription_type,
            "subscription_status":    subscription_status,
            "subscription_start_date": subscription_start_date.isoformat() if subscription_start_date else None,
            "email_open_rate":        email_open_rate,
            "last_email_click_date":  last_email_click_date.isoformat() if last_email_click_date else None,
            "event_attendance_count": event_attendance_count,
            "wealth_score":           wealth_score,
            "notes":                  notes,
        })

    return contacts


def _city_for_state(state: str) -> str:
    """Return a plausible city name for a given state abbreviation."""
    city_map = {
        "VA": ["Charlottesville", "Richmond", "Alexandria", "Arlington", "Roanoke"],
        "NY": ["New York", "Brooklyn", "Manhattan", "Bronx", "Buffalo"],
        "DC": ["Washington"],
        "MD": ["Bethesda", "Chevy Chase", "Silver Spring", "Rockville", "Annapolis"],
        "MA": ["Boston", "Cambridge", "Brookline", "Newton", "Somerville"],
        "IL": ["Chicago", "Evanston", "Oak Park", "Naperville", "Wilmette"],
        "CA": ["San Francisco", "Los Angeles", "Berkeley", "Oakland", "Palo Alto"],
        "TX": ["Houston", "Austin", "Dallas", "San Antonio", "Fort Worth"],
        "FL": ["Miami", "Tampa", "Orlando", "Fort Lauderdale", "Boca Raton"],
        "PA": ["Philadelphia", "Pittsburgh", "Ardmore", "Media", "Wayne"],
        "OH": ["Columbus", "Cleveland", "Cincinnati", "Dayton", "Toledo"],
        "GA": ["Atlanta", "Decatur", "Athens", "Savannah", "Marietta"],
        "NC": ["Chapel Hill", "Durham", "Raleigh", "Charlotte", "Asheville"],
        "WA": ["Seattle", "Bellevue", "Redmond", "Kirkland", "Olympia"],
        "CO": ["Denver", "Boulder", "Fort Collins", "Colorado Springs", "Aspen"],
        "MN": ["Minneapolis", "St. Paul", "Edina", "Minnetonka", "Bloomington"],
        "MO": ["St. Louis", "Kansas City", "Clayton", "Ladue", "Columbia"],
        "AZ": ["Phoenix", "Scottsdale", "Tempe", "Tucson", "Mesa"],
        "TN": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Brentwood"],
        "NJ": ["Princeton", "Hoboken", "Montclair", "Summit", "Morristown"],
    }
    return random.choice(city_map.get(state, ["Unknown"]))


def _draw_event_count() -> int:
    """
    Draw event attendance count.  Most people attend 0 events; a few attend many.
    Rough shape: P(0) ≈ 0.55, P(1-3) ≈ 0.30, P(4-12) ≈ 0.15.
    """
    r = random.random()
    if r < 0.55:
        return 0
    elif r < 0.85:
        return random.randint(1, 3)
    else:
        return random.randint(4, 12)


def generate_gifts(contacts: list[dict]) -> list[dict]:
    """
    Generate individual gift transactions for all non-prospect donors.
    Each donor gets exactly total_number_of_gifts transactions whose amounts
    average close to average_gift and sum close to total_gifts.
    """
    gifts = []
    gift_id = 1

    for contact in contacts:
        if contact["donor_status"] == "prospect":
            continue  # Prospects have no gift history

        n          = contact["total_number_of_gifts"]
        total      = contact["total_gifts"]
        avg        = contact["average_gift"]
        first_date = date.fromisoformat(contact["first_gift_date"])
        last_date  = date.fromisoformat(contact["last_gift_date"])
        cid        = contact["contact_id"]

        # Generate n amounts that sum to total.
        # Strategy: draw (n-1) random amounts, assign remainder to last.
        if n == 1:
            amounts = [round(total, 2)]
        else:
            # Draw from log-normal centered at avg; then rescale to hit total exactly.
            raw = [max(1.0, random.lognormvariate(math.log(max(avg, 1)), 0.6))
                   for _ in range(n)]
            raw_sum = sum(raw)
            amounts = [round(total * v / raw_sum, 2) for v in raw]
            # Fix rounding drift on last element
            amounts[-1] = round(total - sum(amounts[:-1]), 2)
            amounts[-1] = max(1.0, amounts[-1])

        # Distribute dates between first_gift_date and last_gift_date,
        # biased toward year-end giving season.
        gift_dates = sorted([
            year_end_biased_date(first_date, last_date)
            for _ in range(n)
        ])

        for gdate, amount in zip(gift_dates, amounts):
            gift_type = weighted_choice(GIFT_TYPES, GIFT_TYPE_WEIGHTS)
            # Large gifts are more likely to have a campaign attached
            campaign = random.choice(CAMPAIGNS) if random.random() < 0.75 else None

            gifts.append({
                "gift_id":    gift_id,
                "contact_id": cid,
                "gift_date":  gdate.isoformat(),
                "amount":     max(1.0, round(amount, 2)),
                "gift_type":  gift_type,
                "campaign":   campaign,
            })
            gift_id += 1

    return gifts


def generate_interactions(contacts: list[dict]) -> list[dict]:
    """
    Generate 0–20 interaction records per contact.
    Contacts with higher email engagement or event attendance get more interactions.
    """
    interactions = []
    interaction_id = 1
    today = date(2026, 2, 25)

    for contact in contacts:
        open_rate    = contact["email_open_rate"] or 0.0
        event_count  = contact["event_attendance_count"]
        donor_status = contact["donor_status"]

        # Base interaction count from engagement signals
        base = int(open_rate * 10) + event_count
        # Active/lapsed donors tend to have more tracked interactions
        if donor_status in ("active", "lapsed"):
            base += random.randint(0, 5)
        n_interactions = max(0, min(20, base + random.randint(-2, 3)))

        for _ in range(n_interactions):
            itype = random.choice(INTERACTION_TYPES)
            # Interaction dates spread across last ~5 years
            idate = random_date(date(2020, 1, 1), today)

            # Generate contextually appropriate details
            details = _interaction_details(itype)

            interactions.append({
                "interaction_id":   interaction_id,
                "contact_id":       contact["contact_id"],
                "interaction_date": idate.isoformat(),
                "interaction_type": itype,
                "details":          details,
            })
            interaction_id += 1

    return interactions


def _interaction_details(itype: str) -> str | None:
    """Return a plausible detail string for a given interaction type."""
    detail_pool = {
        "email_open": [
            "Year-End Appeal 2023",
            "Hedgehog Review issue announcement",
            "Spring fundraising newsletter",
            "IASC event invitation",
            "Annual Fund thank-you",
            None,
        ],
        "email_click": [
            "Clicked donate button",
            "Clicked event registration link",
            "Clicked Hedgehog Review article link",
            None,
        ],
        "event_attended": [
            "Hedgehog Gala 2022",
            "Hedgehog Gala 2023",
            "UVA Homecoming Reception 2023",
            "IASC Book Launch – Strangers in a Strange Land",
            "Virtual Symposium on Culture & Democracy",
        ],
        "meeting": [
            "Introductory meeting with CDO Andrew Westhouse",
            "Stewardship call – discussed giving impact",
            "Major gift conversation – preliminary",
            "Cultivation lunch in Charlottesville",
            "Phone meeting rescheduled",
        ],
        "phone_call": [
            "Thank-you call after Year-End gift",
            "Outreach about Planned Giving Society",
            "Follow-up on lapsed donor reengagement",
            "Left voicemail",
            None,
        ],
        "mail_sent": [
            "Annual Fund appeal letter",
            "Holiday card",
            "Hedgehog Review print copy",
            "Planned giving brochure",
            "Stewardship impact report",
        ],
    }
    pool = detail_pool.get(itype, [None])
    return random.choice(pool)


# ---------------------------------------------------------------------------
# Database creation
# ---------------------------------------------------------------------------

DDL_CONTACTS = """
CREATE TABLE IF NOT EXISTS contacts (
    contact_id              TEXT PRIMARY KEY,
    first_name              TEXT NOT NULL,
    last_name               TEXT NOT NULL,
    email                   TEXT,
    city                    TEXT,
    state                   TEXT,
    zip_code                TEXT,
    donor_status            TEXT NOT NULL,
    contact_created_date    DATE,
    first_gift_date         DATE,
    last_gift_date          DATE,
    total_gifts             REAL,
    total_number_of_gifts   INTEGER,
    average_gift            REAL,
    giving_vehicle          TEXT,
    subscription_type       TEXT,
    subscription_status     TEXT,
    subscription_start_date DATE,
    email_open_rate         REAL,
    last_email_click_date   DATE,
    event_attendance_count  INTEGER DEFAULT 0,
    wealth_score            INTEGER,
    notes                   TEXT
);
"""

DDL_GIFTS = """
CREATE TABLE IF NOT EXISTS gifts (
    gift_id     INTEGER PRIMARY KEY,
    contact_id  TEXT NOT NULL REFERENCES contacts(contact_id),
    gift_date   DATE NOT NULL,
    amount      REAL NOT NULL,
    gift_type   TEXT,
    campaign    TEXT
);
"""

DDL_INTERACTIONS = """
CREATE TABLE IF NOT EXISTS interactions (
    interaction_id   INTEGER PRIMARY KEY,
    contact_id       TEXT NOT NULL REFERENCES contacts(contact_id),
    interaction_date DATE NOT NULL,
    interaction_type TEXT NOT NULL,
    details          TEXT
);
"""


def create_database(db_path: Path, contacts: list[dict], gifts: list[dict],
                    interactions: list[dict]) -> None:
    """Create SQLite database and populate all three tables."""
    # Remove existing DB so the script is idempotent
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # Enable foreign keys
    cur.execute("PRAGMA foreign_keys = ON;")

    # Create tables
    cur.execute(DDL_CONTACTS)
    cur.execute(DDL_GIFTS)
    cur.execute(DDL_INTERACTIONS)

    # Insert contacts
    cur.executemany(
        """
        INSERT INTO contacts VALUES (
            :contact_id, :first_name, :last_name, :email, :city, :state,
            :zip_code, :donor_status, :contact_created_date, :first_gift_date,
            :last_gift_date, :total_gifts, :total_number_of_gifts, :average_gift,
            :giving_vehicle, :subscription_type, :subscription_status,
            :subscription_start_date, :email_open_rate, :last_email_click_date,
            :event_attendance_count, :wealth_score, :notes
        )
        """,
        contacts,
    )

    # Insert gifts
    cur.executemany(
        """
        INSERT INTO gifts VALUES (
            :gift_id, :contact_id, :gift_date, :amount, :gift_type, :campaign
        )
        """,
        gifts,
    )

    # Insert interactions
    cur.executemany(
        """
        INSERT INTO interactions VALUES (
            :interaction_id, :contact_id, :interaction_date,
            :interaction_type, :details
        )
        """,
        interactions,
    )

    conn.commit()
    conn.close()
    print(f"Database written to: {db_path}")


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def print_summary(contacts: list[dict], gifts: list[dict],
                  interactions: list[dict]) -> None:
    """Print summary statistics to stdout after generation."""

    print("\n" + "=" * 60)
    print("MOCK DATA GENERATION SUMMARY")
    print("=" * 60)

    # --- Contacts by donor_status ---
    print(f"\nTotal contacts: {len(contacts)}")
    status_counts: dict[str, int] = {}
    for c in contacts:
        status_counts[c["donor_status"]] = status_counts.get(c["donor_status"], 0) + 1
    print("\nContacts by donor_status:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status:<15} {count:>4}  ({count/len(contacts)*100:.1f}%)")

    # --- Contacts by state (top 10) ---
    state_counts: dict[str, int] = {}
    for c in contacts:
        state_counts[c["state"]] = state_counts.get(c["state"], 0) + 1
    print("\nContacts by state (top 10):")
    for state, count in sorted(state_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {state:<4} {count:>4}  ({count/len(contacts)*100:.1f}%)")

    # --- Gift amount distribution ---
    amounts = [c["total_gifts"] for c in contacts if c["total_gifts"] is not None]
    if amounts:
        sorted_amounts = sorted(amounts)
        n = len(sorted_amounts)
        median = sorted_amounts[n // 2]
        mean   = sum(sorted_amounts) / n
        total  = sum(sorted_amounts)
        print(f"\nGift amount distribution (n={n} donors with gift data):")
        print(f"  Min:    ${sorted_amounts[0]:>14,.2f}")
        print(f"  Median: ${median:>14,.2f}")
        print(f"  Mean:   ${mean:>14,.2f}")
        print(f"  Max:    ${sorted_amounts[-1]:>14,.2f}")
        print(f"  Total:  ${total:>14,.2f}")

    # --- Subscription breakdown ---
    sub_counts: dict[str, int] = {}
    for c in contacts:
        key = f"{c['subscription_type']} / {c['subscription_status']}"
        sub_counts[key] = sub_counts.get(key, 0) + 1
    print("\nSubscription breakdown:")
    for key, count in sorted(sub_counts.items(), key=lambda x: -x[1]):
        print(f"  {key:<28} {count:>4}")

    # --- Wealth score coverage ---
    scored = [c for c in contacts if c["wealth_score"] is not None]
    print(f"\nWealth score coverage: {len(scored)}/{len(contacts)} "
          f"({len(scored)/len(contacts)*100:.1f}%)")

    # --- Gift and interaction row counts ---
    print(f"\nTotal gift transactions: {len(gifts)}")
    print(f"Total interactions:      {len(interactions)}")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Resolve paths relative to this script's location so the script works
    # when called from any working directory.
    script_dir = Path(__file__).parent
    db_path    = script_dir / "donors.db"

    print("Generating 300 synthetic donor contacts...")
    contacts = generate_contacts(300)

    print("Generating gift transactions...")
    gifts = generate_gifts(contacts)

    print("Generating interaction records...")
    interactions = generate_interactions(contacts)

    print("Writing SQLite database...")
    create_database(db_path, contacts, gifts, interactions)

    print_summary(contacts, gifts, interactions)


if __name__ == "__main__":
    main()
