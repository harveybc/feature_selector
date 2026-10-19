import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from complete_core_selection import snapshot, verify_snapshot, RUN_FILES


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
