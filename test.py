import time
from bs4 import BeautifulSoup
from curl_cffi import requests


class ContractRegistryParser:
    BASE_URL = "https://goszakup.gov.kz"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9",
        }

    def parse_bin_data(self, show_url: str) -> dict:
        """
        Парсит страницу 'Заказчик и поставщик' по точной структуре блоков col-md-6
        """
        if not show_url:
            return {"customer_bin": None, "supplier_bin": None, "supplier_iin": None}

        # Подменяем вкладку /show/ на /customer_n_supplier/
        supplier_url = show_url.replace("/cpublic/show/", "/cpublic/customer_n_supplier/")

        print(f"   --> Извлечение БИН/ИИН по ссылке: {supplier_url}")
        try:
            res = requests.get(supplier_url, headers=self.headers, impersonate="chrome120", timeout=15)
            if res.status_code != 200:
                print(f"   Ошибка загрузки деталей: {res.status_code}")
                return {"customer_bin": None, "supplier_bin": None, "supplier_iin": None}

            soup = BeautifulSoup(res.text, "html.parser")

            customer_bin = None
            supplier_bin = None
            supplier_iin = None

            # Находим блоки заказчика и поставщика по тегам h3
            # Это гарантирует, что мы не перемешаем их данные
            h3_elements = soup.find_all("h3")

            for h3 in h3_elements:
                title = h3.get_text(strip=True)
                # Ищем родительский контейнер col-md-6, в котором лежит таблица с реквизитами
                container = h3.find_parent("div", class_="col-md-6")
                if not container:
                    continue

                if "Заказчик" in title:
                    # Ищем строку с БИН внутри блока Заказчика
                    for row in container.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) == 2 and cells[0].get_text(strip=True) == "БИН":
                            customer_bin = cells[1].get_text(strip=True)
                            break

                elif "Поставщик" in title:
                    # Ищем строки БИН и ИИН внутри блока Поставщика
                    for row in container.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) == 2:
                            label = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            if label == "БИН":
                                supplier_bin = value if value else None
                            elif label == "ИИН":
                                supplier_iin = value if value else None

            return {
                "customer_bin": customer_bin,
                "supplier_bin": supplier_bin,
                "supplier_iin": supplier_iin
            }
        except Exception as e:
            print(f"   Исключение при извлечении БИН: {e}")
            return {"customer_bin": None, "supplier_bin": None, "supplier_iin": None}

    def parse_contracts_page(self, page_number: int = 1, deep_parse_bin: bool = True):
        """Парсит страницу реестра и обогащает данными БИН"""
        url = f"{self.BASE_URL}/ru/registry/contract?page={page_number}"
        print(f"=== Скачивание страницы договоров №{page_number} ===")

        try:
            response = requests.get(url, headers=self.headers, impersonate="chrome120", timeout=30)
            if response.status_code != 200:
                print(f"Ошибка получения страницы {page_number}: Код {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            tables = soup.find_all("table")
            target_table = None
            for t in tables:
                if len(t.find_all("tr")) > 15:
                    target_table = t
                    break

            if not target_table and tables:
                target_table = tables[-1]
            if not target_table:
                return []

            contracts = []
            rows = target_table.find_all("tr")

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 8 or row.find("th"):
                    continue

                columns = [c.get_text(" ", strip=True) for c in cells]

                contract_url = None
                contract_link_tag = cells[1].find("a", href=True)
                if contract_link_tag:
                    contract_url = contract_link_tag["href"]

                contract_id = columns[0]
                contract_number = columns[1]
                status = columns[4]
                amount = columns[6]
                customer_name = columns[7]
                supplier_name = columns[8]
                subject = columns[9] if len(columns) > 9 else "Поставка товаров/услуг"

                contract_data = {
                    "contract_id": contract_id,
                    "contract_number": contract_number,
                    "contract_url": contract_url,
                    "customer_name": customer_name,
                    "customer_bin": None,  # Заполнится ниже
                    "supplier_name": supplier_name,
                    "supplier_bin": None,  # Заполнится ниже
                    "subject": subject,
                    "amount": amount,
                    "status": status
                }

                # Если включен глубокий парсинг — проваливаемся внутрь за БИН-ами
                if deep_parse_bin and contract_url:
                    bin_data = self.parse_bin_data(contract_url)
                    contract_data["customer_bin"] = bin_data["customer_bin"]
                    contract_data["supplier_bin"] = bin_data["supplier_bin"]
                    # Пауза между запросами к карточкам, чтобы портал не ругался
                    time.sleep(1.5)

                contracts.append(contract_data)

            return contracts
        except Exception as e:
            print(f"Исключение при парсинге страницы {page_number}: {e}")
            return []

    def get_contracts_massively(self, pages_to_parse: int = 1):
        all_parsed_contracts = []
        for page in range(1, pages_to_parse + 1):
            page_contracts = self.parse_contracts_page(page_number=page, deep_parse_bin=True)
            if not page_contracts:
                continue
            all_parsed_contracts.extend(page_contracts)
            print(f"Успешно обработано {len(page_contracts)} сделок.")
            time.sleep(2.5)

        return all_parsed_contracts


if __name__ == "__main__":
    parser = ContractRegistryParser()
    # Для теста берем 1 страницу, так как внутри будут дополнительные подзапросы
    test_deals = parser.get_contracts_massively(pages_to_parse=1)

    if test_deals:
        import json

        print("\n=== РЕЗУЛЬТАТ ПЕРВОГО КОНТРАКТА С БИН ===")
        print(json.dumps(test_deals[0], indent=4, ensure_ascii=False))