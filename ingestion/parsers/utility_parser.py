"""
Utility CSV parser for electricity consumption data.

Design decision: I chose the utility portal CSV export format over
Green Button XML, PDF bills, or utility APIs because:

1. CSV is the most universally available format. Every utility portal
   (PG&E, ConEd, Duke, Dominion, etc.) offers a CSV download.
2. Green Button is standardized but adoption is spotty — many utilities
   don't support it, and the XML format is complex for a prototype.
3. PDF bills require OCR — that's a separate project entirely.
4. Utility APIs require per-utility integration contracts. Not feasible
   for a prototype that needs to handle any utility.

This parser handles:
- Variable column names across utility providers
- Billing periods that don't align with calendar months
- Meter multipliers (CT/PT ratios)
- Estimated vs actual readings
- Multiple rate schedule formats
- Missing fields (demand_kw is common to be absent for small accounts)

What I'm NOT handling:
- Green Button XML/ATOM format
- Interval (15-min or hourly) data
- PDF bill extraction
- Net metering (import/export separation)
- Time-of-use period disaggregation
"""

import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional


# Column name mapping: various utility CSV headers → canonical names
# Utilities use wildly different column names for the same data
COLUMN_MAPPINGS = {
    # Account/Meter identifiers
    'account_number': ['account_number', 'account no', 'accountno', 'acct_no', 'acct number', 'customer_id', 'customer id'],
    'meter_number': ['meter_number', 'meter no', 'meterno', 'meter_no', 'meter id', 'meter_id', 'meter_number', 'service_id'],
    'service_address': ['service_address', 'service address', 'address', 'premise_address', 'service_location'],
    'rate_schedule': ['rate_schedule', 'rate schedule', 'rate', 'tariff', 'rate_class', 'rate class', 'schedule'],
    
    # Billing period
    'bill_start_date': ['bill_start_date', 'bill start', 'start date', 'billing_start', 'billing start', 'from_date', 'from date', 'period_start', 'read_start_date'],
    'bill_end_date': ['bill_end_date', 'bill end', 'end date', 'billing_end', 'billing end', 'to_date', 'to date', 'period_end', 'read_end_date'],
    'bill_days': ['bill_days', 'billing days', 'days', 'no_of_days', 'number of days'],
    
    # Consumption
    'consumption_kwh': ['consumption_kwh', 'consumption (kwh)', 'kwh', 'usage_kwh', 'usage (kwh)', 'energy_kwh', 'energy (kwh)', 'total_kwh', 'kwh_consumed', 'net_consumption'],
    'demand_kw': ['demand_kw', 'demand (kw)', 'kw', 'peak_demand', 'peak demand', 'max_demand', 'maximum demand', 'billed_demand'],
    'meter_multiplier': ['meter_multiplier', 'multiplier', 'meter_multiplier', 'ct_pt_ratio', 'ct/pt ratio', 'kh_factor'],
    
    # Reading metadata
    'reading_type': ['reading_type', 'reading type', 'type', 'read_type', 'bill_type', 'reading_method'],
    
    # Cost
    'total_charge': ['total_charge', 'total charge', 'total_cost', 'amount', 'total_amount', 'charges', 'billed_amount'],
}

# Build reverse lookup for fast column matching
REVERSE_COLUMN_MAP = {}
for canonical, variants in COLUMN_MAPPINGS.items():
    for variant in variants:
        REVERSE_COLUMN_MAP[variant.lower().strip()] = canonical


