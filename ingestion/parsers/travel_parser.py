"""
Corporate travel data parser for Concur/Navan-style JSON data.

Design decision: I chose the Concur Itinerary API v4 JSON format because:

1. Concur (SAP Concur) is the dominant corporate travel platform with ~60% market share
2. The Itinerary API v4 provides structured JSON with typed segments (Air, Hotel, Car, Rail, Ride)
3. Concur already includes CarbonEmissionLbs and Miles fields in Air segments
4. JSON is the natural format for API responses — we'd receive this via webhook or API pull
5. For the prototype, we accept JSON file uploads that mimic the Concur API response shape

This parser handles:
- Multiple segment types in a single trip (Air, Hotel, Car, Rail)
- IATA airport codes for origin/destination
- Missing cabin class (default to Economy per DEFRA guidance)
- Missing distances (calculate from airport codes using great-circle distance)
- Multi-leg flights appearing as separate segments
- Hotel stays with number of nights
- Car rentals where distance driven is almost never provided

What I'm NOT handling:
- Concur ESS webhook real-time ingestion
- Concur Standard Accounting Extract (SAE) CSV format
- Navan/TripActions format (no public API docs)
- Multi-segment trip aggregation (each segment becomes a separate emission record)
- Expense report matching (linking travel bookings to expense claims)
"""

import json
import math
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional


# ─────────────────────────────────────────────────────────
# IATA Airport Code → Lat/Lon Lookup
# ─────────────────────────────────────────────────────────
# A small subset of major airport codes for distance calculation.
# In production, you'd use a full IATA database (3,000+ codes).
# This covers common Indian and international airports for sample data.

AIRPORT_COORDS = {
    # India
    'DEL': (28.5562, 77.1000),   # Delhi IGI
    'BOM': (19.0896, 72.8656),   # Mumbai CSI
    'BLR': (13.1986, 77.7066),   # Bangalore
    'MAA': (12.9940, 80.1709),   # Chennai
    'CCU': (22.6547, 88.4467),   # Kolkata
    'HYD': (17.2403, 78.4294),   # Hyderabad
    'PNQ': (18.5822, 73.9197),   # Pune
    'GOI': (15.3808, 73.8312),   # Goa
    'AMD': (23.0772, 72.6345),   # Ahmedabad
    'COK': (10.1520, 76.4019),   # Kochi
    'JAI': (26.8242, 75.8112),   # Jaipur
    # International
    'JFK': (40.6413, -73.7781),  # New York JFK
    'LHR': (51.4700, -0.4543),   # London Heathrow
    'SIN': (1.3644, 103.9915),   # Singapore Changi
    'DXB': (25.2532, 55.3657),   # Dubai
    'HKG': (22.3080, 113.9185),  # Hong Kong
    'NRT': (35.7720, 140.3929),  # Tokyo Narita
    'SFO': (37.6213, -122.3790), # San Francisco
    'FRA': (50.0379, 8.5622),    # Frankfurt
    'CDG': (49.0097, 2.5479),    # Paris CDG
    'SYD': (-33.9461, 151.1772), # Sydney
    'ICN': (37.4602, 126.4407),  # Seoul Incheon
    'PEK': (40.0799, 116.6031),  # Beijing
    'BKK': (13.6900, 100.7501),  # Bangkok
    'KUL': (2.7456, 101.7099),   # Kuala Lumpur
    'DOH': (25.2731, 51.6081),   # Doha
    'ADD': (8.9779, 38.7993),    # Addis Ababa
    'NBO': (-1.3192, 36.9278),   # Nairobi
}

# Flight distance classification per DEFRA
SHORT_HAUL_THRESHOLD_KM = 3700   # < 3,700 km
LONG_HAUL_THRESHOLD_KM = 3700    # >= 3,700 km

# Cabin class multipliers (relative to Economy)
# Source: DEFRA 2024 conversion factors
CABIN_CLASS_MULTIPLIERS = {
    'economy': 1.0,
    'e': 1.0,
    'premiumeconomy': 1.6,
    'pe': 1.6,
    'business': 2.73,
    'b': 2.73,
    'first': 4.13,
    'f': 4.13,
}

# Car emission factors by type (kg CO2e per km) — DEFRA 2024
CAR_EMISSION_FACTORS = {
    'compact': 0.12,
    'midsize': 0.15,
    'full-size': 0.18,
    'suv': 0.22,
    'luxury': 0.25,
    'van': 0.20,
    'electric': 0.05,
    'hybrid': 0.08,
    'default': 0.15,  # Unknown type
}

