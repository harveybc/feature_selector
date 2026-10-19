"""Real pinned phase engines on synthetic inputs, never source admission."""
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="module")
def runtime():
    spec = importlib.util.spec_from_file_location("selection_rebuild", ROOT / "scripts/selection_rebuild.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    predictor = Path(os.environ["SELECTION_PREDICTOR_ROOT"]).resolve()
    causal = Path(os.environ["SELECTION_CAUSAL_ROOT"]).resolve()
    module.bootstrap(predictor, causal)
    return module, predictor, causal


@pytest.fixture
def bundle(runtime, tmp_path):
    module, predictor, causal = runtime
    manifest = module.make_demo(tmp_path / "fixture")
    config = json.loads((ROOT / "examples/rebuild_cpu.json").read_text())
    return module, predictor, causal, manifest, config, tmp_path / "run"


def test_real_profile_pairwise_filter_passage_and_restart(bundle, monkeypatch):
    module, predictor, causal, manifest, config, output = bundle
    result = module.run(manifest, config, predictor, causal, output)
    assert result["state"] == "PROFILE_FILTERS_COMPLETE"
    assert result["final_selection"] is False
    assert result["causal_evidence_computed"] is False
    assert result["source_admission_verified"] is False
    assert result["phase1_readback"]["variable_profiles"]["count"] > 0
    assert result["phase23_readback"]["feature_pair_metrics"]["count"] > 0
    assert result["phase23_readback"]["feature_filter_rankings"]["count"] > 0
    p1 = json.loads((output / "phase1/PHASE_1_COMPLETE.json").read_text())
    p2 = json.loads((output / "phase23/PHASE_2_COMPLETE.json").read_text())
    p3 = json.loads((output / "phase23/PHASE_3_FILTER_COMPLETE.json").read_text())
    assert p1["terminal_count"] == 5 and p2["expected_pairs"] == 10
    assert len(p3["methods"]) == 9
    assert json.loads((output / "MANIFEST.json").read_text())["phase1"]["gate_sha256"] == p1["gate_sha256"]
    from tools import phase1_inventory_orchestrator as p1_api, feature_pairwise_worker
    def forbidden(*args, **kwargs):
        raise AssertionError("accepted science was recomputed")
    monkeypatch.setattr(p1_api, "_run_item", forbidden)
    monkeypatch.setattr(feature_pairwise_worker, "compute_shard", forbidden)
    before = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*.json")
              if "terminals" in p.parts or p.name.startswith("PHASE_")}
    again = module.run(manifest, config, predictor, causal, output)
    assert again["phase23_readback"] == result["phase23_readback"]
    assert again["phase1_readback"] == result["phase1_readback"]
    assert before == {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*.json")
                      if "terminals" in p.parts or p.name.startswith("PHASE_")}
    snapshot = {p: p.stat().st_mtime_ns for p in output.rglob("*") if p.is_file()}
    status = module.status(output)
    assert status["phase1"]["completed"] == 5
    assert status["phase3"] == "COMPLETE"
    assert snapshot == {p: p.stat().st_mtime_ns for p in output.rglob("*") if p.is_file()}
    import duckdb
    with duckdb.connect(str(output / "phase1.duckdb")) as connection:
        connection.execute("UPDATE df_fact_variable_profile SET metric_value = 999 WHERE metric_value IS NOT NULL")
    with pytest.raises(ValueError, match="readback values mismatch"):
        module.run(manifest, config, predictor, causal, output)


