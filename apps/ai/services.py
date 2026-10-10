"""Prepare immutable analysis from saved inputs and publish exact-version text."""
from datetime import date
from decimal import Decimal
import json

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.graph.evidence import digest, source_reference
from apps.graph.models import RiskCluster
from apps.contracts.models import Contract
from apps.ingestion.models import CompanyKgdState
from apps.ingestion.parsers.kgd import DEBT_SOURCE, AMOUNT_FIELDS, validate_facts
from .models import AnalysisSnapshot, AnalysisState, AnalysisTarget, Explanation
from .rules import evaluate, RULES_VERSION
from .presentation import build_document, document_text

TEMPLATE_VERSION = 'explanation-template-5.2'


def plain(value):
    return json.loads(json.dumps(value, default=str))


def collect_inputs(snapshot, as_of=None):
    as_of = as_of or timezone.localdate()
    nodes = {node['company_id']: node for node in snapshot.payload['nodes'] if node['kind'] == 'company'}
    states = {state.supplier_id: state for state in CompanyKgdState.objects.filter(
        supplier_id__in=snapshot.member_ids, source=DEBT_SOURCE).select_related(
        'latest_observation', 'last_successful_observation')}
    checks = []
    for pk in sorted(snapshot.member_ids):
        state = states.get(pk)
        fact = {'company_id': pk, 'status': 'not_checked', 'latest_status': 'not_checked'}
        if state:
            latest, good = state.latest_observation, state.last_successful_observation
            fact['latest_status'] = latest.status
            fact['status'] = latest.status if latest.status != 'success' else 'unavailable'
            fact['attempt_evidence'] = [{'kind': 'observation', 'id': latest.pk, 'source': latest.source}]
            if good and good.status == 'success' and good.supplier_id == pk and good.source == DEBT_SOURCE:
                try:
                    values = plain(validate_facts(DEBT_SOURCE, good.normalized_values, nodes[pk]['bin']))
                    for field in AMOUNT_FIELDS.values():
                        values[field] = format(Decimal(values[field]), '.2f')
                    dates = [date.fromisoformat(value) for value in values['kgd_reporting_dates']]
                    if any(value > as_of for value in dates):
                        raise ValueError('future_reporting_date')
                    fact.update(values=values, observation=source_reference(good))
                    fact['status'] = ('undated' if not dates else 'stale' if
                        (as_of - min(dates)).days > settings.KGD_RESULT_MAX_AGE_DAYS else 'fresh')
                    if fact['status'] == 'fresh' and latest.status != 'success':
                        fact['status'] = 'retained_fresh'
                except (ValueError, TypeError, KeyError):
                    fact['status'] = 'invalid'
        checks.append(fact)
    contracts = [{'id': contract.pk, 'company_id': contract.supplier_id,
                  'contract_number': contract.contract_number, 'customer_bin': contract.customer_bin,
                  'date': str(contract.contract_date), 'amount': str(contract.amount),
                  'source_url': contract.goszakup_url or ''}
                 for contract in Contract.objects.filter(supplier_id__in=snapshot.member_ids).order_by('pk')]
    return {'members': sorted(snapshot.member_ids), 'graph_hash': snapshot.graph_hash,
            'graph_as_of': str(snapshot.as_of), 'graph_state': snapshot.state,
            'graph': snapshot.payload, 'company_checks': checks, 'contracts': contracts}


def input_hash(inputs):
    # Retrieval-only changes retain the original published observation references.
    checks = [{key: value for key, value in item.items()
               if key not in {'observation', 'attempt_evidence'}} for item in inputs['company_checks']]
    return digest({'rules': RULES_VERSION, 'graph_hash': inputs['graph_hash'],
                   'graph_state': inputs['graph_state'], 'graph_as_of': inputs['graph_as_of'],
                   'company_checks': checks, 'contracts': inputs['contracts']})


def explanation_content(analysis, plan=None):
    document = build_document(analysis, plan)
    return {'text': document_text(document), 'presentation': {**(plan or {}), 'document': document}}


def template_for(analysis):
    key = digest({'analysis': analysis.pk, 'hash': analysis.analysis_hash, 'language': 'en',
                  'template': TEMPLATE_VERSION, 'provider': 'template'})
    return Explanation.objects.get_or_create(reuse_key=key, defaults={
        'analysis': analysis, 'provider': 'template', 'prompt_version': TEMPLATE_VERSION,
        'status': 'ready', **explanation_content(analysis)})[0]


