# Cubic³ Market Scan — editorial rubric and content specification

Version 1.0 · September 2026 · Owner: Business Development

This document defines what the weekly Market Scan covers, how items are scored and selected, how they are written, and how the output maps onto the template (`template.html`). The agent is prompted directly from this file; changing this file changes the product.

---

## 1. Scope

### 1.1 Domains (rows of the heat-map)

| Domain | Includes | Excludes |
|---|---|---|
| Automotive OEMs | Passenger and commercial vehicle makers, their captive software/mobility units, Tier-1s when the story is about an OEM platform | Dealer news, sales volumes, financial results with no technology angle |
| Robotics OEMs | Humanoid, mobile, warehouse, service, and industrial robot makers; autonomous-vehicle and robotaxi companies; autonomy-stack vendors when they sign an OEM | Academic papers, component-level chip news |
| Fleets | Logistics and delivery fleets, leasing and rental companies, car-sharing and ride-hailing operators, bus and public-transport operators, fleet telematics and fleet-management platforms | Fuel prices, driver recruitment, fleet sales volumes with no technology angle |
| Energy | Charge-point operators, utilities and grid operators, battery/storage OEMs, V2G/V2X, energy retailers touching vehicles | Commodity prices, generation policy with no asset-connectivity angle |
| Agri / industrial OEMs | Agricultural, construction, mining, materials-handling and off-highway equipment makers | Crop prices, real-estate, pure commodity news |

### 1.2 Themes / lenses (columns of the heat-map)

An item must touch at least one theme to qualify. Tag every theme an item genuinely touches, up to four, using the codes in brackets.

| Lens | The question it answers |
|---|---|
| SDV (`sdv`) | Is the machine becoming a software product — vehicle OS, OTA, app stores, feature-on-demand, centralised compute? |
| Connectivity (`connectivity`) | Who provides, orchestrates, or pays for the link — eSIM, MVNO deals, satellite/NTN, roaming, network APIs, spectrum? |
| AI (`ai`) | Is AI being deployed on the machine or on its data — edge inference, fleet-level models, copilots, autonomy licensing? |
| Data management (`data`) | Who owns, moves, monetises, or is regulated on the data — platforms, marketplaces, data-access rules, privacy? |
| Digital twins (`twins`) | Is a live model of the asset or fleet being built and used for simulation, prediction, or operations? |
| Regulatory framework (`regulatory`) | What laws, rules, type-approval or standards obligations change what makers and operators must do — EU Data Act, Cyber Resilience Act, UNECE R155/R156, AV and robotaxi rules, FCC and MIIT decisions, V2G and grid codes? |
| Cybersecurity (`cyber`) | Is the security of connected machines changing — vulnerabilities and attacks, security recalls, R155 / ISO/SAE 21434 compliance, security certifications, secure elements and eSIM security assurance? |
| Quality (`quality`) | Is product quality or safety in question — safety investigations, recalls, OTA fixes for defects, software quality, ISO 26262 / functional safety, reliability programmes? |
| Telematics services (`telematics`) | Who sells services on top of the connection — TSP and fleet-telematics offers, remote diagnostics, usage-based insurance, stolen-vehicle tracking, eCall, fleet-management platforms and their pricing? |

### 1.3 Time window

Items published Monday 00:00 to Sunday 23:59 UTC of the scan week. Items older than 7 days are excluded unless a material development happened inside the window.

---

## 2. Sources

Tier 1 (always scanned): OEM and vendor newsrooms; regulator and standards bodies (UNECE WP.29, EU Commission, NHTSA, FCC, MIIT, national type-approval authorities such as KBA, GSMA, 3GPP, AUTOSAR, COVESA, SOAFEE, ISO/SAE); recall databases and security advisories (NHTSA recalls, EU Safety Gate, Auto-ISAC, CISA/ENISA, vendor PSIRTs); SoftBank Group and portfolio announcements.

Tier 2 (scanned, weighted lower): Trade press for automotive, robotics, fleets and logistics, energy, and agri/construction; telco and IoT trade press; telematics and fleet-management press; automotive cybersecurity research and press; law-firm regulatory briefings; analyst briefings.

Tier 3 (context only, never sole source): General business press, aggregator sites, social posts by executives.

Rules: every published item cites at least one Tier 1 or Tier 2 source with a date. Press releases about a partnership count as one source for each party. Paywalled articles are cited by headline and outlet only.

---

## 3. Scoring

