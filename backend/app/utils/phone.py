"""Phone number formatting and validation utilities."""

import re


def format_phone_e164(phone: str, country_code: str = "1") -> str:
    """Convert messy phone input to E.164 format (+15551234567)."""
    digits = re.sub(r"\\D", "", phone)

    # Already has country code
    if digits.startswith(country_code) and len(digits) == len(country_code) + 10:
        return "+{}".format(digits)

    # Just 10 digits (US local)
    if len(digits) == 10:
        return "+{}{}".format(country_code, digits)

    # Already starts with +
    if phone.strip().startswith("+"):
        return "+{}".format(digits)

    return "+{}{}".format(country_code, digits)


def is_valid_phone(phone: str) -> bool:
    """Basic check that a phone string can be converted to a plausible E.164 number."""
    try:
        e164 = format_phone_e164(phone)
        return bool(re.match(r"^\\+\\d{11,15}$", e164))
    except Exception:
        return False
