"""Pinned artifact/command bridges to scientific engines owned by other repos."""
from pathlib import Path
import os
import signal
import subprocess

from .contracts import require, validate_dataset, sha
from .io import atomic, digest, file_hash, read

STAGES = ('data_quality', 'profiles', 'causal', 'relationships',
          'candidate_generation', 'encoding', 'extractor_selection')
EVIDENCE_FIELDS = {
    'data_quality': ('inventory','coverage','outliers','availability','source_validation'),
    'profiles': ('per_feature','lag_structure','stationarity','fold_stability'),
    'causal': ('assumptions','conditional_association','multiplicity','placebos','counterfactuals','unidentified'),
    'relationships': ('alias_groups','pairwise','lagged','nonlinear','redundancy_groups'),
    'candidate_generation': ('methods','parent_component_contrasts','interaction_rescue','feature_decisions'),
    'encoding': ('per_feature','contrasts','train_fit_scope','relative_features'),
    'extractor_selection': ('profile_groups','expectations','comparisons','receptive_fields','combination_confirmation'),
    'confirmation': ('evaluation','selection_bias','activity','subset_identity'),
}


def local_path(value, base):
    p = Path(value).expanduser()
    return p.resolve() if p.is_absolute() else (Path(base) / p).resolve()


def checked_files(items, base):
    require(isinstance(items, list), 'FILES_LIST')
    for item in items:
        require(sha(item.get('sha256')), 'FILE_HASH_REQUIRED')
        path = local_path(item['path'], base)
        require(path.is_file() and file_hash(path) == item['sha256'], 'INPUT_FILE_CHANGED')


class ManifestDataset:
    api_version = 1
    plugin_params = dict(path='', sha256='')

    def load(self, params, base):
        path = local_path(params['path'], base)
        require(sha(params['sha256']) and file_hash(path) == params['sha256'], 'DATASET_MANIFEST_PIN')
        d = validate_dataset(read(path))
        require(d['scope'] == 'development', 'REAL_DATASET_SCOPE')
        checked_files(d.get('files', []), path.parent)
        require(d.get('files'), 'DATASET_FILES_REQUIRED')
        # Resolve paths before request hashing; the portable source manifest stays unchanged.
        for item in d['files']:
            item['path'] = str(local_path(item['path'], path.parent))
        return d


def stage_request(stage, context, run_id):
    return dict(schema='feature_selector.stage_request.v1', stage=stage,
                run_id=run_id, context_sha256=digest(context), context=context)


def validate_stage(result, request, base):
    require(result.get('schema') == 'feature_selector.stage_result.v1', 'STAGE_SCHEMA')
    require(result.get('stage') == request['stage'] and
            result.get('context_sha256') == request['context_sha256'], 'STAGE_CONTEXT_MISMATCH')
    require(result.get('status') == 'COMPLETE', 'STAGE_NOT_COMPLETE')
    require(result.get('scope') == request['context']['scope'], 'STAGE_SCOPE')
    require(isinstance(result.get('evidence'), dict) and result['evidence'], 'STAGE_EVIDENCE')
    checked_files(result.get('files', []), base)
    if request['context']['scope'] != 'synthetic':
        require(result.get('files'), 'REAL_STAGE_FILES_REQUIRED')
        require(all(k in result['evidence'] for k in EVIDENCE_FIELDS[request['stage']]), 'INCOMPLETE_STAGE_EVIDENCE')
        for key in EVIDENCE_FIELDS[request['stage']]:
            item = result['evidence'][key]
            require(isinstance(item,dict) and item.get('status') in
                    ('MEASURED','NOT_IDENTIFIED','NOT_APPLICABLE') and item.get('detail'), 'EVIDENCE_ITEM')
    if request['stage'] == 'confirmation':
        require(type(result.get('accepted')) is bool and
                result.get('selected') == request['context'].get('selected'), 'CONFIRMATION_SUBSET')
    return result


class ArtifactStage:
    api_version = 1
    plugin_params = dict(path='', sha256='')

    def run(self, request, params, work, base):
        path = local_path(params['path'], base)
        require(sha(params['sha256']) and file_hash(path) == params['sha256'], 'STAGE_ARTIFACT_PIN')
        r = read(path)
        validate_stage(r, request, path.parent)
        for item in r.get('files', []):
            item['path'] = str(local_path(item['path'], path.parent))
        return r


def execute(command, pins, request, work, base, timeout):
    require(isinstance(command,list) and command and all(isinstance(x,str) for x in command), 'COMMAND_ARGV')
    require(type(timeout) in (int,float) and 0 < timeout <= 604800, 'COMMAND_TIMEOUT')
    require(pins, 'COMMAND_SOURCE_PINS_REQUIRED')
    checked_files(pins, base)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    req, response = work / 'REQUEST.json', work / 'RESPONSE.json'
    require(not response.exists(), 'STALE_COMMAND_RESPONSE')
    atomic(req, request)
    require(any('{request}' in a for a in command) and any('{response}' in a for a in command), 'COMMAND_PLACEHOLDERS')
    args = [s.replace('{request}',str(req)).replace('{response}',str(response)) for s in command]
    # No shell parsing; external implementations may use their own pinned Python environment.
    with (work / 'stdout.log').open('wb') as out, (work / 'stderr.log').open('wb') as err:
        with subprocess.Popen(args, cwd=base, stdout=out, stderr=err, start_new_session=True) as child:
            try:
                child.wait(timeout=timeout)
            except BaseException:
                try:
                    os.killpg(child.pid,signal.SIGTERM)
                    child.wait(timeout=5)
                finally:
                    try:
                        os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait()
                raise
    require(child.returncode == 0, 'COMMAND_FAILED:' + str(child.returncode))
    require(response.is_file(), 'COMMAND_RESPONSE_MISSING')
    checked_files(pins, base)
    return read(response)


class CommandStage:
    api_version = 1
    plugin_params = dict(command=[], source_pins=[], timeout_seconds=3600)

    def run(self, request, params, work, base):
        result = execute(params['command'], params['source_pins'], request, work, base, params['timeout_seconds'])
        validate_stage(result, request, base)
        for item in result.get('files', []):
            item['path'] = str(local_path(item['path'], base))
        return result
