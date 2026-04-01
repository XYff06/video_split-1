"""Utility helpers for converting and formatting video timestamps."""


def format_seconds_to_timestamp(seconds_value: float) -> str:
    """Convert raw seconds value to HH:MM:SS.mmm style for presentation/logging.

    We keep original precision in numeric fields elsewhere. This function only creates a
    readable text representation for logs and response payload readability.
    """

    hours = int(seconds_value // 3600)
    minutes = int((seconds_value % 3600) // 60)
    seconds = seconds_value % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
