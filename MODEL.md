# MODEL.md — Data Model and Justification

## Overview

The Breathe ESG data model is designed around one principle: **every normalized emission must trace back to its raw source through an unbroken chain.** An auditor should be able to look at any CO2e figure and answer: where did this come from, who touched it, and what changed?

## Entity-Relationship Diagram

```
┌─────────────┐
│   Tenant     │◄──────────────────────────────────────────────┐
│─────────────│                                              │
│ name, slug   │        ┌──────────────────┐                 │
│ industry     │        │   DataSource     │                 │
│ reporting_yr │◄───────│──────────────────│                 │
└──────┬───────┘        │ source_type      │                 │
       │                │ ingestion_mech.  │                 │
       │                │ config (JSON)    │                 │
       │                └────────┬─────────┘                 │
       │                         │                           │
       │         ┌───────────────┼───────────────┐           │
       │         ▼               ▼               ▼           │
       │  ┌─────────────┐ ┌────────────┐ ┌────────────┐     │
       │  │RawSAPRecord │ │RawUtilRec  │ │RawTravRec  │     │
       │  │─────────────│ │────────────│ │────────────│     │
       │  │ mblnr, bwart│ │ meter_num  │ │ trip_id    │     │
       │  │ matnr, werks│ │ bill_start │ │ segment_typ│     │
       │  │ menge, meins│ │ consum_kwh │ │ origin_code│     │
       │  │ budat, kostl│ │ rate_schdl │ │ cabin_cls  │     │
       │  └──────┬──────┘ └──────┬─────┘ └──────┬─────┘     │
       │         │               │               │           │
       │         └───────────────┼───────────────┘           │
       │                         ▼                           │
       │                ┌──────────────────┐                 │
       │                │IngestionBatch    │                 │
       │                │──────────────────│                 │
       │                │ status, filename │                 │
       │                │ total/success/   │                 │
       │                │ failed/flagged   │                 │
       │                │ quality_score    │                 │
       │                └────────┬─────────┘                 │
       │                         │                           │
       │                         ▼                           │
       │         ┌───────────────────────────┐               │
       │         │   NormalizedEmission      │               │
       │         │───────────────────────────│               │
       │◄────────│ tenant (FK)               │               │
       │         │ data_source (FK)          │               │
       │         │ batch (FK)                │               │
       │         │ emission_factor (FK)      │               │
       │         │                           │               │
       │         │ raw_record_type           │               │
       │         │ raw_record_id (UUID)      │──┐            │
       │         │ is_edited, edit_history   │  │            │
       │         │                           │  │            │
       │         │ scope, category           │  │            │
       │         │ activity_qty, activity_unit│  │            │
       │         │ original_qty, original_unit│ │            │
       │         │ co2e_kg, co2_kg, ch4_kg   │  │            │
       │         │                           │  │            │
       │         │ status (pending→approved  │  │            │
       │         │   →locked for audit)      │  │            │
       │         │ anomaly_flag, anomaly_notes│ │            │
       │         │ reviewed_by, reviewed_at   │ │            │
       │         │ locked_at                 │  │            │
       │         └───────────┬───────────────┘  │            │
       │                     │                  │            │
       │                     ▼                  │            │
       │          ┌─────────────────┐           │            │
       │          │  ReviewAction   │           │            │
       │          │─────────────────│           │            │
       │          │ action          │           │            │
       │          │ previous_status │           │            │
       │          │ field_changes   │           │            │
       │          │ notes           │           │            │
       │          └─────────────────┘           │            │
       │                                        │            │
       │          ┌─────────────────┐           │            │
       │          │   AuditLog      │           │            │
       │          │─────────────────│           │            │
       │◄─────────│ tenant          │           │            │
       │          │ action_type     │           │            │
       │          │ record_type     │           │            │
       │          │ record_id ──────│───────────┘            │
       │          │ before/after    │                        │
       │          └─────────────────┘                        │
       │                                                     │
       │          ┌─────────────────┐                        │
       │          │ EmissionFactor  │                        │
       │          │─────────────────│                        │
       │◄─────────│ tenant (nullable)│                       │
       │          │ scope, category │                        │
       │          │ co2e_factor     │                        │
       │          │ unit, source    │                        │
       │          └─────────────────┘                        │
       └─────────────────────────────────────────────────────┘
```

## Model-by-Model Justification

