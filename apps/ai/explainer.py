"""Describe saved graph evidence; Phase 5 adds versioned analysis."""
from collections import defaultdict


def _format_company_list(names):
    return ' and '.join(f'«{name}»' for name in names)


def explain_cluster(cluster):
    snapshot = cluster.current_snapshot
    if snapshot is None:
        return 'No evidence graph has been published for this group. Recalculation is required.'
    names = {node['id']: node['name'] for node in snapshot.payload['nodes']}
    shared = defaultdict(list)
    for edge in snapshot.payload['links']:
        shared[(edge['target'], edge['type'])].append(edge)
    sentences = []
    for (_, kind), edges in sorted(shared.items()):
        if len({edge['company_id'] for edge in edges}) < 2:
            continue
        companies = _format_company_list(names[key] for key in sorted({edge['source'] for edge in edges}))
        value = edges[0]['value']
        if kind in {'director', 'owner'}:
            period = 'leadership periods require confirmation' if kind == 'director' else 'ownership periods require confirmation'
            if all(edge['valid_from'] and edge['valid_until'] for edge in edges):
                period = f'role intervals include the graph evaluation date {snapshot.as_of}'
            sentences.append(f'Available records list {value} as {kind} of companies {companies}; {period}.')
        else:
            label = {'address': 'address', 'email': 'contact email', 'phone': 'contact phone number'}[kind]
            sentences.append(f'Companies {companies} share the same {label} ({value}).')
        for limitation in sorted({text for edge in edges for text in edge['limitations']}):
            sentences.append(limitation)
    return (f'Saved graph version {snapshot.version} contains {len(snapshot.member_ids)} companies. '
            + (' '.join(sentences) if sentences else 'No shared links are confirmed in this saved version. ')
            + ' Group membership and the legacy matching score do not establish a violation. '
            'Company arrears are separate company facts and are not assigned to owners.')
