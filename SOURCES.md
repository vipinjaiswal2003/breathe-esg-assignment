# SOURCES.md — Real-World Format Research

## Source 1: SAP — Fuel and Procurement Data

### What Real-World Format I Researched

I researched SAP's material document data as exposed through SE16N (the SAP data browser). Material documents live in the MSEG table (material document segments) with header data in MKPF. The most common export method for sustainability teams is a flat file (tab-delimited) export from SE16N or a custom Z-report.

I also evaluated:
- **IDoc (MATMAS05, MBGMCR):** SAP's standard interchange format. Requires ALE/middleware (PI/PO) configuration. An IT project, not something a sustainability lead can do.
- **OData Services (S/4HANA API_API_MATERIAL_DOCUMENT):** Modern REST API available on S/4HANA. Requires API hub setup, OAuth2, and pagination handling.
- **BAPI (BAPI_MATERIAL_GETALL, BAPI_GOODSMVT_GETDETAIL):** RFC function modules. Requires SAP GUI or RFC programming.
- **ALV Grid Export:** End-user export from SAP list viewer. Inconsistent headers, formatting artifacts.

### What I Learned

1. **Movement type (BWART) is the critical filter.** It determines whether a material document represents consumption (201, 261), procurement (101), transfer (311), or something else. Using the wrong movement type produces wrong emission categorization.

2. **German headers appear when the SAP login language is DE.** The same export can have "Menge" instead of "Quantity", "Werk" instead of "Plant", "Buchungsdatum" instead of "Posting Date". I built a dual-language header mapping.

3. **Decimal separators vary by locale.** German SAP uses comma (1.234,56), English SAP uses period (1,234.56). I built a detection heuristic based on the last separator position.

4. **Material numbers are zero-padded to 18 characters.** 0000000000FUEL001 is the actual value in SAP. Stripping zeros is tempting but breaks traceability.

5. **There is no standard "fuel" classification.** Each client has their own material groups (MATKL from table T023). A material group like "FUEL01" at one client might be "01FUEL" or "KRAFTSTOFF" at another. Keyword matching on the material description (MAKTX) is the best heuristic without a client-specific mapping.

6. **Plant codes (WERKS) are client-specific.** "1000" means nothing without a lookup table. I include a plant code mapping in the DataSource config.

7. **Unit of measure (MEINS) is inconsistent.** The same fuel can be in L (liters), KG (kilograms), GAL (US gallons), or TO (metric tons) depending on the plant configuration.

### What My Sample Data Looks Like and Why

```
Mat_Doc	Doc_Yr	Item	MvT	Material	Material_Description	Matl_Group	Plant	Quantity	UoM	Pstng_Date	Cost_Center	Asset	Order
4900000200	2024	1	201	0000000000FUEL001	Diesel Fuel	FUEL01	1000	5000	L	15.07.2024	CC-MFG-01			
4900000201	2024	1	201	0000000000FUEL002	Natural Gas	FUEL02	2000	2500,00	KG	20.07.2024	CC-MFG-02			
4900000202	2024	1	201	0000000000FUEL003	Diesel (Vehicle Fleet)	FUEL01	1000	1200	L	22.07.2024	CC-TRANS	ASSET-TRK-02		
4900000203	2024	1	261	0000000000FUEL004	LPG Gas	FUEL03	3000	800	L	25.07.2024	CC-PROD-01		ORD-2024-045	
4900000204	2024	1	201	0000000000FUEL005	Gasoline (Unleaded)	FUEL04	1000	3000	GAL	2024-07-28	CC-GEN			
4900000205	2024	1	101	0000000000FUEL001	Diesel Fuel	FUEL01	1000	10000	L	01.07.2024	CC-PROC			
4900000206	2024	1	201	0000000000UNK99999	Unknown Chemical X-99	CHEM99	1000	500	KG	30.07.2024	CC-LAB			
```

**Why it looks like this:**
- Row 1: Standard diesel fuel issue to cost center (BWART 201). Typical Scope 1 stationary combustion.
- Row 2: Natural gas with German decimal format (2500,00 instead of 2500.00). Tests decimal separator handling.
- Row 3: Diesel with an asset number (ANLN1), indicating vehicle fleet fuel. Should be categorized as mobile combustion, not stationary.
- Row 4: LPG gas issued to a production order (AUFNR). Should be categorized as process emissions.
- Row 5: Gasoline in gallons (GAL) with ISO date format (YYYY-MM-DD). Tests unit conversion and mixed date formats.
- Row 6: Goods receipt (BWART 101). Should be EXCLUDED from emission calculation — this is procurement, not consumption.
- Row 7: Unknown material that can't be classified as fuel. Tests the anomaly detection for unclassifiable materials.

