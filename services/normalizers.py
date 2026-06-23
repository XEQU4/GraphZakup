import re

BLACKLIST_EMAILS = {
    "info@adata.kz",
    "support@adata.kz"
}


def normalize_email(email):
    if not email:
        return None

    email = email.strip().lower()

    if email in BLACKLIST_EMAILS:
        return None

    return email


def normalize_phone(phone):
    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)

    if digits.startswith("8"):
        digits = "7" + digits[1:]

    if len(digits) != 11:
        return None

    return digits
