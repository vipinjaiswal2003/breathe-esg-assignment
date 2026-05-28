"""
Normalization pipeline: converts raw ingestion records into NormalizedEmission records.

This is the core business logic of the application. Each raw record type
(SAP, Utility, Travel) has its own normalization path, but they all produce
the same NormalizedEmission record structure.

Design principles:
1. Preserve raw data — normalization never mutates raw records
2. All unit conversions happen here — raw records store original units
3. Scope categorization is derived from source type + activity type
4. Anomaly detection happens during normalization, before review
5. Every normalized record links back to its raw source

Unit normalization reference:
- SAP: L → liters (no conversion), KG → kg, GAL → 3.78541 L, TO → 1000 KG
- Utility: kWh → 0.001 MWh (store in MWh for consistency with grid factors)
- Travel: miles → 1.60934 km, passenger-km stays as-is
"""

from datetime import datetime
from typing import Optional, Dict, List
from decimal import Decimal

from ingestion.models import (
    NormalizedEmission, EmissionFactor,
    RawSAPRecord, RawUtilityRecord, RawTravelRecord,
)
from ingestion.parsers.sap_parser import FUEL_MOVEMENT_TYPES, classify_fuel_type
from ingestion.parsers.travel_parser import (
    calculate_flight_distance, CABIN_CLASS_MULTIPLIERS,
    CAR_EMISSION_FACTORS, HOTEL_EMISSION_FACTORS, RAIL_EMISSION_FACTOR,
    AIRPORT_COORDS,
)


# ─────────────────────────────────────────────────────────
# Unit Conversion Tables
# ─────────────────────────────────────────────────────────

# Volume conversions TO LITERS
VOLUME_TO_LITERS = {
    'l': 1.0,
    'lit': 1.0,
    'liter': 1.0,
    'liters': 1.0,
    'gal': 3.78541,     # US gallon
    'gal_us': 3.78541,
    'gal_uk': 4.54609,  # UK imperial gallon
    'kgal': 3785.41,
    'ml': 0.001,
    'm3': 1000.0,
    'm³': 1000.0,
    'ft3': 28.3168,
    'cf': 28.3168,       # cubic feet (for natural gas sometimes)
}

# Mass conversions TO KILOGRAMS
MASS_TO_KG = {
    'kg': 1.0,
    'kgs': 1.0,
    'kilogram': 1.0,
    'g': 0.001,
    'mg': 0.000001,
    't': 1000.0,
    'to': 1000.0,        # SAP "TO" = metric ton
    'ton': 1000.0,
    'mt': 1000.0,        # metric ton
    'lb': 0.453592,
    'lbs': 0.453592,
    'st': 907.185,       # short ton (US)
    'lt': 1016.05,       # long ton (UK)
}

# Energy conversions TO MWh
ENERGY_TO_MWH = {
    'kwh': 0.001,
    'wh': 0.000001,
    'mwh': 1.0,
    'gwh': 1000.0,
    'tj': 277.778,
    'gj': 0.277778,
    'mj': 0.000277778,
    'btu': 2.93071e-10,
    'kbtu': 2.93071e-7,
    'mmbtu': 0.293071,
}

# Distance conversions TO KM
DISTANCE_TO_KM = {
    'km': 1.0,
    'mi': 1.60934,
    'miles': 1.60934,
    'mile': 1.60934,
    'm': 0.001,
    'ft': 0.0003048,
}


def convert_unit(value: float, from_unit: str, to_unit: str) -> Optional[float]:
    """
    Convert a quantity from one unit to another.
    Returns None if conversion is not possible.
    """
    from_unit = from_unit.lower().strip()
    to_unit = to_unit.lower().strip()
    
    if from_unit == to_unit:
        return value
    
    # Try volume conversion
    if from_unit in VOLUME_TO_LITERS and to_unit in VOLUME_TO_LITERS:
        liters = value * VOLUME_TO_LITERS[from_unit]
        return liters / VOLUME_TO_LITERS[to_unit]
    
    # Try mass conversion
    if from_unit in MASS_TO_KG and to_unit in MASS_TO_KG:
        kg = value * MASS_TO_KG[from_unit]
        return kg / MASS_TO_KG[to_unit]
    
    # Try energy conversion
    if from_unit in ENERGY_TO_MWH and to_unit in ENERGY_TO_MWH:
        mwh = value * ENERGY_TO_MWH[from_unit]
        return mwh / ENERGY_TO_MWH[to_unit]
    
    # Try distance conversion
    if from_unit in DISTANCE_TO_KM and to_unit in DISTANCE_TO_KM:
        km = value * DISTANCE_TO_KM[from_unit]
        return km / DISTANCE_TO_KM[to_unit]
    
    return None


