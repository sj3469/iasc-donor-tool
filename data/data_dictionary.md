# IASC Donor Analytics — Data Dictionary

This document defines every field in the three database tables: **contacts**, **gifts**, and **interactions**.
Source systems are:
- **Salesforce** — CRM; primary record of donors, gift history, and contact metadata.
- **MailChimp** — Email marketing platform; supplies email engagement metrics.
- **WealthEngine** — Prospect research tool; supplies estimated giving capacity scores.
- **Derived** — Calculated from other fields within this system; not ingested from an external source.

---

## Table: contacts

One row per person. This is the primary record linking all donor, subscriber, and prospect data.

| Field | Data Type | Source | Description | Example Values | NULL Handling |
|---|---|---|---|---|---|
| `contact_id` | TEXT (PK) | Salesforce | Salesforce-format 18-character unique identifier for the contact. | `003XX00000AbCd1234` | Never NULL; primary key. |
| `first_name` | TEXT | Salesforce | Contact's first (given) name. | `Mary`, `Rajesh`, `Wei` | Never NULL. |
| `last_name` | TEXT | Salesforce | Contact's last (family) name. | `Johnson`, `Patel`, `Okafor` | Never NULL. |
| `email` | TEXT | Salesforce | Primary email address used for communications and MailChimp list membership. | `mary.johnson42@example.com` | NULL if no email on file; rare in practice. |
| `city` | TEXT | Salesforce | City of the contact's mailing address. | `New York`, `Charlottesville`, `Chicago` | NULL if address is incomplete. |
| `state` | TEXT | Salesforce | Two-letter US state abbreviation of the contact's mailing address. | `VA`, `NY`, `DC` | NULL if address is incomplete. |
| `zip_code` | TEXT | Salesforce | 5-digit US ZIP code of the contact's mailing address. | `22901`, `10001`, `20001` | NULL if address is incomplete. |
| `donor_status` | TEXT | Derived | Categorical giving status: `active` (gave within last 2 years), `lapsed` (gave 2+ years ago), `new_donor` (first gift within ~18 months), `prospect` (no gift on record). | `active`, `lapsed`, `prospect`, `new_donor` | Never NULL; derived at data load time. |
| `contact_created_date` | DATE | Salesforce | Date the contact record was created in Salesforce; proxy for when IASC first became aware of this person. | `2010-03-15`, `2019-11-01` | Rarely NULL; defaults to import date if unknown. |
| `first_gift_date` | DATE | Salesforce | Date of the contact's earliest recorded gift. | `1998-12-12`, `2015-06-03` | NULL for prospects (no giving history). |
| `last_gift_date` | DATE | Salesforce | Date of the contact's most recent gift. | `2024-11-28`, `2021-03-10` | NULL for prospects. For lapsed donors, always earlier than 2024-02-25. |
| `total_gifts` | REAL | Salesforce | Cumulative lifetime giving amount in USD. | `250.00`, `15000.00`, `1200000.00` | NULL for prospects. |
| `total_number_of_gifts` | INTEGER | Salesforce | Total count of individual gift transactions on record. | `1`, `12`, `47` | NULL for prospects. |
| `average_gift` | REAL | Derived | Mean gift amount: `total_gifts / total_number_of_gifts`. | `125.00`, `1250.00` | NULL for prospects. |
| `giving_vehicle` | TEXT | Salesforce | Predominant method used for gifts: `check`, `online`, `stock`, `DAF` (donor-advised fund), or `wire`. | `online`, `DAF`, `stock` | NULL for prospects. |
| `subscription_type` | TEXT | Salesforce | Type of Hedgehog Review subscription: `print`, `digital`, `both`, or `none`. | `digital`, `print`, `both`, `none` | Never NULL; `none` if no subscription exists. |
| `subscription_status` | TEXT | Salesforce | Current subscription state: `active`, `expired`, or `never` (no subscription of this type was ever held). | `active`, `expired`, `never` | Never NULL. |
| `subscription_start_date` | DATE | Salesforce | Date the contact's first subscription began. | `2008-09-01`, `2021-01-15` | NULL when `subscription_type` is `none`. |
| `email_open_rate` | REAL | MailChimp | Proportion of emails opened over the contact's lifetime in MailChimp (0.0–1.0). | `0.28`, `0.05`, `0.71` | NULL for a minority of contacts not on the MailChimp list or with no send history. |
| `last_email_click_date` | DATE | MailChimp | Date the contact last clicked a link in a MailChimp email. | `2024-08-14`, `2023-12-01` | NULL if the contact has never clicked, or if MailChimp data is unavailable. |
| `event_attendance_count` | INTEGER | Salesforce | Total number of IASC events (galas, lectures, receptions) the contact has attended, as logged in Salesforce. | `0`, `2`, `7` | Never NULL; defaults to 0 for contacts with no event history. |
| `wealth_score` | INTEGER | WealthEngine | Estimated philanthropic giving capacity on a 1–10 scale (10 = highest capacity), sourced from WealthEngine screening. | `3`, `7`, `10` | NULL for a significant portion of contacts not yet screened by WealthEngine. |
| `notes` | TEXT | Salesforce | Free-text notes entered by development staff, such as meeting context, referral source, or communication preferences. | `Met at conference 2019`, `Prefers email contact` | NULL for most contacts with no recorded notes. |

