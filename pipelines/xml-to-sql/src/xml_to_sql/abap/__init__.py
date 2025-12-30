"""
ABAP Generator Module

Two generation modes available:

1. EXEC SQL Mode (generator.py) - HANA-only:
   - Creates temporary view using the SQL
   - Fetches data using native SQL cursor
   - Exports to CSV (GUI download or Application Server)

2. Pure ABAP Mode (sql_to_abap.py) - Portable:
   - Uses native SELECT statements (no EXEC SQL)
   - Uses FOR ALL ENTRIES for JOIN simulation
   - Works on ANY SAP system (HANA, Oracle, SQL Server, etc.)
"""

from .generator import generate_abap_report, extract_columns_from_sql
from .sql_to_abap import generate_pure_abap_from_sql

__all__ = [
    "generate_abap_report",        # EXEC SQL mode (HANA-only)
    "extract_columns_from_sql",
    "generate_pure_abap_from_sql", # Pure ABAP mode (portable)
]