def get_normalized_unit(raw_unit: str, source_type: str) -> tuple:
    """
    Determine the target normalized unit and convert.
    
    Returns (normalized_quantity, normalized_unit, original_quantity, original_unit)
    """
    raw_unit_lower = raw_unit.lower().strip()
    
    if source_type == 'sap':
        # For SAP fuel data: normalize to liters (volume) or kg (mass)
        if raw_unit_lower in VOLUME_TO_LITERS:
            return ('liter', raw_unit_lower)
        elif raw_unit_lower in MASS_TO_KG:
            return ('kg', raw_unit_lower)
    elif source_type == 'utility':
        # For utility data: normalize to MWh
        if raw_unit_lower in ENERGY_TO_MWH:
            return ('MWh', raw_unit_lower)
    elif source_type == 'travel':
        # For travel: normalize to passenger-km or room-night
        if raw_unit_lower in DISTANCE_TO_KM:
            return ('passenger-km', raw_unit_lower)
    
    # Default: keep original unit
    return (raw_unit, raw_unit_lower)


# ─────────────────────────────────────────────────────────
# Normalization Functions
# ─────────────────────────────────────────────────────────

def normalize_sap_record(raw: RawSAPRecord, tenant) -> Optional[NormalizedEmission]:
    """
    Normalize a raw SAP record into a NormalizedEmission record.
    
    Key logic:
    1. Filter by movement type (only fuel consumption types)
    2. Classify fuel type from material description
    3. Convert units to standard (liters or kg)
    4. Look up emission factor
    5. Calculate CO2e
    6. Determine scope and category
    """
    # Skip non-fuel movement types
    if raw.bwart not in FUEL_MOVEMENT_TYPES:
        return None
    
    # Parse quantity
    from ingestion.parsers.sap_parser import parse_sap_quantity
    quantity = parse_sap_quantity(raw.menge)
    if quantity is None or quantity <= 0:
        return None
    
    # Determine target unit
    raw_unit = raw.meins.strip()
    target_info = get_normalized_unit(raw_unit, 'sap')
    normalized_unit, original_unit_key = target_info
    
    # Convert quantity
    if normalized_unit == 'liter' and original_unit_key in VOLUME_TO_LITERS:
        normalized_qty = quantity * VOLUME_TO_LITERS[original_unit_key]
    elif normalized_unit == 'kg' and original_unit_key in MASS_TO_KG:
        normalized_qty = quantity * MASS_TO_KG[original_unit_key]
    else:
        normalized_qty = quantity
        normalized_unit = raw_unit
    
    # Classify fuel type
    fuel_type = classify_fuel_type(raw.maktx, raw.matkl)
    
    # Determine scope and category
    category = FUEL_MOVEMENT_TYPES.get(raw.bwart, 'stationary_combustion')
    # If asset number present → mobile combustion (vehicle)
    if raw.anln1:
        category = 'mobile_combustion'
    # If production order → process emissions
    if raw.aufnr:
        category = 'process_emissions'
    
    # Parse date
    from ingestion.parsers.sap_parser import parse_sap_date
    parsed_date = parse_sap_date(raw.budat)
    if not parsed_date:
        parsed_date = '2024-01-01'  # Fallback
    
    # Look up emission factor
    ef = find_emission_factor(tenant, 'scope1', category, fuel_type)
    
    # Calculate CO2e
    if ef:
        co2e = normalized_qty * ef.co2e_factor
        activity_unit = ef.unit
    else:
        # Fallback: use a generic factor
        co2e = normalized_qty * 2.68  # Generic diesel: ~2.68 kg CO2e/liter
        activity_unit = normalized_unit
    
    # Detect anomalies
    anomaly_flag = 'none'
    anomaly_notes = ''
    if quantity < 0:
        anomaly_flag = 'negative_value'
        anomaly_notes = 'Negative quantity in SAP record'
    elif not fuel_type:
        anomaly_flag = 'missing_field'
        anomaly_notes = f'Could not classify fuel type from material: {raw.maktx} (group: {raw.matkl})'
    elif normalized_qty > 100000:
        anomaly_flag = 'outlier_value'
        anomaly_notes = f'Unusually high quantity: {normalized_qty} {normalized_unit}'
    
    return NormalizedEmission(
        tenant=tenant,
        data_source=raw.data_source,
        batch=raw.batch,
        emission_factor=ef,
        raw_record_type='sap',
        raw_record_id=raw.id,
        scope='scope1',
        category=category,
        activity_description=f'{raw.maktx or "Unknown fuel"} — Plant {raw.werks} — {raw.get_bwart_display() if hasattr(raw, "get_bwart_display") else raw.bwart}',
        activity_quantity=normalized_qty,
        activity_unit=activity_unit or normalized_unit,
        original_quantity=quantity,
        original_unit=raw_unit,
        co2e_kg=round(co2e, 4),
        activity_date=parsed_date,
        facility_or_plant=raw.werks,
        anomaly_flag=anomaly_flag,
        anomaly_notes=anomaly_notes,
    )


