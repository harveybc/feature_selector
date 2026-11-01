"""Predeclared structural contrasts, before an adaptive subset search."""
import re

from .contracts import require, subset_view, validate_dataset, validate_score


class FixedAblation:
    api_version = 1
    plugin_params = dict(arms=[])

    def plan(self, dataset, params):
        validate_dataset(dataset)
        require(set(params) <= {'arms'}, 'ABLATION_UNKNOWN_OPTION')
        arms = [dict(name='full', **subset_view(dataset, dataset['features']))]
        groups = {g['name']: g['columns'] for g in dataset['groups']}
        names = {'full'}
        subsets = {tuple(dataset['features'])}
        for arm in params.get('arms', []):
            require(set(arm) <= {'name', 'drop', 'drop_group'}, 'ABLATION_FIELDS')
            name = arm.get('name', '')
            require(isinstance(name, str) and re.fullmatch('[a-z][a-z0-9_]*', name)
                    and name not in names, 'ABLATION_NAME')
            require(('drop' in arm) != ('drop_group' in arm), 'ABLATION_DROP_SPEC')
            if 'drop_group' in arm:
                require(arm['drop_group'] in groups, 'ABLATION_UNKNOWN_GROUP')
                drop = groups[arm['drop_group']]
            else:
                drop = arm['drop']
            require(isinstance(drop, list) and drop and len(set(drop)) == len(drop)
                    and set(drop) <= set(dataset['features']), 'ABLATION_COLUMNS')
            kept = [c for c in dataset['features'] if c not in drop]
            require(tuple(kept) not in subsets, 'ABLATION_DUPLICATE_SUBSET')
            arms.append(dict(name=name, removed=list(drop), **subset_view(dataset, kept)))
            names.add(name)
            subsets.add(tuple(kept))
        return arms

    def select(self, dataset, evaluate, params):
        results = [dict(arm=a['name'], features=a['features'],
                        **validate_score(evaluate(a['features'])))
                   for a in self.plan(dataset, params)]
        return dict(selected=None, termination='DIAGNOSTIC_ONLY', evaluations=len(results),
                    results=results, trace=[], globally_optimal=False,
                    scope='MODEL_SPECIFIC_DEVELOPMENT')
