import copy
from feature_selector.search import TwoPassGreedy
from test_plugin_contract import dataset


def test_two_complete_passes_and_current_reference():
    d = dataset(); d['features'] = list('abcd')
    d['groups'] = [dict(name='all',columns=d['features'],extractor='causal_conv')]
    d['blocks'] = [[c] for c in d['features']]
    scores = {'abcd':-10, 'bcd':-9, 'cd':-8, 'd':-12, 'c':-11, 'acd':-7, 'abc':-6}
    calls=[]; snapshots=[]
    def evaluate(c):
        key=''.join(c); calls.append(key)
        return dict(score=scores[key], gap=0, eligible=True)
    r=TwoPassGreedy().select(d,evaluate,dict(tolerance=0,min_features=1),
                             progress=lambda s:snapshots.append(copy.deepcopy(s)))
    assert calls == ['abcd','bcd','cd','d','c','acd']
    # Adding b after a would return the original, already measured full set.
    assert r['selected'] == list('acd')
    assert r['counts'] == dict(initial=4,after_deletion=2,final=3)
    assert [t['accepted'] for t in r['trace']] == [True,True,False,False,True,False]
    assert [t['pass'] for t in r['trace']] == [1,1,1,1,2,2]
    assert snapshots[-1]['counts']==r['counts']
    assert r['evaluations']==6 and r['evaluation_bound']==9


def test_equal_or_within_tolerance_does_not_remove():
    calls=[]
    def evaluate(c):
        calls.append(c)
        return dict(score=1 if len(c)==3 else 1.001, gap=0, eligible=True)
    r=TwoPassGreedy().select(dataset(),evaluate,dict(tolerance=.01,min_features=1))
    assert r['selected']==list('abc') and r['counts']['after_deletion']==3
    assert len(calls)==4 and all(t['pass']==1 for t in r['trace'])


def test_atomic_blocks_and_minimum():
    d=dataset(); d['blocks']=[['a','b'],['c']]
    r=TwoPassGreedy().select(d,lambda c:dict(score=-len(c),gap=0,eligible=True),{})
    assert r['selected']==['c']
    assert r['counts']==dict(initial=3,after_deletion=1,final=1)
    assert all(set(x['features']) in (set('abc'),set('c')) for x in r['results'])


def test_ineligible_candidate_cannot_win_and_invalid_baseline_stops():
    d=dataset()
    r=TwoPassGreedy().select(d,lambda c:dict(score=100-len(c),gap=0,eligible=len(c)==3),{})
    assert r['selected']==list('abc')
    r=TwoPassGreedy().select(d,lambda c:dict(score=None,gap=None,eligible=False),{})
    assert r['selected'] is None and r['termination']=='NO_ELIGIBLE_BASELINE'
    assert r['evaluations']==1
