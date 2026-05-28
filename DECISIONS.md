# DECISIONS.md — Ambiguity Resolutions and Design Choices

Every ambiguity I encountered, what I chose, and what I'd ask the PM if I could.

---

## Data Source Decisions

### 1. SAP Export Format: Flat File (Tab-Delimited)

**Options:** IDoc, Flat File, OData, BAPI, ALV Grid Export, SAP Query

**Choice:** Flat file (tab-delimited from SE16N or Z-report)

**Why:** In the real world, the person pulling SAP data for ESG reporting is a sustainability lead, not an SAP Basis administrator. They can run SE16N (the SAP data browser) and export to a spreadsheet. They cannot configure IDoc/ALE middleware, set up OData services, or write RFC programs. The flat file is what a non-technical user can produce on their own.

**What I'd ask the PM:** "Does the client have a dedicated SAP team that could set up automated data extraction (OData/IDoc), or are we building for a sustainability lead who exports manually?"

**What would break in production:** 
- The client might have S/4HANA and expect OData — we'd need to build an API connector
- Very large SAP installations might have millions of material documents per quarter — file upload would time out
- Some clients use SAP BW (Business Warehouse) instead of ECC/S4HANA, which has different extraction options

---

### 2. Utility Data Format: Portal CSV Export

**Options:** Portal CSV, Green Button XML/CSV, PDF Bills, Utility API (PG&E Share My Data, UtilityAPI), ESP/MDM System Export

**Choice:** Portal CSV export (what a facilities team downloads from the utility website)

**Why:** Every utility portal offers a CSV download. It's the lowest common denominator. Green Button adoption is spotty — many Indian and European utilities don't support it. PDF bills require OCR (a separate project). Utility APIs require per-utility integration contracts and weeks of setup. For a prototype, CSV is the format that works with any utility, anywhere.

**What I'd ask the PM:** "Are the client's utilities primarily in India or the US? If US, Green Button might be viable. If India, CSV is the only option — Indian utilities don't offer APIs or Green Button."

**What would break in production:**
- Each utility has different column names and formats — we'd need format-specific adapters
- Interval (15-minute) data would require a different parser
- Net metering (solar panels) produces import/export data that this parser doesn't handle
- Some utilities include taxes and surcharges in the total charge; our parser ignores cost entirely for emission calculations

---

### 3. Travel Data Format: Concur Itinerary API v4 JSON

**Options:** Concur Itinerary API v4 (JSON), Concur Standard Accounting Extract (CSV/SFTP), Navan API, Manual spreadsheet

**Choice:** Concur Itinerary API v4 JSON format, accepted via file upload

**Why:** Concur is the dominant corporate travel platform (~60% market share). The Itinerary API v4 provides structured JSON with typed segments (Air, Hotel, Car, Rail) and already includes carbon emission estimates and distance data. For the prototype, we accept JSON files that match the Concur API shape. In production, we'd connect to the actual Concur API via webhook (ESS v4) for real-time updates.

I rejected Navan because they have essentially no public API documentation and most integrations use CSV/SFTP export or browser automation.

**What I'd ask the PM:** "Which travel platform does the client actually use? If it's not Concur, the ingestion format will be completely different. Also, do they want real-time trip ingestion (webhooks) or periodic batch imports?"

**What would break in production:**
- Concur API has rate limits (10 req/min for backfill)
- TripLink bookings and manual entries often have empty segment data
- Employee ID in Concur is a UUID that doesn't match HR employee IDs — we'd need a user provisioning integration
- Historical data is limited to 6 months via the API

---

## Ingestion Mechanism Decisions

### 4. File Upload for All Three Sources

**Options:** File upload, API pull, Manual paste, Scheduled SFTP pull

**Choice:** File upload for all three sources

**Why:** File upload is the simplest mechanism that works for a prototype. It doesn't require API credentials, webhook configuration, or scheduled jobs. The user uploads a file, we parse it, normalize it, and surface the results.

**What I'd ask the PM:** "How often does data come in? If it's daily, file upload is fine. If it's hourly or real-time, we need API integration with webhooks."

