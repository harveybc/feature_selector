"""Selector-owned TRAIN handoff checks; never an upstream admission authority."""
import json
from pathlib import Path
import re


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read_json(path):
    from inventory_probe import _object, _nonfinite, _finite_float
    with Path(path).open("rb") as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    require(len(raw) <= 16 * 1024 * 1024, "JSON exceeds 16 MiB")
    return json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite,
                      parse_float=_finite_float)


def member(root, name):
    require(isinstance(name, str) and Path(name).name == name and name not in {"", ".", ".."},
            "bundle members must be direct relative filenames")
    path = (root / name).resolve()
    require(path.parent == root.resolve() and path.is_file(), "missing or escaping bundle member")
    return path


def validate(path, config):
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    from tools.fs_phase23_manifest import sha256_file, FORBIDDEN_SPLIT_TOKENS

    require(config.get("schema") == "feature_selector.rebuild_config.v1", "unknown rebuild config")
    require(config.get("phase1_mode") == "PROFILE_ONLY", "this adapter implements PROFILE_ONLY")
    require(config.get("target_pack_id") in {"ETH", "EURUSD"}, "unsupported upstream target pack")
    require(config.get("calendar") in {"24x7", "weekday_24h", "observed_only"}, "unsupported profiler calendar")
    for key in ("max_file_bytes", "max_rows", "max_features", "max_attempts", "worker_timeout_seconds", "n_shards"):
        require(type(config.get(key)) is int and config[key] > 0, f"invalid {key}")
    require(config["max_attempts"] <= 3 and config["n_shards"] <= 64, "dispatch bounds exceeded")
    spec = read_json(path)
    root = Path(path).resolve().parent
    require(spec.get("schema") == "feature_selector.rebuild_input.v1", "unknown handoff schema")
    require(spec.get("scope") in {"SYNTHETIC", "ADMITTED_TRAIN"}, "explicit input scope required")
    require(spec.get("target_clock") == "HOURLY_ELAPSED", "target clock must be HOURLY_ELAPSED")
    population = spec["population"]
    require(not {"phase1", "identity_source", "causal_supported", "identity"} & population.keys(),
            "old phase1/selection identities cannot be supplied")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+", population["population_id"]) is not None,
            "population id must be a safe logical identifier")
    features = population["features"]
    ids = [f["feature_id"] for f in features]
    require(2 <= len(ids) <= config["max_features"] and len(ids) == len(set(ids)), "invalid variable population")
    require(all(re.fullmatch(r"[A-Za-z0-9_.-]+", fid) for fid in ids), "unsafe variable id")
    for feature in features:
        for field in ("family", "source", "transform", "unit", "clock", "availability_time"):
            require(isinstance(feature.get(field), str) and bool(feature[field]), f"missing feature {field}")
        require(feature["availability_time"] == feature["feature_id"], "availability column must match variable id")
    admission = spec["admission"]
    require(sorted(admission["variable_ids"]) == sorted(ids), "admission variable membership differs")
    if spec["scope"] == "SYNTHETIC":
        require(admission.get("disposition") == "SYNTHETIC_NOT_ADMITTED", "synthetic scope cannot assert admission")
    else:
        require(admission.get("disposition") == "ADMITTED" and admission.get("authority") == "financial-data",
                "owner admission attestation required")
    data = population["data"]
    require(all(not any(token in data[f"{kind}_file"].lower() for token in FORBIDDEN_SPLIT_TOKENS)
                for kind in ("features", "targets")), "non-TRAIN input filename")
    refs = {kind: {"file": data[f"{kind}_file"], "sha256": data[f"{kind}_sha256"]}
            for kind in ("features", "targets")}
    refs["availability"] = spec["availability"]
    require(isinstance(admission.get("evidence"), list) and admission["evidence"], "admission evidence required")
    for ref in [*refs.values(), *admission["evidence"]]:
        file = member(root, ref["file"])
        require(file.stat().st_size <= config["max_file_bytes"], "file exceeds configured byte bound")
        require(sha256_file(file) == ref["sha256"], "input file hash mismatch")
    targets = population["targets"]
    tids = [t["target_id"] for t in targets]
    columns = [t["column"] for t in targets]
    require(targets and len(set(tids)) == len(tids) and len(set(columns)) == len(columns), "invalid targets")
    require(len(targets) <= 64, "target count exceeds bound")
    require(all(type(t["horizon_hours"]) is int and t["horizon_hours"] > 0 for t in targets), "invalid target horizon")
    keys = [data["row_id_column"], data["timestamp_column"]]
    require(len(set(keys + ids + columns)) == len(keys + ids + columns), "overlapping feature/target/key names")
    require(type(data["bar_hours"]) is int and data["bar_hours"] == 1, "this adapter supports hourly decision grids")
    frames = {}
    for kind, ref in refs.items():
        file = member(root, ref["file"])
        metadata = pq.ParquetFile(file)
        wanted = keys + (columns if kind == "targets" else ids)
        require(metadata.schema_arrow.names == wanted, f"{kind} column order/membership differs")
        require(0 < metadata.metadata.num_rows <= config["max_rows"], "row limit exceeded")
        frames[kind] = pd.read_parquet(file)
    x, y, availability = (frames[k] for k in ("features", "targets", "availability"))
    require(len(x) == data["train_rows"], "TRAIN row denominator differs")
    require(x[keys].equals(y[keys]) and x[keys].equals(availability[keys]), "row identity alignment differs")
    require(not x[keys].isna().any().any() and x[keys[0]].is_unique, "missing/duplicate row ids")
    ts = x[keys[1]]
    require(isinstance(ts.dtype, pd.DatetimeTZDtype) and str(ts.dt.tz) == "UTC", "decision times must be UTC")
    require(ts.is_unique and ts.is_monotonic_increasing, "decision times must be unique and ordered")
    start, end = map(pd.Timestamp, spec["train_period"])
    require(start.tzinfo is not None and end.tzinfo is not None and start < end, "invalid TRAIN interval")
    require(((ts >= start) & (ts < end)).all(), "non-TRAIN timestamp")
    months = pd.period_range(start.tz_localize(None), (end - pd.Timedelta(nanoseconds=1)).tz_localize(None), freq="M")
    expected = spec["expected_monthly_rows"]
    require(set(expected) == {str(m) for m in months}, "required month denominator differs")
    actual = ts.dt.strftime("%Y-%m").value_counts().to_dict()
    require(all(type(n) is int and n > 0 and actual.get(m, 0) == n for m, n in expected.items()),
            "prepared monthly support differs")
    for feature in features:
        fid = feature["feature_id"]
        at = availability[fid]
        require(isinstance(at.dtype, pd.DatetimeTZDtype) and str(at.dt.tz) == "UTC", "availability must be UTC")
        require(not at.isna().any() and (at <= ts).all(), "input available after decision time")
        require(pd.api.types.is_numeric_dtype(x[fid]) and not np.isinf(x[fid]).any(), "invalid numeric feature")
        require(abs(float(x[fid].notna().mean()) - feature["train_coverage"]) < 1e-12, "coverage metadata differs")
    require(all(pd.api.types.is_numeric_dtype(y[c]) and not np.isinf(y[c]).any() for c in columns),
            "invalid target values")
    folds = population["folds"]
    require(folds and len({f["fold_id"] for f in folds}) == len(folds), "invalid folds")
    require(all(f["train_rows"][0] == 0 and 0 < f["train_rows"][1] <= len(x) for f in folds),
            "only prefix TRAIN folds supported")
    for target in targets:
        endpoint = ts + pd.Timedelta(hours=target["horizon_hours"])
        finite = y[target["column"]].notna()
        require(not (finite & (endpoint >= end)).any(), "finite target reaches exclusive TRAIN boundary")
        for fold in folds:
            stop = fold["train_rows"][1]
            cutoff = ts.iloc[stop] if stop < len(ts) else end
            require(not (finite.iloc[:stop] & (endpoint.iloc[:stop] >= cutoff)).any(),
                    "finite target reaches exclusive fold boundary")
    return spec
