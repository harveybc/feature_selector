"""Small reproducible CPU example. Never a financial or RL proxy selection."""
import numpy as np

from .contracts import require
from .io import digest


class SyntheticDataset:
    api_version = 1
    plugin_params = dict(seed=41, train_rows=240, validation_rows=120)

    def load(self, params, base):
        require(type(params['seed']) is int and params['seed'] >= 0, 'DEMO_SEED')
        require(all(type(params[k]) is int and params[k]>=32 for k in ('train_rows','validation_rows')), 'DEMO_ROWS')
        require(params['train_rows'] + params['validation_rows'] <= 10000, 'DEMO_ROW_LIMIT')
        rng = np.random.default_rng(params['seed'])
        n = params['train_rows'] + params['validation_rows']
        a, b, noise, redundant, weak = rng.normal(size=(5,n))
        x = np.column_stack((a,b,noise,a + redundant*.001,weak))
        y = 2*a - b + rng.normal(scale=.1,size=n)
        split = params['train_rows']
        mean,std = x[:split].mean(0), x[:split].std(0)
        cols = ['signal_a','signal_b','noise','redundant_a','weak_noise']
        data = dict(x=x.tolist(),y=y.tolist(),train_rows=split)
        return dict(schema='feature_selector.dataset.v1',scope='synthetic',
            features=cols, blocks=[[c] for c in cols],
            groups=[dict(name='signals',columns=cols[:2],extractor='linear_demo'),
                    dict(name='others',columns=cols[2:],extractor='linear_demo')],
            support_hash=digest(data),scaler_hash=digest(dict(mean=mean.tolist(),std=std.tolist())),
            representation=dict(id='synthetic_linear_demo_not_RL'),
            splits=dict(train=['2020-01-01','2023-07-01'],selection=['2023-07-01','2024-01-01'],test_start='2025-01-01'),
            constraints=dict(agent_state='none',scaling='fixed_train',clipping=False,fit_scope='train_only',test_access=False),
            data=data)


class SyntheticEvaluator:
    api_version = 1
    plugin_params = dict(ridge=0.1)

    def evaluate(self, request, context, params, work, base):
        require(context['scope']=='synthetic','DEMO_CANNOT_EVALUATE_MARKET_DATA')
        require(type(params['ridge']) in (int,float) and params['ridge']>0,'DEMO_RIDGE')
        data=context['data']
        indices=[context['features'].index(c) for c in request['features']]
        x=np.asarray(data['x'])[:,indices];y=np.asarray(data['y']);n=data['train_rows']
        mean,std=x[:n].mean(0),x[:n].std(0)
        z=(x-mean)/np.where(std>0,std,1)
        z=np.column_stack((np.ones(len(z)),z))
        penalty=np.eye(z.shape[1])*params['ridge'];penalty[0,0]=0
        weights=np.linalg.solve(z[:n].T@z[:n]+penalty,z[:n].T@y[:n])
        prediction=z@weights
        train=float(np.mean((prediction[:n]-y[:n])**2));val=float(np.mean((prediction[n:]-y[n:])**2))
        return dict(score=-val,train_score=-train,gap=max(0,val-train),eligible=True,
                    model='synthetic_linear_demo',weights=weights.tolist(),
                    mean=mean.tolist(),std=std.tolist(),request_sha256=digest(request))


class SyntheticStage:
    api_version=1
    plugin_params={}

    def run(self, request, params, work, base):
        context=request['context']
        require(context['scope']=='synthetic','SYNTHETIC_STAGE_REFUSES_REAL_DATA')
        evidence=dict(kind='SYNTHETIC_CONTRACT_EXAMPLE', production_admission=False)
        if request['stage']=='profiles':
            x=np.asarray(context['data']['x'])[:context['data']['train_rows']]
            evidence['train_profiles']={c:dict(mean=float(x[:,i].mean()),std=float(x[:,i].std()))
                                        for i,c in enumerate(context['features'])}
        elif request['stage']=='relationships':
            x=np.asarray(context['data']['x'])[:context['data']['train_rows']]
            evidence['train_correlation']=np.corrcoef(x.T).tolist()
        elif request['stage']=='causal':
            evidence['causal_effect']='NOT_IDENTIFIED; no causal discovery simulated'
        elif request['stage']=='encoding':
            evidence['encoding']='identity; evaluator fits fixed TRAIN scaling'
        elif request['stage']=='extractor_selection':
            evidence['representation']='linear demo only, no temporal extractor chosen'
        result=dict(schema='feature_selector.stage_result.v1',stage=request['stage'],
            context_sha256=request['context_sha256'],status='COMPLETE',scope='synthetic',
            evidence=evidence,files=[])
        if request['stage']=='confirmation':
            result.update(accepted=False,selected=context['selected'])
        return result