**Production evolution:**
- SAP: Scheduled SFTP pull or SAP OData integration
- Utility: Green Button Connect My Data (automated) or utility API
- Travel: Concur ESS v4 webhooks for real-time trip ingestion

---

### 5. SAP Movement Type Filtering

**Choice:** Only process BWART 201 (fuel to cost center) and 261 (fuel to production order). Exclude 101 (goods receipt), 311 (plant transfer), 561 (initial stock entry), and 701 (revaluation).

**Why:** Only consumption-type movement types produce emissions. Goods receipts (101) are procurement events, not consumption. Plant transfers (311) are internal movements, not emissions. Including them would double-count or misattribute emissions.

**What I'd ask the PM:** "Does the client track fugitive emissions (refrigerant leaks) in SAP? Those are typically in the PM module (PMCO/AFRU tables), not in MSEG. We'd need a separate extraction for that."

---

### 6. Fuel Type Classification Heuristic

**Choice:** Keyword matching on material description and material group

**Why:** SAP has no standard "fuel" classification. Each client has their own material groups (MATKL) that may or may not indicate fuel. I use keyword matching as a starting heuristic with the expectation that clients will provide a mapping table.

**What I'd ask the PM:** "Can the client provide their material group catalog (T023/T023T table) so we can map material groups to fuel types? Without it, we're guessing."

---

### 7. Utility Meter Multiplier Handling

**Choice:** Apply meter multiplier (CT/PT ratio) during normalization

**Why:** Large commercial meters use current transformers (CT) and potential transformers (PT) that scale the actual consumption. A meter reading of 1,000 kWh with a multiplier of 40 means actual consumption of 40,000 kWh. Forgetting to apply the multiplier is one of the most common errors in utility data ingestion.

**What I'd ask the PM:** "Do the client's utility bills include the meter multiplier, or do we need to maintain a separate lookup table of multiplier values per meter?"

---

### 8. Flight Distance Calculation

**Choice:** Calculate great-circle distance from IATA airport codes with 9% DEFRA uplift factor