### What Would Break in a Real Deployment

1. **Millions of rows.** A large SAP installation might have 100,000+ material documents per quarter. File upload and synchronous processing would time out. Need async processing (Celery) and chunked upload.

2. **Custom Z-tables.** Some clients store fuel data in custom Z-tables rather than MSEG. The parser would need to be adapted.

3. **Multiple SAP instances.** The client might have separate SAP systems for different regions, each with different configurations. The DataSource config would need per-instance settings.

4. **Currency fields.** I excluded cost data from the SAP parser. In reality, cost center budgeting and emission reporting are linked. A client would want to see emissions per cost center alongside budget data.

5. **SAP BW instead of ECC/S4HANA.** If the client uses SAP Business Warehouse, the extraction format and table structure are completely different.

---

## Source 2: Utility — Electricity Data

### What Real-World Format I Researched

I researched utility portal CSV exports, which is how most facilities teams get their electricity data. I looked at:

- **PG&E (Pacific Gas & Electric):** Green Button CSV and billing CSV exports
- **ConEdison (Consolidated Edison):** Portal billing data export
- **Duke Energy:** Business account billing export
- **Tata Power / Adani Electricity (India):** Consumer portal CSV downloads
- **Green Button Data (NAESB ESPI standard):** XML and CSV formats for standardized utility data

I also evaluated:
- **Green Button Connect My Data (CMD):** Automated API-based data sharing using OAuth + ESPI. Adoption is limited, especially outside the US.
- **PDF utility bills:** Universal but require OCR. The bill contains rich information (tariff breakdown, demand charges, time-of-use) but in an unstructured format.
- **Utility APIs (UtilityAPI, Bayou Energy):** Third-party APIs that normalize data across utilities. Commercial products, not free.
- **ESP/MDM systems (EnergyCAP, IBM Envizi):** Enterprise energy management platforms that pre-normalize data. Upstream of our ingestion.

### What I Learned

1. **Billing periods don't align with calendar months.** A utility bill from June 28 to July 27 spans two months. The bill date range is the authoritative period, not the calendar month. This is the #1 source of confusion in utility data.

2. **Meter multipliers (CT/PT ratios) are critical.** Large commercial meters use current transformers with multipliers of 20, 40, 80, or even 200. A reading of 1,000 kWh with multiplier 40 = 40,000 kWh actual consumption. Forgetting the multiplier understates consumption by 10-200x.

3. **Estimated readings are common.** When a meter can't be read (access issues, damaged equipment), the utility estimates consumption. Estimated readings should be flagged for analyst review.

4. **Rate schedule determines emission factor applicability.** Time-of-use rates (peak/off-peak) may require different emission factors if the grid mix varies by time of day. Our parser doesn't disaggregate by TOU period.

5. **Net metering (solar) produces negative consumption values.** If a facility has rooftop solar, the meter may show net export. This requires separate handling — you can't just use the net value.

6. **Column headers vary wildly between utilities.** "consumption_kwh" vs "Usage (kWh)" vs "kWh" vs "Energy_kWh" — all mean the same thing. I built a fuzzy column name mapping.

7. **Header metadata rows.** PG&E's Green Button CSV starts with 5 metadata rows before the actual column headers. I built a header-row detector that looks for known column names.

### What My Sample Data Looks Like and Why

```csv
account_number,meter_number,service_address,rate_schedule,bill_start_date,bill_end_date,bill_days,consumption_kwh,demand_kw,meter_multiplier,reading_type,total_charge
ACCT-TP-2001,MTR-101,Plot 12 MIDC Mumbai,HT-1,01/07/2024,31/07/2024,30,45600,120,1.0,actual,387600
ACCT-TP-2002,MTR-102,Block C Okhla Delhi,HT-2,2024-06-28,2024-07-27,29,32100,85,1.0,actual,272850
ACCT-TP-2003,MTR-103,Unit 5 Electronic City Bangalore,LT-5,07/05/2024,07/07/2024,61,12400,,1.0,estimated,99200
ACCT-TP-2001,MTR-101,Plot 12 MIDC Mumbai,HT-1,01/08/2024,31/08/2024,30,48200,128,1.0,actual,409700
ACCT-TP-2004,MTR-104,Warehouse 9 Peenya Bangalore,HT-1,2024-07-01,2024-07-31,30,68000,200,40,actual,612000
```

