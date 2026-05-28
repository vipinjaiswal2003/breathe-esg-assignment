"""
Ingestion models: data sources, raw ingestion records, emission factors,
and normalized emissions.

Key design principles:
1. Raw data is preserved verbatim — we never overwrite what came in
2. Normalized data links back to its raw source (source-of-truth tracking)
3. Every row knows which source produced it, when, and whether it's been edited
4. Unit normalization happens at the NormalizedEmission level, not at the raw level
5. Scope categorization is derived from source type + activity type
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from tenants.models import Tenant


# ─────────────────────────────────────────────────────────
# Data Sources
# ─────────────────────────────────────────────────────────

class DataSource(models.Model):
    """
    Represents a connected data source (SAP, utility portal, travel platform).
    
    Each tenant can have multiple data sources of the same type (e.g., 
    SAP instance for Indian operations + SAP instance for German operations).
    """
    SOURCE_TYPE_CHOICES = [
        ('sap', 'SAP (Fuel & Procurement)'),
        ('utility', 'Utility (Electricity)'),
        ('travel', 'Corporate Travel'),
    ]
    
    INGESTION_MECHANISM_CHOICES = [
        ('file_upload', 'File Upload'),
        ('api_pull', 'API Pull'),
        ('manual_entry', 'Manual Entry'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='data_sources')
    name = models.CharField(max_length=255, help_text="e.g., 'SAP S/4HANA - India Plant'")
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    ingestion_mechanism = models.CharField(max_length=20, choices=INGESTION_MECHANISM_CHOICES, default='file_upload')
    
    # Configuration stored as JSON — different fields per source type
    # SAP: plant_code_mapping, material_group_whitelist, date_format
    # Utility: meter_multiplier_default, timezone
    # Travel: platform_name, api_base_url
    config = models.JSONField(default=dict, blank=True, help_text="Source-specific configuration")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_sources')

    class Meta:
        db_table = 'data_sources'

    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"


class IngestionBatch(models.Model):
    """
    Tracks a single ingestion run: one file upload or API pull.
    
    Every batch has a status, row counts, and links to the source.
    This gives analysts visibility into what came in and whether it
    succeeded or failed.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('completed_with_errors', 'Completed with Errors'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ingestion_batches')
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='batches')
    
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='pending')
    original_filename = models.CharField(max_length=500, blank=True)
    file_content = models.TextField(blank=True, help_text="Raw file content stored for audit trail")
    
    total_rows = models.IntegerField(default=0)
    successful_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    flagged_rows = models.IntegerField(default=0, help_text="Rows with anomalies detected")
    
    error_summary = models.JSONField(default=dict, blank=True, help_text="Aggregated error details")
    quality_score = models.FloatField(null=True, blank=True, help_text="0-100 quality score for this batch")
    
    ingested_at = models.DateTimeField(auto_now_add=True)
    ingested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ingestion_batches')

    class Meta:
        db_table = 'ingestion_batches'
        ordering = ['-ingested_at']

    def __str__(self):
        return f"Batch {self.id} ({self.status}) — {self.data_source.name}"


# ─────────────────────────────────────────────────────────
# Raw Ingestion Records
# ─────────────────────────────────────────────────────────

