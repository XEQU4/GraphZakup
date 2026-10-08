import json
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ..normalizers import normalize_bin, normalize_email, normalize_phone
from ..errors import SourceError
from ..transport import HttpTransport



def _company_page_matches(page, bin_number):
    if not isinstance(page, str):
        return False
    try:
        url = urlsplit(page)
        return (url.scheme == "https" and url.hostname == "pk.adata.kz"
                and url.port in (None, 443) and not url.username and not url.password
                and url.path.rstrip("/") == f"/counterparty/main/company/{bin_number}/basic-info"
                and not url.query and not url.fragment)
    except ValueError:
        return False


def _public_profile(soup, bin_number, *, require_page_binding=False):
    """Use public JSON-LD only when its company identity is explicit."""
    records = []

    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise SourceError("adata_structured_duplicate_key_invalid")
            value[key] = item
        return value

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or script.get_text(), object_pairs_hook=unique_object)
        except (ValueError, TypeError, RecursionError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("@graph"), list):
            payload = payload["@graph"]
        if isinstance(payload, dict):
            payload = [payload]
        if isinstance(payload, list):
            if len(payload) > 100 or len(records) + len(payload) > 100:
                raise SourceError("adata_structured_profile_invalid")
            records.extend(item for item in payload if isinstance(item, dict))
    profiles = []
    missing = {"", "-", "—", "null", "none", "нет данных", "информация отсутствует"}

    def text(value, limit):
        if not isinstance(value, str) or len(value) > limit:
            return None
        value = value.strip()
        return None if value.casefold() in missing or "*" in value else value

    for item in records:
        if item.get("@type") != "Organization":
            continue
        identifiers = [item[key] for key in ("identifier", "vatID") if item.get(key) not in (None, "")]
        if bin_number not in identifiers:
            continue
        if any(value != bin_number for value in identifiers):
            raise SourceError("adata_structured_identity_invalid")
        if require_page_binding and (
                item.get("identifier") != bin_number or item.get("vatID") != bin_number
                or not _company_page_matches(item.get("url"), bin_number)):
            raise SourceError("adata_structured_identity_invalid")
        if item.get("url") and not _company_page_matches(item["url"], bin_number):
            raise SourceError("adata_structured_identity_invalid")
        raw = {"bin": bin_number, "name": text(item.get("name"), 255),
               "address": text(item.get("address"), 1000),
               "email": text(item.get("email"), 254), "phone": text(item.get("telephone"), 100)}
        values = {**raw, "email": normalize_email(raw["email"]), "phone": normalize_phone(raw["phone"])}
        profiles.append((values, raw))
    if not profiles:
        return None
    values, raw = profiles[0]
    if any(other != values for other, _ in profiles[1:]):
        raise SourceError("adata_structured_profile_invalid")
    directors = set()
    roles = {"руководитель", "директор", "первый руководитель", "генеральный директор",
             "руководитель компании"}
    for item in records:
        if item.get("@type") != "Person" or not isinstance(item.get("jobTitle"), str):
            continue
        if item["jobTitle"].strip().casefold() not in roles:
            continue
        bound = _company_page_matches(item.get("mainEntityOfPage"), bin_number)
        name = text(item.get("name"), 255)
        if bound and name:
            directors.add(name)
    if len(directors) > 1:
        raise SourceError("adata_structured_director_invalid")
    values["director"] = raw["director"] = next(iter(directors), None)
    return values, raw

def parse_company_html(html, bin_number):
    bin_number = normalize_bin(bin_number)
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    identities = list(re.finditer(r"(?:БИН|ИИН)\s*:?\s*([0-9]{12})(?![0-9])", title, re.IGNORECASE))
    if any(identity.group(1) != bin_number for identity in identities):
        raise SourceError("adata_identity_unconfirmed")
    profile = _public_profile(soup, bin_number, require_page_binding=not identities)
    if not identities and profile is None:
        raise SourceError("adata_identity_unconfirmed")
    name = title[:identities[0].start()].strip(" ,.;:-") if identities else None
    result = {
        "bin": bin_number, "name": name or None,
        "director": None, "address": None, "phone": None, "email": None,
    }
    if profile is not None:
        values, raw = profile
        if not values["name"]:
            values["name"] = raw["name"] = result["name"]
        result.update(values)
        result["_raw"] = raw
        return result
    # Only explicitly labelled fields outside navigation/support blocks are used.
    # The old global first-phone/email regex could attach site contacts to every company.
    raw = dict(result)
    for label in soup.find_all(["th", "dt"]):
        if label.find_parent(["header", "footer", "nav"]):
            continue
        value_node = label.find_next_sibling("td" if label.name == "th" else "dd")
        if value_node is None:
            continue
        key = label.get_text(" ", strip=True).lower().rstrip(":")
        value = value_node.get_text(" ", strip=True)
        if key in {"директор", "руководитель", "фио руководителя"}:
            raw['director'] = value
            result['director'] = value or None
        elif key in {"email", "e-mail", "электронная почта"}:
            raw['email'] = value
            result["email"] = normalize_email(value)
        elif key in {"телефон", "контактный телефон"}:
            raw['phone'] = value
            result["phone"] = normalize_phone(value)
        elif key in {"адрес", "юридический адрес"}:
            raw['address'] = value
            result["address"] = value or None
    result['_raw'] = raw
    return result


def fetch_company_data(bin_number: str, transport=None):
    bin_number = normalize_bin(bin_number)
    url = f"https://pk.adata.kz/counterparty/main/company/{bin_number}/basic-info"
    client = transport or HttpTransport()
    try:
        response = client.get(url, timeout=20, allow_not_found=True)
        if response.status_code == 404:
            return None
        return parse_company_html(response.text, bin_number)
    finally:
        if transport is None:
            client.close()
