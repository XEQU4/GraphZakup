import logging
import time
from datetime import datetime

from bs4 import BeautifulSoup
from curl_cffi import requests

logger = logging.getLogger(__name__)


class ContractRegistryParser:
    """
    Скрапер реестра договоров goszakup.gov.kz.
    Все print() заменены на logger — теперь видно в файлах логов.
    """

    BASE_URL               = "https://goszakup.gov.kz"
    REQUEST_DELAY          = 1.5
    RATE_LIMIT_COOLDOWN    = 60
    MAX_RATE_LIMIT_RETRIES = 3

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Referer": "https://goszakup.gov.kz/ru/registry/contract",
        }
        self.session = requests.Session()

    @staticmethod
    def _is_rate_limited(response):
        if response.status_code == 429:
            return True
        if len(response.text) < 5000:
            if any(m in response.text for m in ("Too Many Requests", "g-recaptcha", "recaptchasubmit")):
                return True
        return False

    def _get(self, url, timeout=30):
        for attempt in range(self.MAX_RATE_LIMIT_RETRIES + 1):
            time.sleep(self.REQUEST_DELAY)
            response = self.session.get(
                url, headers=self.headers, impersonate="chrome120", timeout=timeout
            )
            if not self._is_rate_limited(response):
                return response

            if attempt >= self.MAX_RATE_LIMIT_RETRIES:
                logger.error("Rate limit: gave up on %s after %d retries", url, self.MAX_RATE_LIMIT_RETRIES)
                return response

            logger.warning(
                "Rate limited (429/captcha) на %s — cooldown %ds (попытка %d/%d)",
                url, self.RATE_LIMIT_COOLDOWN, attempt + 1, self.MAX_RATE_LIMIT_RETRIES,
            )
            time.sleep(self.RATE_LIMIT_COOLDOWN)

        return response

    def parse_bin_data(self, contract_gos_id):
        if not contract_gos_id:
            return {"customer_bin": None, "supplier_bin": None}

        url = f"{self.BASE_URL}/ru/egzcontract/cpublic/customer_n_supplier/{contract_gos_id}"
        try:
            response = self._get(url, timeout=15)
            if response.status_code != 200:
                logger.debug("BIN lookup: HTTP %d для id=%s", response.status_code, contract_gos_id)
                return {"customer_bin": None, "supplier_bin": None}

            soup = BeautifulSoup(response.text, "html.parser")
            customer_bin = None
            supplier_bin = None

            for h3 in soup.find_all("h3"):
                title = h3.get_text(strip=True)
                table = h3.find_next("table")
                if not table:
                    continue
                data = {}
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) == 2:
                        data[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True).replace("\xa0", "").strip()

                if "Заказчик" in title:
                    customer_bin = data.get("БИН") or None
                elif "Поставщик" in title:
                    supplier_bin = data.get("БИН") or data.get("ИИН") or None

            return {"customer_bin": customer_bin, "supplier_bin": supplier_bin}

        except Exception:
            logger.exception("BIN parse error (id=%s)", contract_gos_id)
            return {"customer_bin": None, "supplier_bin": None}

    def parse_contracts_page(self, page_number=1):
        url = f"{self.BASE_URL}/ru/registry/contract?page={page_number}"
        try:
            response = self._get(url, timeout=30)
            if response.status_code != 200:
                logger.warning("Page %d: HTTP %d", page_number, response.status_code)
                return []
            if self._is_rate_limited(response):
                logger.error("Page %d: всё ещё rate-limited после retries, останавливаемся.", page_number)
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            target_table = None
            for table in soup.find_all("table"):
                if "Номер договора" in [th.get_text(strip=True) for th in table.find_all("th")]:
                    target_table = table
                    break

            if not target_table:
                logger.warning("Page %d: таблица не найдена (len=%d)", page_number, len(response.text))
                return []

            rows_data = []
            for row in target_table.find_all("tr"):
                if row.find("th"):
                    continue
                cells = row.find_all("td")
                if len(cells) < 9:
                    continue

                columns = [c.get_text(" ", strip=True).replace("\xa0", " ") for c in cells]
                try:
                    contract_gos_id = int(columns[0].strip())
                except (ValueError, IndexError):
                    contract_gos_id = None

                sign_date = None
                date_raw = columns[5].strip() if len(columns) > 5 else ""
                for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y"):
                    try:
                        sign_date = datetime.strptime(date_raw, fmt).date().isoformat()
                        break
                    except ValueError:
                        continue

                amount_raw = columns[6].replace(" ", "").replace(",", ".")
                try:
                    amount = float(amount_raw)
                except ValueError:
                    amount = 0

                rows_data.append({
                    "contract_number": columns[1].strip(),
                    "contract_gos_id": contract_gos_id,
                    "sign_date":       sign_date,
                    "supplier_name":   columns[8].strip(),
                    "customer_name":   columns[7].strip(),
                    "subject":         columns[9].strip() if len(columns) > 9 else "",
                    "amount":          amount,
                    "purchase_number": columns[2].strip(),
                })

            contracts = []
            total = len(rows_data)
            for i, r in enumerate(rows_data, start=1):
                bin_data = self.parse_bin_data(r["contract_gos_id"])
                r["customer_bin"] = bin_data["customer_bin"]
                r["supplier_bin"] = bin_data["supplier_bin"]
                contracts.append(r)
                if i % 10 == 0:
                    logger.debug("BIN lookup %d/%d на странице %d...", i, total, page_number)

            logger.info("Страница %d: получено %d контрактов", page_number, len(contracts))
            return contracts

        except Exception:
            logger.exception("Contract parse error (page=%d)", page_number)
            return []

    def search_contracts_paginated(self, total=500, start_page=1):
        logger.info("Запуск парсинга: total=%d, start_page=%d", total, start_page)
        contracts = []
        pages_needed = max(1, (total + 49) // 50)

        for page in range(start_page, start_page + pages_needed):
            logger.info("Парсинг страницы %d...", page)
            page_contracts = self.parse_contracts_page(page)

            if not page_contracts:
                logger.warning("Страница %d пустая, останавливаемся.", page)
                break

            contracts.extend(page_contracts)
            logger.info("Страница %d: +%d контрактов, итого %d", page, len(page_contracts), len(contracts))

            if len(contracts) >= total:
                break

        logger.info("Парсинг завершён: собрано %d контрактов", len(contracts))
        return contracts[:total]
