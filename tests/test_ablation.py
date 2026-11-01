import pytest

from feature_selector.ablation import FixedAblation
from test_plugin_contract import dataset


def test_order_and_whole_branch():
    d = dataset()
    arms = FixedAblation().plan(d, {'arms': [dict(name='branch', drop_group='pair')]})
    assert arms[0]['features'] == ['a', 'b', 'c']
    assert arms[1]['features'] == ['c']
    assert [g['name'] for g in arms[1]['groups']] == ['single']
    assert d['features'] == ['a', 'b', 'c']


def test_partial_atomic_block_rejected():
    d = dataset(); d['blocks'] = [['a', 'b'], ['c']]
    with pytest.raises(ValueError):
        FixedAblation().plan(d, {'arms': [dict(name='partial', drop=['a'])]})


@pytest.mark.parametrize('arms', [
    [dict(name='../x', drop=['a'])], [dict(name='full', drop=['a'])],
    [dict(name='x', drop=['z'])], [dict(name='x', drop=['a', 'b', 'c'])],
    [dict(name='x', drop_group='missing')],
    [dict(name='x', drop=['a']), dict(name='y', drop=['a'])],
])
def test_malformed_or_duplicate_arms_rejected(arms):
    with pytest.raises(ValueError): FixedAblation().plan(dataset(), {'arms': arms})


def test_diagnostic_never_promotes_a_winner():
    r = FixedAblation().select(dataset(), lambda c: dict(eligible=True, score=1, gap=0),
                              {'arms': [dict(name='single', drop=['a'])]})
    assert r['selected'] is None and r['evaluations'] == 2