@transaction.atomic
def prepare_analysis(cluster_id, *, as_of=None, expected_graph_id=None, expected_input_hash=None):
    cluster = RiskCluster.objects.select_for_update(of=('self',)).select_related('current_snapshot').get(pk=cluster_id)
    snapshot = cluster.current_snapshot
    if not snapshot or snapshot.state != 'active':
        raise ValueError('active_graph_required')
    if expected_graph_id is not None and snapshot.pk != expected_graph_id:
        raise ValueError('analysis_input_superseded')
    as_of = as_of or timezone.localdate()
    inputs = collect_inputs(snapshot, as_of)
    signature = input_hash(inputs)
    if expected_input_hash is not None and signature != expected_input_hash:
        raise ValueError('analysis_input_superseded')
    findings, metrics, limits = evaluate(inputs)
    # Finding references contain observation IDs; their meaning is hashed separately.
    result_hash = digest({'input_hash': signature, 'metrics': metrics, 'rules': RULES_VERSION})
    analysis = AnalysisSnapshot.objects.filter(graph_snapshot=snapshot, analysis_hash=result_hash).first()
    created = analysis is None
    if created:
        version = (cluster.analyses.aggregate(value=Max('version'))['value'] or 0) + 1
        analysis = AnalysisSnapshot.objects.create(cluster=cluster, graph_snapshot=snapshot, version=version,
            analysis_hash=result_hash, input_hash=signature, rules_version=RULES_VERSION, as_of=as_of,
            inputs=plain(inputs), findings=findings, metrics=metrics, limitations=limits)
    template = template_for(analysis)
    state = AnalysisState.objects.filter(cluster=cluster).first()
    if not state:
        AnalysisState.objects.create(cluster=cluster, analysis=analysis, explanation=template)
    elif state.analysis_id != analysis.pk:
        state.analysis, state.explanation = analysis, template
        state.save(update_fields=['analysis', 'explanation', 'updated_at'])
    return analysis, created


@transaction.atomic
def publish_explanation(analysis, explanation, expected_job_id=None):
    if explanation.analysis_id != analysis.pk:
        raise ValueError('explanation_analysis_mismatch')
    cluster = RiskCluster.objects.select_for_update(of=('self',)).select_related('current_snapshot').get(pk=analysis.cluster_id)
    if cluster.current_snapshot_id != analysis.graph_snapshot_id:
        return False
    if expected_job_id is not None and not AnalysisTarget.objects.filter(cluster=cluster, job_id=expected_job_id).exists():
        return False
    if input_hash(collect_inputs(cluster.current_snapshot)) != analysis.input_hash:
        return False
    state = AnalysisState.objects.select_for_update().filter(cluster=cluster).first()
    if not state or state.analysis_id != analysis.pk:
        return False
    if state.explanation_id != explanation.pk:
        state.explanation = explanation
        state.save(update_fields=['explanation', 'updated_at'])
    return True


def saved_analysis(cluster, snapshot):
    if not snapshot:
        return None, None, False
    state = AnalysisState.objects.filter(cluster=cluster, analysis__graph_snapshot=snapshot).select_related(
        'analysis__graph_snapshot', 'explanation').first()
    if state:
        analysis, explanation = state.analysis, state.explanation
    else:
        analysis = snapshot.analyses.select_related('graph_snapshot').first()
        explanation = historical_explanation(analysis) if analysis else None
    stale = bool(analysis and snapshot.pk == cluster.current_snapshot_id
                 and input_hash(collect_inputs(snapshot)) != analysis.input_hash)
    return analysis, explanation, stale


def historical_explanation(analysis):
    """Read the last published text, excluding retained but superseded output."""
    published = analysis.explanations.filter(analysisjob__status__in=['succeeded', 'fallback']).order_by(
        '-analysisjob__finished_at', '-analysisjob__pk').first()
    return published or analysis.explanations.filter(provider='template').first()


@transaction.atomic
def refresh_graph_analysis(*, as_of=None, supplier_ids=None, publication_guard=None):
    """Authorised graph work also prepares affected templates; never call an LLM."""
    from apps.graph.services import rebuild_clusters
    summary = rebuild_clusters(as_of=as_of, supplier_ids=supplier_ids, publication_guard=publication_guard)
    summary['analysis_versions_created'] = 0
    for result in summary['results']:
        if result['state'] != 'active':
            continue
        cluster_id = RiskCluster.objects.only('pk').get(uuid=result['cluster_uuid']).pk
        analysis, created = prepare_analysis(cluster_id, as_of=as_of)
        summary['analysis_versions_created'] += int(created)
        result.update(analysis_version=analysis.version, analysis_hash=analysis.analysis_hash)
    if publication_guard:
        publication_guard()
    return summary
