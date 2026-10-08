import re

from bs4 import BeautifulSoup

from ..normalizers import normalize_bin, normalize_date, normalize_email, normalize_phone, normalize_website
from ..errors import SourceError
from ..transport import HttpTransport


class SupplierRegistryParser:
    BASE_URL = "https://old.goszakup.gov.kz"

    def __init__(self, transport=None):
        self.transport = transport or HttpTransport()
        self.session = self.transport.session

    def _get(self, url):
        return self.transport.get(url)

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
        matching_ids = set()
        for link in links:
            row = link.find_parent("tr")
            text = row.get_text(" ", strip=True) if row else link.get_text(" ", strip=True)
            if re.search(r"(?<![0-9])" + re.escape(bin_number) + r"(?![0-9])", text):
                match = re.search(r"/ru/registry/show_supplier/([0-9]+)(?:/|$|\?)", link["href"])
                if not match or int(match.group(1)) <= 0:
                    raise SourceError("supplier_link_invalid")
                matching_ids.add(int(match.group(1)))
        if len(matching_ids) > 1:
            raise SourceError("supplier_search_identity_invalid")
        if matching_ids:
            return matching_ids.pop()
        if links:
            raise SourceError("supplier_search_identity_mismatch")
        # Only the recognisable registry results table can establish an empty result.
        # Unrelated layout tables and maintenance messages do not prove absence.
        for table in soup.find_all("table"):
            if table.find_parent(["header", "footer", "nav"]):
                continue
            headings = " ".join(th.get_text(" ", strip=True) for th in table.find_all("th"))
            if not re.search(r"(?<![А-Я])(БИН|ИИН)(?![А-Я])", headings.upper()):
                continue
            body = table.find("tbody")
            if body is None:
                continue
            text = body.get_text(" ", strip=True).lower()
            if not body.find("td") and not text:
                return None
            cells = body.find_all("td")
            if len(cells) == 1 and any(marker in text for marker in (
                    "нет данных", "ничего не найдено", "записи не найдены")):
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

    @staticmethod
    def _is_director_table(table):
        # A section applies only to its next table, never to subsequent contact tables.
        caption = table.find("caption", recursive=False)
        heading = caption or table.find_previous(["h1", "h2", "h3", "h4", "h5", "h6", "table"])
        if heading is None or heading.name == "table":
            return False
        label = heading.get_text(" ", strip=True).casefold().rstrip(":")
        return label in {"руководитель", "первый руководитель",
                         "сведения о руководителе", "информация о руководителе"}

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

        participant_ids = set()
        for table in soup.find_all("table"):
            if table.find_parent(["header", "footer", "nav"]):
                continue
            director_section = self._is_director_table(table)
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
                    # Individual participants can have an IIN and an empty BIN cell.
                    if not value:
                        continue
                    try:
                        participant_ids.add(normalize_bin(value))
                    except ValueError as error:
                        raise SourceError("supplier_fields_invalid") from error
                    if len(participant_ids) > 1:
                        raise SourceError("supplier_card_identity_invalid")
                    result["bin"] = value

                elif key == "КАТО":
                    result["kato"] = value

                elif key in {"ФИО руководителя", "Руководитель", "Первый руководитель"} or (
                        key == "ФИО" and director_section):
                    if result["director"] not in (None, "", value):
                        raise SourceError("supplier_director_fields_invalid")
                    result["director"] = value or None

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

        result['_raw'] = dict(result)
        try:
            result["bin"] = normalize_bin(result["bin"])
            result["registration_date"] = normalize_date(result["registration_date"])
        except ValueError as error:
            raise SourceError("supplier_fields_invalid") from error
        result["email"] = normalize_email(result["email"])
        result["phone"] = normalize_phone(result["phone"])
        result["website"] = normalize_website(result["website"])
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
