"""Bridge that requires real RL training receipts rather than proxy scores."""
import math
from .contracts import require, sha, finite
from .io import digest
from .stages import execute, checked_files

TRADING_METRICS = ('profit', 'sharpe', 'max_drawdown', 'orders', 'orders_per_week',
                   'win_rate', 'buy_orders', 'sell_orders', 'buy_win_rate',
                   'sell_win_rate', 'early_closes', 'costs')


class RLModelEvaluator:
    api_version = 1
    production_rl = True
    plugin_params = dict(command=[], source_pins=[], timeout_seconds=3600,
                         model_id='', model_sha256='', engine_sha256='',
                         training_budget={}, score_metric='sharpe',
                         minimum_orders_per_week=2.0, max_gap=None,
                         cost_mode='configured', cost_profile={}, selection_use='cost_aware')

    def validate(self, params):
        require(params['model_id'] and sha(params['model_sha256']) and sha(params['engine_sha256']), 'REAL_MODEL_ID_REQUIRED')
        require(isinstance(params['training_budget'],dict) and params['training_budget'], 'TRAINING_BUDGET_REQUIRED')
        require(params['score_metric'] in ('sharpe','profit'), 'SCORE_METRIC')
        require(finite(params['minimum_orders_per_week']) and params['minimum_orders_per_week'] >= 2, 'ACTIVITY_REQUIREMENT')
        require(params['max_gap'] is None or finite(params['max_gap']) and params['max_gap'] >= 0, 'GAP_LIMIT')
        require(params['cost_mode'] in ('configured','zero_cost'), 'COST_MODE')
        require(params['selection_use'] in ('cost_aware','diagnostic'), 'SELECTION_USE')
        profile = params['cost_profile']
        # Canonical cost components carry their units/settings plus numerical charge rates.
        require(isinstance(profile,dict) and set(profile)=={'spread','slippage','commission','financing'}, 'COST_PROFILE')
        rates=[]
        for name, component in profile.items():
            require(isinstance(component,dict) and set(component)=={'rates','settings'}
                    and isinstance(component['rates'],list) and component['rates']
                    and isinstance(component['settings'],dict) and component['settings'], 'COST_PROFILE_COMPONENT')
            require(all(finite(x) and (name=='financing' or x>=0) for x in component['rates']), 'COST_PROFILE_RATE')
            rates.extend(component['rates'])
        if params['cost_mode']=='zero_cost':
            require(params['selection_use']=='diagnostic','ZERO_COST_DIAGNOSTIC_ONLY')
        if params['selection_use']=='cost_aware':
            require(any(x!=0 for x in rates), 'NONZERO_COST_PROFILE')

    def can_release(self, params):
        return params['cost_mode']=='configured' and params['selection_use']=='cost_aware'

    def evaluate(self, request, context, params, work, base):
        self.validate(params)
        require(context['scope'] == 'development', 'RL_REQUIRES_REAL_ADMITTED_DATA')
        result = execute(params['command'], params['source_pins'], request, work, base, params['timeout_seconds'])
        return self.verify(result, request, params, base)

    def verify(self, result, request, params, base):
        self.validate(params)
        require(result.get('schema') == 'feature_selector.rl_result.v1', 'RL_RECEIPT_SCHEMA')
        require(result.get('request_sha256') == digest(request), 'RL_REQUEST_MISMATCH')
        require(result.get('cost_mode')==params['cost_mode'], 'RL_COST_MODE')
        require(result.get('cost_profile_sha256')==digest(params['cost_profile']), 'RL_COST_PROFILE')
        for key in ('features','groups','seed','support_hash','scaler_hash','splits'):
            require(result.get(key) == request[key], 'RL_RECEIPT_MISMATCH:' + key)
        for key in ('model_id','model_sha256','engine_sha256','training_budget'):
            require(result.get(key) == params[key], 'RL_MODEL_MISMATCH:' + key)
        require(result.get('fresh_training') is True and result.get('test_access') is False
                and result.get('observation_contract') == request['constraints'], 'RL_TRAINING_CONTRACT')
        require(type(result.get('parameter_count')) is int and result['parameter_count'] > 0, 'RL_PARAMETER_COUNT')
        require(result.get('artifacts'), 'RL_ARTIFACTS_REQUIRED')
        checked_files(result['artifacts'], base)
        metrics = result['metrics']
        require(set(metrics) == {'train','selection'}, 'RL_METRIC_SPLITS')
        components=result.get('cost_components',{})
        require(set(components)=={'train','selection'}, 'RL_COST_COMPONENT_SPLITS')
        for split_name,split in metrics.items():
            costs=components[split_name]
            require(isinstance(costs,dict) and set(costs)=={'spread','slippage','commission','financing'}
                    and all(finite(v) and (k=='financing' or v>=0) for k,v in costs.items()), 'RL_COST_COMPONENTS')
            require(finite(split.get('costs')) and math.isclose(sum(costs.values()),split['costs'],rel_tol=1e-9,abs_tol=1e-8), 'RL_COST_RECONCILIATION')
            if params['cost_mode']=='zero_cost':
                require(all(v==0 for v in costs.values()), 'RL_ZERO_COST_NONZERO_CHARGE')
            require(all(k in split for k in TRADING_METRICS), 'RL_METRICS_MISSING')
            for k in TRADING_METRICS:
                require(finite(split[k]) or (k in ('sharpe','win_rate','buy_win_rate','sell_win_rate') and split[k] is None), 'RL_METRIC_NONFINITE:' + k)
            require(all(type(split[k]) is int and split[k] >= 0 for k in ('orders','buy_orders','sell_orders','early_closes')), 'RL_COUNTS')
            require(split['orders'] == split['buy_orders'] + split['sell_orders'], 'RL_DIRECTION_COUNT')
            require(split['early_closes'] <= split['orders'], 'RL_CLOSE_COUNT')
            for k in ('win_rate','buy_win_rate','sell_win_rate'):
                require(split[k] is None or 0 <= split[k] <= 1, 'RL_WIN_RATE_UNIT')
            for rate,count in (('win_rate','orders'),('buy_win_rate','buy_orders'),('sell_win_rate','sell_orders')):
                require((split[rate] is None) == (split[count] == 0), 'RL_UNSUPPORTED_RATE')
            require(0 <= split['max_drawdown'] <= 1 and split['orders_per_week'] >= 0, 'RL_METRIC_UNIT')
        key = params['score_metric']
        train, val = metrics['train'][key], metrics['selection'][key]
        gap = max(0.0, train - val) if train is not None and val is not None else None
        eligible = metrics['selection']['orders_per_week'] >= params['minimum_orders_per_week']
        eligible = eligible and gap is not None and (params['max_gap'] is None or gap <= params['max_gap'])
        return dict(score=val if gap is not None else None, train_score=train,
                    gap=gap, eligible=eligible, native=result)
