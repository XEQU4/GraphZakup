import re

from bs4 import BeautifulSoup
from curl_cffi import requests

from services.normalizers import normalize_bin, normalize_date, normalize_email, normalize_phone
from services.parser_errors import SourceError, require_html_response


class SupplierRegistryParser:
    BASE_URL = "https://goszakup.gov.kz"

    def __init__(self):
        self.session = requests.Session()

    def _get(self, url):
        try:
            response = self.session.get(url, impersonate="chrome120", timeout=30)
        except requests.RequestsError as error:
            raise SourceError("supplier_request_failed") from error
        require_html_response(response)
        return response

    def parse_region_city(self, address):
        if not address:
            return None, None

        parts = [
            p.strip()
            for p in address.split(",")
            if p.strip()
        ]

        if parts and parts[0].lower() in (
                "казахстан",
                "республика казахстан",
        ):
            parts = parts[1:]

        if not parts:
            return None, None

        region = parts[0]

        city = None

        for part in parts[1:]:
            lower = part.lower()

            if (
                    "район" in lower
                    or lower.startswith("г.")
                    or lower.startswith("город ")
                    or lower.startswith("с.")
                    or lower.startswith("п.")
            ):
                city = part
                break

        INVALID_CITY_PREFIXES = (
            "улица",
            "ул.",
            "микрорайон",
            "мкр",
            "жилой массив",
        )

        if not city:
            for part in parts[1:]:
                lower = part.lower()

                if lower.startswith(INVALID_CITY_PREFIXES):
                    continue

                city = part
                break

        if not city:
            city = region

        return region, city

    def get_supplier_id(self, bin_number: str):
        bin_number = normalize_bin(bin_number)
        url = (
            f"{self.BASE_URL}/ru/registry/supplierreg"
            f"?filter[name]={bin_number}&search=&filter[attribute]="
        )

        response = self._get(url)

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        links = soup.select('a[href*="/ru/registry/show_supplier/"]')
        for link in links:
            row = link.find_parent("tr")
            text = row.get_text(" ", strip=True) if row else link.get_text(" ", strip=True)
            if re.search(r"(?<![0-9])" + re.escape(bin_number) + r"(?![0-9])", text):
                match = re.search(r"/ru/registry/show_supplier/([0-9]+)(?:/|$|\?)", link["href"])
                if not match:
                    raise SourceError("supplier_link_invalid")
                return int(match.group(1))
        if links:
            raise SourceError("supplier_search_identity_mismatch")
        text = soup.get_text(" ", strip=True).lower()
        if any(marker in text for marker in ("нет данных", "ничего не найдено", "записи не найдены")):
            return None
        empty_table = any(table.find("tbody") is not None and not table.find("tbody").find("td")
                          for table in soup.find_all("table"))
        if empty_table:
            return None
        raise SourceError("supplier_search_structure_invalid")

    def get_supplier_html(
            self,
            supplier_id: int
    ):
        url = (
            f"{self.BASE_URL}"
            f"/ru/registry/show_supplier/{supplier_id}"
        )

        return self._get(url).text

    def parse_supplier_page(
            self,
            html: str
    ):
        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        result = {
            "name": None,
            "bin": None,
            "director": None,
            "address": None,
            "region": None,
            "city": None,
            "kato": None,
            "email": None,
            "phone": None,

            "resident_status": None,
            "registration_date": None,
            "company_size": None,
            "kopf": None,
            "economic_sector": None,
            "website": None,
        }

        h1 = soup.find("h1")
        if h1:
            result["name"] = h1.get_text(strip=True)

        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                th = row.find("th")
                td = row.find("td")

                if not th or not td:
                    continue

                key = th.get_text(
                    " ",
                    strip=True
                )

                value = td.get_text(
                    " ",
                    strip=True
                )

                if "БИН участника" in key or "ИИН участника" in key:
                    result["bin"] = value

                elif key == "КАТО":
                    result["kato"] = value

                elif key == "ФИО":
                    result["director"] = value

                elif "E-Mail" in key:
                    result["email"] = value

                elif "Контактный телефон" in key:
                    result["phone"] = value

                elif "Резидентство" in key:
                    result["resident_status"] = value

                elif "Дата свидетельства" in key:
                    result["registration_date"] = value

                elif key == "КОПФ":
                    result["kopf"] = value

                elif "Размерность предприятия" in key:
                    result["company_size"] = value

                elif "Код сектора экономики" in key:
                    result["economic_sector"] = value

                elif "Вебсайт" in key or "Веб-сайт" in key:
                    result["website"] = value

        contact_header = soup.find(
            "h4",
            string=lambda x: (
                    x and
                    "Контактная информация" in x
            )
        )

        if contact_header:
            panel = contact_header.find_parent(
                "div",
                class_="panel"
            )

            if panel:
                rows = panel.find_all("tr")

                for row in rows[1:]:
                    cells = row.find_all("td")

                    if len(cells) < 3:
                        continue

                    address = cells[2].get_text(
                        " ",
                        strip=True
                    )

                    kato = cells[1].get_text(
                        " ",
                        strip=True
                    )

                    if address:
                        result["address"] = address

                        region, city = self.parse_region_city(
                            address
                        )

                        result["region"] = region
                        result["city"] = city

                    if kato:
                        result["kato"] = kato

                    break

        try:
            result["bin"] = normalize_bin(result["bin"])
            result["registration_date"] = normalize_date(result["registration_date"])
        except ValueError as error:
            raise SourceError("supplier_fields_invalid") from error
        result["email"] = normalize_email(result["email"])
        result["phone"] = normalize_phone(result["phone"])
        return result

    def get_supplier_data(
            self,
            bin_number: str
    ):
        bin_number = normalize_bin(bin_number)
        supplier_id = self.get_supplier_id(
            bin_number
        )

        if not supplier_id:
            return None

        html = self.get_supplier_html(
            supplier_id
        )

        data = self.parse_supplier_page(
            html
        )

        if data["bin"] != bin_number:
            raise SourceError("supplier_card_identity_mismatch")

        data["supplier_id"] = supplier_id

        return data
