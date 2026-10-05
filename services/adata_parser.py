import re

import requests
from bs4 import BeautifulSoup

from services.normalizers import normalize_bin, normalize_email, normalize_phone
from services.parser_errors import SourceError, is_challenge, require_html_response


def parse_company_html(html, bin_number):
    bin_number = normalize_bin(bin_number)
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    identity = re.search(r"БИН\s*:?\s*([0-9]{12})(?![0-9])", title, re.IGNORECASE)
    if not identity or identity.group(1) != bin_number:
        raise SourceError("adata_identity_unconfirmed")
    parts = [part.strip() for part in title.split(",")]
    result = {
        "bin": bin_number, "name": parts[0] if len(parts) >= 2 else None,
        "director": None, "address": None, "phone": None, "email": None,
    }
    if len(parts) >= 2:
        candidate = re.sub(r"БИН\s*:?\s*[0-9]{12}\.\s*", "", parts[-1], flags=re.IGNORECASE).strip()
        if candidate and not re.search(r"БИН", candidate, re.IGNORECASE):
            result["director"] = candidate
    # Only explicitly labelled fields outside navigation/support blocks are used.
    # The old global first-phone/email regex could attach site contacts to every company.
    for label in soup.find_all(["th", "dt"]):
        if label.find_parent(["header", "footer", "nav"]):
            continue
        value_node = label.find_next_sibling("td" if label.name == "th" else "dd")
        if value_node is None:
            continue
        key = label.get_text(" ", strip=True).lower().rstrip(":")
        value = value_node.get_text(" ", strip=True)
        if key in {"email", "e-mail", "электронная почта"}:
            result["email"] = normalize_email(value)
        elif key in {"телефон", "контактный телефон"}:
            result["phone"] = normalize_phone(value)
        elif key in {"адрес", "юридический адрес"}:
            result["address"] = value or None
    return result


def fetch_company_data(bin_number: str):
    bin_number = normalize_bin(bin_number)
    url = f"https://pk.adata.kz/counterparty/main/company/{bin_number}/basic-info"
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    except requests.RequestException as error:
        raise SourceError("adata_request_failed") from error
    if response.status_code == 404 and not is_challenge(response):
        return None
    require_html_response(response)
    return parse_company_html(response.text, bin_number)