**Why it looks like this:**
- Row 1: Standard high-tension (HT-1) commercial account. Clean data, actual reading, multiplier of 1.0.
- Row 2: Different date format (ISO YYYY-MM-DD) and billing period that crosses months (June 28 to July 27). Tests date format handling and cross-month billing periods.
- Row 3: Low-tension (LT-5) account with estimated reading and no demand value. Tests missing field handling and estimated reading detection.
- Row 4: Same meter as Row 1 but for August. Tests that the same meter can appear in multiple billing periods.
- Row 5: **The critical test case.** Meter multiplier of 40 (CT ratio). The raw reading is 68,000 kWh, but actual consumption is 68,000 × 40 = 2,720,000 kWh. This is the most common real-world error — forgetting the multiplier.

### What Would Break in a Real Deployment

1. **Format variability.** Every utility portal has different column names, date formats, and data layouts. We'd need format-specific adapters or a column mapping UI.

2. **Interval data (15-minute or hourly).** Our parser handles monthly billing data only. Interval data is vertical (one row per interval) or horizontal (48 columns for half-hour intervals). This requires a completely different parser and a time-series data model.

3. **Green Button XML.** The Green Button format is XML based on the NAESB ESPI standard, with a complex hierarchy (UsagePoint → MeterReading → IntervalBlock → IntervalReading). Our parser doesn't handle this.

4. **Multi-utility aggregation.** A large client might have accounts with 5-10 different utilities across India. Each utility's portal works differently.

5. **Net metering and solar.** Facilities with rooftop solar may have net consumption values that can be negative. Our parser doesn't handle negative consumption or separate import/export.

6. **Tariff structure complexity.** Indian electricity tariffs (HT-1, HT-2, LT-5, TOU-GS-1) have different structures for demand charges, energy charges, fuel adjustment charges, and electricity duty. Our parser stores the rate schedule but doesn't use it for emission calculations.

---

## Source 3: Corporate Travel — Flights, Hotels, Ground Transport

### What Real-World Format I Researched

I researched the SAP Concur Itinerary API v4, which is the standard data source for corporate travel emissions. I examined:

- **Concur Itinerary API v4 (REST):** Returns trip itineraries as JSON with typed segments (Air, Hotel, Car, Rail, Ride, Parking, Dining). This is the primary data source.
- **Concur Event Subscription Service (ESS) v4:** Webhooks for real-time trip updates. Requires a publicly accessible HTTPS endpoint.
- **Concur Standard Accounting Extract (SAE):** CSV format delivered via SFTP. Primarily for expense data, not travel itineraries.
- **Concur Expense API v3/v4:** Expense report data. Different from itinerary data — expenses are filed after travel, itineraries are booked before travel.
- **Navan (formerly TripActions):** Minimal public API documentation. Most integrations use CSV/SFTP export or browser automation.

I also looked at:
- **DEFRA 2024 emission factors** for business travel
- **GHG Protocol Scope 3 Category 6 guidance** for business travel
- **ISO 14083** standard for transport emissions (Concur is the first platform to offer ISO 14083-assured emissions)
- **IATA airport code database** for distance calculations

### What I Learned

1. **Concur already provides carbon emissions and distance.** The Air segment includes `CarbonEmissionLbs` and `Miles` fields. However, these use Concur's methodology, which may differ from the client's preferred methodology (DEFRA vs EPA vs ISO 14083). For the prototype, I calculate emissions independently using DEFRA factors.

2. **Cabin class is missing in 5-15% of bookings.** TripLink bookings and manual entries often have empty or defaulted cabin class. DEFRA recommends defaulting to Economy when unknown.

3. **Car rental distance is almost never provided.** The booking tells you the car type and rental dates, but not how far it was driven. This is the biggest gap in travel emission data. Options: (a) estimate based on rental duration, (b) use spend-based emission factor, (c) flag for manual entry.

