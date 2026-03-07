# IASC organizational context

This document provides background on the Institute for Advanced Studies in Culture (IASC) for use in AI-generated fundraising analysis. It helps the system interpret data, make contextually appropriate recommendations, and avoid generic advice that doesn't fit IASC's situation.

---

## Who IASC is

The Institute for Advanced Studies in Culture is a research center and nonprofit publisher. IASC publishes *The Hedgehog Review: Critical Reflections on Contemporary Culture*, a peer-reviewed journal focused on ideas, values, and contemporary cultural life. The journal's audience is academically oriented — scholars, intellectuals, and engaged general readers who care about the life of the mind.

IASC operates its own development function. Some donors have multiple institutional relationships: they may be university alumni, Hedgehog Review subscribers, event attendees, and IASC donors simultaneously. This layered relationship is an asset but requires care in communications to avoid generic institutional messaging.

---

## Development team

**Andrew** leads development strategy, major donor relationships, and fundraising travel. He uses a "center-out" approach to trip planning: beginning with the closest and strongest relationships (board-connected donors, long-term major donors), then expanding to warm prospects in the same geography. He prioritizes personal meetings as the primary cultivation and solicitation vehicle for major donors.

**Rosemary** manages donor data, operations, and reporting. She is the primary user of this tool for operational analysis and reporting; Andrew relies on her analysis for trip planning and portfolio decisions.

---

## Data systems

**Salesforce** is the system of record for donor and prospect information. It holds giving history, contact information, relationship notes, and stage tracking. Data quality is uneven: many records are incomplete, particularly for older contacts and non-donors.

**MailChimp** manages email campaigns and tracks engagement (opens, clicks, unsubscribes). Engagement data is incomplete for older contacts and is affected by Apple Mail Privacy Protection (which inflates reported open rates for Apple Mail users). Click data is more reliable than open data.

**WealthEngine** provides wealth screening: estimated net worth, real estate holdings, philanthropic giving history, and a composite wealth rating. Coverage is partial -- screening has not been applied uniformly across the full donor list, and a meaningful share of records have no match. Treat wealth ratings as one signal among many, not as a definitive ranking.

---

## Current situation and priorities

IASC is in a cultivation phase, focused on two simultaneous goals: acquiring new donors from the subscriber base and re-engaging lapsed donors. Recent campaigns have emphasized broadening the donor base -- increasing the number of first-time donors has been as important as dollar totals.

This dual focus means the pipeline contains a mix of warm prospects (Hedgehog Review subscribers who have never given) and lapsed donors (people who gave previously but not recently). These two groups require different messaging and different asks.

---

## Donor base characteristics

- **Scale:** Hundreds of donors, not thousands. This is a relationship-driven development program, not a mass-market one.
- **Giving pattern:** Most donors give once per year, typically at year-end. Frequency is therefore a weak signal; recency and amount are more meaningful for segmentation.
- **Geography:** Concentrated in Charlottesville and the broader Virginia area. Secondary concentration in the Northeast corridor: Washington DC, New York City, and Boston. Additional donors scattered across other metro areas. This geographic pattern directly shapes travel priorities.
- **Donor profile:** Academically oriented, interested in ideas and cultural commentary, often connected to universities. IASC's appeals work best when they are intellectually framed — donors respond to mission and ideas, not generic charity language. Some donors have multiple university affiliations.
- **Prospect pipeline:** *The Hedgehog Review* subscriber list is the primary source of new donor prospects. Subscribers who have not yet donated are warm leads — they have demonstrated affinity through subscription and (for many) sustained email engagement.

---

## Data quality challenges

When interpreting data from this system, keep the following in mind:

- **Missing fields are common.** Many records lack complete contact information, WealthEngine scores, or MailChimp engagement history. Absence of data is not the same as absence of giving capacity or interest.
- **WealthEngine gaps.** A significant portion of records have no wealth screening data. Do not treat unscreened records as low-priority by default; they may simply not have been matched.
- **MailChimp engagement gaps.** Older contacts may predate the current MailChimp setup or have inconsistent tracking due to technical issues. Low engagement scores for long-tenured donors may reflect data limitations, not actual disengagement.
- **Salesforce data entry variation.** Giving history is generally reliable. Contact details, relationship notes, and stage classifications are entered manually and vary in completeness.

When the system surfaces recommendations, it should flag when those recommendations are based on incomplete data and suggest manual verification where it matters.

---

## How to use this context

This document is loaded into the AI system's context to help it give advice that fits IASC's actual situation. When the system makes recommendations about trip planning, it should apply the center-out principle. When it interprets email engagement, it should account for known data quality limits. When it segments donors or prospects, it should reflect IASC's typical giving pattern (annual, year-end) rather than generic nonprofit norms.

Recommendations should always prioritize actual donor data over general best practices, and should acknowledge uncertainty when data is incomplete.
