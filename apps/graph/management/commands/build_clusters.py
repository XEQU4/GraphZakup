from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Prefetch

from apps.companies.models import Supplier
from apps.graph.models import RiskCluster
from apps.owners.models import Directorship
from apps.core.utils import get_int_setting

EXCLUDED_EMAILS = {
    "info@adata.kz",
    "support@adata.kz",
}


def build_director_map(suppliers):
    return {
        supplier.id: {
            directorship.director_id
            for directorship in supplier.directorships.all()
        }
        for supplier in suppliers
    }


def get_connection_types(s1, s2, director_map):
    """
    Возвращает МНОЖЕСТВО типов связи между парой компаний
    (а не просто True/False) — нужно и для группировки, и для
    осмысленного риск-скоринга по типам, а не по числу пар.
    """
    types = set()

    if director_map[s1.id] & director_map[s2.id]:
        types.add("director")

    if s1.address and s2.address and s1.address == s2.address:
        types.add("address")

    if s1.phone and s2.phone and s1.phone == s2.phone:
        types.add("phone")

    if (
        s1.email
        and s2.email
        and s1.email == s2.email
        and s1.email not in EXCLUDED_EMAILS
    ):
        types.add("email")

    return types


def is_connected(s1, s2, director_map):
    return bool(get_connection_types(s1, s2, director_map))


def find_connected_groups(suppliers, director_map):
    supplier_list = list(suppliers)
    parent = list(range(len(supplier_list)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i, s1 in enumerate(supplier_list):
        for j, s2 in enumerate(supplier_list[i + 1:], i + 1):
            if is_connected(s1, s2, director_map):
                union(i, j)

    groups = defaultdict(list)
    for i, supplier in enumerate(supplier_list):
        groups[find(i)].append(supplier)

    return [group for group in groups.values() if len(group) > 1]


def get_risk_weights():
    return {
        "director": get_int_setting("risk_director_weight", 35),
        "address": get_int_setting("risk_address_weight", 25),
        "phone": get_int_setting("risk_phone_weight", 20),
        "email": get_int_setting("risk_email_weight", 15),
        # Доп. баллы за КАЖДУЮ компанию в группе сверх двух —
        # большая группа подозрительнее сама по себе.
        "group_size": get_int_setting("risk_group_size_weight", 5),
    }


def calculate_risk(suppliers, director_map):
    """
    ПЕРЕСМОТРЕНО: раньше риск суммировался по КАЖДОЙ ПАРЕ компаний в
    группе — при 5 компаниях с одним общим признаком это давало
    C(5,2)=10 пар и мгновенно упиралось в потолок 100/100, маскируя
    реальную тяжесть связей (один слабый признак выглядел так же
    тревожно, как несколько сильных).

    Теперь риск считается по ТИПАМ связей, обнаруженным хоть где-то
    в группе (а не по количеству пар, где они встретились), плюс
    небольшая добавка за размер самой группы. Так группа с одним
    общим телефоном и группа с общим директором+адресом+телефоном
    больше не получают одинаковый счёт только из-за числа компаний.
    """
    weights = get_risk_weights()
    supplier_list = list(suppliers)

    # Множество ВСЕХ типов связей, встретившихся хотя бы у одной пары
    all_types_found = set()
    for i, s1 in enumerate(supplier_list):
        for s2 in supplier_list[i + 1:]:
            all_types_found |= get_connection_types(s1, s2, director_map)

    score = sum(weights[t] for t in all_types_found if t in weights)

    # Бонус за размер группы: каждая компания сверх двух добавляет
    # фиксированный вес (группа из 5 подозрительнее группы из 2 при
    # прочих равных типах связей).
    extra_companies = max(0, len(supplier_list) - 2)
    score += extra_companies * weights["group_size"]

    return min(score, 100)


def generate_cluster_name(group, index):
    """
    Вместо безликого "Подозрительная группа N" — короткое описание
    на основе самой крупной/заметной компании группы, чтобы по
    списку кластеров можно было ориентироваться без захода внутрь.
    """
    # Берём компанию с максимальным risk_score как "анкер" имени;
    # при равенстве — первую по алфавиту для стабильности между перезапусками.
    anchor = sorted(
        group,
        key=lambda s: (-s.risk_score, s.name),
    )[0]

    short_name = anchor.name
    if len(short_name) > 40:
        short_name = short_name[:37] + "..."

    others = len(group) - 1
    if others > 0:
        return f"Группа: {short_name} и ещё {others}"
    return f"Группа: {short_name}"


class Command(BaseCommand):
    help = "Build affiliation clusters from suppliers"

    def handle(self, *args, **options):
        self.stdout.write("Clearing old clusters...")
        RiskCluster.objects.all().delete()

        suppliers = (
            Supplier.objects
            .prefetch_related(
                Prefetch(
                    "directorships",
                    queryset=Directorship.objects.only(
                        "supplier_id",
                        "director_id",
                    )
                ),
                "contracts",
            )
        )

        self.stdout.write(f"Analyzing {suppliers.count()} suppliers...")

        director_map = build_director_map(suppliers)
        groups = find_connected_groups(suppliers, director_map)

        self.stdout.write(f"Found {len(groups)} affiliated groups")

        for index, group in enumerate(groups, start=1):
            total_amount = sum(
                contract.amount
                for supplier in group
                for contract in supplier.contracts.all()
            )

            risk = calculate_risk(group, director_map)
            name = generate_cluster_name(group, index)

            cluster = RiskCluster.objects.create(
                name=name,
                risk_score=risk,
                total_contract_amount=total_amount,
            )
            cluster.suppliers.set(group)

            self.stdout.write(
                f"  {name}: {len(group)} компаний, риск {risk}/100"
            )

        self.stdout.write(
            self.style.SUCCESS(f"Done! Created {len(groups)} clusters")
        )
