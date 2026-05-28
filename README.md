# Breathe ESG — Data Ingestion Prototype

A Django REST + React application that ingests emissions data from three source types (SAP, utility, corporate travel), normalizes it, and surfaces a review dashboard where analysts can approve, flag, or reject records before they're locked for audit.

## Quick Start

```bash
# Backend setup
cd breathe-esg
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data          # Creates sample tenant, users, and data
python manage.py runserver          # http://localhost:8000

# Frontend (development)
cd frontend
npm install
npm run dev                         # http://localhost:5173

# Frontend (production build)
cd frontend
npm run build                       # Output → frontend/dist/
# Django serves the built React app at /
```

## Login Credentials

| Username  | Password    | Role    |
|-----------|-------------|---------|
| admin     | admin123    | Admin   |
| analyst   | analyst123  | Analyst |

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   React Frontend                      │
│  Dashboard │ Ingestion │ Review Queue │ Audit Log     │
└──────────────────┬───────────────────────────────────┘
                   │ REST API (Token Auth)
┌──────────────────┴───────────────────────────────────┐
│                   Django Backend                      │
│                                                       │
│  ┌─────────┐ ┌───────────┐ ┌────────┐ ┌───────────┐ │
│  │ Tenants  │ │ Ingestion │ │ Review │ │   Audit   │ │
│  │          │ │           │ │        │ │           │ │
│  │ Multi-   │ │ Parsers:  │ │ Approve│ │ Trail     │ │
│  │ tenancy  │ │ SAP       │ │ Reject │ │ Logging   │ │
│  │          │ │ Utility   │ │ Flag   │ │ Export    │ │
│  │          │ │ Travel    │ │ Lock   │ │           │ │
│  └─────────┘ └───────────┘ └────────┘ └───────────┘ │
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │           SQLite / PostgreSQL                     │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

## Data Sources

### 1. SAP — Fuel & Procurement (Scope 1)
- **Format:** Tab-delimited flat file (SAP SE16N export)
- **Key fields:** Material document, movement type, material, plant, quantity, unit, posting date
- **Handles:** German headers, decimal comma, inconsistent units, zero-padded material numbers

### 2. Utility — Electricity (Scope 2)
- **Format:** CSV (utility portal export)
- **Key fields:** Account number, meter number, billing period, consumption (kWh), demand, meter multiplier
- **Handles:** Variable column names, billing periods ≠ calendar months, meter multipliers, estimated readings

### 3. Travel — Flights, Hotels, Cars (Scope 3)
- **Format:** JSON (Concur Itinerary API v4 structure)
- **Key fields:** Trip ID, segment type, IATA codes, cabin class, hotel country, car type
- **Handles:** Missing cabin class (default Economy), missing distances (calculate from airport codes), missing car fuel type

## Review Workflow

```
File Upload → Parse → Normalize → Flag Anomalies → Analyst Review → Approve/Reject → Lock for Audit
```

1. **Upload** a data file via the Ingestion page
2. **Parse** — the system extracts structured records from the file
3. **Normalize** — unit conversion, scope categorization, CO2e calculation
4. **Flag** — anomalies are auto-detected (outliers, missing fields, unit mismatches)
5. **Review** — analysts see a filterable queue of records needing attention
6. **Approve/Reject/Flag** — bulk actions on selected records
7. **Lock** — approved records are locked and cannot be modified without audit trail

## Key Documentation

| Document | Purpose |
|----------|---------|
| [MODEL.md](MODEL.md) | Data model design and justification |
| [DECISIONS.md](DECISIONS.md) | Every ambiguity resolved, choices made, what to ask the PM |
| [TRADEOFFS.md](TRADEOFFS.md) | Three things deliberately not built and why |
| [SOURCES.md](SOURCES.md) | Real-world format research for each data source |

## Sample Data

The `sample_data/` directory contains realistic test files:
- `sap_export_sample.txt` — SAP flat file with German dates, mixed formats, and excluded movement types
- `utility_export_sample.csv` — Utility CSV with meter multipliers, estimated readings, and cross-month billing periods
- `concur_itinerary_sample.json` — Concur-style JSON with multiple segment types and missing fields

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/login/ | Login with username/password |
| GET | /api/dashboard/stats/ | Dashboard statistics |
| GET | /api/sources/ | List data sources |
| POST | /api/ingest/sap/ | Upload SAP file |
| POST | /api/ingest/utility/ | Upload utility CSV |
| POST | /api/ingest/travel/ | Upload travel JSON |
| GET | /api/emissions/ | List normalized emissions |
| POST | /api/review/action/ | Approve/reject/flag/lock records |
| PUT | /api/review/edit/:id/ | Edit a record |
| GET | /api/review/export/ | Export for auditors |
| GET | /api/audit/ | Audit log |

## Technology Stack

- **Backend:** Django 6.0, Django REST Framework, SQLite (PostgreSQL for production)
- **Frontend:** React 19, Vite, TypeScript, Tailwind CSS v4
- **Auth:** Token-based (DRF TokenAuthentication)
- **Deployment:** Render / Railway (Django serves React build)
