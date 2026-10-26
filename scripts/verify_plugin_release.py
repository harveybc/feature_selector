#!/usr/bin/env python3
"""Installed CPU smoke and byte-identical resume; emits a small verification record."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import subprocess
import sys

from feature_selector.io import atomic, read


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    output=Path(args.output).resolve()
    if output.exists():
        raise ValueError('Verification requires a new directory')
    command=[sys.executable,'-m','feature_selector','--load_config',str(root/'examples/plugin_demo.json'),
             '--output',str(output)]
    subprocess.run(command,check=True)
    paths=[output/'RESULT.json',*sorted((output/'evaluations').glob('*.json'))]
    before={p.name:(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in paths}
    subprocess.run(command,check=True)
    after={p.name:(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in paths}
    if before!=after:
        raise AssertionError('Resume changed completed results or rewrote evaluations')
    result=read(output/'RESULT.json')
    record=dict(schema='feature_selector.package_verification.v1',
        versions={name:metadata.version(name) for name in ('feature-selector','numpy','pytest')},
        selected=result['selected'],subset_evaluations=result['search']['evaluations'],
        termination=result['search']['termination'],search_complete=result['search_complete'],
        final_selection=result['final_selection'],scope=result['scope'],
        retained_files=len(before),resume_bytes_and_mtimes_equal=True,
        result_sha256=before['RESULT.json'][0])
    atomic(output/'PACKAGE_VERIFICATION.json',record)
    print(json.dumps(record,indent=2))


if __name__=='__main__':
    main()
