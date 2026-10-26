"""Shared subset and financial evaluator contracts."""
import copy
from datetime import datetime
import math


def require(value, code):
    if not value:
        raise ValueError(code)


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def validate_dataset(d):
    require(d.get('schema') == 'feature_selector.dataset.v1', 'DATASET_SCHEMA')
    require(d.get('scope') in ('synthetic', 'development'), 'DATASET_SCOPE')
    features = d['features']
    require(isinstance(features, list) and features and all(isinstance(c,str) and c for c in features)
            and len(features) == len(set(features)), 'FEATURES')
    groups = d['groups']
    require(groups and len({g['name'] for g in groups}) == len(groups), 'GROUP_NAMES')
    require(all(g['columns'] and g.get('extractor') for g in groups), 'EMPTY_GROUP')
    require(sorted(c for g in groups for c in g['columns']) == sorted(features), 'GROUP_PARTITION')
    require(all(d['blocks']) and sorted(c for block in d['blocks'] for c in block) == sorted(features), 'BLOCK_PARTITION')
    require(sha(d['support_hash']) and sha(d['scaler_hash']), 'SUPPORT_OR_SCALER_ID')
    require(isinstance(d['representation'], dict) and d['representation'], 'REPRESENTATION')
    s = d['splits']
    try:
        ts = [datetime.fromisoformat(x.replace('Z','+00:00')) for x in
              [*s['train'], *s['selection'], s['test_start']]]
        require(len(ts) == 5 and ts[0] < ts[1] <= ts[2] < ts[3] <= ts[4], 'TEMPORAL_SPLITS')
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError('TEMPORAL_SPLITS') from exc
    c = d['constraints']
    require(c.get('agent_state') == 'none' and c.get('scaling') == 'fixed_train'
            and c.get('clipping') is False and c.get('fit_scope') == 'train_only'
            and c.get('test_access') is False, 'OBSERVATION_AND_FIT_CONTRACT')
    return d


def subset_view(dataset, columns):
    validate_dataset(dataset)
    require(columns and len(columns) == len(set(columns)) and set(columns) <= set(dataset['features']), 'SUBSET')
    keep = set(columns)
    require(all(not keep.intersection(b) or set(b) <= keep for b in dataset['blocks']), 'PARTIAL_ENCODING_BLOCK')
    ordered = [c for c in dataset['features'] if c in keep]
    index = {c:i for i,c in enumerate(ordered)}
    groups = []
    for group in dataset['groups']:
        cols = [c for c in group['columns'] if c in keep]
        if cols:
            g = copy.deepcopy(group)
            g.update(columns=cols, indices=[index[c] for c in cols])
            groups.append(g)
    return dict(features=ordered, groups=groups)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_score(result):
    require(type(result.get('eligible')) is bool, 'EVALUATION_SCORE')
    measured = finite(result.get('score')) and finite(result.get('gap'))
    undefined = result.get('score') is None and result.get('gap') is None and result['eligible'] is False
    require(measured or undefined, 'EVALUATION_SCORE')
    return result