class RawSAPRecord(models.Model):
    """
    Raw SAP material document data, preserved exactly as received.
    
    Based on SAP MSEG+MKPF flat file export format (tab-delimited).
    This represents fuel and procurement data from SAP MM module.
    
    Key fields from SAP reality:
    - MBLNR: Material document number
    - BWART: Movement type (201=fuel to cost center, 261=fuel to prod order)
    - MATNR: Material number (zero-padded, 18 chars)
    - WERKS: Plant code
    - MENGE: Quantity (decimal with comma in German locale)
    - MEINS: Unit of measure (L, KG, GAL, TO, etc.)
    - BUDAT: Posting date (format varies: DD.MM.YYYY, YYYY-MM-DD, MM/DD/YYYY)
    - KOSTL: Cost center
    - MATKL: Material group (client-specific, not standardized as 'fuel')
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='raw_sap_records')
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='sap_records')
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='sap_records')
    
    # SAP material document fields (preserving German field names for traceability)
    mblnr = models.CharField(max_length=10, help_text="Material document number (MBLNR)")
    mjahr = models.CharField(max_length=4, help_text="Material document year (MJAHR)")
    zeile = models.CharField(max_length=4, help_text="Item in material document (ZEILE)")
    bwart = models.CharField(max_length=3, help_text="Movement type (BWART) — 201, 261, etc.")
    matnr = models.CharField(max_length=18, help_text="Material number (MATNR), zero-padded")
    maktx = models.CharField(max_length=40, blank=True, help_text="Material description (MAKTX)")
    matkl = models.CharField(max_length=9, blank=True, help_text="Material group (MATKL)")
    werks = models.CharField(max_length=4, help_text="Plant (WERKS)")
    menge = models.CharField(max_length=17, help_text="Quantity (MENGE) — stored as string to preserve decimal format")
    meins = models.CharField(max_length=3, help_text="Base unit of measure (MEINS): L, KG, GAL, TO")
    budat = models.CharField(max_length=10, help_text="Posting date (BUDAT) — format varies")
    kostl = models.CharField(max_length=10, blank=True, help_text="Cost center (KOSTL)")
    anln1 = models.CharField(max_length=12, blank=True, help_text="Main asset number (ANLN1) — for vehicles")
    aufnr = models.CharField(max_length=12, blank=True, help_text="Order number (AUFNR) — for production")
    lgort = models.CharField(max_length=4, blank=True, help_text="Storage location (LGORT)")
    lifnr = models.CharField(max_length=10, blank=True, help_text="Vendor account (LIFNR)")
    ebelp = models.CharField(max_length=5, blank=True, help_text="Purchasing document item (EBELP)")
    
    # Parsing metadata
    parse_errors = models.JSONField(default=list, blank=True, help_text="Per-field parse warnings/errors")
    is_parsed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'raw_sap_records'
        verbose_name = 'Raw SAP Record'

    def __str__(self):
        return f"SAP {self.mblnr}/{self.zeile} — {self.matnr} @ {self.werks}"


class RawUtilityRecord(models.Model):
    """
    Raw utility electricity data from portal CSV export.
    
    Based on typical utility portal CSV formats (PG&E, ConEd, Duke, etc.)
    with fields that account for billing periods, meter multipliers,
    and time-of-use structures.
    
    Key design: billing periods don't align with calendar months.
    We store bill_start and bill_end as separate fields and compute
    monthly allocation downstream if needed.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='raw_utility_records')
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='utility_records')
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='utility_records')
    
    # Utility account and meter identification
    account_number = models.CharField(max_length=50, help_text="Utility account number")
    meter_number = models.CharField(max_length=50, help_text="Meter identifier")
    service_address = models.CharField(max_length=255, blank=True)
    rate_schedule = models.CharField(max_length=50, blank=True, help_text="e.g., E-19, GS-2, TOU-GS-1")
    
    # Billing period (NOT calendar month)
    bill_start_date = models.CharField(max_length=20, help_text="Billing period start — format varies")
    bill_end_date = models.CharField(max_length=20, help_text="Billing period end — format varies")
    bill_days = models.IntegerField(null=True, blank=True, help_text="Number of days in billing period")
    
    # Consumption data
    consumption_kwh = models.CharField(max_length=20, help_text="kWh consumed — stored as string for parsing")
    demand_kw = models.CharField(max_length=20, blank=True, help_text="Peak demand in kW")
    meter_multiplier = models.DecimalField(max_digits=8, decimal_places=4, default=1.0, help_text="CT/PT multiplier")
    
    # Reading metadata
    reading_type = models.CharField(max_length=20, blank=True, help_text="actual, estimated, customer")
    
    # Cost (optional — for reconciliation, not emission calculation)
    total_charge = models.CharField(max_length=20, blank=True, help_text="Total bill amount")
    
    # Parsing metadata
    parse_errors = models.JSONField(default=list, blank=True)
    is_parsed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'raw_utility_records'
        verbose_name = 'Raw Utility Record'

    def __str__(self):
        return f"Meter {self.meter_number} — {self.bill_start_date} to {self.bill_end_date}"


