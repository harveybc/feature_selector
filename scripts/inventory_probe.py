#!/usr/bin/env python3
"""Probe financial-data's candidate inventory; never confer data admission.

Exit 2: structurally valid candidate, blocked pending an upstream admission
interface. Exit 1: invalid, unsupported or unreadable input. No success exit
exists: this command must not be used to authorize a selection successor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat

MAX_BYTES = 16 * 1024 * 1024
SCHEMA = "financial_data.required_variable_inventory.candidate.v1"
GROUPS = {
    "ALL_CATALOG_VARIABLES": "all_catalog_variables",
    "TRADING_REQUIRED": "trading_required",
    "MODEL_CANDIDATES": "model_candidates",
}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("NONFINITE_JSON")


def _finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        _nonfinite(value)
    return parsed


def _counts(document):
    """Check the producer's envelope and per-record counts, not data quality."""
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise ValueError("UNSUPPORTED_SCHEMA")
    if (document.get("state") != "CANDIDATE_NOT_ADMITTED"
            or document.get("admitted") is not False
            or document.get("selection_complete") is not False):
        raise ValueError("INVALID_CANDIDATE_STATE")
    if document.get("hardcoded_population_sizes") != []:
        raise ValueError("INVALID_POPULATION_POLICY")
    variables = document.get("variables")
    if not isinstance(variables, list):
        raise ValueError("INVALID_VARIABLES")
    if not variables:
        raise ValueError("EMPTY_POPULATION")
    counts = dict.fromkeys(GROUPS.values(), 0)
    counts.update(total_records=len(variables), files_present=0, files_missing=0)
    identities = set()
    for variable in variables:
        if not isinstance(variable, dict):
            raise ValueError("INVALID_VARIABLE")
        identity = variable.get("variable_id")
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("INVALID_VARIABLE_ID")
        if identity in identities:
            raise ValueError("DUPLICATE_VARIABLE_ID")
        identities.add(identity)
        group = variable.get("group")
        if not isinstance(group, str) or group not in GROUPS:
            raise ValueError("INVALID_VARIABLE_GROUP")
        counts[GROUPS[group]] += 1
        if "file_status" in variable:
            status = variable["file_status"]
            if status not in ("PRESENT", "MISSING"):
                raise ValueError("INVALID_FILE_STATUS")
            counts["files_present" if status == "PRESENT" else "files_missing"] += 1
    declared = document.get("denominator")
    if not isinstance(declared, dict):
        raise ValueError("INVALID_DENOMINATOR")
    for field, observed in counts.items():
        if type(declared.get(field)) is not int or declared[field] < 0:
            raise ValueError("INVALID_DENOMINATOR")
        if declared[field] != observed:
            raise ValueError("DENOMINATOR_MISMATCH")
    return counts


def probe(path: Path) -> dict:
    """Read at most MAX_BYTES of one regular file; return no raw input fields."""
    result = {
        "schema": "feature_selector.inventory_probe.v1",
        "state": "INVALID_INVENTORY", "candidate_contract_valid": False,
        "data_admission_complete": False, "selection_complete": False,
        "may_launch_selection": False, "source_bytes_verified": False,
        "input_sha256": None,
    }
    try:
        # Nonblocking open also prevents a supplied FIFO from becoming monitoring.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("INPUT_NOT_REGULAR_FILE")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(MAX_BYTES + 1)
        finally:
            os.close(fd)
        if len(raw) > MAX_BYTES:
            raise ValueError("INPUT_TOO_LARGE")
        result["input_sha256"] = hashlib.sha256(raw).hexdigest()
        document = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite,
                              parse_float=_finite_float)
        counts = _counts(document)
    except OSError:
        result["reason"] = "INPUT_UNREADABLE"
    except (json.JSONDecodeError, UnicodeError, RecursionError):
        result["reason"] = "INVALID_JSON"
    except ValueError as exc:
        result["reason"] = str(exc)
    else:
        result.update(
            state="BLOCKED_ADMISSION", candidate_contract_valid=True,
            reason="UPSTREAM_ADMISSION_INTERFACE_REQUIRED",
            denominator=counts,
            file_status_unreported_records=(counts["total_records"]
                                           - counts["files_present"] - counts["files_missing"]),
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.inventory)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 2 if result["state"] == "BLOCKED_ADMISSION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
