from apps.graph.models import Connection
from apps.owners.models import (
    Ownership,
)

COMMON_OWNER = 30
COMMON_DIRECTOR = 20
COMMON_ADDRESS = 15
COMMON_PHONE = 10

OWNER_DEBT = 15
OWNER_BANKRUPT = 20
OWNER_COURT_CASE = 10


def calculate_cluster_risk(cluster):
    score = 0

    suppliers = cluster.suppliers.all()

    connections = Connection.objects.filter(
        source_supplier__in=suppliers,
        target_supplier__in=suppliers
    )

    for connection in connections:

        if connection.connection_type == Connection.OWNER:
            score += COMMON_OWNER

        elif connection.connection_type == Connection.DIRECTOR:
            score += COMMON_DIRECTOR

        elif connection.connection_type == Connection.ADDRESS:
            score += COMMON_ADDRESS

        elif connection.connection_type == Connection.PHONE:
            score += COMMON_PHONE

    for supplier in suppliers:

        ownerships = Ownership.objects.filter(
            supplier=supplier
        ).select_related("owner")

        for ownership in ownerships:

            owner = ownership.owner

            if owner.has_tax_debt:
                score += OWNER_DEBT

            if owner.is_bankrupt:
                score += OWNER_BANKRUPT

            if owner.has_court_cases:
                score += OWNER_COURT_CASE

    return min(score, 100)


def find_connections(suppliers):
    created = 0

    suppliers = list(suppliers)

    for i in range(len(suppliers)):

        left = suppliers[i]

        for j in range(i + 1, len(suppliers)):

            right = suppliers[j]

            left_owner_ids = set(
                Ownership.objects.filter(
                    supplier=left
                ).values_list(
                    "owner_id",
                    flat=True
                )
            )

            right_owner_ids = set(
                Ownership.objects.filter(
                    supplier=right
                ).values_list(
                    "owner_id",
                    flat=True
                )
            )

            common_owners = (
                    left_owner_ids &
                    right_owner_ids
            )

            if common_owners:
                Connection.objects.get_or_create(
                    source_supplier=left,
                    target_supplier=right,
                    connection_type=Connection.OWNER,
                    defaults={
                        "weight": len(common_owners)
                    }
                )

                created += 1

            left_directors = set(
                Directorship.objects.filter(
                    supplier=left
                ).values_list(
                    "director_id",
                    flat=True
                )
            )

            right_directors = set(
                Directorship.objects.filter(
                    supplier=right
                ).values_list(
                    "director_id",
                    flat=True
                )
            )

            common_directors = (
                    left_directors &
                    right_directors
            )

            if common_directors:
                Connection.objects.get_or_create(
                    source_supplier=left,
                    target_supplier=right,
                    connection_type=Connection.DIRECTOR,
                    defaults={
                        "weight": len(common_directors)
                    }
                )

                created += 1

            if (
                    left.address and
                    right.address and
                    left.address == right.address
            ):
                Connection.objects.get_or_create(
                    source_supplier=left,
                    target_supplier=right,
                    connection_type=Connection.ADDRESS
                )

                created += 1

            if (
                    left.phone and
                    right.phone and
                    left.phone == right.phone
            ):
                Connection.objects.get_or_create(
                    source_supplier=left,
                    target_supplier=right,
                    connection_type=Connection.PHONE
                )

                created += 1

    return created
