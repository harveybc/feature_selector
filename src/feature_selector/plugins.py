"""Installed entry points only; no path scanning or first-match ambiguity."""
import importlib
import importlib.metadata as md
import inspect
from pathlib import Path

from .io import digest, file_hash

ROLES = ('pipelines', 'methodologies', 'selectors', 'evaluators', 'datasets', 'stages')


def resolve(role, name):
    if role not in ROLES or not isinstance(name, str):
        raise ValueError('PLUGIN_ROLE_OR_NAME')
    matches = list(md.entry_points(group='feature_selector.' + role, name=name))
    if len(matches) != 1:
        raise ValueError(('PLUGIN_AMBIGUOUS' if matches else 'PLUGIN_NOT_INSTALLED') + f': {role}/{name}')
    ep = matches[0]
    cls = ep.load()
    if getattr(cls, 'api_version', None) != 1 or not isinstance(getattr(cls, 'plugin_params', None), dict):
        raise ValueError('PLUGIN_API_VERSION_OR_PARAMS')
    source = Path(inspect.getfile(cls)).resolve()
    package = importlib.import_module(cls.__module__.split('.')[0])
    # Hash the plugin package, never all of site-packages for a single-file plugin.
    if hasattr(package, '__path__'):
        files = {}
        for i, location in enumerate(sorted(package.__path__)):
            root = Path(location).resolve()
            files.update({str(i)+'/'+str(p.relative_to(root)):file_hash(p)
                          for p in sorted(root.rglob('*.py')) if '__pycache__' not in p.parts})
    else:
        files = {source.name:file_hash(source)}
    dist = ep.dist
    witness = dict(role=role, name=name, entry_point=ep.value,
                   distribution=dist.metadata['Name'], version=dist.version,
                   source_sha256=digest(files), api_version=1)
    return cls(), witness


def installed():
    return {role: sorted(ep.name for ep in md.entry_points(group='feature_selector.' + role))
            for role in ROLES}
