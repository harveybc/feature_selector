"""Example maintained/installed independently of the host application."""
from feature_selector.search import FixedSubset


class Plugin(FixedSubset):
    api_version = 1
    plugin_params = dict(columns=[])
