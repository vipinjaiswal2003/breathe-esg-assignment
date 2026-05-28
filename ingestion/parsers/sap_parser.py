"""
SAP flat-file parser for fuel and procurement data.

Design decision: I chose the SAP flat-file (tab-delimited) export format
over IDoc, OData, or BAPI because:

1. Flat file is the most common export format for sustainability teams
   who don't have IT resources. They use SE16N or custom Z-reports
   to export data from SAP.
2. IDoc requires ALE/middleware configuration — that's an IT project.
3. OData is only available on S/4HANA and requires API setup.
4. BAPI requires RFC programming — definitely an IT task.
5. Flat files are what a sustainability lead can produce on their own.

This parser handles:
- Tab-delimited format with German or English headers
- Inconsistent date formats (DD.MM.YYYY, YYYY-MM-DD, MM/DD/YYYY)
- Decimal separators (comma in German locale, period in English)
- Zero-padded material numbers
- Multiple movement types (201, 261, etc.)
- Unit of measure variations (L, KG, GAL, TO)

What I'm NOT handling (deliberate scope cut):
- IDoc XML format
- BAPI/RFC calls
- OData pagination
- Multi-line item aggregation within a single material document
- Currency conversion
"""

import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional


# Header mapping: German → canonical English field names
# This is based on actual SAP SE16N/MSEG exports where German headers
# appear when the user's SAP login language is DE.
GERMAN_TO_ENGLISH = {
    'Materialbeleg': 'mblnr',
    'Belegjahr': 'mjahr',
    'Position': 'zeile',
    'Bewegungsart': 'bwart',
    'Material': 'matnr',
    'Materialtext': 'maktx',
    'Warengruppe': 'matkl',
    'Werk': 'werks',
    'Menge': 'menge',
    'BME': 'meins',
    'Buchungsdatum': 'budat',
    'Kostenstelle': 'kostl',
    'Anlage': 'anln1',
    'Auftrag': 'aufnr',
    'Lagerort': 'lgort',
    'Lieferant': 'lifnr',
    'Bestellposition': 'ebelp',
}

# English headers as they appear in SAP exports
ENGLISH_HEADERS = {
    'Mat_Doc': 'mblnr',
    'Doc_Yr': 'mjahr',
    'Item': 'zeile',
    'MvT': 'bwart',
    'Material': 'matnr',
    'Material_Description': 'maktx',
    'Matl_Group': 'matkl',
    'Plant': 'werks',
    'Quantity': 'menge',
    'UoM': 'meins',
    'Pstng_Date': 'budat',
    'Cost_Center': 'kostl',
    'Asset': 'anln1',
    'Order': 'aufnr',
    'SLoc': 'lgort',
    'Vendor': 'lifnr',
    'PO_Item': 'ebelp',
    # Also handle underscores replaced by spaces
    'Mat Doc': 'mblnr',
    'Doc Yr': 'mjahr',
    'Pstng Date': 'budat',
    'Cost Center': 'kostl',
    'Matl Group': 'matkl',
    'Material Description': 'maktx',
    'PO Item': 'ebelp',
}

# Movement types that represent fuel consumption (Scope 1)
# This is a critical mapping — wrong movement type = wrong emission category
FUEL_MOVEMENT_TYPES = {
    '201': 'stationary_combustion',  # Fuel issued to cost center
    '261': 'stationary_combustion',  # Fuel issued to production order
}

# Movement types to EXCLUDE (not consumption)
EXCLUDED_MOVEMENT_TYPES = {
    '101',  # Goods receipt — this is procurement, not consumption
    '311',  # Plant-to-plant transfer
    '322',  # Return to storage
    '561',  # Initial entry of stock
    '701',  # Stock increase from revaluation
}

# Material groups typically associated with fuel
# In reality, this is client-specific and would need a lookup table
FUEL_MATERIAL_KEYWORDS = [
    'diesel', 'gasoline', 'petrol', 'fuel', 'kerosene', 'lpg',
    'natural gas', 'cng', 'lng', 'propane', 'butane', 'heating oil',
    'kraftstoff', 'treibstoff', 'dieselkraftstoff', 'benzin',  # German
]


