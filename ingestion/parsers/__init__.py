"""
Parsers for converting raw source data into normalized emission records.

Each parser:
1. Takes raw file content (string)
2. Extracts structured records
3. Handles format-specific gotchas (German headers, date formats, etc.)
4. Returns a list of dicts ready for model creation

Design principle: parsers are pure functions. They don't touch the database.
The view layer handles persistence and error handling.
"""
