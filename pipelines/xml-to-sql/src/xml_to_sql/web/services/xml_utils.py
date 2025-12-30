"""XML formatting utilities."""

from __future__ import annotations

from lxml import etree


def prettify_xml(xml_content: bytes | str) -> str:
    """
    Format XML with proper indentation.
    
    Args:
        xml_content: XML content as bytes or string
        
    Returns:
        Formatted XML as string, or original content if formatting fails
    """
    try:
        # Convert to bytes if string
        if isinstance(xml_content, str):
            xml_bytes = xml_content.encode('utf-8')
        else:
            xml_bytes = xml_content
        
        # Parse with blank text removal for cleaner output
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(xml_bytes, parser)
        
        # Format with pretty print
        formatted = etree.tostring(
            tree,
            pretty_print=True,
            encoding='unicode',
            xml_declaration=True if tree.getroottree().docinfo.xml_version else False
        )
        
        return formatted
    except Exception:
        # If formatting fails, return original content as string
        if isinstance(xml_content, bytes):
            try:
                return xml_content.decode('utf-8')
            except UnicodeDecodeError:
                return xml_content.decode('latin-1', errors='replace')
        return xml_content

