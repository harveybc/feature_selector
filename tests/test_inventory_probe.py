"""Candidate-contract checks are not financial data admission tests."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/inventory_probe.py"


@pytest.fixture
def probe():
    spec = importlib.util.spec_from_file_location("inventory_probe", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def candidate():
    # Minimal shape emitted by financial-data's required_variable_inventory.build.
    return {
        "schema": "financial_data.required_variable_inventory.candidate.v1",
        "state": "CANDIDATE_NOT_ADMITTED", "admitted": False,
        "selection_complete": False, "hardcoded_population_sizes": [], "chunk": [0, 1],
        "denominator": {"all_catalog_variables": 1, "trading_required": 1,
                        "model_candidates": 1, "total_records": 3,
                        "files_present": 0, "files_missing": 1},
        "variables": [
            {"variable_id": "catalog:sensor", "group": "ALL_CATALOG_VARIABLES",
             "file_status": "MISSING", "dataset_path": "not-opened.parquet"},
            {"variable_id": "calendar:sensor", "group": "TRADING_REQUIRED"},
            {"variable_id": "model:sensor", "group": "MODEL_CANDIDATES"},
        ],
    }


def write_candidate(tmp_path, candidate):
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(candidate))
    return path


def test_actual_candidate_shape_is_valid_but_never_admitted(probe, candidate, tmp_path):
    path = write_candidate(tmp_path, candidate)
    before = path.read_bytes()
    result = probe.probe(path)
    assert result["state"] == "BLOCKED_ADMISSION"
    assert result["candidate_contract_valid"] is True
    assert result["data_admission_complete"] is False
    assert result["selection_complete"] is False
    assert result["may_launch_selection"] is False
    assert result["denominator"] == candidate["denominator"]
    assert result["file_status_unreported_records"] == 2
    assert result == probe.probe(path)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    assert "not-opened.parquet" not in json.dumps(result)


@pytest.mark.parametrize("field", ["admitted", "selection_complete", "state", "schema"])
def test_forged_admission_and_unknown_contracts_refused(probe, candidate, tmp_path, field):
    candidate[field] = True if field.endswith("complete") or field == "admitted" else "ADMITTED"
    result = probe.probe(write_candidate(tmp_path, candidate))
    assert result["state"] == "INVALID_INVENTORY"
    assert not result["may_launch_selection"]


@pytest.mark.parametrize("mutation,code", [
    ("omit", "DENOMINATOR_MISMATCH"), ("duplicate", "DUPLICATE_VARIABLE_ID"),
    ("unknown_group", "INVALID_VARIABLE_GROUP"), ("bool_count", "INVALID_DENOMINATOR"),
    ("file_status", "INVALID_FILE_STATUS"), ("empty", "EMPTY_POPULATION"),
])
def test_population_checks(probe, candidate, tmp_path, mutation, code):
    if mutation == "omit":
        candidate["variables"].pop()
    elif mutation == "duplicate":
        candidate["variables"][1]["variable_id"] = candidate["variables"][0]["variable_id"]
    elif mutation == "unknown_group":
        candidate["variables"][0]["group"] = "ASSUMED_ADMITTED"
    elif mutation == "bool_count":
        candidate["denominator"]["files_present"] = False
    elif mutation == "file_status":
        candidate["variables"][0]["file_status"] = "ADMITTED"
    else:
        candidate["variables"] = []
    result = probe.probe(write_candidate(tmp_path, candidate))
    assert result["state"] == "INVALID_INVENTORY"
    assert result["reason"] == code


def test_population_not_hardcoded_and_missing_files_retained(probe, candidate, tmp_path):
    candidate["variables"].append({"variable_id": "model:another", "group": "MODEL_CANDIDATES"})
    candidate["denominator"]["model_candidates"] += 1
    candidate["denominator"]["total_records"] += 1
    candidate["chunk"] = "MERGED_0..3_OF_4"
    result = probe.probe(write_candidate(tmp_path, candidate))
    assert result["state"] == "BLOCKED_ADMISSION"
    assert result["denominator"]["total_records"] == 4
    assert result["denominator"]["files_missing"] == 1


def test_observed_evidence_and_all_present_do_not_confer_admission(probe, candidate, tmp_path):
    candidate["variables"][0].update(file_status="PRESENT", nonfinite_cells=0,
                                     absent_months=["2020-02"], sha256="a" * 64)
    candidate["denominator"].update(files_present=1, files_missing=0)
    result = probe.probe(write_candidate(tmp_path, candidate))
    assert result["state"] == "BLOCKED_ADMISSION"
    assert result["source_bytes_verified"] is False


@pytest.mark.parametrize("body", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', '{', '[]'])
def test_bad_json_refused(probe, tmp_path, body):
    path = tmp_path / "bad.json"
    path.write_text(body)
    assert probe.probe(path)["state"] == "INVALID_INVENTORY"


def test_size_bound_and_unreadable_input(probe, tmp_path, monkeypatch):
    path = tmp_path / "large.json"
    path.write_bytes(b" " * 65)
    monkeypatch.setattr(probe, "MAX_BYTES", 64)
    assert probe.probe(path)["reason"] == "INPUT_TOO_LARGE"
    assert probe.probe(tmp_path / "missing")["reason"] == "INPUT_UNREADABLE"
    assert probe.probe(tmp_path)["reason"] == "INPUT_NOT_REGULAR_FILE"


def test_fifo_is_rejected_without_waiting_for_a_writer(tmp_path):
    path = tmp_path / "pipe"
    os.mkfifo(path)
    result = subprocess.run([sys.executable, str(SCRIPT), "--inventory", str(path)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout)["reason"] == "INPUT_NOT_REGULAR_FILE"


def test_changed_bytes_change_identity(probe, candidate, tmp_path):
    path = write_candidate(tmp_path, candidate)
    first = probe.probe(path)
    path.write_bytes(path.read_bytes() + b"\n")
    second = probe.probe(path)
    assert first["input_sha256"] != second["input_sha256"]
    assert first["denominator"] == second["denominator"]


def test_cli_is_deterministic_read_only_and_blocks_chaining(candidate, tmp_path):
    path = write_candidate(tmp_path, candidate)
    command = [sys.executable, str(SCRIPT), "--inventory", str(path)]
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    first = subprocess.run(command, capture_output=True, text=True, timeout=10)
    second = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert first.returncode == second.returncode == 2
    assert first.stdout == second.stdout
    assert not first.stderr
    assert json.loads(first.stdout)["state"] == "BLOCKED_ADMISSION"
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    invalid = copy.deepcopy(candidate)
    invalid["admitted"] = True
    write_candidate(tmp_path, invalid)
    failed = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert failed.returncode == 1
    assert json.loads(failed.stdout)["state"] == "INVALID_INVENTORY"
