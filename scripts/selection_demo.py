#!/usr/bin/env python3
"""Run the pinned pairwise/ranking engines on a small synthetic sensor dataset.

This adapter demonstrates phases 2/3 and local OLAP readback. It does not run
causal inference, train a model or declare a final feature selection.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ("sensor", "duplicate", "squared", "noise", "sparse")


def check_predictor(path: Path) -> str:
    """Require the documented upstream revision before importing its engines."""
    expected = json.loads((ROOT / "upstream.lock.json").read_text())["predictor"]["commit"]
    proc = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=False)
    if proc.returncode or proc.stdout.strip() != expected:
        raise ValueError(f"predictor revision must be {expected}")
    dirty = subprocess.run(["git", "-C", str(path), "status", "--porcelain", "--", "tools", "olap"],
                           capture_output=True, text=True, check=True)
    if dirty.stdout.strip():
        raise ValueError("predictor revision has modified engine files; use a clean checkout")
    for relative in ("olap/store/src", "olap/duckdb_store/src", "."):
        sys.path.insert(0, str((path / relative).resolve()))
    return expected


def write_json(path: Path, value: dict) -> None:
    """Replace a small JSON record atomically inside the example directory."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def prepare(config: dict, output: Path) -> dict:
    """Generate TRAIN data once; reject reuse with different settings or bytes."""
    from tools import fs_phase23_manifest as manifest_api
    if config.get("schema") != "dataset_selection.synthetic_demo.v1":
        raise ValueError("unsupported configuration schema")
    for key, low, high in (("rows", 256, 4096), ("seed", 0, 2**32 - 1), ("n_shards", 1, 8)):
        if type(config.get(key)) is not int or not low <= config[key] <= high:
            raise ValueError(f"configuration {key} must be an integer in [{low}, {high}]")
    config_sha = manifest_api.digest(config)
    record = output / "PREPARED.json"
    if record.exists():
        previous = json.loads(record.read_text())
        if previous["config_sha256"] != config_sha:
            raise ValueError("configuration changed: use another output directory")
        manifest = manifest_api.load_manifest(output / "MANIFEST.json")
        if manifest["manifest_sha256"] != previous["manifest_sha256"]:
            raise ValueError("manifest digest changed")
        manifest_api.verify_data(manifest, output / "data")
        return manifest

    import numpy as np
    import pandas as pd
    n = config["rows"]
    rng = np.random.default_rng(config["seed"])
    signal = rng.normal(size=n)
    sparse = np.full(n, np.nan)
    sparse[:8] = rng.normal(size=8)
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC"),
        "row_id": np.arange(n), "sensor": signal, "duplicate": signal.copy(),
        "squared": signal**2, "noise": rng.normal(size=n), "sparse": sparse,
    })
    targets = frame[["timestamp", "row_id"]].copy()
    targets["load_next_hour"] = 0.7 * signal + 0.3 * signal**2 + rng.normal(0, 0.1, n)
    targets.loc[n - 1, "load_next_hour"] = np.nan
    data = output / "data"
    data.mkdir(exist_ok=True)
    frame.to_parquet(data / "features_train.parquet", index=False)
    targets.to_parquet(data / "targets_train.parquet", index=False)
    manifest = manifest_api.build_manifest(
        population_id=config["population_id"], identity=f"synthetic-demo:{config_sha}",
        identity_source={"kind": "SYNTHETIC_DEMO", "seed": config["seed"]},
        phase1={"state": "NOT_RUN", "scope": "SYNTHETIC_DEMO_ONLY"},
        data={"features_file": "features_train.parquet", "targets_file": "targets_train.parquet",
              "features_sha256": manifest_api.sha256_file(data / "features_train.parquet"),
              "targets_sha256": manifest_api.sha256_file(data / "targets_train.parquet"),
              "timestamp_column": "timestamp", "row_id_column": "row_id", "bar_hours": 1,
              "train_rows": n},
        features=[{"feature_id": f, "family": "sensor", "source": "synthetic:generated",
                   "transform": "identity", "unit": "arbitrary", "clock": "OBSERVED",
                   "availability_time": "timestamp", "support_h": 1,
                   "train_coverage": float(frame[f].notna().mean()), "source_bytes": n * 8}
                  for f in FEATURES],
        targets=[{"target_id": "load_next_hour", "column": "load_next_hour",
                  "family": "synthetic_load", "head": "regression", "horizon_hours": 1}],
        folds=[{"fold_id": "prefix_half", "train_rows": [0, n // 2]},
               {"fold_id": "prefix_three_quarters", "train_rows": [0, 3 * n // 4]}],
        causal_supported=[], contract_source="synthetic_demo_not_phase1_evidence", data_root=data,
    )
    manifest_api.write_manifest(manifest, output / "MANIFEST.json")
    write_json(record, {"config_sha256": config_sha, "config": config,
                        "manifest_sha256": manifest["manifest_sha256"]})
    return manifest


def run(config: dict, predictor_root: Path, output: Path) -> dict:
    """Resume real engine work, close local readback, and retain a scoped report."""
    revision = check_predictor(predictor_root)
    from tools import feature_pairwise_campaign as campaign
    from tools.fs_phase23_warehouse import Warehouse, core
    if not Path(campaign.__file__).resolve().is_relative_to(predictor_root.resolve()) or not \
            Path(core.__file__).resolve().is_relative_to(predictor_root.resolve()):
        raise ValueError("imported engine differs from the pinned predictor checkout")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".writer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = prepare(config, output)
        state = output / "campaign"
        plan_path = state / "PLAN.json"
        if not plan_path.exists():
            campaign.plan(manifest_path=output / "MANIFEST.json", state_root=state,
                          n_shards=config["n_shards"], hosts=[{"host_id": "local", "size_class": "small"}],
                          params=config.get("pairwise_params", {}))
        plan = campaign.load_plan(plan_path)
        if plan["manifest_sha256"] != manifest["manifest_sha256"]:
            raise ValueError("plan manifest digest differs from the prepared input")
        worker = campaign.run_worker(plan_path=plan_path, state_root=state,
                                     data_root=output / "data", host_id="local")
        wh = Warehouse(output / "metrics.duckdb")
        try:
            closure = campaign.follow_once(plan_path=plan_path, state_root=state,
                terminal_dirs=[state / "terminals"], warehouse_path=output / "metrics.duckdb",
                data_root=output / "data", warehouse=wh)
            if not closure["phase2_closed"] or not closure["phase3_closed"]:
                raise RuntimeError(f"demo incomplete: {closure}")
            readback = wh.reconcile(manifest["identity"])["tables"]
            # Verify existing closures through readback without writing new receipts.
            for name in ("PHASE_2_COMPLETE.json", "PHASE_3_FILTER_COMPLETE.json"):
                final = json.loads((state / name).read_text())
                from tools.fs_phase23_manifest import digest
                if digest({k: v for k, v in final.items() if k != "closure_sha256"}) != final["closure_sha256"]:
                    raise ValueError("closure digest mismatch")
                for table, count in final["row_counts"].items():
                    if readback[table]["count"] != count or \
                            readback[table]["rows_sha256"] != final["table_sha256"][table]:
                        raise ValueError(f"warehouse readback mismatch: {table}")
        finally:
            wh.close()
        result = {"state": "DEMO_FILTERS_COMPLETE", "scope": "SYNTHETIC_PHASES_2_3",
                  "upstream_revision": revision, "seed": config["seed"], "worker": worker,
                  "final_selection": False, "causal_evidence_computed": False,
                  "readback": readback, "methods": final["methods"]}
        write_json(output / "REPORT.json", result)
        return result


def status(predictor_root: Path, output: Path) -> dict:
    """Generate status and ETA from retained terminals without running tasks."""
    check_predictor(predictor_root)
    from tools.feature_selection_phase23_status import build_status
    state = output / "campaign"
    if not (state / "PLAN.json").exists():
        return {"state": "NOT_STARTED", "eta_seconds": None}
    return build_status(plan_paths=[state / "PLAN.json"], terminal_dirs=[state / "terminals"],
                        state_roots=[state], out_path=output / "STATUS.json")


def main() -> int:
    """Expose the example's run/resume and status commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "status"))
    parser.add_argument("--predictor-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "examples/synthetic.json")
    args = parser.parse_args()
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    try:
        result = (status(args.predictor_root, args.output) if args.command == "status" else
                  run(json.loads(args.config.read_text()), args.predictor_root, args.output))
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"state": "FAILED", "reason": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
