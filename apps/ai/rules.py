"""Versioned review-priority rules. Scores are indices, never guilt probabilities."""
from collections import defaultdict
from decimal import Decimal

from apps.graph.evidence import digest

RULES_VERSION = 'review-rules-5.0'
BASE_LIMITATIONS = [
    'Review priority is an uncalibrated heuristic index, not a probability of wrongdoing.',
    'Identity reliability, relationship strength and behavioural risk are separate dimensions.',
    'Bidders, bids and lot outcomes are unavailable; coordinated bidding cannot be assessed.',
    'Unknown checks do not establish absence of a finding. Company arrears are not owner arrears.',
]


def evaluate(inputs):
    findings, groups = [], defaultdict(list)
    categories, strengths = {}, []

    def add(code, company_ids, evidence, statements, contribution=0, dimension='relationship', limits=()):
        identifier = 'f-' + digest([code, sorted(company_ids), evidence])[:16]
        findings.append({'id': identifier, 'code': code, 'rule_version': RULES_VERSION,
                         'company_ids': sorted(company_ids), 'evidence': evidence,
                         'statements': statements, 'candidate_contribution': contribution, 'contribution': 0,
                         'dimension': dimension, 'limitations': list(limits)})

    for edge in inputs['graph']['links']:
        groups[(edge['target'], edge['type'])].append(edge)
    for (_, kind), edges in sorted(groups.items()):
        companies = sorted({edge['company_id'] for edge in edges})
        if len(companies) < 2:
            continue
        evidence = [{'kind': 'graph_edge', 'id': edge['id']} for edge in edges]
        limits = sorted({item for edge in edges for item in edge['limitations']})
        count = len(companies)
        if kind in {'director', 'owner'}:
            known_period = all(edge['valid_from'] and edge['valid_until'] for edge in edges)
            contribution = (35 if kind == 'owner' else 25) if known_period else (20 if kind == 'owner' else 15)
            categories[kind] = max(categories.get(kind, 0), contribution)
            strengths.append(95)
            period = (f"Recorded role intervals include {inputs['graph_as_of']}." if known_period else
                      'Legal interval boundaries are incomplete; simultaneous roles require confirmation.')
            add(f'shared_{kind}', companies, evidence,
                [f'Saved records list an identifier-confirmed shared {kind} for {count} companies. {period}',
                 f'An identifier-confirmed {kind} links {count} companies in the saved records. {period}'],
                contribution, limits=limits)
        else:
            common = any(edge['common_contact'] for edge in edges)
            contribution = 0 if common else {'address': 2, 'phone': 5, 'email': 5}[kind]
            categories['contacts'] = max(categories.get('contacts', 0), contribution)
            strengths.append(10 if common else 25)
            label = {'address': 'address', 'phone': 'phone number', 'email': 'email address'}[kind]
            add(f'shared_{kind}', companies, evidence,
                [f'{count} companies share a recorded {label}. This is weak evidence requiring verification.',
                 f'A shared {label} occurs in {count} company records; it does not establish affiliation.'],
                contribution, limits=limits)

    people = defaultdict(list)
    for edge in inputs['graph']['links']:
        if edge['type'] in {'owner', 'director'}:
            people[edge['target']].append(edge)
    for edges in people.values():
        companies = sorted({edge['company_id'] for edge in edges})
        by_kind = {kind: {edge['company_id'] for edge in edges if edge['type'] == kind}
                   for kind in ('owner', 'director')}
        if len(companies) < 2 or any(len(ids) > 1 for ids in by_kind.values()):
            continue
        known_period = all(edge['valid_from'] and edge['valid_until'] for edge in edges)
        points = 20 if known_period else 10
        categories['cross_role'] = max(categories.get('cross_role', 0), points)
        strengths.append(95)
        limits = sorted({item for edge in edges for item in edge['limitations']})
        add('mixed_person_roles', companies, [{'kind': 'graph_edge', 'id': edge['id']} for edge in edges],
            [f'{len(companies)} companies are connected through an identifier-confirmed person holding different recorded roles.',
             f'One identifier-confirmed person connects {len(companies)} companies across recorded ownership and directorship roles.'],
            points, limits=limits)

    positive, checked, missing, retained = [], 0, 0, 0
    for fact in inputs['company_checks']:
        pk, status = fact['company_id'], fact['status']
        if fact.get('values'):
            value = Decimal(fact['values']['kgd_total_arrears'])
            dates = ', '.join(fact['values']['kgd_reporting_dates']) or 'date unavailable'
            evidence = [{'kind': 'observation', 'id': fact['observation']['observation_id'],
                         'source': fact['observation']['source'], 'url': fact['observation']['url'],
                         'observed_at': fact['observation']['observed_at']}]
            fresh = status in {'fresh', 'retained_fresh'}
            if status == 'fresh':
                checked += 1
            else:
                missing += 1
                retained += int(status == 'retained_fresh')
            limits = [] if fresh else ['This retained result does not establish current arrears.']
            if fact['latest_status'] != 'success':
                limits.append('The latest source attempt was unsuccessful; the last success is retained.')
            if value > 0:
                contribution = 20 if fresh else 0
                if fresh:
                    positive.append(pk)
                add('company_arrears', [pk], evidence,
                    [f'Company {pk} has a saved KGD aggregate arrears result of {value} KZT (reporting dates: {dates}).',
                     f'The retained KGD result for company {pk} reports {value} KZT in aggregate arrears; dates: {dates}.'],
                    contribution, dimension='company_financial', limits=limits)
            else:
                add('company_zero_arrears', [pk], evidence,
                    [f'KGD reported zero aggregate arrears for company {pk} (reporting dates: {dates}).',
                     f'The saved KGD aggregate arrears amount for company {pk} is zero; dates: {dates}.'],
                    dimension='company_financial', limits=limits)
        else:
            missing += 1
            add('company_check_unknown', [pk], fact.get('attempt_evidence', []),
                [f'Current company arrears are unknown for company {pk}: {status.replace("_", " ")}.',
                 f'No usable current arrears result is available for company {pk} ({status.replace("_", " ")}).'],
                dimension='coverage')
    winners = {}
    for finding in sorted(findings, key=lambda item: (-item['candidate_contribution'], item['id'])):
        if finding['dimension'] == 'company_financial':
            category = 'financial'
        elif finding['code'] in {'shared_owner', 'shared_director', 'mixed_person_roles'}:
            category = finding['code']
        elif finding['dimension'] == 'relationship':
            category = 'contacts'
        else:
            continue
        if finding['candidate_contribution'] and category not in winners:
            winners[category] = finding
    remaining = 50
    for category, finding in winners.items():
        points = finding['candidate_contribution'] if category == 'financial' else min(remaining, finding['candidate_contribution'])
        finding['contribution'] = points
        if category != 'financial':
            remaining -= points
    relationship_priority = 50 - remaining
    financial_priority = 20 if positive else 0
    contracts = inputs['contracts']
    total = sum((Decimal(item['amount']) for item in contracts), Decimal('0.00'))
    buyers = defaultdict(set)
    for item in contracts:
        if item['customer_bin']:
            buyers[item['customer_bin']].add(item['company_id'])
    shared_buyers = sum(len(companies) > 1 for companies in buyers.values())
    if contracts:
        add('stored_contract_summary', inputs['members'],
            [{'kind': 'contract_record', 'id': item['id'], 'url': item['source_url'],
              'quality': 'Stored contract record; source completeness unverified'} for item in contracts],
            [f'The saved company records contain {len(contracts)} contracts totalling {total} KZT. This is contract volume, not damage.',
             f'Available stored contracts total {total} KZT across {len(contracts)} records; this amount is not a loss estimate.'],
            dimension='procurement', limits=['Contracts alone do not establish coordinated bidding.'])
    metrics = {'review_priority': min(100, relationship_priority + financial_priority),
               'relationship_priority': relationship_priority, 'financial_priority': financial_priority,
               'link_strength': max(strengths, default=0), 'behavioural_risk': None,
               'behavioural_status': 'not_assessable', 'company_count': len(inputs['members']),
               'fresh_arrears_checks': checked, 'unknown_current_arrears': missing,
               'retained_recent_arrears_results': retained,
               'companies_with_fresh_arrears': sorted(positive),
               'score_interpretation': 'uncalibrated_review_priority',
               'stored_contract_count': len(contracts), 'stored_contract_amount': str(total),
               'shared_customer_count': shared_buyers,
               'score_categories': categories,
               'score_breakdown': [{'finding_id': item['id'], 'points': item['contribution']}
                                   for item in findings if item['contribution']]}
    findings.sort(key=lambda item: (-item['contribution'], item['id']))
    return findings, metrics, BASE_LIMITATIONS.copy()
