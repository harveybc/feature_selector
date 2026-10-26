"""Predictor-style precedence, with namespaced plugin parameters."""
import copy
import json
from pathlib import Path

from .io import read
from .plugins import resolve

DEFAULTS = dict(pipeline=dict(plugin='sequential', params={}),
                methodology=dict(plugin='causal_selection', params={}),
                selector=dict(plugin='floating_backward', params={}),
                evaluator=dict(plugin='rl_model', params={}),
                dataset=dict(plugin='manifest', params={}), stages={},
                seeds=[7, 19, 43], output='output/selection', max_attempts=2)
ROLE_MAP = dict(pipeline='pipelines', methodology='methodologies', selector='selectors',
                evaluator='evaluators', dataset='datasets')


def merge(*values):
    result = {}
    for value in values:
        for key, item in value.items():
            if isinstance(item, dict) and isinstance(result.get(key), dict):
                result[key] = merge(result[key], item)
            else:
                result[key] = copy.deepcopy(item)
    return result


def overrides(items):
    result = {}
    for item in items:
        key, sep, raw = item.partition('=')
        if not sep or not key or any(not k for k in key.split('.')):
            raise ValueError('SET_REQUIRES_PATH_EQUALS_JSON')
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        node = result
        parts = key.split('.')
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                raise ValueError('SET_PATH_COLLISION')
        node[parts[-1]] = value
    return result


def prepare(path, cli=None):
    raw = read(path)
    if not isinstance(raw, dict):
        raise ValueError('CONFIG_OBJECT_REQUIRED')
    # Parameters of the replaced plugin must not leak into its replacement.
    for key, value in (cli or {}).items():
        if key in ROLE_MAP and isinstance(value, dict) and 'plugin' in value:
            if value['plugin'] != raw.get(key, DEFAULTS[key]).get('plugin'):
                raw[key] = dict(plugin=value['plugin'], params={})
        if key == 'stages' and isinstance(value, dict):
            for name, stage in value.items():
                old = raw.get('stages',{}).get(name,{})
                if isinstance(stage,dict) and 'plugin' in stage and stage['plugin'] != old.get('plugin'):
                    raw.setdefault('stages',{})[name] = dict(plugin=stage['plugin'], params={})
    chosen = merge(DEFAULTS, raw, cli or {})
    unknown = set(chosen) - set(DEFAULTS)
    if unknown:
        raise ValueError('UNKNOWN_CONFIG_KEYS: ' + ','.join(sorted(unknown)))
    plugins, witnesses, defaults = {}, {}, {}
    specs = [(key, role, chosen[key]) for key, role in ROLE_MAP.items()]
    specs += [('stages.' + name, 'stages', spec) for name, spec in chosen['stages'].items()]
    for key, role, spec in specs:
        if not isinstance(spec, dict) or set(spec) - {'plugin', 'params'} or 'plugin' not in spec:
            raise ValueError('PLUGIN_SPEC: ' + key)
        obj, witness = resolve(role, spec['plugin'])
        plugins[key], witnesses[key] = obj, witness
        default_spec = dict(plugin=spec['plugin'], params=obj.plugin_params)
        if key.startswith('stages.'):
            defaults.setdefault('stages', {})[key.split('.', 1)[1]] = default_spec
        else:
            defaults[key] = default_spec
    effective = merge(defaults, DEFAULTS, raw, cli or {})
    for key, _, _ in specs:
        spec = effective['stages'][key.split('.',1)[1]] if key.startswith('stages.') else effective[key]
        if not isinstance(spec['params'], dict):
            raise ValueError('PLUGIN_PARAMS_OBJECT: ' + key)
        extra = set(spec['params']) - set(plugins[key].plugin_params)
        if extra:
            raise ValueError('UNKNOWN_PLUGIN_PARAMS: ' + key + ': ' + ','.join(sorted(extra)))
    seeds = effective['seeds']
    if not seeds or any(type(s) is not int or s < 0 for s in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError('SEEDS')
    if type(effective['max_attempts']) is not int or not 1 <= effective['max_attempts'] <= 3:
        raise ValueError('MAX_ATTEMPTS')
    return effective, plugins, witnesses, Path(path).resolve().parent
