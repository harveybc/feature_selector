import sys
from pathlib import Path
import json
import re
import types

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from finalize_core_selection import choose_subset


def candidates():
    return [dict(method='MRMR', k=12, target_id=t, members=['a', 'b', 'c'] + extras())
            for t in ('RETURN_4H', 'RETURN_12H', 'ABS_RETURN_12H')]


def extras():
    return ['x'+str(i) for i in range(9)]


def variables():
    return ['a', 'b', 'c', 'd'] + extras()


def clusters():
    return [dict(members=['a', 'b'], representative='a'),
            dict(members=['c'], representative='c'), dict(members=['d'], representative='d')] + [
                dict(members=[x], representative=x) for x in extras()]


def test_fixed_union_and_existing_redundancy_keep_one_representative():
    names, reasons = choose_subset(candidates(), variables(), clusters())
    assert names == ['a', 'c'] + extras()
    assert reasons['b'].startswith('REDUNDANT_WITH:a')
    assert reasons['d'].startswith('OUTSIDE_FILTER')


@pytest.mark.parametrize('fault', ['target_missing', 'unknown', 'duplicate', 'uncovered', 'repeated_member'])
def test_missing_or_inconsistent_evidence_never_becomes_selected(fault):
    values, groups = candidates(), clusters()
    if fault == 'target_missing': values.pop()
    if fault == 'unknown': values[0]['members'].append('future_macro')
    if fault == 'duplicate': groups.append(groups[0])
    if fault == 'uncovered': groups.pop()
    if fault == 'repeated_member': values[0]['members'][-1] = values[0]['members'][0]
    with pytest.raises(ValueError):
        choose_subset(values, variables(), groups)


def test_representative_must_come_from_actual_selected_intersection():
    values = candidates()
    for v in values:
        v['members'] = ['b', 'c', 'd'] + extras()
    selected, _ = choose_subset(values, variables(), clusters())
    assert selected == ['b', 'c', 'd'] + extras()


@pytest.mark.parametrize('tamper', [False, True])
def test_native_readback_pages_with_terminal_limit_and_compares_actual_values(tmp_path, monkeypatch, tamper):
    from finalize_core_selection import publish
    run, output = tmp_path/'run', tmp_path/'output'
    (run/'phase1/finalizer').mkdir(parents=True)
    output.mkdir()
    rows = [dict(row_sha256=f'{i:064x}', metric_value=i) for i in range(502)]
    def put(path, body): path.write_text(json.dumps(body))
    put(run/'phase1/finalizer/result.json', {'envelope': {'run': {'run_id': 'profiles'}, 'rows': {'profiles': rows}}})
    put(output/'DECISIONS_ENVELOPE.json', {'run': {'run_id': 'decisions'}, 'rows': {'profiles': []}})
    put(output/'SELECTION.json', {'selected': ['a']})
    put(run/'REPORT.json', {'identity': 'pairs'})
    stored = {}
    class Remote:
        def __init__(self, *a, **kw): pass
        def _call(self, method, endpoint, envelope):
            stored[envelope['run']['run_id']] = envelope['rows']['profiles']
        def query(self, sql):
            assert re.search(r'LIMIT 500$', sql) and 'OFFSET' not in sql
            rid = re.search(r"run_id = '([^']+)'", sql).group(1)
            cursor = re.search(r"row_sha256 > '([^']+)'", sql)
            got = [dict(r, run_id=rid) for r in stored[rid]
                   if cursor is None or r['row_sha256'] > cursor.group(1)][:500]
            if tamper and got: got[0]['metric_value'] = -999
            return got
        def submit_rows(self, rid, table, values): self.pairs = values
        def read_run(self, rid, table): return self.pairs
    class Local:
        def __init__(self, *a, **kw): pass
        def read_run(self, rid, table): return [{'metric': 'rho', 'value': .5}]
        def close(self): pass
    module = types.ModuleType('tools.fs_phase23_warehouse')
    module.Warehouse, module.ServiceWarehouse, module.FACT_TABLES = Local, Remote, ['pairs']
    store = types.ModuleType('predictor_olap_store.feature_selection_store')
    store.FAMILY_TABLES = {'profiles': 'profile_table'}
    monkeypatch.setitem(sys.modules, 'tools.fs_phase23_warehouse', module)
    monkeypatch.setitem(sys.modules, 'predictor_olap_store.feature_selection_store', store)
    if tamper:
        with pytest.raises(ValueError, match='stored values differ'):
            publish(run, output, 'http://localhost', 'UNUSED')
        assert not (output/'PUBLICATION.json').exists()
    else:
        result = publish(run, output, 'http://localhost', 'UNUSED')
        assert result['phase1']['profiles']['profiles']['count'] == 502
        assert result['pending'] == result['mismatch'] == 0