Each candidate is scored 0–10 as the sum of three components.

| Component | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Significance (0–4) | Routine | Minor update | Notable for one company | Sector-level shift | Category-defining or regulatory |
| Novelty (0–3) | Repeat of known plan | Incremental | New direction for the actor | First of its kind in the domain | — |
| Relevance to Cubic³ (0–3) | None | Indirect market context | Touches a customer, prospect, competitor, or partner | Direct implication for orchestration, VAS, Fleet Wallet, or SoftBank | — |

Modifiers: −2 if the only source is Tier 3; +1 if two or more domains are involved; +1 if an existing Cubic³ customer or named prospect is a party.

Thresholds:
- Score ≥ 6 → qualifies for a domain section.
- Score 4–5 → Watch list.
- Score ≤ 3 → dropped, logged only.

---

## 4. Selection rules

1. Signal of the Week: the single highest-scoring item overall; ties broken by Relevance, then Significance.
2. Domain sections: up to 3 items per domain, highest score first. A domain with fewer than 2 qualifying items shows what it has; an empty domain shows one line: "No qualifying items this week."
3. No actor appears in more than two items on the same page, so the scan is not captured by one company's news cycle.
4. Deals table: every qualifying item that is a signed agreement, investment, or acquisition, regardless of whether it also appears as a card. Maximum 6 rows.
5. Watch list: up to 6 items scored 4–5, preferring items likely to mature within a month.
6. Heat-map counts: the number of qualifying items (score ≥ 6) per domain × theme cell; an item tagged with several themes counts once in each. The script computes the heat-map from the items; the agent does not.
7. Read-across: written last, after selection, and must reference the heat-map.

---

## 5. Item schema

The curation pass emits one JSON object per item. The publish step fills the template from these fields.

```json
{
  "id": "2026-W37-007",
  "domain": "automotive | robotics | fleets | energy | agri",
  "lenses": ["sdv", "connectivity", "ai", "data", "twins", "regulatory", "cyber", "quality", "telematics"],
  "headline": "≤ 14 words, present tense, names the actor",
  "summary": "2–3 sentences, ≤ 40 words, facts only",
  "so_what": "1 sentence, ≤ 20 words, plain factual significance; no advice or actions",
  "sources": [{"outlet": "", "date": "YYYY-MM-DD", "url": "", "tier": 1}],
  "score": {"significance": 3, "novelty": 2, "relevance": 3, "modifiers": 0, "total": 8},
  "actors": ["Company A", "Company B"],
  "deal": {"who": "", "with": "", "what": "", "relevance": "Competitive | Prospect | Partner | Customer | Fleet Wallet | SoftBank"} ,
  "relationship_flags": ["customer", "prospect", "competitor", "partner", "softbank"]
}
```

Edition-level fields:

```json
{
  "edition": 1,
  "week_label": "Week of 7–13 September 2026",
  "generated": "2026-09-12",
  "counts": {"screened": 48, "qualified": 11, "customer_relevant": 3},
  "heatmap": {"automotive": {"sdv": 7, "connectivity": 4, "ai": 5, "data": 2, "twins": 3}, "robotics": {}, "fleets": {}, "energy": {}, "agri": {}},
  "signal": "<item id>",
  "read_across": ["paragraph 1", "paragraph 2"]
}
```

---

## 6. House style

- Headlines name the actor and the action: "Company X moves its data platform to a single twin layer", not "Big changes in data platforms".
- Summaries carry the specifics: scope, geography, timing, money, partners. No adjectives the facts do not earn; no "game-changing", "leverage", "ecosystem play".
- The So-what line states, in plain words, why the fact is significant: what it changes in the market and for whom (e.g. "First European OEM to make eSIM standard across its whole range."). It describes; it does not advise. No recommendations, no actions for Cubic³ or anyone else, no "should", "must", "opportunity to", "time to", "watch for", and no speculation beyond what the sources support.
- British English, sentence case, numerals for all numbers over nine, currency in the original with a GBP or EUR conversion in brackets where above £10m.
- Company names as they style themselves; no stock tickers.
- Sources are named with the date of publication, never "reports say".
- Layout: page 1 is the overview (Signal of the week, the nine-theme heat-map, the read-across); the verticals, deals and watch list follow from page 2. The edition is capped at `layout.max_pages` in config.yaml (default 4); the script trims deals, the watch list and then cards to stay within it. The agent must keep to the per-field word limits in §5; over-length text is rewritten, never cut mid-sentence.

