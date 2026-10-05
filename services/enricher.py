from services.adata_parser import fetch_company_data as fetch_adata
from services.normalizers import normalize_bin, normalize_date, normalize_email, normalize_phone
from services.parser_errors import SourceError
from services.supplier_registry_parser import SupplierRegistryParser

registry_parser = SupplierRegistryParser()


def _normalize_source(data, bin_number):
    if not data:
        return {}
    if normalize_bin(data.get("bin")) != bin_number:
        raise SourceError("enrichment_identity_mismatch")
    normalized = dict(data)
    normalized["phone"] = normalize_phone(data.get("phone"))
    normalized["email"] = normalize_email(data.get("email"))
    normalized["registration_date"] = normalize_date(data.get("registration_date"))
    return normalized


def enrich_supplier(bin_number):
    bin_number = normalize_bin(bin_number)
    sources, errors = [], []
    for fetch in (registry_parser.get_supplier_data, fetch_adata):
        try:
            sources.append(_normalize_source(fetch(bin_number), bin_number))
        except (SourceError, ValueError) as error:
            sources.append({})
            errors.append(error.code if isinstance(error, SourceError) else "source_fields_invalid")
    registry, adata = sources
    if not registry and not adata:
        if errors:
            raise SourceError("enrichment_sources_failed")
        return None
    result = {
        "bin": bin_number,
        "name": registry.get("name") or adata.get("name"),
        "director_name": registry.get("director") or adata.get("director"),
        "address": registry.get("address") or adata.get("address"),
        "phone": adata.get("phone") or registry.get("phone"),
        "email": adata.get("email") or registry.get("email"),
        "registration_date": registry.get("registration_date"),
        "_source_errors": errors,
    }
    for field in ("region", "city", "resident_status", "company_size", "kopf", "economic_sector", "website"):
        result[field] = registry.get(field)
    return result
