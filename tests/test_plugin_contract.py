import copy
import importlib.metadata as md
import json

import pytest

from feature_selector.config import merge, prepare
from feature_selector.contracts import validate_dataset, subset_view
from feature_selector.plugins import resolve
from feature_selector.search import FloatingBackward


def dataset():
    return dict(schema='feature_selector.dataset.v1', scope='synthetic',
        features=['a', 'b', 'c'], groups=[dict(name='pair', columns=['a','b'], extractor='causal_conv'),
                                       dict(name='single', columns=['c'], extractor='pointwise')],
        blocks=[['a'], ['b'], ['c']], support_hash='a'*64, scaler_hash='b'*64,
        representation=dict(id='test'), splits=dict(train=['2020-01-01','2023-07-01'],
             selection=['2023-07-01','2024-01-01'], test_start='2025-01-01'),
        constraints=dict(agent_state='none', scaling='fixed_train', clipping=False,
                         fit_scope='train_only', test_access=False))


def test_precedence_and_no_input_mutation():
    a={'p': {'x':1, 'y':2}}
    assert merge(a, {'p':{'x':3}}, {'p':{'x':4}})=={'p':{'x':4,'y':2}}
    assert a['p']['x']==1


def test_structural_pruning_removes_empty_branch_without_reordering():
    d=dataset();validate_dataset(d)
    s=subset_view(d,['b'])
    assert s['features']==['b']
    assert s['groups']==[dict(name='pair', columns=['b'], indices=[0], extractor='causal_conv')]
    assert d['groups'][0]['columns']==['a','b']
    assert len(subset_view(d,['a','c'])['groups'])==2


@pytest.mark.parametrize('change', [dict(agent_state='full'),dict(scaling='rolling_z'),
                                  dict(clipping=True), dict(test_access=True)])
def test_unapproved_transform_rejected(change):
    d=dataset();d['constraints'].update(change)
    with pytest.raises(ValueError):validate_dataset(d)


def test_overlapping_splits_and_duplicate_groups_rejected():
    d=dataset();d['splits']['selection'][0]='2023-01-01'
    with pytest.raises(ValueError):validate_dataset(d)
    d=dataset();d['groups'][1]['columns']=['b','c']
    with pytest.raises(ValueError):validate_dataset(d)


def test_coherent_blocks_not_partially_removed():
    d=dataset();d['blocks']=[['a','b'],['c']]
    with pytest.raises(ValueError):subset_view(d,['a'])


def test_backward_search_records_best_size_and_does_not_refit():
    # ABC -> BC -> C, then AC improves the recorded best pair BC.
    scores={('a','b','c'):0,('b','c'):4,('a','c'):3,('a','b'):1,
            ('c',):5,('b',):2,('a',):1}
    calls=[]
    def evaluate(cols):
        calls.append(tuple(cols))
        return dict(score=scores[tuple(cols)],eligible=True,gap=0)
    result=FloatingBackward().select(dataset(), evaluate, dict(min_features=1,max_evaluations=30,tolerance=0))
    assert result['selected']==['c']
    assert len(calls)==len(set(calls))
    assert result['termination']=='MIN_SIZE'


def test_actual_floating_reversal():
    d=dataset();d['features']=['a','b','c','d'];d['blocks']=[[x] for x in d['features']]
    d['groups']=[dict(name='all',columns=d['features'],extractor='causal_conv')]
    scores={('a','b','c','d'):0,('a','b','c'):8,('a','b','d'):6,('a','c','d'):5,('b','c','d'):4,
            ('a','b'):9,('a','c'):7,('b','c'):6,('a',):10,('b',):1,('a','d'):12,('c',):0,('d',):0}
    result=FloatingBackward().select(d,lambda c:dict(score=scores.get(tuple(c),0),eligible=True,gap=0),
                                     dict(min_features=1,max_evaluations=50,tolerance=0))
    assert any(e['operation']=='reinclude' and e['features']==['a','d'] for e in result['trace'])
    assert result['selected']==['a','d']


def test_budget_and_no_eligible_are_explicit():
    r=FloatingBackward().select(dataset(),lambda c:dict(score=0,eligible=False,gap=0),
                                dict(min_features=1,max_evaluations=2,tolerance=0))
    assert r['termination']=='BUDGET'
    assert r['selected'] is None


def test_undefined_scores_remain_undefined():
    r=FloatingBackward().select(dataset(),lambda c:dict(score=None,eligible=False,gap=None),
                                dict(min_features=1,max_evaluations=20,tolerance=0))
    assert r['selected'] is None
    assert all(item['score'] is None for item in r['results'])


def test_ambiguous_external_plugin_rejected(monkeypatch):
    eps=[md.EntryPoint(name='x',value='fake:One',group='feature_selector.selectors'),
         md.EntryPoint(name='x',value='fake:Two',group='feature_selector.selectors')]
    monkeypatch.setattr(md,'entry_points',lambda **kw:eps)
    with pytest.raises(ValueError,match='AMBIGUOUS'):resolve('selectors','x')
