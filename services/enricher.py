from services.adata_parser import fetch_company_data as fetch_adata
from services.normalizers import normalize_email
from services.normalizers import normalize_phone
from services.supplier_registry_parser import SupplierRegistryParser

registry_parser = SupplierRegistryParser()


def enrich_supplier(bin_number):
    registry_data = (
            registry_parser.get_supplier_data(bin_number)
            or {}
    )

    adata_data = (
            fetch_adata(bin_number)
            or {}
    )

    result = {
        "name": (
                registry_data.get("name")
                or adata_data.get("name")
        ),

        "director_name": (
                registry_data.get("director")
                or adata_data.get("director")
        ),

        "address": (
                registry_data.get("address")
                or adata_data.get("address")
        ),

        "region": registry_data.get("region"),

        "city": registry_data.get("city"),

        "phone": normalize_phone(
            adata_data.get("phone")
            or registry_data.get("phone")
        ),

        "email": normalize_email(
            adata_data.get("email")
            or registry_data.get("email")
        ),

        "registration_date": (
            registry_data.get("registration_date")
        ),

        "resident_status": (
            registry_data.get("resident_status")
        ),

        "company_size": (
            registry_data.get("company_size")
        ),

        "kopf": (
            registry_data.get("kopf")
        ),

        "economic_sector": (
            registry_data.get("economic_sector")
        ),

        "website": (
            registry_data.get("website")
        ),
    }

    if not any(result.values()):
        return None

    return result