### Tenant

**Why it exists:** Multi-tenancy is non-negotiable for an ESG platform. Each client company has its own data, emission factors, and reporting periods.

**Design choice — shared database with FK scoping:** I chose a single database with `tenant_id` foreign keys on every table rather than PostgreSQL schema-per-tenant. This is simpler for a prototype: one database, one set of migrations, one connection pool. The tradeoff is that every query must include a tenant filter — I enforce this through the TenantMiddleware that sets `request.tenant` on every request.

**What I'd change for production:** Add row-level security (RLS) policies in PostgreSQL as a defense-in-depth measure. A buggy view that forgets to filter by tenant is a data leakage incident waiting to happen.

### TenantMembership

**Why it exists:** A user can belong to multiple tenants (e.g., a Breathe ESG consultant managing multiple clients). The `role` field (admin/analyst/viewer) controls what actions a user can perform within a tenant.

**Why session-based tenant selection:** The active tenant is stored in the user's session. I considered subdomain-based isolation (client1.breatheesg.com) but rejected it for the prototype — it requires DNS configuration, wildcard SSL, and more complex deployment. Session-based is simpler and sufficient.

### DataSource

**Why it exists:** Not all SAP instances look the same. A client might have SAP for Indian operations and a separate SAP for German operations, each with different plant codes, date formats, and material group mappings. The `config` JSON field stores source-specific settings like plant code mappings and date format preferences.

**Why JSON config instead of separate tables:** The configuration is different for each source type. SAP needs plant code mappings and date format. Utility needs timezone and default multiplier. Travel needs platform name and API version. A JSON field avoids a proliferation of configuration tables.

### IngestionBatch

**Why it exists:** When an analyst uploads a file, they need to know what happened. The batch tracks: how many rows came in, how many succeeded, how many failed, and what the errors were. The `quality_score` (0-100) gives a quick health check.

**Why store file_content:** The raw file content is stored (truncated to 500KB) for audit traceability. If an auditor asks "what exactly was uploaded?", we have the answer. In production, this would move to object storage (S3) with a reference here.

### RawSAPRecord / RawUtilityRecord / RawTravelRecord

**Why three separate models instead of one polymorphic table:** Each source type has fundamentally different fields. SAP has material document numbers and movement types. Utility has meter numbers and billing periods. Travel has IATA codes and segment types. A single "raw_data" JSON column would make it impossible to query or validate source-specific fields.

**Why store raw data at all:** The golden rule of data pipelines: never destroy your source data. If a normalization rule is wrong, we need to be able to re-process from the original. The raw records are the source of truth for what came in; the normalized records are the source of truth for what goes to auditors.

**Why German field names in RawSAPRecord:** The fields use SAP's actual German abbreviations (MBLNR, BWART, MATNR) because that's what's in the export. Renaming them in the raw record would break the traceability chain — an auditor comparing our raw record to the SAP export should see identical field names.

### EmissionFactor

**Why `tenant` is nullable:** Global emission factors (DEFRA, EPA eGRID, India CEA) apply to all tenants. Tenant-specific factors override globals when a client has measured their own factors (e.g., a utility that provides actual grid emission data for their region).

**Why separate CO2, CH4, N2O fields:** Under the GHG Protocol, some reporting frameworks require separate reporting of CO2, CH4, and N2O rather than just CO2e. Storing them separately allows flexible reporting.

### NormalizedEmission

This is the most important model in the system. It is the ONLY table that feeds into audit reports.

**Source-of-truth tracking:**
- `raw_record_type` + `raw_record_id`: Polymorphic reference back to the source raw record
- `is_edited` + `edit_history`: If an analyst modifies a value (e.g., correcting a unit conversion), every change is tracked with old/new values, who changed it, and when
- `original_quantity` + `original_unit`: The values before normalization, so you can see both the raw input and the converted output

**Unit normalization:**
- All activity quantities are stored in normalized units (liters, kg, MWh, passenger-km, room-night)
- The original quantity and unit are preserved for verification
- Conversion happens in the normalization pipeline, not at the raw level

**Scope categorization:**
- Scope is derived from source type + activity type:
  - SAP fuel data → Scope 1 (stationary/mobile combustion)
  - Utility electricity → Scope 2 (purchased electricity)
  - Corporate travel → Scope 3 (business travel)