**Why:** Concur provides Miles for most air segments, but not all. When distance is missing, we calculate it from airport codes using the Haversine formula. The 9% uplift accounts for indirect routing (planes don't fly in straight lines due to air traffic control, weather, and preferred routes).

**What I'd ask the PM:** "Does the client want DEFRA's 9% uplift applied, or do they prefer to use the exact distances from Concur without adjustment? Some jurisdictions have different uplift requirements."

---

### 9. Default Cabin Class for Missing Values

**Choice:** Default to Economy when cabin class is missing (~5-15% of bookings)

**Why:** DEFRA guidance states that where cabin class is unknown, the most conservative (lowest emission) assumption should be used, which is Economy. This avoids overstating emissions.

**What I'd ask the PM:** "Is Economy the right default for the client's travel policy? If they primarily fly Business class, defaulting to Economy could significantly understate their travel emissions."

---

### 10. Car Rental Distance Fallback

**Choice:** When distance driven is not provided (which is almost always the case), estimate 300 km (3 days × 100 km/day average) and flag as an anomaly

**Why:** Car rental bookings almost never include distance driven. The booking only tells you the car type and rental duration. Without telematics integration, the best we can do is estimate based on typical usage patterns. The estimate is flagged so the analyst can override it if they have better data.

**What I'd ask the PM:** "Does the client have fleet management or telematics data that could provide actual distances? If not, should we use a spend-based emission factor instead of distance-based?"

---

## Architecture Decisions

### 11. Multi-Tenancy: Shared Database with FK Scoping

**Options:** Schema-per-tenant, Database-per-tenant, Shared database with FK, Shared database with RLS

**Choice:** Shared database with FK scoping

**Why:** Simplest to implement for a prototype. One database, one set of migrations. The tradeoff is that every query must include a tenant filter — a missing filter could leak data between clients.

**What I'd ask the PM:** "How many clients do we expect to onboard initially? If <20, shared database is fine. If >100, we'd want PostgreSQL RLS or schema-per-tenant for isolation."

---

### 12. Date Format Handling

**Choice:** Try multiple date formats in sequence (ISO, German DD.MM.YYYY, US MM/DD/YYYY, UK DD/MM/YYYY)

**Why:** SAP exports use the date format configured in the user's profile. German users get DD.MM.YYYY, US users get MM/DD/YYYY. The parser tries all common formats and takes the first one that parses. This is a heuristic that works most of the time.

**Ambiguity:** MM/DD/YYYY vs DD/MM/YYYY is ambiguous for dates like 01/02/2024 (Jan 2 vs Feb 1). The parser tries MM/DD first for US format. This could be wrong for UK/Indian users.

**What I'd ask the PM:** "What is the client's SAP date format setting? This is critical for correct date parsing."

---

### 13. Decimal Separator Handling

**Choice:** Detect German vs English format by looking at the last separator position

**Why:** German SAP uses comma as decimal separator (1.234,56 = 1234.56), English SAP uses period (1,234.56 = 1234.56). The parser detects which format is used by checking whether the last separator is a comma or period.

**What I'd ask the PM:** "What language is the client's SAP login set to? This determines the decimal separator."

---

### 14. Scope 2 Reporting: Location-Based Only

**Choice:** Only implement location-based Scope 2 (grid-average emission factors)

**Why:** The GHG Protocol requires dual reporting (location-based AND market-based), but market-based reporting requires data about contractual instruments (RECs, PPAs, green tariffs) that we don't have from utility data alone. For the prototype, location-based is sufficient. Market-based would require a separate data source for contractual instruments.

**What I'd ask the PM:** "Does the client purchase renewable energy certificates (RECs) or have power purchase agreements (PPAs)? If so, we need to implement market-based Scope 2 with contractual instrument tracking."

---

### 15. Review Workflow: Linear States

**Choice:** States flow linearly: pending → flagged/approved/rejected → locked

**Why:** The simplest workflow that satisfies the requirement of "analysts review and sign off before data goes to auditors." Once locked, a record cannot be changed without unlocking it (which creates an audit trail entry).

**What I'd ask the PM:** "Does the client need a multi-level approval workflow (e.g., analyst reviews → manager approves → partner locks)? Or is single-level sufficient?"

---

### 16. SQLite for Prototype, PostgreSQL for Production

**Choice:** SQLite for development/prototype, PostgreSQL configuration ready for production

**Why:** SQLite requires zero setup — no database server, no connection strings. For a prototype that will be demoed and reviewed, this is pragmatic. The Django ORM abstraction means switching to PostgreSQL requires only a settings change.

**What I'd ask the PM:** "What is the target deployment environment? If we're deploying to Render or Railway, PostgreSQL is the default and we should use it from the start."

---

### 17. Token Authentication (Not JWT)

**Choice:** Django REST Framework TokenAuthentication

**Why:** Simpler than JWT for a prototype. One token per user, stored in the database, sent as an Authorization header. No token refresh logic needed. For a B2B tool used by a handful of analysts, this is sufficient.

**What I'd ask the PM:** "Does the client need SSO (SAML/OIDC) integration? If so, we'd need to implement OAuth2/OIDC instead of simple token auth."

---

### 18. What I Excluded from Each Source

**SAP:**
- Excluded: IDoc XML, BAPI/RFC, OData pagination, multi-line item aggregation, currency conversion
- Reason: These require SAP middleware (PI/PO) or custom ABAP development — not something a sustainability team can do

**Utility:**
- Excluded: Green Button XML, interval (15-min) data, PDF OCR, net metering, time-of-use disaggregation
- Reason: Each is a significant separate project. Interval data alone would require a different data model (time-series) and storage strategy

**Travel:**
- Excluded: Concur webhook (ESS), Concur SAE CSV, Navan format, expense report matching, multi-leg trip aggregation
- Reason: Webhook requires a publicly accessible endpoint and Concur partner certification. SAE CSV is for expense data, not travel data. Navan has no public API docs.