def normalize_utility_record(raw: RawUtilityRecord, tenant) -> Optional[NormalizedEmission]:
    """
    Normalize a raw utility record into a NormalizedEmission record.
    
    Key logic:
    1. Parse consumption (kWh)
    2. Apply meter multiplier
    3. Convert to MWh
    4. Look up grid emission factor (location-based)
    5. Calculate CO2e
    6. Handle estimated vs actual readings
    """
    # Parse consumption
    from ingestion.parsers.utility_parser import parse_numeric
    consumption_kwh = parse_numeric(raw.consumption_kwh)
    if consumption_kwh is None or consumption_kwh <= 0:
        return None
    
    # Apply meter multiplier
    multiplier = float(raw.meter_multiplier) if raw.meter_multiplier else 1.0
    adjusted_kwh = consumption_kwh * multiplier
    
    # Convert to MWh
    consumption_mwh = adjusted_kwh / 1000.0
    
    # Parse dates
    from ingestion.parsers.utility_parser import parse_utility_date
    bill_start = parse_utility_date(raw.bill_start_date)
    bill_end = parse_utility_date(raw.bill_end_date)
    
    # Use bill start as the activity date (or midpoint)
    activity_date = bill_start or '2024-01-01'
    
    # Look up emission factor (location-based for India grid)
    ef = find_emission_factor(tenant, 'scope2', 'purchased_electricity_location', 'grid_india')
    
    if ef:
        co2e = consumption_mwh * ef.co2e_factor  # Factor is per MWh
        activity_unit = ef.unit
    else:
        # Fallback: India CEA 2023 grid factor ~0.726 tCO2/MWh = 726 kg CO2/MWh
        co2e = consumption_mwh * 726.0
        activity_unit = 'MWh'
    
    # Detect anomalies
    anomaly_flag = 'none'
    anomaly_notes = ''
    if raw.reading_type and raw.reading_type.lower().startswith('estim'):
        anomaly_notes = 'Estimated meter reading — verify with actual reading if available'
    if consumption_kwh > 500000:
        anomaly_flag = 'outlier_value'
        anomaly_notes += ('; ' if anomaly_notes else '') + f'Unusually high consumption: {consumption_kwh} kWh'
    
    return NormalizedEmission(
        tenant=tenant,
        data_source=raw.data_source,
        batch=raw.batch,
        emission_factor=ef,
        raw_record_type='utility',
        raw_record_id=raw.id,
        scope='scope2',
        category='purchased_electricity_location',
        activity_description=f'Electricity — Meter {raw.meter_number} — {raw.rate_schedule or "Unknown tariff"}',
        activity_quantity=consumption_mwh,
        activity_unit=activity_unit,
        original_quantity=consumption_kwh,
        original_unit='kWh',
        co2e_kg=round(co2e, 4),
        activity_date=activity_date,
        reporting_period_start=bill_start,
        reporting_period_end=bill_end,
        facility_or_plant=raw.service_address or raw.meter_number,
        anomaly_flag=anomaly_flag,
        anomaly_notes=anomaly_notes,
    )


