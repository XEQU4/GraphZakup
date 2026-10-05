import requests
from django.conf import settings

from apps.graph.models import Connection

OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)


def explain_cluster(cluster):
    suppliers = cluster.suppliers.all()

    company_names = [
        supplier.name
        for supplier in suppliers
    ]

    connection_types = list(
        Connection.objects.filter(
            source_supplier__in=suppliers,
            target_supplier__in=suppliers
        )
        .values_list(
            "connection_type",
            flat=True
        )
        .distinct()
    )

    prompt = f"""
Explain in plain English why this group of companies
may require review by a financial intelligence analyst
in the Republic of Kazakhstan.

Companies:
{", ".join(company_names)}

Link types:
{", ".join(connection_types)}

Risk score:
{cluster.risk_score}

Response:
- English only
- no more than 150 words
- no lists
- one coherent paragraph
"""

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization":
                    f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type":
                    "application/json",
            },
            json={
                "model": settings.OPENROUTER_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 250,
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise "OpenRouter error:" + str(response.status_code) + str(response.text)

        data = response.json()

        return (
            data["choices"][0]
            ["message"]
            ["content"]
            .strip()
        )

    except Exception as error:
        raise "OpenRouter exception:" + str(error)