def test_render_uses_owner_schemas_and_dynamic_denominator(bundle):
    module, predictor, causal, manifest, config, output = bundle
    module.render(manifest, config, predictor, causal, output)
    from tools import phase1_inventory_orchestrator as api
    loaded = api.load_config(output / "PHASE1_CONFIG.json")
    assert loaded["schema"] == api.CONFIG_SCHEMA
    assert len(api.load_inventory(loaded)) == 5
    assert loaded["population"]["mode"] == "PROFILE_ONLY"
    assert loaded["worker"]["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    assert "causal_inference_provider.feature_selection_worker" in loaded["worker"]["command"]
    assert not (output / "phase23").exists()
    assert not list(output.rglob("*.duckdb"))
    changed = dict(config, n_shards=3)
    with pytest.raises(ValueError, match="changed"):
        module.render(manifest, changed, predictor, causal, output)


@pytest.mark.parametrize("attack", ["hash", "late", "alignment", "duplicate", "missing_month", "escape", "admission", "variable"])
def test_contract_refuses_bad_handoff_before_any_work(bundle, attack):
    module, predictor, causal, path, config, output = bundle
    import pandas as pd
    from tools.fs_phase23_manifest import sha256_file
    spec = json.loads(path.read_text())
    data = spec["population"]["data"]
    if attack == "hash":
        (path.parent / data["features_file"]).write_bytes(b"changed")
    elif attack in {"late", "alignment", "duplicate"}:
        key = "availability" if attack == "late" else "targets"
        name = spec["availability"]["file"] if key == "availability" else data["targets_file"]
        frame = pd.read_parquet(path.parent / name)
        if attack == "late":
            frame.loc[0, "sensor"] += pd.Timedelta(hours=1)
        elif attack == "alignment":
            frame = frame.iloc[::-1]
        else:
            frame.loc[1, "row_id"] = frame.loc[0, "row_id"]
        frame.to_parquet(path.parent / name, index=False)
        if key == "availability":
            spec["availability"]["sha256"] = sha256_file(path.parent / name)
        else:
            data["targets_sha256"] = sha256_file(path.parent / name)
    elif attack == "missing_month":
        spec["train_period"][1] = "2020-03-01T00:00:00Z"
    elif attack == "escape":
        spec["availability"]["file"] = "../outside.parquet"
    elif attack == "admission":
        spec["scope"] = "ADMITTED_TRAIN"
    else:
        spec["admission"]["variable_ids"].pop()
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError):
        module.render(path, config, predictor, causal, output)
    assert not output.exists()


def test_publication_failure_stops_successor_and_resumes_without_refitting(bundle, monkeypatch):
    module, predictor, causal, manifest, config, output = bundle
    from predictor_duckdb_store.provider import PredictorDuckdbStore
    original = PredictorDuckdbStore.write_feature_selection_envelope
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic publication outage")
    monkeypatch.setattr(PredictorDuckdbStore, "write_feature_selection_envelope", fail)
    first = module.run(manifest, config, predictor, causal, output)
    assert first["state"] == "WAITING_FOR_WAREHOUSE_RECEIPTS"
    assert not (output / "phase23").exists()
    assert len(list((output / "phase1/terminals").glob("*.json"))) == 5
    monkeypatch.setattr(PredictorDuckdbStore, "write_feature_selection_envelope", original)
    from tools import phase1_inventory_orchestrator as api
    def forbidden(*args, **kwargs):
        raise AssertionError("publication retry recomputed a feature")
    monkeypatch.setattr(api, "_run_item", forbidden)
    assert module.run(manifest, config, predictor, causal, output)["state"] == "PROFILE_FILTERS_COMPLETE"


@pytest.mark.parametrize("boundary", ["train", "fold", "clock", "fold_later"])
def test_future_labels_refused_before_render(bundle, boundary):
    module, predictor, causal, path, config, output = bundle
    import pandas as pd
    from tools.fs_phase23_manifest import sha256_file
    spec = json.loads(path.read_text())
    data = spec["population"]["data"]
    label_path = path.parent / data["targets_file"]
    labels = pd.read_parquet(label_path)
    target = spec["population"]["targets"][0]
    if boundary == "clock":
        spec["target_clock"] = "MARKET_TIME"
    else:
        if boundary == "train":
            # A finite last label matures exactly at the declared exclusive end.
            cutoff = labels[data["timestamp_column"]].iloc[-1] + pd.Timedelta(hours=target["horizon_hours"])
            spec["train_period"][1] = cutoff.isoformat()
            row = len(labels) - 1
        else:
            row = spec["population"]["folds"][0]["train_rows"][1] - 1
            if boundary == "fold_later":
                target["horizon_hours"] = 2
        labels.loc[row, target["column"]] = 123.0
        labels.to_parquet(label_path, index=False)
        data["targets_sha256"] = sha256_file(label_path)
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="target"):
        module.render(path, config, predictor, causal, output)
    assert not output.exists()


def test_declared_boundary_masks_are_preserved_not_rewritten(bundle):
    module, predictor, causal, path, config, output = bundle
    from rebuild_contract import validate
    spec = json.loads(path.read_text())
    labels = path.parent / spec["population"]["data"]["targets_file"]
    before = labels.read_bytes()
    validate(path, config)
    assert labels.read_bytes() == before
