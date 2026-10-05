import logging
from dataclasses import dataclass

from bs4 import BeautifulSoup

from ..normalizers import normalize_amount, normalize_bin, normalize_date
from ..errors import SourceError, is_challenge
from ..transport import HttpTransport

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContractPage:
    number: int
    records: tuple
    eof: bool = False


class ContractRegistryParser:
    BASE_URL = "https://goszakup.gov.kz"

    def __init__(self, transport=None):
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Referer": f"{self.BASE_URL}/ru/registry/contract",
        }
        self.transport = transport or HttpTransport()
        self.session = self.transport.session

    _is_rate_limited = staticmethod(is_challenge)

    def _get(self, url, timeout=30):
        return self.transport.get(url, headers=self.headers, timeout=timeout)

    def parse_bin_data(self, contract_gos_id):
        if not isinstance(contract_gos_id, int) or contract_gos_id <= 0:
            raise SourceError("contract_external_id_missing")
        url = f"{self.BASE_URL}/ru/egzcontract/cpublic/customer_n_supplier/{contract_gos_id}"
        soup = BeautifulSoup(self._get(url, timeout=15).text, "html.parser")
        result = {"customer_bin": None, "supplier_bin": None}
        raw = {}
        try:
            for heading in soup.find_all("h3"):
                title = heading.get_text(strip=True)
                table = heading.find_next("table")
                if not table:
                    continue
                values = {}
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) == 2:
                        values[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)
                if "Заказчик" in title:
                    raw['customer_bin'] = values.get('БИН')
                    result["customer_bin"] = normalize_bin(values.get("БИН"))
                elif "Поставщик" in title:
                    raw['supplier_bin'] = values.get('БИН') or values.get('ИИН')
                    result["supplier_bin"] = normalize_bin(values.get("БИН") or values.get("ИИН"))
        except ValueError as error:
            raise SourceError("contract_party_identifier_invalid") from error
        if not result["supplier_bin"] or not result["customer_bin"]:
            raise SourceError("contract_party_identifier_missing")
        result['_raw'] = raw
        return result

    def fetch_page(self, page_number=1):
        if page_number < 1:
            raise ValueError("page_number_must_be_positive")
        response = self._get(f"{self.BASE_URL}/ru/registry/contract?page={page_number}")
        soup = BeautifulSoup(response.text, "html.parser")
        table = next((table for table in soup.find_all("table")
                      if "Номер договора" in [th.get_text(strip=True) for th in table.find_all("th")]), None)
        if table is None:
            raise SourceError("contract_table_missing")
        if table.find("tbody") is None:
            raise SourceError("contract_table_body_missing")
        records = []
        for row in table.find("tbody").find_all("tr"):
            if row.find("th"):
                continue
            cells = row.find_all("td")
            if not cells:
                continue
            if len(cells) == 1 and any(marker in cells[0].get_text(" ", strip=True).lower()
                                       for marker in ("нет данных", "ничего не найдено", "записи не найдены")):
                continue
            if len(cells) < 9:
                raise SourceError("contract_row_invalid")
            values = [cell.get_text(" ", strip=True) for cell in cells]
            try:
                identifier = int(values[0])
                if identifier <= 0 or not values[1]:
                    raise ValueError("invalid_contract_identity")
                signed = normalize_date(values[5])
                if signed is None:
                    raise ValueError("contract_date_missing")
                record = {
                    "contract_number": values[1], "contract_gos_id": identifier,
                    "sign_date": signed, "supplier_name": values[8], "customer_name": values[7],
                    "subject": values[9] if len(values) > 9 else "",
                    "amount": normalize_amount(values[6]), "purchase_number": values[2],
                }
                record['_raw'] = {
                    'contract_number': values[1], 'contract_gos_id': values[0], 'sign_date': values[5],
                    'supplier_name': values[8], 'customer_name': values[7],
                    'amount': values[6], 'purchase_number': values[2], 'subject': record['subject'],
                }
            except ValueError as error:
                raise SourceError("contract_row_invalid") from error
            records.append(record)
        for record in records:
            parties = self.parse_bin_data(record["contract_gos_id"])
            record['_raw'].update(parties.pop('_raw', {}))
            record.update(parties)
        return ContractPage(page_number, tuple(records), eof=not records)

    def iter_pages(self, start_page=1):
        page_number = start_page
        while True:
            page = self.fetch_page(page_number)
            yield page
            if page.eof:
                return
            page_number += 1

    def parse_contracts_page(self, page_number=1):
        """Compatibility helper; source failures propagate instead of becoming []."""
        return list(self.fetch_page(page_number).records)

    def search_contracts_paginated(self, total=500, start_page=1):
        """Convenience reader; import checkpoints must use complete ContractPage objects."""
        if total <= 0:
            raise ValueError("total_must_be_positive")
        contracts = []
        for page in self.iter_pages(start_page):
            contracts.extend(page.records)
            if page.eof or len(contracts) >= total:
                break
        return contracts[:total]