---

## 7. Template slot map

| Template element | Filled from |
|---|---|
| Masthead edition and week | `edition`, `week_label` |
| Signal of the Week | item referenced by `signal`: headline, summary, so_what, sources |
| Heat-map | computed from items with score ≥ 6: domain × nine themes; cell class h0 (0), h1 (1–2), h2 (3–5), h3 (6+) |
| The read-across | `read_across[0..1]`; stats from `counts` |
| Domain sections | top 3 items per domain by score; tags from `lenses` |
| Deals table | items with a non-empty `deal` |
| Watch list | items with score 4–5 |
| Footer | `edition`, `generated`, screened count |

---

## 8. Agent prompt skeleton (for the pipeline build)

**Scan pass** — one web-search call per domain (5 domains) covering all nine themes, with dedicated searches for regulatory, cybersecurity, quality and telematics services; past 7 days, English and Japanese, returning up to 10 candidates each with outlet, date, URL, and a two-line gist. De-duplicate on actor + event.

**Curation pass** — receives candidate list and this rubric (§1–§4, §6). Scores each candidate, returns the JSON in §5, and writes the read-across last.

**Review pass** — a second model call checks: every item has a Tier 1–2 source and date; no field exceeds its word limit; no actor exceeds two cards per page; the Signal is the top score; the heat-map counts reconcile with the items. Failures are corrected before render.

**Publish** — fill `template.html`, render to A4 PDF with WeasyPrint within `layout.max_pages`, email as attachment with the Signal headline as the subject line.

---

## 9. Open decisions for Ric

1. Customer, prospect, and competitor lists to feed the Relevance score and the deals-table tags (a simple CSV is enough).
2. Whether the Japanese-language scan runs every week or only when Japanese accounts are in the news.
3. Send day and time (proposed: Monday 06:00 UK).
4. Whether the review pass should also flag items to escalate to you mid-week rather than waiting for the edition.

---

## Appendix A — Actor list (v1, 12 September 2026)

The names below are examples that define each category, not a closed list. The agent is expected to recognise comparable companies (same domain, same role, similar scale or ambition) and treat them the same way — e.g. Stellantis, VW Group or Nissan as automotive named accounts; CNH or Caterpillar as agri/industrial; Enel or Iberdrola as energy; Cruise, Nuro or Motional as autonomous-vehicle names; Europcar, Uber or FedEx as fleets; 1NCE, Telefónica Kite or Vodafone IoT as connectivity competitors. When the agent extends a category it says so in the item's `relationship_flags` (add `"inferred"`) so the addition can be confirmed or rejected.

Named accounts score Relevance 2 by default and take the +1 modifier in §3; competitors score Relevance 2 and are tagged Competitive; data-management platforms are tagged Partner. Update this table rather than the prose above.

| Actor | Domain | Role |
|---|---|---|
| GM | Automotive | Named account |
| BMW | Automotive | Named account |
| Ford | Automotive | Named account |
| Hyundai | Automotive | Named account |
| Honda | Automotive | Named account |
| Toyota | Automotive | Named account |
| AGCO | Agri / industrial | Named account |
| John Deere | Agri / industrial | Named account |
| Komatsu | Agri / industrial | Named account |
| EDF | Energy | Named account |
| TEPCO | Energy | Named account |
| Vattenfall | Energy | Named account |
| Boston Dynamics | Robotics | Named account |
| ABB Robotics | Robotics | Named account |
| Zoox | Robotics — autonomous vehicles | Named account |
| Waymo | Robotics — autonomous vehicles | Named account |
| Wayve | Robotics — autonomous vehicles | Named account |
| Pony.ai | Robotics — autonomous vehicles | Named account |
| May Mobility | Robotics — autonomous vehicles | Named account |
| DHL, Amazon, UPS | Fleets — logistics | Named account (proposed — please confirm) |
| Ayvens, Arval, Hertz, Sixt | Fleets — leasing and rental | Named account (proposed — please confirm) |
| Samsara, Geotab, Webfleet | Fleets — telematics platforms | Watch (proposed — partner or competitor, please confirm) |
| KDDI / Soracom | Connectivity | Competitor |
| NTT / Transatel | Connectivity | Competitor |
| Data-management platforms (any) | Data management | Partner — flag deals as partnership opportunities, not threats |

Role vocabulary: Named account (customer or prospect; refine to Customer / Prospect when useful), Competitor, Partner, Watch.