- Category is more granular: `stationary_combustion`, `mobile_combustion`, `purchased_electricity_location`, `business_travel_air`, etc.

**Review workflow:**
- Status flows: `pending` → `approved` → `locked`
- Also: `pending` → `flagged` → `approved` → `locked`
- Also: `pending` → `rejected` (removed from audit)
- `locked` records cannot be edited without unlocking first
- `reviewed_by` and `reviewed_at` track who approved and when

**Anomaly detection:**
- `anomaly_flag`: System-detected issues (unit mismatch, outlier value, missing field, negative value, potential duplicate)
- `anomaly_notes`: Auto-generated explanation or analyst-entered notes
- Anomalies are detected during normalization, before the analyst reviews

### ReviewAction

**Why a separate table instead of just updating status:** A single emission record may go through multiple review states (pending → flagged → approved → locked). The ReviewAction table captures every state transition with who did it and when. This is essential for audit compliance.

### AuditLog

**Why a separate system-wide log:** The AuditLog is the append-only record that external auditors inspect. It captures everything: ingestion events, review actions, edits, exports, login events. Unlike ReviewAction (which is scoped to emission records), AuditLog is polymorphic and can reference any record type.

**Why before/after snapshots:** For edit actions, the AuditLog stores the complete before and after state. This means we can reconstruct the full history of any record at any point in time.

## Multi-Tenancy Implementation

Every query filters by `tenant_id`, enforced at the view level through the TenantMiddleware:

```python
class TenantMiddleware:
    def process_request(self, request):
        # 1. Check session for active_tenant_id
        # 2. Fallback to user's first active membership
        # 3. Set request.tenant
```

All views use `request.tenant` to scope queries:
```python
NormalizedEmission.objects.filter(tenant=request.tenant)
```

## Scope 1/2/3 Categorization Logic

| Source Type | Movement/Activity | Scope | Category |
|-------------|------------------|-------|----------|
| SAP | BWART 201 (fuel to cost center) | Scope 1 | Stationary Combustion |
| SAP | BWART 201 + ANLN1 (asset/vehicle) | Scope 1 | Mobile Combustion |
| SAP | BWART 261 + AUFNR (production order) | Scope 1 | Process Emissions |
| Utility | Electricity consumption | Scope 2 | Purchased Electricity (Location-based) |
| Travel | Air segment | Scope 3 | Business Travel — Air |
| Travel | Hotel segment | Scope 3 | Business Travel — Hotel |
| Travel | Car segment | Scope 3 | Business Travel — Car |
| Travel | Rail segment | Scope 3 | Business Travel — Rail |

## Unit Normalization Reference

| Source | Raw Unit | Normalized Unit | Conversion |
|--------|----------|----------------|------------|
| SAP | L (liters) | liter | 1:1 |
| SAP | GAL (US gallons) | liter | × 3.78541 |
| SAP | KG (kilograms) | kg | 1:1 |
| SAP | TO (metric tons) | kg | × 1000 |
| Utility | kWh | MWh | × 0.001 |
| Travel | miles | passenger-km | × 1.60934 |
| Travel | room-night | room-night | 1:1 |

## Audit Trail Design

The audit trail has two layers:

1. **ReviewAction** — Captures the review workflow (approve/reject/flag/lock) for each emission record
2. **AuditLog** — System-wide append-only log of all significant actions

Together, they provide:
- Who ingested the data (IngestionBatch.ingested_by)
- Who reviewed and approved it (NormalizedEmission.reviewed_by, ReviewAction.performed_by)
- What changed between ingestion and approval (NormalizedEmission.edit_history, AuditLog.before_data/after_data)
- When each action happened (timestamps on all records)
- Why it was flagged or modified (anomaly_notes, review_notes, ReviewAction.notes)

## What I'd Add for Production

1. **Row-level security** in PostgreSQL for defense-in-depth on multi-tenancy
2. **Temporal tables** for the AuditLog (SQL:2011 standard) for efficient time-travel queries
3. **Materialized views** for dashboard aggregations (avoid counting on every page load)
4. **Soft delete** on NormalizedEmission — never hard-delete audit-relevant records
5. **Versioned emission factors** — factors change annually; old calculations must reference the factor version used at the time
6. **Reporting period model** — define fiscal years, quarters, and custom periods per tenant
7. **Data lineage graph** — for complex transformations, a DAG of processing steps with input/output references
