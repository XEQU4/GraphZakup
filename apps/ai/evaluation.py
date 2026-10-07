"""Compare score estimates against independent analyst review-priority labels."""
from math import sqrt


def compare_scores(rows):
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError('Provide at least two independently labelled holdout cases.')
    identifiers = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'case_id', 'label_priority', 'rule_score', 'model_score'}:
            raise ValueError('Invalid evaluation fields.')
        if not isinstance(row['case_id'], str) or not row['case_id'] or row['case_id'] in identifiers:
            raise ValueError('Case identifiers must be unique.')
        identifiers.add(row['case_id'])
        if any(type(row[key]) is not int or not 0 <= row[key] <= 100
               for key in ('label_priority', 'rule_score', 'model_score')):
            raise ValueError('Scores and labels must be integers from zero to 100.')
    metrics = {}
    for key in ('rule_score', 'model_score'):
        differences = [row[key] - row['label_priority'] for row in rows]
        metrics[key] = {'mae': sum(abs(value) for value in differences) / len(rows),
                        'rmse': sqrt(sum(value * value for value in differences) / len(rows)),
                        'overestimation_cases': sum(value > 0 for value in differences)}
    return {'cases': len(rows), 'metrics': metrics,
            'model_lower_mae': metrics['model_score']['mae'] < metrics['rule_score']['mae'],
            'promotion_authorised': False,
            'limitation': 'Lower error on a supplied sample alone does not establish generalisation or calibrated risk.'}
