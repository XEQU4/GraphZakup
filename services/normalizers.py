import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

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
    if not isinstance(phone, str) or re.search(r"[A-Za-zА-Яа-я]", phone):
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits if len(digits) == 11 and digits.startswith("7") else None


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
    raw = re.sub(r"\s", "", str(value)).replace(",", ".")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", raw):
        raise ValueError("invalid_amount")
    try:
        amount = Decimal(raw)
    except InvalidOperation as error:
        raise ValueError("invalid_amount") from error
    if not amount.is_finite() or amount >= Decimal("1000000000000000000"):
        raise ValueError("invalid_amount")
    return amount