class RawTravelRecord(models.Model):
    """
    Raw corporate travel data, structured like Concur Itinerary API v4 response.
    
    Concur exposes travel data as JSON via its Itinerary API, with 
    segment types: Air, Hotel, Car, Rail, Ride, Parking.
    
    Key challenges:
    - Distances not always provided (only airport codes for flights)
    - Car rental fuel type almost never specified
    - Cabin class missing in ~5-15% of bookings
    - Multi-leg trips appear as multiple segments
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='raw_travel_records')
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='travel_records')
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='travel_records')
    
    # Trip identification
    trip_id = models.CharField(max_length=100, help_text="Concur TripId or equivalent")
    segment_type = models.CharField(max_length=20, help_text="Air, Hotel, Car, Rail, Ride, Parking")
    
    # Employee (anonymized ID — we don't need PII for emissions)
    employee_id = models.CharField(max_length=100, blank=True, help_text="HR employee ID or hashed identifier")
    
    # Air-specific fields
    origin_code = models.CharField(max_length=10, blank=True, help_text="IATA airport code (e.g., DEL, JFK)")
    destination_code = models.CharField(max_length=10, blank=True, help_text="IATA airport code")
    cabin_class = models.CharField(max_length=10, blank=True, help_text="Economy, Business, First, PremiumEconomy")
    airline_code = models.CharField(max_length=10, blank=True, help_text="IATA airline code")
    
    # Hotel-specific fields
    hotel_city = models.CharField(max_length=100, blank=True)
    hotel_country = models.CharField(max_length=3, blank=True, help_text="ISO 3166-1 alpha-3")
    nights = models.IntegerField(null=True, blank=True)
    
    # Car-specific fields
    car_type = models.CharField(max_length=50, blank=True, help_text="e.g., Compact, SUV, Full-size")
    car_fuel_type = models.CharField(max_length=30, blank=True, help_text="e.g., Gasoline, Diesel, Electric — usually blank")
    distance_km = models.CharField(max_length=20, blank=True, help_text="Distance driven — rarely provided")
    
    # Common fields
    travel_date = models.CharField(max_length=20, help_text="Date of travel — format varies")
    distance_miles = models.CharField(max_length=20, blank=True, help_text="Great-circle distance (from Concur or calculated)")
    
    # Full segment data as JSON (for reference and future parsing)
    raw_segment_data = models.JSONField(default=dict, blank=True, help_text="Complete segment JSON from Concur API")
    
    # Parsing metadata
    parse_errors = models.JSONField(default=list, blank=True)
    is_parsed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'raw_travel_records'
        verbose_name = 'Raw Travel Record'

    def __str__(self):
        if self.segment_type == 'Air':
            return f"Flight {self.origin_code}→{self.destination_code} ({self.travel_date})"
        elif self.segment_type == 'Hotel':
            return f"Hotel {self.hotel_city} — {self.nights} nights ({self.travel_date})"
        elif self.segment_type == 'Car':
            return f"Car {self.car_type} ({self.travel_date})"
        return f"{self.segment_type} ({self.travel_date})"


# ─────────────────────────────────────────────────────────
# Emission Factors
# ─────────────────────────────────────────────────────────

class EmissionFactor(models.Model):
    """
    Emission factors by fuel type, electricity grid, and travel mode.
    
    Sources: IPCC, EPA eGRID, DEFRA, India CEA
    For prototype: a curated set of the most common factors.
    For production: these would be versioned by year and jurisdiction.
    """
    SCOPE_CHOICES = [
        ('scope1', 'Scope 1 — Direct Emissions'),
        ('scope2', 'Scope 2 — Purchased Electricity'),
        ('scope3', 'Scope 3 — Value Chain'),
    ]
    
    CATEGORY_CHOICES = [
        # Scope 1
        ('stationary_combustion', 'Stationary Combustion'),
        ('mobile_combustion', 'Mobile Combustion'),
        ('process_emissions', 'Process Emissions'),
        ('fugitive_emissions', 'Fugitive Emissions'),
        # Scope 2
        ('purchased_electricity_location', 'Purchased Electricity (Location-based)'),
        ('purchased_electricity_market', 'Purchased Electricity (Market-based)'),
        # Scope 3
        ('business_travel_air', 'Business Travel — Air'),
        ('business_travel_hotel', 'Business Travel — Hotel'),
        ('business_travel_car', 'Business Travel — Car'),
        ('business_travel_rail', 'Business Travel — Rail'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='emission_factors', null=True, blank=True, help_text="Null = global factor")
    
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
    
    # What this factor applies to
    activity_name = models.CharField(max_length=255, help_text="e.g., 'Diesel — stationary', 'Indian Grid (2024)', 'Economy flight short-haul'")
    fuel_or_activity_type = models.CharField(max_length=100, help_text="e.g., 'diesel', 'natural_gas', 'grid_india_2024', 'flight_economy_shorthaul'")
    
    # The factor itself
    co2e_factor = models.FloatField(help_text="kg CO2e per unit of activity")
    co2_factor = models.FloatField(null=True, blank=True, help_text="kg CO2 per unit (separate from CO2e for reporting)")
    ch4_factor = models.FloatField(null=True, blank=True, help_text="kg CH4 per unit")
    n2o_factor = models.FloatField(null=True, blank=True, help_text="kg N2O per unit")
    
    unit = models.CharField(max_length=30, help_text="Unit the factor applies to: liter, kg, kWh, MWh, passenger-km, room-night")
    
    # Metadata
    source = models.CharField(max_length=255, help_text="e.g., 'DEFRA 2024', 'EPA eGRID 2022', 'India CEA 2023'")
    year = models.IntegerField(help_text="Year the factor was published")
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'emission_factors'

    def __str__(self):
        return f"{self.activity_name}: {self.co2e_factor} kg CO2e/{self.unit}"


# ─────────────────────────────────────────────────────────
# Normalized Emission Records
# ─────────────────────────────────────────────────────────

class NormalizedEmission(models.Model):
    """
    The unified emission record that the review workflow operates on.
    
    Every normalized emission links back to its raw source record(s),
    preserving the chain of custody. An analyst reviews these records
    and approves, rejects, or flags them before they're locked for audit.
    
    Key design: this is the ONLY table that feeds into audit reports.
    Raw records are for traceability; normalized records are for reporting.
    """
    SCOPE_CHOICES = [
        ('scope1', 'Scope 1 — Direct Emissions'),
        ('scope2', 'Scope 2 — Purchased Electricity'),
        ('scope3', 'Scope 3 — Value Chain'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('flagged', 'Flagged for Investigation'),
        ('locked', 'Locked for Audit'),
    ]
    
    ANOMALY_CHOICES = [
        ('none', 'No Anomaly'),
        ('unit_mismatch', 'Unit Mismatch'),
        ('outlier_value', 'Outlier Value'),
        ('missing_field', 'Missing Required Field'),
        ('duplicate', 'Potential Duplicate'),
        ('date_mismatch', 'Date Format Issue'),
        ('negative_value', 'Negative Value'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='normalized_emissions')
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='normalized_emissions')
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='normalized_emissions')
    emission_factor = models.ForeignKey(EmissionFactor, on_delete=models.SET_NULL, null=True, related_name='emission_records')
    
    # Source-of-truth tracking
    raw_record_type = models.CharField(max_length=20, help_text="sap, utility, or travel")
    raw_record_id = models.UUIDField(help_text="ID of the source raw record")
    is_edited = models.BooleanField(default=False, help_text="Has an analyst modified the normalized values?")
    edit_history = models.JSONField(default=list, blank=True, help_text="List of {field, old_value, new_value, changed_by, changed_at}")
    
    # Scope and category
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=40, help_text="e.g., stationary_combustion, purchased_electricity_location")
    activity_description = models.TextField(blank=True, help_text="Human-readable description of the activity")
    
    # Normalized activity data (always in standard units)
    activity_quantity = models.FloatField(help_text="Quantity in normalized unit")
    activity_unit = models.CharField(max_length=30, help_text="Normalized unit: liter, kg, MWh, passenger-km, room-night")
    original_quantity = models.FloatField(null=True, blank=True, help_text="Original quantity before unit conversion")
    original_unit = models.CharField(max_length=30, blank=True, help_text="Original unit before conversion")
    
    # Emission calculation
    co2e_kg = models.FloatField(help_text="Total CO2e in kilograms")
    co2_kg = models.FloatField(null=True, blank=True)
    ch4_kg = models.FloatField(null=True, blank=True)
    n2o_kg = models.FloatField(null=True, blank=True)
    
    # Temporal and spatial context
    activity_date = models.DateField(help_text="Date the activity occurred")
    reporting_period_start = models.DateField(null=True, blank=True)
    reporting_period_end = models.DateField(null=True, blank=True)
    facility_or_plant = models.CharField(max_length=100, blank=True, help_text="Plant code, facility name, or location")
    country = models.CharField(max_length=3, blank=True, help_text="ISO 3166-1 alpha-3 for grid factor selection")
    
    # Review status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    anomaly_flag = models.CharField(max_length=20, choices=ANOMALY_CHOICES, default='none')
    anomaly_notes = models.TextField(blank=True, help_text="Auto-detected or analyst-entered explanation")
    review_notes = models.TextField(blank=True, help_text="Analyst notes during review")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_emissions')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True, help_text="When this record was locked for audit")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'normalized_emissions'
        ordering = ['-activity_date']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'scope']),
            models.Index(fields=['tenant', 'activity_date']),
            models.Index(fields=['data_source', 'batch']),
        ]

    def __str__(self):
        return f"{self.scope}/{self.category}: {self.co2e_kg} kg CO2e ({self.status})"