def normalize_travel_record(raw: RawTravelRecord, tenant) -> Optional[NormalizedEmission]:
    """
    Normalize a raw travel record into a NormalizedEmission record.
    
    Key logic varies by segment type:
    - Air: distance-based (passenger-km × cabin class multiplier × EF)
    - Hotel: room-night × country EF
    - Car: distance-based or spend-based fallback
    - Rail: passenger-km × EF
    """
    if raw.segment_type == 'Air':
        return normalize_air_travel(raw, tenant)
    elif raw.segment_type == 'Hotel':
        return normalize_hotel_travel(raw, tenant)
    elif raw.segment_type == 'Car':
        return normalize_car_travel(raw, tenant)
    elif raw.segment_type == 'Rail':
        return normalize_rail_travel(raw, tenant)
    
    return None


def normalize_air_travel(raw: RawTravelRecord, tenant) -> Optional[NormalizedEmission]:
    """Normalize air travel segment."""
    # Calculate distance
    distance_km = calculate_flight_distance(raw.origin_code, raw.destination_code)
    
    # Try to use stored distance_miles
    if raw.distance_miles:
        try:
            distance_miles = float(raw.distance_miles)
            if distance_km is None:
                distance_km = distance_miles * 1.60934
        except (ValueError, TypeError):
            pass
    
    if distance_km is None:
        distance_km = 0.0
    
    # Determine haul type for emission factor selection
    if distance_km < 3700:
        haul_type = 'shorthaul'
    else:
        haul_type = 'longhaul'
    
    # Get cabin class multiplier
    cabin = (raw.cabin_class or 'economy').lower().strip()
    cabin_multiplier = CABIN_CLASS_MULTIPLIERS.get(cabin, 1.0)
    
    # Look up emission factor
    ef = find_emission_factor(tenant, 'scope3', 'business_travel_air', f'flight_economy_{haul_type}')
    
    # Base EF is for economy; adjust for cabin class
    if ef:
        base_ef = ef.co2e_factor
    else:
        # Fallback: DEFRA 2024 average
        if haul_type == 'shorthaul':
            base_ef = 0.15659  # kg CO2e per passenger-km (economy, short-haul)
        else:
            base_ef = 0.10239  # kg CO2e per passenger-km (economy, long-haul)
    
    adjusted_ef = base_ef * cabin_multiplier
    passenger_km = distance_km
    co2e = passenger_km * adjusted_ef
    
    # Detect anomalies
    anomaly_flag = 'none'
    anomaly_notes = ''
    if distance_km == 0:
        anomaly_flag = 'missing_field'
        anomaly_notes = f'Cannot calculate flight distance: {raw.origin_code}→{raw.destination_code}'
    elif not raw.cabin_class:
        anomaly_notes = 'Cabin class not specified — defaulted to Economy per DEFRA guidance'
    
    return NormalizedEmission(
        tenant=tenant,
        data_source=raw.data_source,
        batch=raw.batch,
        emission_factor=ef,
        raw_record_type='travel',
        raw_record_id=raw.id,
        scope='scope3',
        category='business_travel_air',
        activity_description=f'Flight {raw.origin_code}→{raw.destination_code} ({raw.cabin_class or "Economy"}, {haul_type}) — {raw.airline_code or "Unknown airline"}',
        activity_quantity=passenger_km,
        activity_unit='passenger-km',
        original_quantity=distance_km * 0.621371 if distance_km else None,
        original_unit='miles',
        co2e_kg=round(co2e, 4),
        activity_date=raw.travel_date or '2024-01-01',
        country='',  # Flight doesn't map to a single country
        anomaly_flag=anomaly_flag,
        anomaly_notes=anomaly_notes,
    )


def normalize_hotel_travel(raw: RawTravelRecord, tenant) -> Optional[NormalizedEmission]:
    """Normalize hotel stay segment."""
    nights = raw.nights or 1
    country = (raw.hotel_country or '').upper()
    
    # Look up emission factor
    ef = find_emission_factor(tenant, 'scope3', 'business_travel_hotel', f'hotel_{country.lower()}' if country else 'hotel_default')
    
    if ef:
        ef_per_night = ef.co2e_factor
    else:
        ef_per_night = HOTEL_EMISSION_FACTORS.get(country, HOTEL_EMISSION_FACTORS['default'])
    
    co2e = nights * ef_per_night
    
    return NormalizedEmission(
        tenant=tenant,
        data_source=raw.data_source,
        batch=raw.batch,
        emission_factor=ef,
        raw_record_type='travel',
        raw_record_id=raw.id,
        scope='scope3',
        category='business_travel_hotel',
        activity_description=f'Hotel stay — {raw.hotel_city or "Unknown city"}, {country or "Unknown country"} — {nights} nights',
        activity_quantity=float(nights),
        activity_unit='room-night',
        co2e_kg=round(co2e, 4),
        activity_date=raw.travel_date or '2024-01-01',
        country=country,
        facility_or_plant=raw.hotel_city,
    )


