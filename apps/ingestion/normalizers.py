import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email

BLACKLIST_EMAILS = {"info@adata.kz", "support@adata.kz"}


def normalize_email(email):
    if not isinstance(email, str) or not email.strip():
        return None
    email = email.strip().lower()
    if email in BLACKLIST_EMAILS:
        return None
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


def normalize_phone(phone):
    # Never discard letters or unsupported symbols to manufacture a shared contact.
    if not isinstance(phone, str) or not re.fullmatch(r"\+?[0-9()\s.\-]+", phone.strip()):
        return None
    digits = re.sub(r"[^0-9]", "", phone)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits if len(digits) == 11 and digits.startswith("7") else None


def normalize_website(value):
    """Normalize an optional displayed URL without contacting or verifying the site."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if not re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", value):
        value = "https://" + value
    if len(value) > 200:
        return None
    try:
        url = urlsplit(value)
        if url.username or url.password:
            return None
        URLValidator(schemes=["http", "https"])(value)
    except (ValueError, ValidationError):
        return None
    return value


def normalize_bin(value):
    # Keep identifiers as strings, including their leading zeroes.
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{12}", value.strip()):
        raise ValueError("invalid_bin_or_iin")
    return value.strip()


def normalize_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("invalid_date")
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError("invalid_date")


def normalize_amount(value):
    if isinstance(value, float) or isinstance(value, bool) or value is None:
        raise ValueError("invalid_amount")
    raw = re.sub(r"\s+", " ", str(value).strip())
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?: [0-9]{3})+)(?:[.,][0-9]{1,2})?", raw):
        raise ValueError("invalid_amount")
    try:
        amount = Decimal(raw.replace(" ", "").replace(",", "."))
    except InvalidOperation as error:
        raise ValueError("invalid_amount") from error
    if not amount.is_finite() or amount >= Decimal("1000000000000000000"):
        raise ValueError("invalid_amount")
    return amount
