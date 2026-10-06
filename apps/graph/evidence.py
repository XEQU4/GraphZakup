"""One indexed evidence representation for grouping, saved graphs and consumers."""
from collections import defaultdict
import hashlib
import json
from urllib.parse import urlsplit

from django.urls import reverse
from django.utils import timezone
from apps.owners.querysets import is_confirmed_role

ALGORITHM_VERSION = 'evidence-graph-4.0'
COMMON_CONTACT_LIMIT = 20
CONTACT_TYPES = ('address', 'phone', 'email')
EXCLUDED_EMAILS = {'info@adata.kz', 'support@adata.kz'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def contact_value(kind, value):
    value = value.strip() if isinstance(value, str) else ''
    return value.lower() if kind == 'email' else value


def applicable(role, as_of):
    return role.is_current and (role.start_date is None or role.start_date <= as_of) and (
        role.end_date is None or role.end_date > as_of)


def confirmed_owner(role):
    if not (role.identity_status == 'verified' and role.person_identity_id and role.source_observation_id):
        return False
    person, observation = role.person_identity, role.source_observation
    if not (person.is_verified and person.iin and person.owner_id == role.owner_id
            and observation.supplier_id == role.supplier_id and observation.status == 'success'
            and observation.source == role.source):
        return False
    values = observation.normalized_values
    if not isinstance(values, dict) or not isinstance(values.get('owners'), list):
        return False
    return any(item.get('iin_verified') is True and item.get('iin') == person.iin
               for item in values['owners'] if isinstance(item, dict))


def source_reference(observation=None, *, supplier=None):
    if observation is None:
        return {'source': 'project_company_record', 'record_id': supplier.pk,
                'url': reverse('companies:detail', args=[supplier.pk]),
                'quality': 'External provenance unconfirmed', 'observed_at': None}
    url = observation.source_url
    parsed = urlsplit(url)
    # Evidence links never expose query credentials or executable URL schemes.
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        url = ''
    return {'source': observation.source, 'observation_id': observation.pk, 'url': url,
            'quality': 'Source observation', 'observed_at': observation.observed_at.isoformat()}


def semantic_edge(edge):
    value = {key: item for key, item in edge.items() if key != 'evidence'}
    value['evidence'] = [{key: item for key, item in ref.items()
                          if key not in {'observation_id', 'observed_at'}} for ref in edge['evidence']]
    return value


class EvidenceIndex:
    """O(companies + roles + features); dense contacts use shared feature nodes."""
    def __init__(self, suppliers, as_of=None):
        self.as_of = as_of or timezone.localdate()
        self.suppliers = {supplier.pk: supplier for supplier in suppliers}
        self.nodes, self.edges = {}, {}
        self.company_edges = defaultdict(list)
        self.features = defaultdict(set)
        self.feature_types = {}
        self.company_features = defaultdict(set)
        for supplier in self.suppliers.values():
            company = f'company:{supplier.pk}'
            self.nodes[company] = {'id': company, 'kind': 'company', 'name': supplier.name,
                                   'bin': supplier.bin, 'company_id': supplier.pk,
                                   'url': reverse('companies:detail', args=[supplier.pk])}
            selected = {fact.field: fact.observation for fact in supplier.selected_facts.all()}
            for kind in CONTACT_TYPES:
                value = contact_value(kind, getattr(supplier, kind))
                if not value or (kind == 'email' and value in EXCLUDED_EMAILS):
                    continue
                target = f'contact:{kind}:{digest(value)}'
                observation = selected.get(kind)
                if observation and (observation.status != 'success' or observation.supplier_id != supplier.pk
                                    or contact_value(kind, observation.normalized_values.get(kind)) != value):
                    observation = None
                self.nodes[target] = {'id': target, 'kind': 'contact', 'name': value, 'contact_type': kind}
                self._add(supplier, company, target, kind, value, [source_reference(observation, supplier=supplier)],
                          confidence='0.250', limitations=['A shared contact alone does not establish affiliation or a violation.'])
            for kind, roles in (('director', supplier.directorships.all()), ('owner', supplier.ownerships.all())):
                for role in roles:
                    if not applicable(role, self.as_of) or not (is_confirmed_role(role) if kind == 'director' else confirmed_owner(role)):
                        continue
                    person = role.person_identity
                    target = f'person:{person.pk}'
                    self.nodes[target] = {'id': target, 'kind': 'person', 'name': person.full_name,
                                          'identity_verified': True}
                    self._add(supplier, company, target, kind, person.full_name,
                              [source_reference(role.source_observation)], confidence='0.950',
                              valid_from=role.start_date, valid_until=role.end_date,
                              limitations=[] if role.start_date is not None and role.end_date is not None else
                              ['Unknown legal period boundaries require confirmation.'])
        for edge in self.edges.values():
            frequency = len(self.features[edge['target']])
            edge['common_contact'] = edge['type'] in CONTACT_TYPES and frequency > COMMON_CONTACT_LIMIT
            if edge['common_contact']:
                edge['confidence'] = '0.100'
                edge['limitations'].append('High-frequency contact excluded from group formation.')

    def _add(self, supplier, source, target, kind, value, evidence, *, confidence, valid_from=None,
             valid_until=None, limitations):
        key = digest([source, target, kind])
        self.edges[key] = {'id': key, 'source': source, 'target': target, 'type': kind, 'value': value,
                           'company_id': supplier.pk, 'confidence': confidence,
                           'valid_from': str(valid_from) if valid_from else None,
                           'valid_until': str(valid_until) if valid_until else None,
                           'temporal_status': 'Known interval' if valid_from and valid_until else 'Unknown interval bounds',
                           'evidence': evidence, 'limitations': limitations}
        if key not in self.company_edges[supplier.pk]:
            self.company_edges[supplier.pk].append(key)
        self.features[target].add(supplier.pk)
        self.feature_types[target] = self.nodes[target].get('contact_type', 'person')
        self.company_features[supplier.pk].add(target)

    def components(self):
        parent = {pk: pk for pk in self.suppliers}

        def root(pk):
            while parent[pk] != pk:
                parent[pk] = parent[parent[pk]]
                pk = parent[pk]
            return pk

        for key, members in self.features.items():
            if self.feature_types[key] in CONTACT_TYPES and len(members) > COMMON_CONTACT_LIMIT:
                continue
            members = sorted(members)
            for member in members[1:]:
                parent[root(member)] = root(members[0])
        groups = defaultdict(list)
        for pk in sorted(parent):
            groups[root(pk)].append(self.suppliers[pk])
        return sorted((group for group in groups.values() if len(group) > 1), key=lambda group: tuple(s.pk for s in group))

    def graph(self, members):
        members = set(members)
        edges = [self.edges[key] for pk in sorted(members) for key in self.company_edges[pk]]
        # A private contact of one company contributes no relational evidence.
        counts = defaultdict(set)
        for edge in edges:
            counts[edge['target']].add(edge['company_id'])
        edges = [edge for edge in edges if self.nodes[edge['target']]['kind'] == 'person'
                 or len(counts[edge['target']]) > 1]
        keys = {f'company:{pk}' for pk in members}
        keys.update(edge['target'] for edge in edges)
        return {'nodes': [self.nodes[key] for key in sorted(keys)],
                'links': sorted(edges, key=lambda edge: edge['id'])}


def graph_hash(payload, state='active'):
    return digest({'algorithm': ALGORITHM_VERSION, 'state': state, 'nodes': payload['nodes'],
                   'links': [semantic_edge(edge) for edge in payload['links']]})
