"""Seal a TRAIN-only filter-selected subset and publish existing native metric tables."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from rebuild_contract import read_json, require, validate
from selection_demo import write_json
from selection_rebuild import bootstrap, immutable


TARGETS = ('RETURN_4H', 'RETURN_12H', 'ABS_RETURN_12H')
FLAGS = dict(scope='SELECTED_ADMITTED_POPULATION', feature_selection_complete=True,
             selection_complete='WITHIN_DECLARED_ADMITTED_POPULATION', full_inventory_complete=False)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def digest(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def choose_subset(candidates, variables, clusters):
    choices = [c for c in candidates if c['method'] == 'MRMR' and c['k'] == 12]
    require(len(choices) == len(TARGETS) and {c['target_id'] for c in choices} == set(TARGETS),
            'MRMR k12 evidence missing or duplicated')
    require(all(isinstance(c['members'], list) and len(c['members']) == 12
                and len(set(c['members'])) == 12 for c in choices),
            'MRMR k12 requires twelve unique actual members')
    chosen = set().union(*(set(c['members']) for c in choices))
    require(chosen and chosen <= set(variables), 'unknown or empty selected candidate')
    seen, final, reasons = set(), set(), {v: 'OUTSIDE_FILTER_NOT_PROOF_OF_IRRELEVANCE' for v in variables}
    for cluster in clusters:
        members = cluster['members']
        require(members and not seen.intersection(members), 'overlapping redundancy clusters')
        seen.update(members)
        available = set(members) & chosen
        if not available:
            continue
        keep = cluster['representative'] if cluster['representative'] in available else sorted(available)[0]
        final.add(keep)
        for v in available:
            reasons[v] = 'SELECTED_TRAIN_ONLY_FILTER' if v == keep else 'REDUNDANT_WITH:' + keep
    require(seen == set(variables), 'redundancy evidence does not cover declared candidates')
    require(final, 'selection is empty')
    return [v for v in variables if v in final], reasons


def closure(path, field):
    doc = read_json(path)
    require(doc.get(field) == digest({k:v for k,v in doc.items() if k != field}), 'closure digest differs')
    return doc


def seal(bundle, run, output):
    import pandas as pd
    from tools.fs_phase23_warehouse import Warehouse
    from predictor_duckdb_store.provider import PredictorDuckdbStore

    spec = validate(bundle/'REBUILD_INPUT.json', read_json(bundle/'REBUILD_CONFIG.json'))
    transport = read_json(bundle/'TRANSPORT_VERIFICATION.json')
    require(transport.get('state') == 'VERIFIED'
            and transport['train_bundle_sha256'] == sha(bundle/'REBUILD_INPUT.json')
            and transport['preparation_binding_sha256'] == sha(bundle/'BINDING.json')
            and transport['prepared_candidates_sha256'] == sha(bundle/'candidates_train_validation.parquet'),
            'candidate transport differs from verified source/recipe')
    require(read_json(run/'BINDING.json')['input_sha256'] == sha(bundle/'REBUILD_INPUT.json'), 'wrong selector population')
    report = read_json(run/'REPORT.json')
    require(report['state'] == 'PROFILE_FILTERS_COMPLETE', 'profiles/filters not complete')
    p2 = closure(run/'phase23/PHASE_2_COMPLETE.json', 'closure_sha256')
    p3 = closure(run/'phase23/PHASE_3_FILTER_COMPLETE.json', 'closure_sha256')
    candidates = read_json(run/'phase23/CANDIDATES_FOR_VALIDATION.json')
    require(candidates['phase3_closure_sha256'] == p3['closure_sha256']
            and p3['phase2_closure_sha256'] == p2['closure_sha256'], 'closure chain differs')
    wh = Warehouse(run/'phase23.duckdb', read_only=True)
    try:
        groups = wh.read_run(report['identity'], 'feature_redundancy_clusters')
    finally:
        wh.close()
    variables = [v['feature_id'] for v in spec['population']['features']]
    selected, reasons = choose_subset(candidates['candidates'], variables, groups)
    output.mkdir(parents=True, exist_ok=True)
    evidence = {name:sha(run/name) for name in ('BINDING.json', 'REPORT.json',
        'phase1/PHASE_1_COMPLETE.json', 'phase23/PHASE_2_COMPLETE.json',
        'phase23/PHASE_3_FILTER_COMPLETE.json', 'phase23/CANDIDATES_FOR_VALIDATION.json')}
    population = sha(bundle/'REBUILD_INPUT.json')
    selection = dict(schema='selected_rl_selection.v1', **FLAGS,
        feature_columns=selected, candidate_columns=variables, population_sha256=population,
        causal_transforms_verified=True, validation_used_for_selection=False,
        causal_effects_identified=False, causal_evidence_state='NOT_COMPUTED_NO_CAUSAL_REJECTION',
        fit_period_start='2020-01-01T00:00:00+00:00', fit_period_end='2024-01-01T00:00:00+00:00',
        availability_column='SELECTED_AVAILABLE_AT', availability_semantics='row_max_selected_available_at',
        normalization=dict(mode='rolling_zscore', window_bars=256, fit_scope='PAST_ONLY', binary_columns=[]),
        policy='MRMR_K12_UNION_RETURN4_RETURN12_ABSRETURN12_THEN_EXISTING_SPEARMAN_CLUSTERS',
        predictive_winner=False, reasons=reasons, evidence=evidence, sealer_sha256=sha(__file__),
        derivation_admission_sha256=sha(bundle/'DERIVED_ADMISSION.json'))
    selection['candidate_transport_verification_sha256'] = sha(bundle/'TRANSPORT_VERIFICATION.json')
    immutable(output/'SELECTION.json', selection)
    pin = sha(output/'SELECTION.json')
    source_admission = read_json(bundle/'SOURCE_ADMISSION.json')
    for source_name, dest_name in [('SOURCE_ADMISSION.json','SOURCE_ADMISSION.json'),
                                   ('SOURCE_CLOSURE_INTERVALS.json','closures.json'),
                                   ('DERIVED_ADMISSION.json','DERIVED_ADMISSION.json')]:
        dst = output/dest_name
        require(not dst.exists() or sha(dst) == sha(bundle/source_name), 'copied evidence changed')
        if not dst.exists():
            shutil.copyfile(bundle/source_name, dst)
    columns = hashlib.sha256(json.dumps(selected, separators=(',', ':')).encode()).hexdigest()
    receipt = dict(schema='selected_rl_bundle.v1', status='ADMITTED', **FLAGS,
        selection_file='SELECTION.json', selection_sha256=pin, feature_columns=selected,
        feature_columns_sha256=columns, population_sha256=population,
        calendar_sha256=source_admission['binding']['calendar_sha256'],
        closure_intervals_file='closures.json', closure_intervals_sha256=sha(output/'closures.json'), splits={})
    frame = pd.read_parquet(bundle/'candidates_train_validation.parquet')
    frame['ASSUMED_SPREAD'] = .0001  # Declared analytical stability input, not measured ask data.
    frame['SELECTED_AVAILABLE_AT'] = frame.DATE_TIME
    keep = list(dict.fromkeys(['DATE_TIME', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'ASSUMED_SPREAD'] + selected + ['SELECTED_AVAILABLE_AT']))
    for role, start, end in [('train', '2020-01-01', '2024-01-01'), ('validation', '2024-01-01', '2025-01-01')]:
        a,b = pd.Timestamp(start, tz='UTC'),pd.Timestamp(end, tz='UTC')
        part = frame.loc[(frame.DATE_TIME >= a) & (frame.DATE_TIME < b), keep].reset_index(drop=True)
        path = output/(role+'.parquet')
        if path.exists():
            pd.testing.assert_frame_equal(pd.read_parquet(path), part, check_exact=True)
        else:
            part.to_parquet(path, index=False)
        manifest = dict(schema='curated_rl_input.v1', status='ADMITTED', **FLAGS,
            availability_verified=True, open_session_coverage_verified=True, availability_column='SELECTED_AVAILABLE_AT',
            input_sha256=sha(path), split=role, feature_columns=selected, selection_sha256=pin,
            inventory_sha256=population, calendar_sha256=receipt['calendar_sha256'],
            timestamp_semantics='completed_bar_available_at', period_start=a.isoformat(), period_end=b.isoformat(),
            row_count=len(part), leading_source_warmup_rows_removed=(read_json(bundle/'DERIVED_ADMISSION.json')['leading_warmup_rows_removed'] if role=='train' else 0),
            expected_timestamps_sha256=hashlib.sha256(''.join(t.isoformat()+'\n' for t in part.DATE_TIME).encode()).hexdigest())
        immutable(output/(role+'.json'), manifest)
        receipt['splits'][role] = dict(input_file=path.name, manifest_file=role+'.json', manifest_sha256=sha(output/(role+'.json')))
    immutable(output/'RECEIPT.json', receipt)
    original = read_json(run/'phase1/finalizer/result.json')['envelope']
    envelope = {'schema_version': original['schema_version'], 'run': dict(original['run']),
                'rows': {k:[] for k in original['rows']}}
    envelope['run'].update(run_id='selected-core:'+pin, code_sha256=sha(__file__), input_sha256=pin)
    for target in spec['population']['targets']:
        for fid in variables:
            row = dict(feature_id=fid, target_id=target['target_id'], horizon=target['horizon_hours'],
                       method='MRMR_UNION_REDUNDANCY_FILTER', score=None, rank=None,
                       decision='SELECTED' if fid in selected else 'REJECTED', rule=reasons[fid],
                       evidence_sha256=pin, population_id=spec['population']['population_id'])
            row['row_sha256'] = digest(row)
            envelope['rows']['selection_decisions'].append(row)
    envelope['envelope_sha256'] = digest(envelope)
    immutable(output/'DECISIONS_ENVELOPE.json', envelope)
    store = PredictorDuckdbStore()
    store.set_params(duckdb_path=str(output/'decisions.duckdb'), schema='main', memory_limit='256MB', threads=1)
    try:
        store.write_feature_selection_envelope(envelope)
    finally:
        if store._engine is not None:
            store._engine.dispose()
    summary = dict(state='FILTER_SELECTION_SEALED_REMOTE_PUBLICATION_PENDING', **FLAGS,
                   selected_count=len(selected), candidate_count=len(variables), selected_columns=selected,
                   selection_sha256=pin, causal_evidence_computed=False, requires_remote_readback=True)
    immutable(output/'SELECTION_STATUS.json', summary)
    return summary


def publish(run, output, url, token_env):
    from tools.fs_phase23_warehouse import Warehouse, ServiceWarehouse, FACT_TABLES
    from predictor_olap_store.feature_selection_store import FAMILY_TABLES
    remote = ServiceWarehouse(url, token_env=token_env, timeout=120, retries=2)
    phase1 = {}
    for envelope in (read_json(run/'phase1/finalizer/result.json')['envelope'], read_json(output/'DECISIONS_ENVELOPE.json')):
        rid = envelope['run']['run_id']
        remote._call('POST', '/api/v2/feature-selection-envelopes', envelope)
        counts = {}
        for family, table in FAMILY_TABLES.items():
            expected = {r['row_sha256']:r for r in envelope['rows'][family]}
            observed, after = [], None
            while True:
                cursor = f" AND row_sha256 > '{after}'" if after is not None else ''
                page = remote.query(f"SELECT * FROM {table} WHERE run_id = '{rid}'{cursor} ORDER BY row_sha256 LIMIT 500")
                observed.extend(page)
                if len(page) < 500:
                    break
                next_after = page[-1]['row_sha256']
                require(after is None or next_after > after, 'warehouse cursor did not advance')
                after = next_after
            require(len(observed) == len(expected), 'native phase1 readback count differs: '+family)
            for row in observed:
                require(row['row_sha256'] in expected, 'native phase1 readback row missing')
                want = expected[row['row_sha256']]
                require(all(value == want.get(key) for key,value in row.items()
                            if key not in ('row_identity_sha256', 'run_id')), 'native phase1 stored values differ: '+family)
            counts[family] = dict(count=len(observed), rows_sha256=digest(sorted(expected)))
        phase1[rid] = counts
    rid = read_json(run/'REPORT.json')['identity']
    local = Warehouse(run/'phase23.duckdb', read_only=True)
    phase23 = {}
    try:
        for table in FACT_TABLES:
            rows = local.read_run(rid, table)
            if not rows:
                phase23[table] = dict(count=0, rows_sha256=digest([]))
                continue
            for start in range(0,len(rows),500):
                remote.submit_rows(rid, table, rows[start:start+500])
            observed = remote.read_run(rid, table)
            wanted = sorted(digest(row) for row in rows)
            require(sorted(digest(row) for row in observed) == wanted, 'native phase23 stored values differ: '+table)
            phase23[table] = dict(count=len(rows), rows_sha256=digest(wanted))
    finally:
        local.close()
    result = dict(state='SELECTION_NATIVE_WAREHOUSE_READBACK_VERIFIED', selection_sha256=sha(output/'SELECTION.json'),
                  phase1=phase1, phase23=phase23, pending=0, mismatch=0, full_inventory_complete=False,
                  causal_evidence_computed=False)
    immutable(output/'PUBLICATION.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=['seal','publish'])
    parser.add_argument('--predictor-root', type=Path, required=True)
    parser.add_argument('--causal-root', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--warehouse-url', default='http://localhost:5057')
    parser.add_argument('--token-env', default='DATA_GOV_LAKE_TOKEN')
    args = parser.parse_args()
    bootstrap(args.predictor_root, args.causal_root)
    result = (seal(args.bundle, args.run, args.output) if args.action == 'seal' else
              publish(args.run, args.output, args.warehouse_url, args.token_env))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
