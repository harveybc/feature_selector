#!/usr/bin/env python3
"""Sequential pinned phase-1 profiles -> phase-2 pairs -> phase-3 filters."""
from __future__ import annotations

import argparse
import csv
import fcntl
import io
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys

from rebuild_contract import read_json, require, validate
from selection_demo import check_predictor, write_json

ROOT = Path(__file__).resolve().parents[1]
CPU = {"CUDA_VISIBLE_DEVICES": "", "NVIDIA_VISIBLE_DEVICES": "void",
       "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}


def bootstrap(predictor, causal):
    os.environ.update(CPU)
    check_predictor(predictor)
    expected = read_json(ROOT / "upstream.lock.json")["causal-inference"]["commit"]
    observed = subprocess.check_output(["git", "-C", str(causal), "rev-parse", "HEAD"], text=True).strip()
    require(observed == expected, "causal revision differs from upstream.lock.json")
    dirty = subprocess.check_output(["git", "-C", str(causal), "status", "--porcelain", "--", "provider"], text=True)
    require(not dirty.strip(), "causal runtime is modified")
    sys.path.insert(0, str(causal / "provider/src"))
    from tools import phase1_inventory_orchestrator as p1
    from causal_inference_provider import feature_selection_worker as worker
    from predictor_duckdb_store import provider
    for module, root in ((p1, predictor), (worker, causal), (provider, predictor)):
        require(Path(module.__file__).resolve().is_relative_to(root.resolve()), "imported code is not pinned runtime")


def immutable(path, value):
    if path.exists():
        require(read_json(path) == value, f"{path.name} changed; use a new output directory")
    else:
        write_json(path, value)


def render(path, config, predictor, causal, output):
    """Render owner configs only; no worker or warehouse is started."""
    from tools import fs_phase23_manifest as man, phase1_inventory_orchestrator as p1
    spec = validate(path, config)
    output, root = output.resolve(), path.resolve().parent
    identity = {"input_sha256": man.sha256_file(path), "config": config,
                "upstream": read_json(ROOT / "upstream.lock.json"),
                "python": sys.version.split()[0],
                "packages": {name: version(name) for name in (
                    "numpy", "pandas", "scipy", "scikit-learn", "pyarrow", "statsmodels",
                    "sqlalchemy", "duckdb", "duckdb-engine")},
                "adapter_sha256": {f: man.sha256_file(ROOT / "scripts" / f)
                                   for f in ("selection_rebuild.py", "rebuild_contract.py", "selection_demo.py", "inventory_probe.py")}}
    identity["binding_sha256"] = man.digest(identity)
    if output.exists() and not (output / "BINDING.json").exists():
        require(not any(p.name != ".writer.lock" for p in output.iterdir()), "output is not owned by this rebuild")
    output.mkdir(parents=True, exist_ok=True)
    immutable(output / "BINDING.json", identity)
    population, data = spec["population"], spec["population"]["data"]
    inventory = io.StringIO()
    fields = ["feature_id", "feature_column", "resource_key", "family", "clock", "train_rows"]
    writer = csv.DictWriter(inventory, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for f in population["features"]:
        writer.writerow({"feature_id": f["feature_id"], "feature_column": f["feature_id"],
                         "resource_key": "train", "family": f["family"], "clock": f["clock"],
                         "train_rows": data["train_rows"]})
    inv = output / "INVENTORY.csv"
    if inv.exists():
        require(inv.read_text() == inventory.getvalue(), "inventory changed")
    else:
        inv.write_text(inventory.getvalue())
    resource = {"resource_id": population["population_id"] + ":train",
                "path": str(root / data["features_file"]), "format": "parquet",
                "timestamp_column": data["timestamp_column"], "frequency": "1h", "calendar": config["calendar"]}
    pack = {"id": config["target_pack_id"], "path": str(root / data["targets_file"]),
            "format": "parquet", "timestamp_column": data["timestamp_column"],
            "definitions": [{"name": t["target_id"], **{k: t[k] for k in ("column", "family", "head", "horizon_hours")}}
                            for t in population["targets"]]}
    deployment = {"schema": "phase1.column_worker_deployment.v1", "version": "selector-rebuild-v1",
                  "output_root": str(output / "phase1-worker"), "resources": {"train": resource},
                  "populations": {population["population_id"]: {
                      "mode": "PROFILE_ONLY", "target_pack_id": config["target_pack_id"], "target_pack": pack,
                      "campaign_sha256": identity["binding_sha256"], "created_at": spec["created_at"],
                      "train_period": spec["train_period"]}}}
    deployment["deployment_sha256"] = man.digest(deployment)
    immutable(output / "DEPLOYMENT.json", deployment)
    pythonpath = os.pathsep.join(str(p.resolve()) for p in (
        causal / "provider/src", predictor / "olap/store/src", predictor / "olap/duckdb_store/src", predictor))
    worker_command = [sys.executable, "-m", "causal_inference_provider.feature_selection_worker",
                      "--stdio", "--deployment-manifest", str(output / "DEPLOYMENT.json")]
    finalizer = [sys.executable, str(Path(__file__).resolve()), "finalize-profile",
                 "--plan", "{plan_path}", "--terminals", "{terminals_dir}", "--output", "{finalizer_output_path}"]
    rendered = {"schema": p1.CONFIG_SCHEMA, "phase": "PHASE_1", "state_root": str(output / "phase1"),
                "population": {"id": population["population_id"], "mode": "PROFILE_ONLY",
                               "target_pack": config["target_pack_id"], "campaign_sha256": identity["binding_sha256"]},
                "inventory": {"files": [str(inv)], "expected_total": len(population["features"])},
                "hosts": [{"id": "local-small", "size_class": "small"}, {"id": "local-large", "size_class": "large"}],
                "worker": {"transport": "stdio-json-v1", "command": worker_command,
                           "timeout_seconds": config["worker_timeout_seconds"], "environment": {**CPU, "PYTHONPATH": pythonpath}},
                "finalizer": {"command": finalizer, "timeout_seconds": config["worker_timeout_seconds"]},
                "retries": {"max_attempts": config["max_attempts"], "retryable_exit_codes": [75, 137, -9],
                            "retryable_failure_classes": ["ADMISSION", "OOM"]},
                "warehouse": {"submit_url": "local://phase1", "reconcile_url": "local://phase1",
                              "token_env": "UNUSED_LOCAL_STORE", "auth_profile": "local-duckdb"}}
    immutable(output / "PHASE1_CONFIG.json", rendered)
    immutable(output / "INPUT.json", spec)
    return spec, p1.load_config(output / "PHASE1_CONFIG.json"), identity


def finalize_profile(plan, terminals, output):
    """Bridge a verified profile merge to the orchestrator's lifecycle envelope."""
    from causal_inference_provider.feature_selection_worker import merge_profile_terminals
    result = merge_profile_terminals(plan, terminals, output.with_suffix(".profile.json"))
    require(result["state"] == "PROFILE_METRICS_COMPLETE", "profile merge is incomplete")
    require(result["unavailable_count"] == 0, "unavailable variables cannot enter this rebuild")
    write_json(output, {"schema": "phase1.finalizer_result.v1", "state": "PHASE_1_COMPLETE",
                        "mode": "PROFILE_ONLY", "scientific_state": result["state"],
                        "causal_evidence_computed": False, "terminal_count": result["terminal_count"],
                        "profile_result_sha256": result["result_sha256"], "envelope": result["envelope"]})


def phase1_readback(store, envelope):
    """Compare actual stored fields, not only stored digest labels, with the envelope."""
    from sqlalchemy import text
    from predictor_olap_store.feature_selection_store import FAMILY_TABLES
    from tools.fs_phase23_manifest import digest
    report = {}
    with store.engine().connect() as connection:
        for family, table in FAMILY_TABLES.items():
            observed = connection.execute(text(f'SELECT * FROM "main"."{table}" WHERE run_id = :run'),
                                          {"run": envelope["run"]["run_id"]}).mappings().all()
            expected = {r["row_sha256"]: r for r in envelope["rows"][family]}
            require(len(observed) == len(expected), f"phase1 readback count mismatch: {family}")
            for row in observed:
                require(row["row_sha256"] in expected, f"phase1 readback digest mismatch: {family}")
                want = expected[row["row_sha256"]]
                require(all(value == want.get(key) for key, value in row.items()
                            if key not in {"row_identity_sha256", "run_id"}), f"phase1 readback values mismatch: {family}")
            report[family] = {"count": len(observed), "rows_sha256": digest(sorted(expected))}
    return report


def status(output):
    from tools import phase1_inventory_orchestrator as p1, phase1_inventory_status as st
    result = {"phase1": "NOT_STARTED", "phase2": "NOT_STARTED", "phase3": "NOT_STARTED",
              "final_selection": False, "causal_evidence_computed": False}
    if (output / "phase1/PLAN.json").exists():
        result["phase1"] = st.build_status(p1.load_config(output / "PHASE1_CONFIG.json"))
    for phase, file in (("phase2", "PHASE_2_COMPLETE.json"), ("phase3", "PHASE_3_FILTER_COMPLETE.json")):
        closure_path = output / "phase23" / file
        result[phase] = "NOT_COMPLETE"
        if closure_path.exists():
            from tools.fs_phase23_manifest import digest
            closure = read_json(closure_path)
            require(closure.get("closure_sha256") == digest({k: v for k, v in closure.items() if k != "closure_sha256"}),
                    "phase closure digest mismatch")
            result[phase] = "COMPLETE"
    if (output / "phase23/STATUS.json").exists():
        result["phase23_last_engine_snapshot"] = read_json(output / "phase23/STATUS.json")
    return result


def run(path, config, predictor, causal, output):
    from tools import phase1_inventory_orchestrator as p1, fs_phase23_manifest as man
    from tools import feature_pairwise_campaign as campaign
    from tools.fs_phase23_warehouse import Warehouse
    from predictor_duckdb_store.provider import PredictorDuckdbStore
    # Validate before creating state, then serialize rendering, dispatch and publication.
    validate(path, config)
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".writer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        spec, cfg, binding = render(path, config, predictor, causal, output)
        output = output.resolve()
        plan = p1.build_plan(cfg)
        store = PredictorDuckdbStore()
        store.set_params(duckdb_path=str(output / "phase1.duckdb"), schema="main", memory_limit="512MB", threads=1)
        def submit(envelope, _settings):
            receipt = store.write_feature_selection_envelope(envelope)
            phase1_readback(store, envelope)
            return receipt
        def reconcile(request, _settings):
            return store.reconcile_feature_selection(request)
        try:
            # Two logical size classes, one physical process: bounded work, no polling.
            for host in cfg["hosts"]:
                assigned = sum(item["host_id"] == host["id"] for item in plan["items"])
                for _ in range(assigned * config["max_attempts"]):
                    step = p1.run_host_once(cfg, host["id"], submit=submit)
                    write_json(output / "STATUS.json", status(output))
                    if step["action"] == "IDLE":
                        break
            validate(path, config)
            phase1 = p1.finalize_if_ready(cfg, submit=submit, reconcile=reconcile)
            if phase1["action"] != "PHASE_1_COMPLETE":
                result = {"state": phase1["action"], "phase1": phase1, **status(output)}
                write_json(output / "REPORT.json", result)
                return result
            gate = p1.require_phase1_complete(cfg)
            final = read_json(output / "phase1/finalizer/result.json")
            # Check actual rows again on restart, including per-column receipts.
            for item in plan["items"]:
                terminal = read_json(output / "phase1/terminals" / (item["key"] + ".json"))
                phase1_readback(store, terminal["result"]["envelope"])
            profile_readback = phase1_readback(store, final["envelope"])
        finally:
            if store._engine is not None:
                store._engine.dispose()
        spec = validate(path, config)
        identity = "rebuild:" + binding["binding_sha256"]
        manifest = man.build_manifest(**spec["population"], identity=identity,
            identity_source={"binding_sha256": binding["binding_sha256"]},
            phase1={"mode": "PROFILE_ONLY", "gate_sha256": gate["gate_sha256"], "plan_sha256": plan["plan_sha256"]},
            causal_supported=[], data_root=path.resolve().parent)
        immutable(output / "MANIFEST.json", manifest)
        state = output / "phase23"
        campaign.plan(manifest_path=output / "MANIFEST.json", state_root=state, n_shards=config["n_shards"],
                      hosts=[{"host_id": "local", "size_class": "small"}], params=config["pairwise_params"])
        worker = campaign.run_worker(plan_path=state / "PLAN.json", state_root=state,
                                     data_root=path.resolve().parent, host_id="local")
        validate(path, config)
        warehouse = Warehouse(output / "phase23.duckdb")
        try:
            follow = campaign.follow_once(plan_path=state / "PLAN.json", state_root=state,
                terminal_dirs=[state / "terminals"], warehouse_path=output / "phase23.duckdb",
                data_root=path.resolve().parent, warehouse=warehouse, phase3_workers=1)
            tables = warehouse.reconcile(identity)["tables"]
            complete = follow["phase2_closed"] and follow["phase3_closed"]
            if complete:
                for name in ("PHASE_2_COMPLETE.json", "PHASE_3_FILTER_COMPLETE.json"):
                    closure = read_json(state / name)
                    require(man.digest({k: v for k, v in closure.items() if k != "closure_sha256"}) == closure["closure_sha256"],
                            "phase closure digest mismatch")
                    for table, count in closure["row_counts"].items():
                        require(tables[table]["count"] == count and tables[table]["rows_sha256"] == closure["table_sha256"][table],
                                f"phase23 readback mismatch: {table}")
        finally:
            warehouse.close()
        result = {"state": "PROFILE_FILTERS_COMPLETE" if complete else "PHASE23_INCOMPLETE",
                  "scope": spec["scope"], "identity": identity, "final_selection": False,
                  "causal_evidence_computed": False, "source_admission_issued": False,
                  "source_admission_verified": False,
                  "phase1_readback": profile_readback, "phase23_readback": tables,
                  "worker": worker, "follow": follow}
        write_json(output / "STATUS.json", status(output))
        write_json(output / "REPORT.json", result)
        return result


def make_demo(root):
    """Reuse the existing sensor fixture generator; mark it explicitly unadmitted."""
    from selection_demo import prepare
    from tools.fs_phase23_manifest import sha256_file
    import pandas as pd
    root.mkdir(parents=True, exist_ok=True)
    config = read_json(ROOT / "examples/synthetic.json")
    manifest = prepare(config, root)
    data_root = root / "bundle"
    data_root.mkdir(exist_ok=True)
    path = data_root / "REBUILD_INPUT.json"
    if path.exists():
        return path
    data = manifest["data"]
    x = pd.read_parquet(root / "data" / data["features_file"])
    ids = [f["feature_id"] for f in manifest["features"]]
    keys = [data["row_id_column"], data["timestamp_column"]]
    # The handoff contract requires explicit matrix order, also for the old demo.
    x = x[keys + ids]
    x.to_parquet(data_root / data["features_file"], index=False)
    y = pd.read_parquet(root / "data" / data["targets_file"])
    # Explicit fixture materialization, before hashing; the runner never masks inputs.
    for target in manifest["targets"]:
        endpoint = y[data["timestamp_column"]] + pd.Timedelta(hours=target["horizon_hours"])
        mask = endpoint >= pd.Timestamp("2020-02-01T00:00:00Z")
        for fold in manifest["folds"]:
            stop = fold["train_rows"][1]
            cutoff = y[data["timestamp_column"]].iloc[stop] if stop < len(y) else pd.Timestamp("2020-02-01T00:00:00Z")
            mask.iloc[:stop] |= endpoint.iloc[:stop] >= cutoff
        y.loc[mask, target["column"]] = float("nan")
    y[keys + [t["column"] for t in manifest["targets"]]].to_parquet(data_root / data["targets_file"], index=False)
    availability = x[keys].copy()
    for fid in ids:
        availability[fid] = x[data["timestamp_column"]]
    availability.to_parquet(data_root / "availability_train.parquet", index=False)
    write_json(data_root / "FIXTURE_ORIGIN.json", {"scope": "SYNTHETIC_NOT_ADMITTED", "seed": config["seed"]})
    population = {k: manifest[k] for k in ("population_id", "data", "features", "targets", "folds", "contract_source")}
    population["data"] = {k: v for k, v in data.items() if k not in {"canonical_columns_sha256", "split"}}
    for kind in ("features", "targets"):
        population["data"][f"{kind}_sha256"] = sha256_file(data_root / data[f"{kind}_file"])
    for feature in population["features"]:
        feature["availability_time"] = feature["feature_id"]
    spec = {"schema": "feature_selector.rebuild_input.v1", "scope": "SYNTHETIC", "created_at": "2026-10-18T00:00:00Z",
            "target_clock": "HOURLY_ELAPSED",
            "population": population, "train_period": ["2020-01-01T00:00:00Z", "2020-02-01T00:00:00Z"],
            "expected_monthly_rows": {"2020-01": len(x)},
            "availability": {"file": "availability_train.parquet", "sha256": sha256_file(data_root / "availability_train.parquet")},
            "admission": {"disposition": "SYNTHETIC_NOT_ADMITTED", "variable_ids": ids,
                          "evidence": [{"file": "FIXTURE_ORIGIN.json", "sha256": sha256_file(data_root / "FIXTURE_ORIGIN.json")}]}}
    write_json(path, spec)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("render", "run", "status", "demo", "finalize-profile"))
    parser.add_argument("--predictor-root", type=Path)
    parser.add_argument("--causal-root", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "examples/rebuild_cpu.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--terminals", type=Path)
    args = parser.parse_args()
    os.environ.update(CPU)
    try:
        if args.command == "finalize-profile":
            finalize_profile(args.plan, args.terminals, args.output)
            return 0
        require(args.predictor_root is not None and args.causal_root is not None, "both runtime roots are required")
        bootstrap(args.predictor_root.resolve(), args.causal_root.resolve())
        config = read_json(args.config)
        if args.command == "status":
            result = status(args.output)
        elif args.command == "render":
            render(args.input, config, args.predictor_root, args.causal_root, args.output)
            result = {"state": "RENDERED", "executed": False}
        else:
            path, output = args.input, args.output
            if args.command == "demo":
                path, output = make_demo(output / "fixture"), output / "run"
            result = run(path, config, args.predictor_root, args.causal_root, output)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0 if args.command in {"status", "render"} or result["state"] == "PROFILE_FILTERS_COMPLETE" else 2
    except Exception as exc:
        print(json.dumps({"state": "FAILED", "reason": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
