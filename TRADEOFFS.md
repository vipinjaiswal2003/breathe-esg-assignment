# TRADEOFFS.md — Three Things I Deliberately Did Not Build

## 1. Automated API Connectors (SAP OData, Concur Webhooks, Utility APIs)

### What I didn't build

I did not build automated, real-time data connectors that pull from source systems on a schedule or via webhooks. The prototype uses file upload for all three source types.

### Why I didn't build it

Automated connectors are an operational problem, not a data model problem. They require:
- **SAP OData:** SAP S/4HANA API configuration, OAuth2 credentials, pagination handling, delta query support, and error recovery for when the SAP system is down for maintenance
- **Concur ESS v4 webhooks:** A publicly accessible HTTPS endpoint, Concur partner certification, event subscription management, and retry logic for failed deliveries
- **Utility APIs (PG&E Share My Data, UtilityAPI):** Per-utility OAuth2 flows, data format normalization across dozens of utilities, and handling of utility-specific rate limits and data lag

Each of these is a multi-week integration project on its own. Building all three would consume the entire 4-day timeline and leave no time for the data model, normalization pipeline, or review workflow — which are the parts that demonstrate judgment.

### What I built instead

File upload that accepts the same data shapes these APIs would produce. The parser logic is identical whether the data comes from a file or an API. When we add API connectors later, they feed into the same parsers and normalization pipeline.

### How long it would take to add

- SAP OData: 2-3 days (if the client has S/4HANA and can provide API credentials)
- Concur webhooks: 2-3 days (requires Concur partner sandbox access)
- Utility API: 3-5 days per utility (each has different authentication and data formats)

---

## 2. Role-Based Access Control (RBAC) and Permission System

### What I didn't build

I did not build a proper role-based access control system. The `TenantMembership.role` field (admin/analyst/viewer) exists in the data model, but the API does not enforce permissions based on it. Any authenticated user within a tenant can perform any action.

### Why I didn't build it

RBAC seems simple on the surface but has deep complexity:
- **Granularity questions:** Can an analyst lock records for audit, or only an admin? Can a viewer add comments? Can an admin re-open a locked record? These are policy decisions, not technical decisions.
- **Cross-tenant isolation:** The middleware sets `request.tenant`, but it doesn't prevent a user from switching tenants and accessing another client's data. In production, you'd want tenant membership verification on every request.
- **API endpoint permissions:** Every view would need a permission class that checks the user's role within the active tenant. This is ~20 views × 4 permission levels = 80 permission rules to define and test.
- **The PM hasn't decided:** Without clear requirements on who can do what, implementing RBAC now would mean making up rules that might conflict with what the PM actually wants.

### What I built instead

Authentication (you must be logged in) and tenant scoping (you can only see data for tenants you belong to). The role field is in the data model, ready for enforcement. Adding permission checks is a mechanical task once the policy is defined.

### How long it would take to add

1-2 days for basic RBAC (admin/analyst/viewer with defined permissions per endpoint).

---

## 3. Time-Series Data and Reporting Period Management

### What I didn't build

I did not build time-series data handling or reporting period management. Specifically:
- No fiscal year / quarter / custom period model
- No monthly allocation logic for utility billing periods that span calendar months
- No trend analysis or period-over-period comparison
- No data aggregation by reporting period
- No handling of the gap between billing periods and reporting periods

### Why I didn't build it

This is the hardest unsolved problem in ESG data management, and it deserves more than a token implementation:

- **Billing periods ≠ calendar months ≠ reporting periods.** A utility bill from June 28 to July 27 spans two calendar months and might fall in Q1 of one fiscal year and Q4 of another. There is no universally correct way to allocate this consumption.
- **SAP posting dates ≠ consumption dates.** A material document posted on July 1 might represent fuel consumed in June. The posting date is an accounting artifact, not a physical measurement.
- **Travel dates span timezones.** A flight departing Mumbai at 23:30 IST and arriving in Singapore at 07:00 SGT crosses two calendar days and two timezones.
- **Annual vs quarterly reporting.** Different jurisdictions and frameworks require different reporting frequencies, and the allocation logic is different for each.

### What I built instead

Simple date-based activity records. Each normalized emission has an `activity_date` (the best approximation of when the activity occurred) and optional `reporting_period_start`/`reporting_period_end` for utility billing periods. This is sufficient for the review workflow but not for period-based reporting.

### How long it would take to add

5-7 days for a proper reporting period model with:
- Configurable fiscal years per tenant
- Billing period → reporting period allocation (pro-rata by days)
- Period-over-period comparison API
- Monthly/quarterly/annual aggregation views

---

## The Pattern

These three tradeoffs share a common theme: I prioritized the **data model and business logic** over **infrastructure and UX features**. The data model is the foundation that everything else builds on. If the model is wrong, no amount of automated connectors or RBAC or reporting will fix it. If the model is right, adding these features later is straightforward.

The assignment asks us to demonstrate judgment. I judge that a sharp data model with honest tradeoffs is more valuable than a feature-rich app with shallow foundations.