4. **Hotel emission factors vary dramatically by country.** A hotel night in India (40.6 kg CO2e/room-night) produces 2x the emissions of a hotel night in France (15.4 kg CO2e/room-night). Country-specific factors are essential.

5. **Flight distance must account for indirect routing.** Great-circle distance underestimates actual flight distance by ~9%. DEFRA recommends a 9% uplift factor.

6. **Cabin class multipliers are significant.** Business class produces ~2.73x the emissions of Economy. First class produces ~4.13x. This is not a rounding error — it can change a company's reported travel emissions by 30-50%.

7. **Rail data is sparse.** Concur's Rail segment often has only origin, destination, and date. Distance is rarely provided and must be calculated or estimated.

### What My Sample Data Looks Like and Why

```json
[
  {
    "id": "TRIP-2024-010",
    "BookedBy": "EMP-2001",
    "Segments": {
      "Air": [{
        "StartCityCode": "BOM",
        "EndCityCode": "DEL",
        "Cabin": "E",
        "CarrierCode": "6E",
        "StartDate": "2024-08-05T09:30:00",
        "Miles": 705
      }],
      "Hotel": [{
        "CityName": "New Delhi",
        "CountryCode": "IND",
        "StartDate": "2024-08-05",
        "EndDate": "2024-08-07",
        "Nights": 2
      }]
    }
  },
  {
    "id": "TRIP-2024-011",
    "BookedBy": "EMP-2002",
    "Segments": {
      "Air": [{
        "StartCityCode": "DEL",
        "EndCityCode": "SIN",
        "Cabin": "B",
        "CarrierCode": "AI",
        "StartDate": "2024-08-12T23:15:00"
      }],
      "Hotel": [{
        "CityName": "Singapore",
        "CountryCode": "SGP",
        "StartDate": "2024-08-13",
        "EndDate": "2024-08-16",
        "Nights": 3
      }],
      "Car": [{
        "CarClass": "SUV",
        "StartDate": "2024-08-13",
        "FuelType": ""
      }]
    }
  },
  {
    "id": "TRIP-2024-012",
    "BookedBy": "EMP-2003",
    "Segments": {
      "Air": [{
        "StartCityCode": "BLR",
        "EndCityCode": "FRA",
        "Cabin": "",
        "CarrierCode": "LH",
        "StartDate": "2024-08-20T02:00:00"
      }],
      "Rail": [{
        "StartCityCode": "FRA",
        "EndCityCode": "MUC",
        "Distance": 400,
        "StartDate": "2024-08-22"
      }]
    }
  }
]
```

**Why it looks like this:**
- Trip 1: Domestic India flight (BOM→DEL) with Economy cabin and known distance (705 miles from Concur). Hotel in India with 2 nights. Clean data.
- Trip 2: International flight (DEL→SIN) with **Business class** cabin and **no Miles field** (tests distance calculation from airport codes). Hotel in Singapore with 3 nights (tests country-specific hotel emission factor). Car rental with **SUV type and no fuel type and no distance** (tests the most common car rental data gap).
- Trip 3: Long-haul flight (BLR→FRA) with **empty Cabin field** (tests default to Economy). Rail segment from FRA to MUC with distance (400 km). Tests multiple segment types in a single trip.

### What Would Break in a Real Deployment

1. **Concur API rate limits.** The Itinerary API is rate-limited to 10 requests per minute for backfill operations. A company with 5,000 employees might have 20,000 trips per quarter. Batch retrieval would take hours.

2. **Employee identity resolution.** Concur uses its own UUID for employees. Matching to HR employee IDs requires the User Provisioning API, which is a separate integration.

3. **Multi-leg flights.** A trip from Mumbai to New York via Frankfurt appears as two Air segments. Our system creates two emission records. For reporting, these should potentially be aggregated as a single trip.

4. **TripLink bookings.** Bookings made through TripLink (Concur's travel booking tool) may have more complete data. Direct bookings on airline websites often have incomplete segment data.

5. **Navan/TripActions.** If the client uses Navan instead of Concur, the data format is completely different and there's no public API documentation. We'd need to work with their support team.

6. **Historical data limitations.** Concur's Itinerary API only returns trips from the last 6 months. For older data, we'd need the Standard Accounting Extract or a one-time data migration.

7. **Rail distance.** European rail data from Concur may include station codes but not distances. We'd need a rail distance database (e.g., German Rail's API or a static distance matrix).
