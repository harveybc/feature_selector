import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from complete_core_selection import snapshot, verify_snapshot, deployment_receipt, RUN_FILES, sha


def test_snapshot_requires_publication_and_detects_any_changed_byte(tmp_path):
    bundle, run, selected, dest = [tmp_path/n for n in ('bundle','run','selected','snapshot')]
    for p in (bundle,run,selected): p.mkdir()
    (selected/'PUBLICATION.json').write_text(json.dumps({'state':'NOT_VERIFIED'}))
    with pytest.raises(ValueError,match='readback'):
        snapshot(bundle,run,selected,dest)
    assert not dest.exists()
    (selected/'PUBLICATION.json').write_text(json.dumps({'state':'SELECTION_NATIVE_WAREHOUSE_READBACK_VERIFIED'}))
    (selected/'SELECTION.json').write_text('{"selected":["a"]}')
    (bundle/'inputs.parquet').write_bytes(b'fixture-only-not-a-real-database')
    for n in RUN_FILES:
        p=run/n; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(n.encode())
    result=snapshot(bundle,run,selected,dest)
    assert result==verify_snapshot(dest)
    assert snapshot(bundle,run,selected,dest)==result
    (dest/'selection/phase1.duckdb').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='HASH_DIFFERS'):
        verify_snapshot(dest)


def test_snapshot_refuses_a_live_wal(tmp_path):
    bundle, run, selected = [tmp_path/n for n in ('bundle','run','selected')]
    for p in (bundle,run,selected): p.mkdir()
    (selected/'PUBLICATION.json').write_text(json.dumps({'state':'SELECTION_NATIVE_WAREHOUSE_READBACK_VERIFIED'}))
    for n in RUN_FILES:
        p=run/n; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(n.encode())
    (run/'phase1.duckdb.wal').write_bytes(b'live')
    with pytest.raises(ValueError,match='live DuckDB'):
        snapshot(bundle,run,selected,tmp_path/'snapshot')


@pytest.mark.parametrize('tamper', [False,True])
def test_deployment_receipt_pins_actual_close_and_rechecks_metadata_copy(tmp_path,monkeypatch,tamper):
    selected,dest=tmp_path/'selected',tmp_path/'snapshot'
    selected.mkdir(); (dest/'selected').mkdir(parents=True)
    (selected/'CLOSE.json').write_text('{"state":"fixture"}')
    (selected/'RECEIPT.json').write_text('{"selection_sha256":"fixture"}')
    calls=[]
    monkeypatch.setattr('complete_core_selection.subprocess.run',lambda args,**kw:calls.append(args))
    def remote(*args,**kw):
        values=[sha(selected/n) for n in ('CLOSE.json','DEPLOYMENT_RECEIPT.json')]
        if tamper: values[0]='0'*64
        return '\n'.join(h+'  fixture' for h in values)
    monkeypatch.setattr('complete_core_selection.subprocess.check_output',remote)
    if tamper:
        with pytest.raises(ValueError,match='metadata mirror differs'):
            deployment_receipt(selected,dest,'fixture-host','/fixture')
    else:
        deployment_receipt(selected,dest,'fixture-host','/fixture')
        body=json.loads((selected/'DEPLOYMENT_RECEIPT.json').read_text())
        assert body['selection_close_sha256']==sha(selected/'CLOSE.json')
        assert '--checksum' in calls[0] and '--fsync' in calls[0]
