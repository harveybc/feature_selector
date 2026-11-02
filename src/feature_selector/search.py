"""Bounded sequential backward floating search with deterministic resumption."""
import math

from .contracts import require, validate_dataset, validate_score


class BudgetReached(Exception):
    pass


class FloatingBackward:
    api_version = 1
    plugin_params = dict(min_features=1, max_evaluations=128, tolerance=0.0)

    def select(self, dataset, evaluate, params):
        validate_dataset(dataset)
        params = {**self.plugin_params, **params}
        minimum, budget, tolerance = (params[k] for k in ('min_features','max_evaluations','tolerance'))
        require(type(minimum) is int and 1 <= minimum <= len(dataset['features']), 'MIN_FEATURES')
        require(type(budget) is int and budget > 0, 'EVALUATION_BUDGET')
        require(type(tolerance) in (int,float) and math.isfinite(tolerance) and tolerance >= 0, 'TOLERANCE')
        blocks = [tuple(b) for b in dataset['blocks']]
        cache, best, trace, visited = {}, {}, [], set()
        def ordered(keys):
            keep = {c for k in keys for c in blocks[k]}
            return [c for c in dataset['features'] if c in keep]
        def rank(keys):
            r = cache[keys]
            return (r['eligible'], r['score'] if r['score'] is not None else -math.inf,
                    -r['gap'] if r['gap'] is not None else -math.inf, tuple(-k for k in keys))
        def run(keys):
            keys = tuple(sorted(keys))
            if keys not in cache:
                if len(cache) >= budget:
                    raise BudgetReached
                cache[keys] = validate_score(evaluate(ordered(keys)))
                size = len(ordered(keys))
                if size not in best or rank(keys) > rank(best[size]):
                    best[size] = keys
            return keys
        current = tuple(range(len(blocks)))
        termination = 'MIN_SIZE'
        try:
            run(current)
            while True:
                visited.add(current)
                choices = [tuple(k for k in current if k != remove) for remove in current]
                choices = [c for c in choices if len(ordered(c)) >= minimum]
                if not choices:
                    break
                current = max((run(c) for c in choices), key=rank)
                trace.append(dict(operation='remove', features=ordered(current), **cache[current]))
                while True:
                    candidates = []
                    # Freeze cardinality incumbents before evaluating additions.
                    incumbents = {size: rank(keys)[:3] for size, keys in best.items()}
                    for k in range(len(blocks)):
                        candidate = tuple(sorted((*current, k)))
                        if k in current or candidate in visited:
                            continue
                        candidate = run(candidate)
                        size = len(ordered(candidate))
                        old = incumbents.get(size)
                        new = rank(candidate)[:3]
                        if old is None or (new[0] and not old[0]) or (new[0] == old[0] and new[1] > old[1] + tolerance):
                            candidates.append(candidate)
                    if not candidates:
                        break
                    current = max(candidates, key=rank)
                    visited.add(current)
                    trace.append(dict(operation='reinclude', features=ordered(current), **cache[current]))
                if current in visited and trace and trace[-1]['operation'] == 'remove':
                    termination = 'NO_NEW_PATH'
                    break
        except BudgetReached:
            termination = 'BUDGET'
        eligible = [k for k,r in cache.items() if r['eligible']]
        winner = None
        if eligible:
            top = max(cache[k]['score'] for k in eligible)
            near = [k for k in eligible if cache[k]['score'] >= top - tolerance]
            winner = min(near, key=lambda k:(len(ordered(k)), -cache[k]['score'], cache[k]['gap'], k))
        return dict(selected=ordered(winner) if winner is not None else None,
                    termination=termination, evaluations=len(cache), trace=trace,
                    best_by_size={str(n):dict(features=ordered(k), **cache[k]) for n,k in sorted(best.items())},
                    results=[dict(features=ordered(k), **v) for k,v in cache.items()],
                    scope='MODEL_SPECIFIC_DEVELOPMENT', globally_optimal=False)


class FixedSubset:
    api_version = 1
    plugin_params = dict(columns=[])

    def select(self, dataset, evaluate, params):
        from .contracts import subset_view
        cols = params['columns'] or dataset['features']
        cols = subset_view(dataset, cols)['features']
        result = validate_score(evaluate(cols))
        return dict(selected=cols if result['eligible'] else None, termination='FIXED_CONTROL',
                    evaluations=1, results=[dict(features=cols, **result)], trace=[],
                    globally_optimal=False, scope='MODEL_SPECIFIC_DEVELOPMENT')


class TwoPassGreedy:
    """One ordered deletion pass, then one pass over accepted deletions only."""
    api_version = 1
    plugin_params = dict(min_features=1, tolerance=0.0)

    def select(self, dataset, evaluate, params, progress=None):
        validate_dataset(dataset)
        params = {**self.plugin_params, **params}
        minimum, tolerance = params['min_features'], params['tolerance']
        require(type(minimum) is int and 1 <= minimum <= len(dataset['features']), 'MIN_FEATURES')
        require(type(tolerance) in (int,float) and math.isfinite(tolerance) and tolerance >= 0, 'TOLERANCE')
        blocks = dataset['blocks']; current = list(dataset['features'])
        cache, trace, removed = {}, [], []
        after_deletion = None

        def run(columns):
            key = tuple(columns)
            if key not in cache:
                cache[key] = validate_score(evaluate(columns))
            return cache[key]

        def snapshot(stage, termination=None):
            r = dict(selected=list(current), counts=dict(initial=len(dataset['features']),
                after_deletion=after_deletion, final=len(current) if termination else None),
                stage=stage, termination=termination, evaluations=len(cache), trace=list(trace),
                evaluation_bound=1+2*len(blocks), globally_optimal=False,
                scope='ORDERED_TWO_PASS_MODEL_SPECIFIC_DEVELOPMENT')
            if progress: progress(r)
            return r

        baseline = run(current)
        if not baseline['eligible']:
            r = snapshot('STOPPED', 'NO_ELIGIBLE_BASELINE'); r['selected'] = None
            return r
        for phase, items in ((1, blocks), (2, removed)):
            for block in items:
                before = list(current)
                wanted = set(current).difference(block) if phase == 1 else set(current).union(block)
                candidate = [c for c in dataset['features'] if c in wanted]
                if len(candidate) < minimum:
                    continue
                old, new = run(current), run(candidate)
                accepted = new['eligible'] and new['score'] > old['score'] + tolerance
                if accepted:
                    current = candidate
                    if phase == 1: removed.append(block)
                trace.append(dict(pass_number=phase, **{'pass':phase}, block=list(block),
                    before=before, candidate=candidate, after=list(current), accepted=bool(accepted),
                    before_score=old['score'], candidate_score=new['score'],
                    candidate_eligible=new['eligible']))
                snapshot('DELETE' if phase == 1 else 'REINSERT')
            if phase == 1:
                after_deletion = len(current)
                snapshot('DELETION_COMPLETE')
        r = snapshot('COMPLETE', 'TWO_PASSES_COMPLETE')
        r['results'] = [dict(features=list(k), **v) for k,v in cache.items()]
        return r