def normalize_car_travel(raw: RawTravelRecord, tenant) -> Optional[NormalizedEmission]:
    """Normalize car rental segment."""
    # Try to get distance
    distance_km = None
    if raw.distance_km:
        try:
            distance_km = float(raw.distance_km)
        except (ValueError, TypeError):
            pass
    
    # Get car type emission factor
    car_type = (raw.car_type or 'default').lower().strip()
    ef_per_km = CAR_EMISSION_FACTORS.get(car_type, CAR_EMISSION_FACTORS['default'])
    
    if distance_km and distance_km > 0:
        co2e = distance_km * ef_per_km
        activity_qty = distance_km
        activity_unit = 'km'
    else:
        # Fallback: estimate based on average rental (3 days × 100 km/day = 300 km)
        estimated_km = 300.0
        co2e = estimated_km * ef_per_km
        activity_qty = estimated_km
        activity_unit = 'km (estimated)'
    
    # Look up emission factor
    ef = find_emission_factor(tenant, 'scope3', 'business_travel_car', 'car_rental')
    
    anomaly_flag = 'none'
    anomaly_notes = ''
    if not distance_km:
        anomaly_flag = 'missing_field'
        anomaly_notes = 'Car rental distance not provided — emission estimate based on 300 km default (3 days × 100 km/day)'
    if not raw.car_fuel_type:
        anomaly_notes += ('; ' if anomaly_notes else '') + 'Fuel type not specified — using average car emission factor'
    
    return NormalizedEmission(
        tenant=tenant,
        data_source=raw.data_source,
        batch=raw.batch,
        emission_factor=ef,
        raw_record_type='travel',
        raw_record_id=raw.id,
        scope='scope3',
        category='business_travel_car',
        activity_description=f'Car rental ({raw.car_type or "Unknown type"}) — {raw.car_fuel_type or "Unknown fuel"}',
        activity_quantity=activity_qty,
        activity_unit=activity_unit,
        co2e_kg=round(co2e, 4),
        activity_date=raw.travel_date or '2024-01-01',
        anomaly_flag=anomaly_flag,
        anomaly_notes=anomaly_notes,
    )


def normalize_rail_travel(raw: RawTravelRecord, tenant) -> Optional[NormalizedEmission]:
    """Normalize rail travel segment."""
    distance_km = None
    if raw.distance_km:
        try:
            distance_km = float(raw.distance_km)
        except (ValueError, TypeError):
            pass
    
    if distance_km is None:
        # Estimate from origin/destination if available
        distance_km = 0.0  # Can't estimate without more data
    
    co2e = distance_km * RAIL_EMISSION_FACTOR
    
    ef = find_emission_factor(tenant, 'scope3', 'business_travel_rail', 'rail')
    
    return NormalizedEmission(
        tenant=tenant,
        data_source=raw.data_source,
        batch=raw.batch,
        emission_factor=ef,
        raw_record_type='travel',
        raw_record_id=raw.id,
        scope='scope3',
        category='business_travel_rail',
        activity_description=f'Rail travel {raw.origin_code or ""}→{raw.destination_code or ""}',
        activity_quantity=distance_km,
        activity_unit='passenger-km',
        co2e_kg=round(co2e, 4),
        activity_date=raw.travel_date or '2024-01-01',
    )


def find_emission_factor(tenant, scope: str, category: str, fuel_or_activity: Optional[str]) -> Optional[EmissionFactor]:
    """
    Look up the applicable emission factor.
    
    Priority:
    1. Tenant-specific factor (if client has custom factors)
    2. Global factor (tenant=None)
    3. Return None (caller must use fallback)
    """
    if not fuel_or_activity:
        return None
    
    # Try tenant-specific first
    ef = EmissionFactor.objects.filter(
        tenant=tenant,
        scope=scope,
        category=category,
        fuel_or_activity_type__icontains=fuel_or_activity,
        is_active=True,
    ).first()
    
    if ef:
        return ef
    
    # Fall back to global factors
    ef = EmissionFactor.objects.filter(
        tenant__isnull=True,
        scope=scope,
        category=category,
        fuel_or_activity_type__icontains=fuel_or_activity,
        is_active=True,
    ).first()
    
    return ef
