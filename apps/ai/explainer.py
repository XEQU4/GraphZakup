"""
The earlier version read graph.Connection, which the current pipeline does
not populate. Cluster building compares Supplier fields without creating
Connection rows, so those explanations were empty or generic. This version
uses the same matching rules as graph analysis and names the companies and
specific values that connect them.

This is a deterministic English template. Versioned evidence-based analysis
and controlled LLM explanations are planned for Phase 5.
"""

from collections import defaultdict

from apps.graph.services import current_directorships

EXCLUDED_EMAILS = {"info@adata.kz", "support@adata.kz"}


def _director_map(suppliers):
    return {
        s.id: {d.person_identity_id: d.director.full_name for d in current_directorships(s)}
        for s in suppliers
    }


def _format_company_list(names):
    """Quote company names and join the final item with an English conjunction."""
    names = list(names)
    if not names:
        return ""
    if len(names) == 1:
        return f'«{names[0]}»'
    if len(names) == 2:
        return f'«{names[0]}» and «{names[1]}»'
    return ", ".join(f'«{n}»' for n in names[:-1]) + f' and «{names[-1]}»'


def explain_cluster(cluster):
    suppliers = list(cluster.suppliers.order_by("pk").prefetch_related(
        "directorships__director", "directorships__person_identity", "directorships__source_observation", "ownerships__owner"))
    director_map = _director_map(suppliers)

    # Group by the exact shared value to identify which companies match.
    by_director = defaultdict(set)  # director_name -> {supplier_id}
    by_address = defaultdict(set)  # address -> {supplier_id}
    by_phone = defaultdict(set)  # phone -> {supplier_id}
    by_email = defaultdict(set)  # email -> {supplier_id}

    for s in suppliers:
        for director_id, director_name in director_map[s.id].items():
            by_director[(director_id, director_name)].add(s.id)
        if s.address:
            by_address[s.address].add(s.id)
        if s.phone:
            by_phone[s.phone].add(s.id)
        email = s.email.strip().lower()
        if email and email not in EXCLUDED_EMAILS:
            by_email[email].add(s.id)

    supplier_by_id = {s.id: s for s in suppliers}

    sentences = []

    # Name each shared director so the frontend can link exact names.
    for (director_id, director_name), supplier_ids in by_director.items():
        if len(supplier_ids) < 2:
            continue
        names = _format_company_list(supplier_by_id[i].name for i in sorted(supplier_ids))
        sentences.append(
            f"Available records list {director_name} as director of companies {names}; "
            "leadership periods require confirmation."
        )

    for address, supplier_ids in by_address.items():
        if len(supplier_ids) < 2:
            continue
        names = _format_company_list(supplier_by_id[i].name for i in sorted(supplier_ids))
        sentences.append(
            f'Companies {names} are registered at the same address: "{address}".'
        )

    for phone, supplier_ids in by_phone.items():
        if len(supplier_ids) < 2:
            continue
        names = _format_company_list(supplier_by_id[i].name for i in sorted(supplier_ids))
        sentences.append(
            f'Companies {names} list the same contact phone number ({phone}).'
        )

    for email, supplier_ids in by_email.items():
        if len(supplier_ids) < 2:
            continue
        names = _format_company_list(supplier_by_id[i].name for i in sorted(supplier_ids))
        sentences.append(
            f'Companies {names} use the same contact email ({email}).'
        )

    # Ownership has no current external source; include saved owner facts
    # separately if records exist.
    owners_with_debts = 0
    owners_with_bankruptcy = 0
    owners_with_courts = 0
    checked_owners = set()

    for supplier in suppliers:
        for ownership in supplier.ownerships.all():
            owner = ownership.owner
            if owner.id in checked_owners:
                continue
            checked_owners.add(owner.id)
            if owner.has_tax_debt:
                owners_with_debts += 1
            if owner.is_bankrupt:
                owners_with_bankruptcy += 1
            if owner.has_court_cases:
                owners_with_courts += 1

    if owners_with_debts:
        sentences.append(
            f"Tax debts are recorded for {owners_with_debts} company owners in the group."
        )
    if owners_with_bankruptcy:
        sentences.append(
            f"Bankruptcy indicators are recorded for {owners_with_bankruptcy} company owners in the group."
        )
    if owners_with_courts:
        sentences.append(
            f"Court cases are recorded for {owners_with_courts} company owners in the group."
        )

    risk = cluster.risk_score
    if risk >= 80:
        level = "high"
    elif risk >= 50:
        level = "medium"
    else:
        level = "low"

    intro = f"The group contains {len(suppliers)} companies with indicators of affiliation."

    if sentences:
        body = " ".join(sentences)
    else:
        body = "No specific indicators of links between group companies were found at the time of analysis."

    outro = (
        f"Based on the number of companies and the nature of the observed links, "
        f"the overall affiliation risk is assessed as {level} ({risk} out of 100)."
    )

    return f"{intro} {body} {outro}"
