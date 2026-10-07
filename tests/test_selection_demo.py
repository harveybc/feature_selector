"""Public example acceptance, using the pinned engines and a disposable cube."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def adapter():
    spec = importlib.util.spec_from_file_location("selection_demo", ROOT / "scripts/selection_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def completed(tmp_path_factory):
    module = adapter()
    predictor = Path(os.environ["SELECTION_PREDICTOR_ROOT"])
    output = tmp_path_factory.mktemp("public_selection")
    config = json.loads((ROOT / "examples/synthetic.json").read_text())
    result = module.run(config, predictor, output)
    return module, predictor, output, config, result


def test_real_engines_and_local_warehouse(completed):
    module, predictor, output, config, result = completed
    assert result["state"] == "DEMO_FILTERS_COMPLETE"
    assert result["final_selection"] is False
    assert result["causal_evidence_computed"] is False
    manifest = json.loads((output / "MANIFEST.json").read_text())
    assert manifest["feature_count"] == 5 and manifest["expected_pairs"] == 10
    assert manifest["causal_supported"] == []
    from tools.fs_phase23_warehouse import Warehouse
    wh = Warehouse(output / "metrics.duckdb", read_only=True)
    try:
        metrics = wh.read_run(manifest["identity"], "feature_pair_metrics")
        assert metrics and any(r["metric"] == "distance_correlation" for r in metrics)
        assert any(r["state"] == "INSUFFICIENT_SUPPORT" for r in metrics)
        nonlinear = {r["metric"]: r for r in metrics if r["left"] == "sensor" and
                     r["right"] == "squared" and r["fold_id"] == "TRAIN" and r["lag_hours"] == 0}
        assert abs(nonlinear["pearson"]["value"]) < 0.3
        assert nonlinear["mutual_information"]["value"] > 0.5
        assert wh.read_run(manifest["identity"], "feature_filter_rankings")
    finally:
        wh.close()
    closure = json.loads((output / "campaign/PHASE_2_COMPLETE.json").read_text())
    assert closure["expected_pairs"] == 10
    assert closure["alias_groups"] == 1
    candidates = json.loads((output / "campaign/CANDIDATES_FOR_VALIDATION.json").read_text())
    assert candidates["predictive_winner"] is None


def test_restart_reuses_terminals(completed, monkeypatch):
    module, predictor, output, config, result = completed
    from tools import feature_pairwise_worker
    def unexpected(*args, **kwargs):
        raise AssertionError("restart recomputed an accepted shard")
    monkeypatch.setattr(feature_pairwise_worker, "compute_shard", unexpected)
    before = {p.name: p.read_bytes() for p in (output / "campaign/terminals").glob("*.json.gz")}
    again = module.run(config, predictor, output)
    assert again["worker"]["computed"] == 0
    assert before == {p.name: p.read_bytes() for p in (output / "campaign/terminals").glob("*.json.gz")}
    assert again["readback"] == result["readback"]


def test_changed_inputs_and_config_refused(completed):
    module, predictor, output, config, _ = completed
    with pytest.raises(ValueError, match="configuration"):
        module.run(dict(config, seed=config["seed"] + 1), predictor, output)
    path = output / "data/features_train.parquet"
    original = path.read_bytes()
    try:
        path.write_bytes(original + b"corrupt")
        with pytest.raises(Exception, match="digest"):
            module.run(config, predictor, output)
    finally:
        path.write_bytes(original)


def test_wrong_revision_refused(tmp_path):
    module = adapter()
    with pytest.raises(ValueError, match="revision"):
        module.check_predictor(tmp_path)
