import re

import requests
from bs4 import BeautifulSoup


def fetch_company_data(bin_number: str):
    url = (
        f"https://pk.adata.kz/counterparty/main/company/"
        f"{bin_number}/basic-info"
    )

    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        if response.status_code != 200:
            return None

        html = response.text

        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.text if soup.title else ""

        company_name = None
        director_name = None

        parts = [p.strip() for p in title.split(",")]

        if len(parts) >= 2:
            company_name = (
                parts[0]
                .replace("&quot;", "")
                .replace('"', "")
                .strip()
            )

            director_name = parts[-1].strip()

            director_name = re.sub(
                r"БИН\s+\d+\.\s*",
                "",
                director_name,
                flags=re.IGNORECASE
            ).strip()

        address = None

        address_match = re.search(
            r'"(город [^"]+)"',
            html
        )

        if address_match:
            address = address_match.group(1)

        phone = None

        phones = re.findall(
            r'(?:\+7|8)[\d\s\-()]{9,20}',
            html
        )

        for candidate in phones:
            digits = re.sub(r"\D", "", candidate)

            if len(digits) >= 11:
                phone = candidate.strip()
                break

        email = None

        email_match = re.search(
            r'([a-zA-Z0-9._%+-]+'
            r'@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            html
        )

        if email_match:
            email = email_match.group(1)

        return {
            "bin": bin_number,
            "name": company_name,
            "director": director_name,
            "address": address,
            "phone": phone,
            "email": email,
            "status": "active",
        }

    except Exception as e:
        print(f"Error parsing {bin_number}: {e}")
        return None
