"""Server-Sent Events (SSE) helper utilities for streaming conversion progress."""

import json
from typing import Any, Dict


def format_sse_message(event: str, data: Dict[str, Any]) -> str:
    """
    Format a message as a Server-Sent Event.

    Args:
        event: Event type (e.g., 'stage_update', 'complete', 'error')
        data: Event data to send as JSON

    Returns:
        Formatted SSE message string
    """
    json_data = json.dumps(data)
    return f"event: {event}\ndata: {json_data}\n\n"


def stage_to_sse_dict(stage) -> Dict[str, Any]:
    """
    Convert a ConversionStage object to a dictionary for SSE transmission.

    Args:
        stage: ConversionStage object from converter service

    Returns:
        Dictionary representation suitable for JSON serialization
    """
    return {
        "stage_name": stage.stage_name,
        "status": stage.status,
        "timestamp": stage.timestamp.isoformat() if stage.timestamp else None,
        "duration_ms": stage.duration_ms,
        "details": stage.details or {},
        "error": stage.error,
    }