# Rail emission factor (kg CO2e per passenger-km) — DEFRA 2024
RAIL_EMISSION_FACTOR = 0.037

# Hotel emission factors by country (kg CO2e per room-night)
# Source: Cornell Hotel Sustainability Benchmarking
HOTEL_EMISSION_FACTORS = {
    'IND': 40.6,   # India
    'USA': 32.2,   # United States
    'GBR': 21.3,   # United Kingdom
    'DEU': 19.8,   # Germany
    'FRA': 15.4,   # France
    'SGP': 50.2,   # Singapore
    'ARE': 65.0,   # UAE
    'JPN': 33.5,   # Japan
    'CHN': 45.0,   # China
    'AUS': 28.7,   # Australia
    'default': 30.0,
}


def parse_travel_json(content: str, source_config: dict = None) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse Concur-style travel itinerary JSON.
    
    Expected structure (based on Concur Itinerary API v4):
    {
        "id": "trip-uuid",
        "Segments": {
            "Air": [...],
            "Hotel": [...],
            "Car": [...],
            "Rail": [...],
            "Ride": [...]
        },
        "BookedBy": "employee-id"
    }
    
    Also accepts a flat array of trip objects for batch ingestion.
    
    Returns:
        (records, errors) — list of parsed record dicts and list of error dicts
    """
    source_config = source_config or {}
    records = []
    errors = []
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        errors.append({'row_number': 0, 'field': 'file', 'message': f'Invalid JSON: {e}', 'raw_value': ''})
        return records, errors
    
    # Handle both single trip and array of trips
    trips = data if isinstance(data, list) else [data]
    
    for trip_idx, trip in enumerate(trips):
        trip_id = trip.get('id', trip.get('TripId', trip.get('trip_id', f'trip-{trip_idx}')))
        employee_id = trip.get('BookedBy', trip.get('EmployeeId', trip.get('employee_id', '')))
        
        segments = trip.get('Segments', trip.get('segments', {}))
        if not segments:
            # Try flat segment list
            for seg in trip.get('segments_list', trip.get('SegmentsList', [])):
                seg_type = seg.get('type', seg.get('SegmentType', '')).lower()
                if seg_type in ('air', 'hotel', 'car', 'rail', 'ride'):
                    if seg_type not in segments:
                        segments[seg_type] = []
                    segments[seg_type].append(seg)
        
        # Parse Air segments
        for seg in segments.get('Air', segments.get('air', [])):
            record, seg_errors = parse_air_segment(seg, trip_id, employee_id, trip_idx)
            if record:
                records.append(record)
            errors.extend(seg_errors)
        
        # Parse Hotel segments
        for seg in segments.get('Hotel', segments.get('hotel', [])):
            record, seg_errors = parse_hotel_segment(seg, trip_id, employee_id, trip_idx)
            if record:
                records.append(record)
            errors.extend(seg_errors)
        
        # Parse Car segments
        for seg in segments.get('Car', segments.get('car', [])):
            record, seg_errors = parse_car_segment(seg, trip_id, employee_id, trip_idx)
            if record:
                records.append(record)
            errors.extend(seg_errors)
        
        # Parse Rail segments
        for seg in segments.get('Rail', segments.get('rail', [])):
            record, seg_errors = parse_rail_segment(seg, trip_id, employee_id, trip_idx)
            if record:
                records.append(record)
            errors.extend(seg_errors)
    
    return records, errors


def parse_air_segment(seg: Dict, trip_id: str, employee_id: str, trip_idx: int) -> Tuple[Optional[Dict], List[Dict]]:
    """Parse an Air segment from Concur API format."""
    errors = []
    record = {
        'trip_id': trip_id,
        'segment_type': 'Air',
        'employee_id': employee_id,
        'raw_segment_data': seg,
    }
    
    # Origin/Destination IATA codes
    record['origin_code'] = seg.get('StartCityCode', seg.get('origin', seg.get('Origin', ''))).upper()
    record['destination_code'] = seg.get('EndCityCode', seg.get('destination', seg.get('Destination', ''))).upper()
    
    # Cabin class
    cabin = seg.get('Cabin', seg.get('cabin_class', seg.get('CabinClass', '')))
    record['cabin_class'] = normalize_cabin_class(cabin)
    
    # Airline code
    record['airline_code'] = seg.get('CarrierCode', seg.get('airline_code', seg.get('Airline', '')))
    
    # Travel date
    date_str = seg.get('StartDate', seg.get('travel_date', seg.get('date', '')))
    record['travel_date'] = parse_travel_date(date_str) or ''
    if not record['travel_date']:
        errors.append({
            'row_number': trip_idx,
            'field': 'travel_date',
            'message': f'Cannot parse air travel date: "{date_str}"',
            'raw_value': date_str,
        })
    
    # Distance — use Concur's Miles if available, otherwise calculate from airport codes
    concur_miles = seg.get('Miles', seg.get('distance_miles', ''))
    if concur_miles:
        try:
            record['distance_miles'] = str(float(concur_miles))
            record['_calculated_distance'] = False
        except (ValueError, TypeError):
            distance_km = calculate_flight_distance(record['origin_code'], record['destination_code'])
            if distance_km:
                record['distance_miles'] = str(round(distance_km * 0.621371, 1))
                record['_calculated_distance'] = True
            else:
                record['distance_miles'] = ''
                record['_calculated_distance'] = False
                errors.append({
                    'row_number': trip_idx,
                    'field': 'distance_miles',
                    'message': f'Cannot determine flight distance: {record["origin_code"]}→{record["destination_code"]}',
                    'raw_value': '',
                })
    else:
        distance_km = calculate_flight_distance(record['origin_code'], record['destination_code'])
        if distance_km:
            record['distance_miles'] = str(round(distance_km * 0.621371, 1))
            record['_calculated_distance'] = True
        else:
            record['distance_miles'] = ''
            record['_calculated_distance'] = False
            errors.append({
                'row_number': trip_idx,
                'field': 'distance_miles',
                'message': f'Cannot calculate distance from airport codes: {record["origin_code"]}→{record["destination_code"]}',
                'raw_value': '',
            })
    
    # Clear hotel/car fields
    record['hotel_city'] = ''
    record['hotel_country'] = ''
    record['nights'] = None
    record['car_type'] = ''
    record['car_fuel_type'] = ''
    record['distance_km'] = ''
    
    record['_parse_errors'] = errors
    return record, errors


def parse_hotel_segment(seg: Dict, trip_id: str, employee_id: str, trip_idx: int) -> Tuple[Optional[Dict], List[Dict]]:
    """Parse a Hotel segment."""
    errors = []
    record = {
        'trip_id': trip_id,
        'segment_type': 'Hotel',
        'employee_id': employee_id,
        'raw_segment_data': seg,
    }
    
    record['hotel_city'] = seg.get('CityName', seg.get('hotel_city', seg.get('City', '')))
    record['hotel_country'] = seg.get('CountryCode', seg.get('hotel_country', seg.get('Country', '')))
    
    # Number of nights
    nights = seg.get('Nights', seg.get('nights', None))
    if nights is not None:
        try:
            record['nights'] = int(nights)
        except (ValueError, TypeError):
            record['nights'] = None
            errors.append({
                'row_number': trip_idx,
                'field': 'nights',
                'message': f'Cannot parse nights: "{nights}"',
                'raw_value': str(nights),
            })
    else:
        # Try to calculate from check-in/check-out dates
        checkin = seg.get('StartDate', seg.get('check_in', ''))
        checkout = seg.get('EndDate', seg.get('check_out', ''))
        if checkin and checkout:
            try:
                start = datetime.strptime(parse_travel_date(checkin), '%Y-%m-%d')
                end = datetime.strptime(parse_travel_date(checkout), '%Y-%m-%d')
                record['nights'] = (end - start).days
            except (ValueError, TypeError):
                record['nights'] = None
    
    if not record['nights']:
        errors.append({
            'row_number': trip_idx,
            'field': 'nights',
            'message': 'Cannot determine number of hotel nights',
            'raw_value': '',
        })
    
    # Travel date (check-in date)
    date_str = seg.get('StartDate', seg.get('travel_date', seg.get('check_in', '')))
    record['travel_date'] = parse_travel_date(date_str) or ''
    
    # Clear air/car fields
    record['origin_code'] = ''
    record['destination_code'] = ''
    record['cabin_class'] = ''
    record['airline_code'] = ''
    record['car_type'] = ''
    record['car_fuel_type'] = ''
    record['distance_km'] = ''
    record['distance_miles'] = ''
    
    record['_parse_errors'] = errors
    return record, errors


def parse_car_segment(seg: Dict, trip_id: str, employee_id: str, trip_idx: int) -> Tuple[Optional[Dict], List[Dict]]:
    """Parse a Car rental segment."""
    errors = []
    record = {
        'trip_id': trip_id,
        'segment_type': 'Car',
        'employee_id': employee_id,
        'raw_segment_data': seg,
    }
    
    record['car_type'] = seg.get('CarClass', seg.get('car_type', seg.get('VehicleType', '')))
    record['car_fuel_type'] = seg.get('FuelType', seg.get('car_fuel_type', ''))
    record['distance_km'] = seg.get('DistanceDriven', seg.get('distance_km', seg.get('Distance', '')))
    
    if not record['distance_km']:
        errors.append({
            'row_number': trip_idx,
            'field': 'distance_km',
            'message': 'Car rental distance not provided — emission estimate will use spend-based fallback or default',
            'raw_value': '',
        })
    
    # Travel date (pickup date)
    date_str = seg.get('StartDate', seg.get('travel_date', seg.get('pickup_date', '')))
    record['travel_date'] = parse_travel_date(date_str) or ''
    
    # Clear air/hotel fields
    record['origin_code'] = ''
    record['destination_code'] = ''
    record['cabin_class'] = ''
    record['airline_code'] = ''
    record['hotel_city'] = ''
    record['hotel_country'] = ''
    record['nights'] = None
    record['distance_miles'] = ''
    
    record['_parse_errors'] = errors
    return record, errors


def parse_rail_segment(seg: Dict, trip_id: str, employee_id: str, trip_idx: int) -> Tuple[Optional[Dict], List[Dict]]:
    """Parse a Rail segment."""
    errors = []
    record = {
        'trip_id': trip_id,
        'segment_type': 'Rail',
        'employee_id': employee_id,
        'raw_segment_data': seg,
    }
    
    record['distance_km'] = seg.get('Distance', seg.get('distance_km', ''))
    record['origin_code'] = seg.get('StartCityCode', seg.get('origin', ''))
    record['destination_code'] = seg.get('EndCityCode', seg.get('destination', ''))
    
    date_str = seg.get('StartDate', seg.get('travel_date', seg.get('date', '')))
    record['travel_date'] = parse_travel_date(date_str) or ''
    
    # Clear unused fields
    record['cabin_class'] = ''
    record['airline_code'] = ''
    record['hotel_city'] = ''
    record['hotel_country'] = ''
    record['nights'] = None
    record['car_type'] = ''
    record['car_fuel_type'] = ''
    record['distance_miles'] = ''
    
    record['_parse_errors'] = errors
    return record, errors


# ─────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────

def calculate_flight_distance(origin: str, destination: str) -> Optional[float]:
    """
    Calculate great-circle distance between two airports using IATA codes.
    Returns distance in kilometers.
    Applies a 9% uplift factor per DEFRA recommendation for indirect routing.
    """
    origin = origin.upper().strip()
    destination = destination.upper().strip()
    
    if origin not in AIRPORT_COORDS or destination not in AIRPORT_COORDS:
        return None
    
    lat1, lon1 = AIRPORT_COORDS[origin]
    lat2, lon2 = AIRPORT_COORDS[destination]
    
    # Haversine formula
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    distance = R * c
    
    # Apply 9% uplift for indirect routing (DEFRA recommendation)
    distance *= 1.09
    
    return round(distance, 1)


def normalize_cabin_class(cabin: str) -> str:
    """Normalize cabin class to canonical values."""
    if not cabin:
        return 'economy'  # Default per DEFRA guidance
    
    cabin = cabin.strip().lower()
    mapping = {
        'e': 'economy', 'y': 'economy', 'economy': 'economy',
        'pe': 'premiumeconomy', 'w': 'premiumeconomy', 'premium economy': 'premiumeconomy',
        'premiumeconomy': 'premiumeconomy',
        'b': 'business', 'j': 'business', 'c': 'business', 'business': 'business',
        'f': 'first', 'a': 'first', 'first': 'first', 'r': 'first',
    }
    return mapping.get(cabin, 'economy')


def parse_travel_date(date_str: str) -> Optional[str]:
    """Parse travel date into ISO format."""
    if not date_str or not date_str.strip():
        return None
    
    date_str = date_str.strip().strip('"')
    
    # Handle ISO datetime (Concur sends full ISO timestamps)
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return None