def parse_utility_csv(content: str, source_config: dict = None) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse a utility portal CSV export.
    
    Handles:
    - Variable column headers
    - Comma or tab delimiters
    - Quoted fields with commas inside
    - Header metadata rows (e.g., PG&E adds 5 rows before column headers)
    
    Returns:
        (records, errors) — list of parsed record dicts and list of error dicts
    """
    source_config = source_config or {}
    records = []
    errors = []
    
    lines = content.strip().split('\n')
    if len(lines) < 2:
        errors.append({'row_number': 0, 'field': 'file', 'message': 'File has no data rows', 'raw_value': ''})
        return records, errors
    
    # Find the header row: look for a row containing "kwh" or "meter" or "account"
    header_idx = find_header_row(lines)
    if header_idx is None:
        errors.append({'row_number': 0, 'field': 'headers', 'message': 'Cannot identify header row — no known column names found', 'raw_value': ''})
        return records, errors
    
    # Parse header
    delimiter = detect_delimiter(lines[header_idx])
    headers = [h.strip().strip('"').lower() for h in lines[header_idx].split(delimiter)]
    
    # Map columns to canonical names
    column_map = {}
    for i, header in enumerate(headers):
        canonical = resolve_column_name(header)
        if canonical:
            column_map[i] = canonical
    
    # Validate minimum required fields
    mapped_fields = set(column_map.values())
    required_fields = {'meter_number', 'bill_start_date', 'bill_end_date', 'consumption_kwh'}
    missing = required_fields - mapped_fields
    if missing:
        errors.append({
            'row_number': 0,
            'field': 'headers',
            'message': f'Missing required columns: {missing}. Found: {mapped_fields}',
            'raw_value': str(headers),
        })
        return records, errors
    
    # Parse data rows
    for row_num, line in enumerate(lines[header_idx + 1:], start=header_idx + 2):
        if not line.strip() or line.strip().startswith('#'):
            continue
        
        values = [v.strip().strip('"') for v in line.split(delimiter)]
        record = {}
        row_errors = []
        
        for col_idx, field_name in column_map.items():
            if col_idx < len(values):
                record[field_name] = values[col_idx]
            else:
                record[field_name] = ''
        
        # Parse dates
        start_date = parse_utility_date(record.get('bill_start_date', ''))
        end_date = parse_utility_date(record.get('bill_end_date', ''))
        if not start_date:
            row_errors.append({
                'row_number': row_num,
                'field': 'bill_start_date',
                'message': f'Cannot parse start date: "{record.get("bill_start_date", "")}"',
                'raw_value': record.get('bill_start_date', ''),
            })
        if not end_date:
            row_errors.append({
                'row_number': row_num,
                'field': 'bill_end_date',
                'message': f'Cannot parse end date: "{record.get("bill_end_date", "")}"',
                'raw_value': record.get('bill_end_date', ''),
            })
        
        # Parse consumption
        consumption = parse_numeric(record.get('consumption_kwh', ''))
        if consumption is None:
            row_errors.append({
                'row_number': row_num,
                'field': 'consumption_kwh',
                'message': f'Cannot parse consumption: "{record.get("consumption_kwh", "")}"',
                'raw_value': record.get('consumption_kwh', ''),
            })
        elif consumption < 0:
            row_errors.append({
                'row_number': row_num,
                'field': 'consumption_kwh',
                'message': 'Negative consumption value',
                'raw_value': record.get('consumption_kwh', ''),
            })
        
        # Parse demand (optional)
        demand = parse_numeric(record.get('demand_kw', '')) if record.get('demand_kw') else None
        
        # Parse meter multiplier (default to 1.0 if not provided)
        multiplier = parse_numeric(record.get('meter_multiplier', '1.0')) or 1.0
        
        # Calculate bill days if not provided
        bill_days = parse_numeric(record.get('bill_days', ''))
        if not bill_days and start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                bill_days = (end - start).days
            except ValueError:
                bill_days = None
        
        record['_parse_errors'] = row_errors
        record['_parsed_start_date'] = start_date
        record['_parsed_end_date'] = end_date
        record['_parsed_consumption'] = consumption
        record['_parsed_demand'] = demand
        record['_parsed_multiplier'] = multiplier
        record['_parsed_bill_days'] = bill_days
        records.append(record)
        errors.extend(row_errors)
    
    return records, errors


def find_header_row(lines: List[str]) -> Optional[int]:
    """Find the row that contains column headers by looking for known field names."""
    for i, line in enumerate(lines):
        lower_line = line.lower()
        if any(keyword in lower_line for keyword in ['kwh', 'meter', 'account', 'billing', 'consumption']):
            return i
    return None


def detect_delimiter(line: str) -> str:
    """Detect whether the file uses comma, tab, or semicolon delimiters."""
    tab_count = line.count('\t')
    comma_count = line.count(',')
    semicolon_count = line.count(';')
    
    if tab_count > comma_count and tab_count > semicolon_count:
        return '\t'
    if semicolon_count > comma_count:
        return ';'
    return ','


def resolve_column_name(header: str) -> Optional[str]:
    """Map a CSV column header to a canonical field name."""
    header = header.strip().lower()
    if header in REVERSE_COLUMN_MAP:
        return REVERSE_COLUMN_MAP[header]
    # Try partial match
    for variant, canonical in REVERSE_COLUMN_MAP.items():
        if variant in header or header in variant:
            return canonical
    return None


def parse_utility_date(date_str: str) -> Optional[str]:
    """Parse date string into ISO format."""
    if not date_str or not date_str.strip():
        return None
    
    date_str = date_str.strip().strip('"')
    
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%d-%m-%Y', '%Y/%m/%d', '%b %d, %Y'):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return None


def parse_numeric(value: str) -> Optional[float]:
    """Parse a numeric value, handling commas in thousand separators."""
    if not value or not value.strip():
        return None
    
    value = value.strip().strip('"').strip('$').strip()
    # Remove thousand separators
    value = value.replace(',', '')
    
    try:
        return float(value)
    except ValueError:
        return None
