"""BUG-054: Sanitize HANA Studio's malformed XML exports before lxml.parse().

HANA Studio sometimes exports calculation view XMLs with unescaped double-quote
characters inside `leftInput`/`rightInput` attribute values, e.g.:

    <join leftInput="#//Join_2/Projection_1"
          rightInput="#//Join_2/"ABAP"./BIC/QEYPOSPER"
          joinType="leftOuter">

The literal `"ABAP"` characters terminate the `rightInput` attribute prematurely,
breaking lxml (and any standards-compliant XML parser, including browsers).
HANA Studio's own parser is lenient with its export bugs but standard SQL
toolchains aren't.

This module exposes `sanitize_hana_xml_bytes(xml_content)` which escapes the
unescaped inner quotes to `&quot;` so lxml can parse cleanly. It's a string-level
pre-processor that runs BEFORE the bytes reach lxml.

Scope: regex is tightly anchored to `leftInput=` / `rightInput=` attribute
values and the inner token must be an uppercase identifier (HANA schema name
pattern). This means:
  * `<entity>#//"ABAP"./BIC/X</entity>` (text content) is untouched — literal
    quotes in element text are valid XML.
  * `<comment text="&quot;X&quot; = '00'"/>` (other attributes) is untouched.
  * Already-escaped `&quot;` cannot be double-escaped (no literal `"` to match).
"""

from __future__ import annotations

import re
from typing import List

__all__ = ["sanitize_hana_xml_bytes", "HANA_MALFORMED_QUOTE_PATTERN"]

# Match: (leftInput|rightInput)="...prefix...""SCHEMA""...suffix..."
# Groups: 1=prefix-with-opening-quote-of-attr, 2=schema-token, 3=suffix-with-closing-quote
HANA_MALFORMED_QUOTE_PATTERN = re.compile(
    rb'((?:left|right)Input="[^"]*?)"([A-Z][A-Z0-9_]*)"([^"]*?")'
)


def sanitize_hana_xml_bytes(xml_content: bytes) -> bytes:
    """Escape HANA Studio's unescaped inner quotes inside leftInput/rightInput attributes.

    Args:
        xml_content: Raw XML bytes as read from disk or HTTP upload.

    Returns:
        Sanitized XML bytes, ready for lxml.etree.parse(BytesIO(...)).
        If no malformation is detected, returns the input bytes unchanged.

    Notes:
        - Idempotent: running twice produces the same output as running once.
        - Safe for already-valid XML: regex matches zero times on clean XML.
        - Conservative scope: only `leftInput`/`rightInput` attributes are
          touched. If new malformation patterns surface in other attributes,
          widen the regex deliberately rather than over-broadly here.
    """
    if not xml_content:
        return xml_content
    # Fast bail-out if the malformation can't be present.
    if b'leftInput' not in xml_content and b'rightInput' not in xml_content:
        return xml_content
    return HANA_MALFORMED_QUOTE_PATTERN.sub(rb'\1&quot;\2&quot;\3', xml_content)


def find_malformed_attributes(xml_content: bytes) -> List[bytes]:
    """Diagnostic helper: return the matched malformed substrings without modifying input.

    Useful for logging which files needed sanitization.
    """
    if not xml_content:
        return []
    return [m.group(0) for m in HANA_MALFORMED_QUOTE_PATTERN.finditer(xml_content)]
