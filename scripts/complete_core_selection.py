"""Finite profiles/pairs/filters -> selected bundle -> native OLAP -> verified copies."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from rebuild_contract import read_json, require
from selection_rebuild import bootstrap, run, immutable
from finalize_core_selection import seal, publish, sha


RUN_FILES = ['BINDING.json', 'INPUT.json', 'MANIFEST.json', 'REPORT.json', 'STATUS.json',
             'phase1.duckdb', 'phase23.duckdb', 'phase1/PLAN.json',
             'phase1/PHASE_1_COMPLETE.json', 'phase1/finalizer/result.json',
             'phase23/PLAN.json', 'phase23/PHASE_2_COMPLETE.json',
             'phase23/PHASE_3_FILTER_COMPLETE.json', 'phase23/CANDIDATES_FOR_VALIDATION.json']


def verify_snapshot(root):
    import hashlib
    import json
    from pathlib import Path
    root = Path(root)
    doc = json.loads((root/'SNAPSHOT.json').read_text())
    for name, expected in doc['files'].items():
        path = (root/name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError('SNAPSHOT_MEMBER_ESCAPES')
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for part in iter(lambda: stream.read(1024*1024), b''):
                h.update(part)
        if h.hexdigest() != expected:
            raise ValueError('SNAPSHOT_HASH_DIFFERS: '+name)
    return {'verified_files': len(doc['files']), 'selection_sha256': doc['selection_sha256']}


def snapshot(bundle, run_root, selected, destination):
    require(read_json(selected/'PUBLICATION.json')['state'] == 'SELECTION_NATIVE_WAREHOUSE_READBACK_VERIFIED',
            'remote readback not complete')
    files = [(run_root/name, 'selection/'+name) for name in RUN_FILES]
    for root, prefix in ((bundle, 'bundle'), (selected, 'selected')):
        files += [(p, prefix+'/'+p.name) for p in sorted(root.iterdir())
                  if p.is_file() and p.suffix not in ('.partial', '.lock') and p.name != 'CLOSE.json']
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for source, name in files:
        require(source.is_file(), 'snapshot source missing: '+name)
        require(not Path(str(source)+'.wal').exists(), 'live DuckDB cannot be snapshotted')
        require(not destination.resolve().is_relative_to(source.parent.resolve()), 'snapshot is inside source tree')
        pin = sha(source)
        target = destination/name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            partial = target.with_suffix(target.suffix+'.partial')
            shutil.copyfile(source, partial)
            with partial.open('rb') as stream:
                os.fsync(stream.fileno())
            require(sha(partial) == pin and sha(source) == pin, 'copy/source changed')
            partial.replace(target)
        require(sha(target) == pin, 'snapshot changed: '+name)
        hashes[name] = pin
    immutable(destination/'SNAPSHOT.json', dict(schema='feature_selector.snapshot.v1',
        state='LOCAL_VERIFIED', selection_sha256=sha(selected/'SELECTION.json'), files=hashes,
        full_inventory_complete=False, causal_evidence_computed=False))
    return verify_snapshot(destination)


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('action', choices=['complete','status','verify'])
    for name in ('bundle','run','selected','snapshot','predictor-root','causal-root'):
        p.add_argument('--'+name, type=Path)
    p.add_argument('--warehouse-url', default='http://localhost:5057')
    p.add_argument('--token-env', default='DATA_GOV_LAKE_TOKEN')
    p.add_argument('--mirror-host')
    p.add_argument('--mirror-root')
    p.add_argument('--mirror-python', default='python3')
    a = p.parse_args()
    if a.action == 'verify':
        print(json.dumps(verify_snapshot(a.snapshot)))
        return
    if a.action == 'status':
        path = a.selected/'CLOSE.json'
        if not path.exists():
            path = a.selected/'PUBLICATION.json'
        print(json.dumps(read_json(path) if path.exists() else {'state':'NOT_CLOSED','eta_seconds':None}))
        return
    bootstrap(a.predictor_root, a.causal_root)
    if (a.selected/'CLOSE.json').exists():
        done = read_json(a.selected/'CLOSE.json')
        require(done['selection_sha256'] == sha(a.selected/'SELECTION.json')
                and done['publication_sha256'] == sha(a.selected/'PUBLICATION.json')
                and read_json(a.selected/'SELECTION.json')['population_sha256'] == sha(a.bundle/'REBUILD_INPUT.json'),
                'closed selection identity changed')
        require(verify_snapshot(a.snapshot)['selection_sha256'] == done['selection_sha256'],
                'closed snapshot differs')
        print(json.dumps(done, indent=2))
        return
    result = run(a.bundle/'REBUILD_INPUT.json', read_json(a.bundle/'REBUILD_CONFIG.json'),
                 a.predictor_root, a.causal_root, a.run)
    require(result['state'] == 'PROFILE_FILTERS_COMPLETE', 'selection engines did not close')
    seal(a.bundle, a.run, a.selected)
    publication = publish(a.run, a.selected, a.warehouse_url, a.token_env)
    verified = snapshot(a.bundle, a.run, a.selected, a.snapshot)
    require(a.mirror_host and a.mirror_root, 'second physical copy destination required')
    subprocess.run(['ssh', a.mirror_host, shlex.join(['mkdir','-p',a.mirror_root])], check=True, timeout=30)
    subprocess.run(['rsync','-a','--checksum','--fsync',str(a.snapshot)+'/', a.mirror_host+':'+a.mirror_root+'/'],
                   check=True, timeout=300)
    import inspect
    code = inspect.getsource(verify_snapshot) + '\nimport sys; print(json.dumps(verify_snapshot(sys.argv[1])))'
    command = shlex.join([a.mirror_python, '-c', 'import json\n'+code, a.mirror_root])
    remote = json.loads(subprocess.check_output(['ssh',a.mirror_host, command], text=True, timeout=120))
    require(remote == verified, 'second-copy verification differs')
    complete = dict(schema='feature_selector.scoped_close.v1',
        state='FILTER_SELECTION_OLAP_AND_TWO_PHYSICAL_COPIES_VERIFIED',
        selected_count=read_json(a.selected/'SELECTION_STATUS.json')['selected_count'],
        candidate_count=read_json(a.selected/'SELECTION_STATUS.json')['candidate_count'],
        selection_sha256=verified['selection_sha256'], verified_files=verified['verified_files'],
        snapshot_manifest_sha256=sha(a.snapshot/'SNAPSHOT.json'), pending=0, mismatch=0,
        full_inventory_complete=False, causal_evidence_computed=False,
        publication_sha256=sha(a.selected/'PUBLICATION.json'))
    immutable(a.selected/'CLOSE.json', complete)
    print(json.dumps(complete, indent=2))


if __name__ == '__main__':
    main()