def parse_sap_flat_file(content: str, source_config: dict = None) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse a SAP flat-file export (tab-delimited).
    
    Returns:
        (records, errors) — list of parsed record dicts and list of error dicts
    
    Each record dict has keys matching RawSAPRecord model fields.
    Each error dict has: {row_number, field, message, raw_value}
    """
    source_config = source_config or {}
    records = []
    errors = []
    
    lines = content.strip().split('\n')
    if len(lines) < 2:
        errors.append({'row_number': 0, 'field': 'file', 'message': 'File has no data rows', 'raw_value': ''})
        return records, errors
    
    # Parse header row
    header_line = lines[0]
    headers = [h.strip().strip('"') for h in header_line.split('\t')]
    
    # Map headers to canonical field names
    field_map = {}
    for i, header in enumerate(headers):
        canonical = resolve_header(header)
        if canonical:
            field_map[i] = canonical
        else:
            errors.append({
                'row_number': 0,
                'field': f'header_{i}',
                'message': f'Unrecognized header: "{header}"',
                'raw_value': header,
            })
    
    # Validate we have minimum required fields
    mapped_fields = set(field_map.values())
    required_fields = {'mblnr', 'bwart', 'matnr', 'werks', 'menge', 'meins', 'budat'}
    missing = required_fields - mapped_fields
    if missing:
        errors.append({
            'row_number': 0,
            'field': 'headers',
            'message': f'Missing required fields: {missing}',
            'raw_value': str(headers),
        })
        return records, errors
    
    # Parse data rows
    for row_num, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        
        values = [v.strip().strip('"') for v in line.split('\t')]
        record = {}
        row_errors = []
        
        for col_idx, field_name in field_map.items():
            if col_idx < len(values):
                record[field_name] = values[col_idx]
            else:
                record[field_name] = ''
                row_errors.append({
                    'row_number': row_num,
                    'field': field_name,
                    'message': 'Missing value',
                    'raw_value': '',
                })
        
        # Skip excluded movement types
        if record.get('bwart', '') in EXCLUDED_MOVEMENT_TYPES:
            continue
        
        # Parse and validate the date
        parsed_date = parse_sap_date(record.get('budat', ''))
        if parsed_date is None:
            row_errors.append({
                'row_number': row_num,
                'field': 'budat',
                'message': f'Cannot parse date: "{record.get("budat", "")}"',
                'raw_value': record.get('budat', ''),
            })
        
        # Validate quantity (handle German decimal comma)
        parsed_qty = parse_sap_quantity(record.get('menge', ''))
        if parsed_qty is None:
            row_errors.append({
                'row_number': row_num,
                'field': 'menge',
                'message': f'Cannot parse quantity: "{record.get("menge", "")}"',
                'raw_value': record.get('menge', ''),
            })
        elif parsed_qty < 0:
            row_errors.append({
                'row_number': row_num,
                'field': 'menge',
                'message': 'Negative quantity',
                'raw_value': record.get('menge', ''),
            })
        
        record['_parse_errors'] = row_errors
        record['_parsed_date'] = parsed_date
        record['_parsed_quantity'] = parsed_qty
        records.append(record)
        errors.extend(row_errors)
    
    return records, errors


def resolve_header(header: str) -> Optional[str]:
    """Map a header string (German or English) to canonical field name."""
    header = header.strip()
    if header in ENGLISH_HEADERS:
        return ENGLISH_HEADERS[header]
    if header in GERMAN_TO_ENGLISH:
        return GERMAN_TO_ENGLISH[header]
    # Try case-insensitive match
    for eng_header, canonical in ENGLISH_HEADERS.items():
        if header.lower() == eng_header.lower():
            return canonical
    for de_header, canonical in GERMAN_TO_ENGLISH.items():
        if header.lower() == de_header.lower():
            return canonical
    return None


def parse_sap_date(date_str: str) -> Optional[str]:
    """
    Parse SAP date string into ISO format (YYYY-MM-DD).
    
    SAP dates come in various formats depending on user settings:
    - DD.MM.YYYY (German default)
    - YYYY-MM-DD (ISO)
    - MM/DD/YYYY (US)
    - DD/MM/YYYY (UK)
    """
    if not date_str or not date_str.strip():
        return None
    
    date_str = date_str.strip().strip('"')
    
    # Try ISO format first
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return None


def parse_sap_quantity(qty_str: str) -> Optional[float]:
    """
    Parse SAP quantity, handling German decimal comma.
    
    In SAP with German locale: 1.234,56 means 1234.56
    In SAP with English locale: 1,234.56 means 1234.56
    
    Heuristic: if the last separator is a comma, it's German format.
    If the last separator is a period, it's English format.
    """
    if not qty_str or not qty_str.strip():
        return None
    
    qty_str = qty_str.strip().strip('"').strip('-')
    if not qty_str:
        return None
    
    # Count separators
    last_comma = qty_str.rfind(',')
    last_period = qty_str.rfind('.')
    
    if last_comma > last_period:
        # German: 1.234,56 → 1234.56
        qty_str = qty_str.replace('.', '').replace(',', '.')
    elif last_period > last_comma:
        # English: 1,234.56 → 1234.56
        qty_str = qty_str.replace(',', '')
    # No separators: just a number
    
    try:
        return float(qty_str)
    except ValueError:
        return None


def classify_fuel_type(material_desc: str, material_group: str) -> Optional[str]:
    """
    Determine fuel type from material description and group.
    
    In SAP, there's no standard "fuel" classification. Each client
    has their own material groups. We use keyword matching as a
    heuristic, with the expectation that clients will provide
    a mapping table for their specific material group codes.
    """
    text = f"{material_desc} {material_group}".lower()
    
    fuel_patterns = {
        'diesel': r'diesel|dieselkraftstoff',
        'gasoline': r'gasoline|petrol|benzin|unleaded',
        'natural_gas': r'natural gas|erdgas|cng|lng',
        'lpg': r'lpg|propane|butane|flüssiggas',
        'kerosene': r'kerosene|jet fuel|kerosin',
        'heating_oil': r'heating oil|fuel oil|heizöl|heavy fuel',
        'coal': r'coal|kohle|anthracite|bituminous',
    }
    
    for fuel_type, pattern in fuel_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            return fuel_type
    
    return None
