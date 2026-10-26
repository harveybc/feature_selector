"""Full ordered methodology; existing scientific engines remain pluggable."""
import copy
import statistics

from .contracts import require, validate_dataset, subset_view, validate_score
from .io import digest
from .stages import STAGES, stage_request, validate_stage, checked_files


class CausalSelection:
    api_version = 1
    plugin_params = dict(require_confirmation=True)

    def run(self, config, plugins, store, context, base, run_id):
        require(config['methodology']['params']['require_confirmation'] is True, 'CONFIRMATION_CANNOT_BE_DISABLED')
        required = set(STAGES) | {'confirmation'}
        require(set(config['stages']) == required, 'METHODOLOGY_REQUIRES_ALL_STAGES')
        evaluator = plugins['evaluator']
        if context['scope'] == 'development':
            require(getattr(evaluator, 'production_rl', False), 'REAL_RL_EVALUATOR_REQUIRED')
        evidence = []
        def attempt(kind, key, action):
            cache_name = kind + '/' + key + '.json'
            cached = store.cache(cache_name)
            if cached is not None:
                return cached
            errors = []
            for i in range(config['max_attempts']):
                work = store.root / 'attempts' / kind / key / str(i)
                if work.exists():
                    continue
                work.mkdir(parents=True)
                store.save('STATUS.json',dict(state='RUNNING', phase=kind, unit=key, attempt=i+1))
                try:
                    result = action(work)
                    store.retain(cache_name, result)
                    return result
                except Exception as exc:
                    error = dict(type=type(exc).__name__, message=str(exc))
                    store.save(str(work.relative_to(store.root) / 'ERROR.json'), error)
                    errors.append(error)
            raise ValueError('ATTEMPTS_EXHAUSTED:' + kind + ':' + key + ':' + str(errors))
        def stage(name):
            request = stage_request(name, context, run_id)
            obj, params = plugins['stages.'+name], config['stages'][name]['params']
            result = attempt('stages',digest(request),lambda work:obj.run(request,params,work,base))
            validate_stage(result, request, base)
            evidence.append(dict(stage=name, sha256=digest(result), result=result))
            if name != 'confirmation':
                updates = result.get('updates',{})
                require(set(updates) <= {'features','groups','blocks','representation','feature_metadata','support_hash','scaler_hash'}, 'STAGE_UPDATE_KEYS')
                if updates:
                    old = context['scope'], context['constraints'], context['splits']
                    context.update(copy.deepcopy(updates))
                    validate_dataset(context)
                    require(old == (context['scope'],context['constraints'],context['splits']), 'STAGE_CHANGED_CONTRACT')
                context.setdefault('stage_evidence',{})[name] = digest(result)
            return result
        for name in STAGES:
            stage(name)
        ep = config['evaluator']['params']
        if hasattr(evaluator, 'validate'):
            evaluator.validate(ep)
        def evaluate(columns):
            view = subset_view(context,columns)
            records = []
            for seed in config['seeds']:
                request = dict(schema='feature_selector.evaluation_request.v1', run_id=run_id,
                    context_sha256=digest(context), **view, seed=seed,
                    representation=context['representation'], support_hash=context['support_hash'],
                    scaler_hash=context['scaler_hash'], splits=context['splits'],
                    constraints=context['constraints'], evaluator=ep,
                    input_files=context.get('files',[]))
                key = digest(request)
                def compute(work):
                    return validate_score(evaluator.evaluate(request,context,ep,work,base))
                r = attempt('evaluations',key,compute)
                validate_score(r)
                if context['scope'] == 'development':
                    # Verify retained native receipts again, including weights/artifact hashes.
                    verified = evaluator.verify(r['native'],request,ep,base)
                    require(r == verified, 'CACHED_EVALUATION_MISMATCH')
                records.append(r)
            if any(r['score'] is None for r in records):
                return dict(score=None,train_score=None,gap=None,eligible=False,score_std=None,
                            seeds=config['seeds'],per_seed=records)
            return dict(score=statistics.mean(r['score'] for r in records),
                        train_score=statistics.mean(r.get('train_score',0) for r in records),
                        gap=statistics.mean(r['gap'] for r in records),
                        eligible=all(r['eligible'] for r in records),
                        score_std=statistics.stdev(r['score'] for r in records) if len(records)>1 else 0,
                        seeds=config['seeds'], per_seed=records)
        search = plugins['selector'].select(context,evaluate,config['selector']['params'])
        context['selected'] = search['selected']
        context['search_sha256'] = digest(search)
        store.immutable('SEARCH.json',search)
        confirmation = stage('confirmation')
        complete = search['termination'] != 'BUDGET'
        cost_aware = not hasattr(evaluator,'can_release') or evaluator.can_release(ep)
        release = (context['scope']=='development' and cost_aware and complete and search['selected'] is not None
                   and confirmation['accepted'])
        checked_files(context.get('files',[]),base)
        return dict(schema='feature_selector.result.v1', run_id=run_id, scope=context['scope'],
                    selected=search['selected'], search=search, stages=evidence,
                    search_complete=complete, final_selection=release,
                    selection_use='cost_aware' if cost_aware else 'diagnostic',
                    financial_result=context['scope']=='development',
                    note='Model-specific development selection, not a global optimum or TEST performance.')
