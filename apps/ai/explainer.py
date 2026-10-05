"""
ВАЖНО: предыдущая версия читала связи из модели graph.Connection, но эта
таблица никогда не заполняется (build_clusters.py вычисляет связи "на лету"
через сравнение полей Supplier, не создавая записи Connection) — поэтому
объяснение всегда было пустым/общим, какие бы реальные связи ни были у
группы. Эта версия считает связи напрямую по тем же правилам, что и
build_clusters.calculate_risk, и явно перечисляет КАКИЕ компании через
ЧТО связаны, а не просто абстрактно "выявлены признаки".

В будущем это будет заменено на полноценный AI-эксплейнер; пока что —
подробный детерминированный текст на основе реальных данных кластера.
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
    """«А», «Б» и «В» — с союзом перед последним элементом."""
    names = list(names)
    if not names:
        return ""
    if len(names) == 1:
        return f'«{names[0]}»'
    if len(names) == 2:
        return f'«{names[0]}» и «{names[1]}»'
    return ", ".join(f'«{n}»' for n in names[:-1]) + f' и «{names[-1]}»'


def explain_cluster(cluster):
    suppliers = list(cluster.suppliers.order_by("pk").prefetch_related(
        "directorships__director", "directorships__person_identity", "directorships__source_observation", "ownerships__owner"))
    director_map = _director_map(suppliers)

    # Группируем компании по конкретному совпадающему значению —
    # не просто "есть общий адрес", а "вот ЭТИ 3 компании сидят по ОДНОМУ
    # конкретному адресу X".
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

    # Общие директора — каждый отдельной фразой, упоминая ФИО (для
    # последующей кликабельности на фронтенде по точному совпадению имени)
    for (director_id, director_name), supplier_ids in by_director.items():
        if len(supplier_ids) < 2:
            continue
        names = _format_company_list(supplier_by_id[i].name for i in sorted(supplier_ids))
        sentences.append(
            f"В имеющихся сведениях {director_name} указан руководителем компаний {names}; "
            "периоды руководства требуют подтверждения."
        )

    for address, supplier_ids in by_address.items():
        if len(supplier_ids) < 2:
            continue
        names = _format_company_list(supplier_by_id[i].name for i in sorted(supplier_ids))
        sentences.append(
            f'Компании {names} зарегистрированы по одному адресу: "{address}".'
        )

    for phone, supplier_ids in by_phone.items():
        if len(supplier_ids) < 2:
            continue
        names = _format_company_list(supplier_by_id[i].name for i in sorted(supplier_ids))
        sentences.append(
            f'Компании {names} указывают один и тот же контактный телефон ({phone}).'
        )

    for email, supplier_ids in by_email.items():
        if len(supplier_ids) < 2:
            continue
        names = _format_company_list(supplier_by_id[i].name for i in sorted(supplier_ids))
        sentences.append(
            f'Компании {names} используют один email для связи ({email}).'
        )

    # Данные о владельцах (Ownership) — пока что эта таблица в проекте
    # обычно тоже не заполнена (нет источника данных по бенефициарам),
    # но если появится — учитывается отдельно.
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
            f"У {owners_with_debts} собственников компаний группы выявлены налоговые задолженности."
        )
    if owners_with_bankruptcy:
        sentences.append(
            f"У {owners_with_bankruptcy} собственников компаний группы есть признаки банкротства."
        )
    if owners_with_courts:
        sentences.append(
            f"У {owners_with_courts} собственников компаний группы имеются судебные дела."
        )

    risk = cluster.risk_score
    if risk >= 80:
        level = "высокий"
    elif risk >= 50:
        level = "средний"
    else:
        level = "низкий"

    intro = f"В группе выявлено {len(suppliers)} компаний с признаками аффилированности."

    if sentences:
        body = " ".join(sentences)
    else:
        body = "Конкретных признаков связи между компаниями группы на момент анализа не обнаружено."

    outro = (
        f"С учётом количества компаний и характера выявленных связей "
        f"совокупный риск аффилированности оценивается как {level} ({risk} из 100)."
    )

    return f"{intro} {body} {outro}"
