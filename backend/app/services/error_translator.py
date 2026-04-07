"""Translate technical integration errors to plain English."""

import re

# Twilio error codes → friendly messages
_TWILIO = {
    "21211": "The phone number doesn't look right. Check if the client's number is correct.",
    "21610": "This phone number has opted out of receiving messages.",
    "21614": "This phone number can't receive text messages.",
    "21408": "Couldn't reach this phone number. It may be disconnected.",
    "30004": "The message was blocked by the carrier.",
    "30005": "Unknown destination. The phone number may not exist.",
    "30006": "The phone is unreachable right now. The message will be retried.",
    "30007": "The message was filtered as spam by the carrier.",
}

# Google / Gmail patterns
_GOOGLE_PATTERNS = [
    (r"401|invalid.credentials|token.*expired", "Your Google connection needs to be refreshed. Head to Connected Tools to reconnect."),
    (r"403|forbidden|insufficient", "Google didn't allow this action. Permissions may need updating."),
    (r"404|not.found", "Couldn't find this item. It may have been deleted."),
    (r"429|rate.limit|quota", "Too many requests to Google right now. I'll try again shortly."),
]

# Generic patterns
_GENERIC_PATTERNS = [
    (r"timeout|timed.out|ETIMEDOUT", "Couldn't reach the service right now. I'll try again shortly."),
    (r"connect.*refused|ECONNREFUSED", "The service isn't responding right now. I'll try again shortly."),
    (r"network|DNS|ENETUNREACH", "There's a network issue. I'll try again shortly."),
]


def translate_error(raw_error: str, service: str = "") -> str:
    """Convert a technical error to owner-friendly language."""
    if not raw_error:
        return "Something unexpected went wrong. I've logged the details."

    error_lower = raw_error.lower()

    # Check Twilio codes
    if "twilio" in service.lower() or "sms" in service.lower():
        for code, msg in _TWILIO.items():
            if code in raw_error:
                return msg

    # Check Google patterns
    if "google" in service.lower() or "gmail" in service.lower() or "calendar" in service.lower():
        for pattern, msg in _GOOGLE_PATTERNS:
            if re.search(pattern, error_lower):
                return msg

    # Generic patterns
    for pattern, msg in _GENERIC_PATTERNS:
        if re.search(pattern, error_lower):
            return msg

    return "Something unexpected went wrong. I've logged the details so this can be looked into."