---

## Table: gifts

One row per individual gift transaction. Prospects have no rows in this table. The sum of `amount` per `contact_id` equals that contact's `total_gifts` in the contacts table.

| Field | Data Type | Source | Description | Example Values | NULL Handling |
|---|---|---|---|---|---|
| `gift_id` | INTEGER (PK) | Derived | Auto-incrementing surrogate key for the gift transaction. | `1`, `42`, `1807` | Never NULL; primary key. |
| `contact_id` | TEXT (FK) | Salesforce | Foreign key referencing `contacts.contact_id`; identifies the donor who made this gift. | `003XX00000AbCd1234` | Never NULL; every gift belongs to a contact. |
| `gift_date` | DATE | Salesforce | Date the gift was received or processed by IASC. Biased toward November–December (year-end giving season). | `2023-12-15`, `2021-11-02` | Never NULL. |
| `amount` | REAL | Salesforce | Dollar value of this individual gift in USD. Always ≥ $1.00. | `100.00`, `5000.00`, `250000.00` | Never NULL. |
| `gift_type` | TEXT | Salesforce | Categorization of the gift: `one_time`, `recurring` (part of a pledge or installment plan), `planned_giving` (bequest or deferred gift), or `event` (ticket purchase / event-linked gift). | `one_time`, `recurring` | NULL if not yet categorized in Salesforce. |
| `campaign` | TEXT | Salesforce | Name of the fundraising campaign the gift is attributed to, as entered in Salesforce. | `Year-End Appeal 2023`, `Spring Gala 2022`, `Annual Fund 2021` | NULL for unrestricted or unattributed gifts (a portion of rows). |

---

## Table: interactions

One row per logged touchpoint between IASC staff (or systems) and a contact. The volume of interactions per contact is loosely correlated with email engagement and event attendance. Prospects and low-engagement donors may have zero rows.

| Field | Data Type | Source | Description | Example Values | NULL Handling |
|---|---|---|---|---|---|
| `interaction_id` | INTEGER (PK) | Derived | Auto-incrementing surrogate key for the interaction record. | `1`, `88`, `2450` | Never NULL; primary key. |
| `contact_id` | TEXT (FK) | Salesforce / MailChimp | Foreign key referencing `contacts.contact_id`; identifies the contact involved in this interaction. | `003XX00000AbCd1234` | Never NULL; every interaction belongs to a contact. |
| `interaction_date` | DATE | Salesforce / MailChimp | Date the interaction occurred or was logged. | `2023-04-10`, `2024-11-30` | Never NULL. |
| `interaction_type` | TEXT | Derived | Categorical type of interaction: `email_open`, `email_click` (from MailChimp), `event_attended`, `meeting`, `phone_call`, or `mail_sent` (from Salesforce). | `email_open`, `meeting`, `event_attended` | Never NULL. |
| `details` | TEXT | Salesforce / MailChimp | Free-text description of the interaction — campaign name for email events, event name for attendance, brief note for meetings and calls. | `Year-End Appeal 2023`, `Spring Gala 2022`, `Cultivation lunch` | NULL for a minority of interactions where no additional detail was recorded. |

---

## Notes on NULL handling and data quality

1. **Prospects vs. donors.** Contacts with `donor_status = 'prospect'` have NULL in all gift-related fields (`first_gift_date`, `last_gift_date`, `total_gifts`, `total_number_of_gifts`, `average_gift`, `giving_vehicle`). Query tools must handle this explicitly to avoid filtering out prospects when that population is relevant.

2. **WealthEngine coverage.** A significant portion of contacts lack a `wealth_score` because WealthEngine screening is not run on every record. Absence of a wealth score does not imply low capacity; it means the contact has not yet been screened. Treat NULL wealth scores as missing, not as zero.

3. **MailChimp coverage.** A minority of contacts have NULL `email_open_rate`. These are contacts not subscribed to the MailChimp list (e.g., mail-only donors), contacts added after the last MailChimp sync, or contacts who opted out of email.

4. **`average_gift` is derived.** It is stored for query convenience but is always equal to `total_gifts / total_number_of_gifts`. Do not treat it as an independent field; recompute from the gifts table for transaction-level analysis.

5. **`donor_status` is derived at load time.** It is not a field that development staff manually maintain. Changes to giving history (e.g., a lapsed donor makes a new gift) require re-running `generate_mock_data.py` or updating this field via a recalculation script.

6. **Gift amounts in the gifts table.** Individual gift `amount` values are generated to approximate `average_gift` per contact but will not match exactly due to rounding. The sum of amounts per contact is guaranteed to equal `total_gifts` to within $0.01.

7. **Date constraints.** `first_gift_date` is always ≤ `last_gift_date`. `contact_created_date` is always ≤ `first_gift_date` for donors. For lapsed donors, `last_gift_date` is always before 2024-02-25 (i.e., more than 2 years before the prototype's reference date of 2026-02-25).
