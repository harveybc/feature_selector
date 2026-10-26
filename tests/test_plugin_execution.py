import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from feature_selector.config import prepare, overrides
from feature_selector.contracts import subset_view
from feature_selector.evaluators import RLModelEvaluator, TRADING_METRICS
from feature_selector.io import atomic, digest, file_hash, read, RunStore
from feature_selector.main import main
from feature_selector.stages import STAGES

ROOT=Path(__file__).resolve().parents[1]


def execute(tmp_path, changes=None):
    cli={'output':str(tmp_path/'run')}
    if changes:cli.update(changes)
    c,p,w,b=prepare(ROOT/'examples/plugin_demo.json',cli)
    return p['pipeline'].run(c,p,w,b)


def test_full_demo_real_fit_and_resume(tmp_path,monkeypatch):
    result=execute(tmp_path)
    assert result['scope']=='synthetic' and result['final_selection'] is False
    assert {s['stage'] for s in result['stages']}==set(STAGES)|{'confirmation'}
    assert result['selected'] and len(result['selected'])<5
    original=(tmp_path/'run/RESULT.json').read_bytes()
    from feature_selector.demo import SyntheticEvaluator
    monkeypatch.setattr(SyntheticEvaluator,'evaluate',lambda *a,**k:pytest.fail('refit on resume'))
    assert execute(tmp_path)==result
    assert (tmp_path/'run/RESULT.json').read_bytes()==original


def test_cache_change_and_config_change_rejected(tmp_path):
    execute(tmp_path)
    with pytest.raises(ValueError,match='IMMUTABLE'):
        execute(tmp_path,{'seeds':[19]})
    p=next((tmp_path/'run/evaluations').glob('*.json'))
    obj=read(p);obj['payload']['score']=123;atomic(p,obj)
    with pytest.raises(ValueError,match='CACHE_DIGEST'):
        execute(tmp_path)


def test_missing_phase_and_unknown_params(tmp_path):
    config=read(ROOT/'examples/plugin_demo.json')
    del config['stages']['causal']
    path=tmp_path/'config.json';atomic(path,config)
    c,p,w,b=prepare(path,{'output':str(tmp_path/'run')})
    with pytest.raises(ValueError,match='ALL_STAGES'):p['pipeline'].run(c,p,w,b)
    with pytest.raises(ValueError,match='UNKNOWN_PLUGIN_PARAMS'):
        prepare(ROOT/'examples/plugin_demo.json',{'selector':{'params':{'typo':5}}})


def test_merge_json_types_and_cli(tmp_path):
    c,_,_,_=prepare(ROOT/'examples/plugin_demo.json',overrides([
        'selector.params.max_evaluations=3','seeds=[1,2]','selector.params.tolerance=0.02']))
    assert c['selector']['params']==dict(max_evaluations=3,min_features=1,tolerance=.02)
    assert c['seeds']==[1,2]
    assert main(['--action','plan','--load_config',str(ROOT/'examples/plugin_demo.json')])==0
    assert main(['--action','status','--output',str(tmp_path/'missing')])==2


def test_lock_rejects_second_writer(tmp_path):
    with RunStore(tmp_path).lock():
        with pytest.raises(ValueError,match='ACTIVE'):
            with RunStore(tmp_path).lock():pass


def receipt(tmp_path):
    f=tmp_path/'weights';f.write_bytes(b'synthetic contract witness, not RL weights')
    request=dict(features=['a'],groups=[dict(name='one',indices=[0],columns=['a'])],
        seed=7,support_hash='a'*64,scaler_hash='b'*64,splits={'train':['2020','2023'],'selection':['2023','2024']},
        constraints=dict(agent_state='none',scaling='fixed_train',clipping=False,fit_scope='train_only',test_access=False))
    params={**RLModelEvaluator.plugin_params, 'model_id':'real-policy-contract',
            'model_sha256':'c'*64,'engine_sha256':'d'*64,'training_budget':{'steps':100}}
    metrics={k:0. for k in TRADING_METRICS}
    metrics.update(orders=100,buy_orders=50,sell_orders=50,early_closes=2,orders_per_week=3,win_rate=.5,
                   buy_win_rate=.5,sell_win_rate=.5,sharpe=.2,max_drawdown=.1)
    result=dict(schema='feature_selector.rl_result.v1',request_sha256=digest(request),**request,
        **{k:params[k] for k in ('model_id','model_sha256','engine_sha256','training_budget')},
        fresh_training=True,test_access=False,observation_contract=request['constraints'],parameter_count=200,
        artifacts=[dict(path=str(f),sha256=file_hash(f))],metrics={'train':metrics,'selection':dict(metrics)})
    return request,params,result


@pytest.mark.parametrize('field,value', [('features',['wrong']),('seed',8),('support_hash','0'*64),
    ('model_sha256','f'*64),('fresh_training',False),('test_access',True)])
def test_rl_falsification(tmp_path,field,value):
    req,params,result=receipt(tmp_path)
    evaluator=RLModelEvaluator();evaluator.validate(params)
    assert evaluator.verify(result,req,params,tmp_path)['eligible']
    result[field]=value
    with pytest.raises(ValueError):evaluator.verify(result,req,params,tmp_path)


def test_rl_metrics_activity_and_artifacts(tmp_path):
    req,params,result=receipt(tmp_path)
    evaluator=RLModelEvaluator()
    result['metrics']['selection']['orders_per_week']=1
    assert not evaluator.verify(result,req,params,tmp_path)['eligible']
    result['metrics']['selection']['buy_orders']=12
    with pytest.raises(ValueError,match='DIRECTION_COUNT'):evaluator.verify(result,req,params,tmp_path)


def test_undefined_sharpe_is_retained_not_converted_to_zero(tmp_path):
    req,params,result=receipt(tmp_path)
    for metric in result['metrics'].values():
        metric.update(orders=0,buy_orders=0,sell_orders=0,early_closes=0,orders_per_week=0,
                      sharpe=None,win_rate=None,buy_win_rate=None,sell_win_rate=None)
    measured=RLModelEvaluator().verify(result,req,params,tmp_path)
    assert measured['score'] is None and measured['gap'] is None
    assert measured['eligible'] is False
    result['metrics']['selection']['win_rate']=0
    with pytest.raises(ValueError,match='UNSUPPORTED_RATE'):
        RLModelEvaluator().verify(result,req,params,tmp_path)


def test_plugin_replacement_does_not_inherit_old_params():
    c,_,_,_=prepare(ROOT/'examples/plugin_demo.json',{'selector':{'plugin':'fixed','params':{'columns':['signal_a']}}})
    assert c['selector']['params']=={'columns':['signal_a']}


def test_timeout_stops_command(tmp_path):
    from feature_selector.stages import execute as command
    script=tmp_path/'slow.py';script.write_text('import time\ntime.sleep(30)\n')
    pins=[dict(path=str(script),sha256=file_hash(script))]
    with pytest.raises(subprocess.TimeoutExpired):
        command([sys.executable,str(script),'{request}','{response}'],pins,{},tmp_path/'job',tmp_path,.05)


def test_real_development_refuses_synthetic_evaluator(tmp_path):
    from feature_selector.methodology import CausalSelection
    c,p,_,b=prepare(ROOT/'examples/plugin_demo.json')
    d=p['dataset'].load(c['dataset']['params'],b);d['scope']='development'
    with pytest.raises(ValueError,match='REAL_RL_EVALUATOR_REQUIRED'):
        CausalSelection().run(c,p,RunStore(tmp_path),d,b,'id')


def test_command_protocol_and_pin_failure(tmp_path):
    from feature_selector.stages import execute as command
    script=tmp_path/'bridge.py'
    script.write_text('import json,sys\njson.dump({"ok":True},open(sys.argv[2],"w"))\n')
    pins=[dict(path=str(script),sha256=file_hash(script))]
    argv=[sys.executable,str(script),'{request}','{response}']
    assert command(argv,pins,{},tmp_path/'attempt',tmp_path,5)=={'ok':True}
    script.write_text('raise RuntimeError("changed")')
    with pytest.raises(ValueError,match='INPUT_FILE_CHANGED'):
        command(argv,pins,{},tmp_path/'other',tmp_path,5)


def test_external_plugin_installed_as_separate_distribution(tmp_path):
    target=tmp_path/'installed'
    subprocess.run([sys.executable,'-m','pip','install','--no-deps','--no-build-isolation',
                    '--target',str(target),str(ROOT/'examples/external_plugin')],check=True,capture_output=True)
    env={**os.environ,'PYTHONPATH':str(target)}
    code="from feature_selector.plugins import resolve; from feature_selector.io import digest,file_hash; import inspect; p,w=resolve('selectors','external_fixed'); assert w['distribution']=='feature-selector-example-plugin'; assert w['source_sha256']==digest({'example_selector.py':file_hash(inspect.getfile(type(p)))}); print(w['entry_point'])"
    r=subprocess.run([sys.executable,'-c',code],env=env,check=True,capture_output=True,text=True)
    assert 'example_selector:Plugin' in r.stdout
    r=subprocess.run([sys.executable,'-m','feature_selector','--load_config',str(ROOT/'examples/plugin_demo.json'),
        '--set','selector.plugin=external_fixed','--set','selector.params={"columns":["signal_a","signal_b"]}',
        '--output',str(tmp_path/'external-run')],env=env,check=True,capture_output=True,text=True)
    assert json.loads(r.stdout)['selected']==['signal_a','signal_b']


def test_full_stage_evidence_required_for_real_context(tmp_path):
    from feature_selector.stages import stage_request, validate_stage, EVIDENCE_FIELDS
    c,p,_,b=prepare(ROOT/'examples/plugin_demo.json')
    context=p['dataset'].load(c['dataset']['params'],b);context['scope']='development'
    request=stage_request('causal',context,'id')
    f=tmp_path/'evidence.json';f.write_text('{}')
    result=dict(schema='feature_selector.stage_result.v1',stage='causal',scope='development',status='COMPLETE',
                context_sha256=digest(context),evidence={'assumptions':{'status':'MEASURED','detail':'example'}},
                files=[dict(path=str(f),sha256=file_hash(f))])
    with pytest.raises(ValueError,match='INCOMPLETE_STAGE_EVIDENCE'):validate_stage(result,request,tmp_path)
    result['evidence']={k:dict(status='NOT_IDENTIFIED',detail='Explicit contract test, not a scientific result')
                        for k in EVIDENCE_FIELDS['causal']}
    validate_stage(result,request,tmp_path)
    f.write_text('{"changed":true}')
    with pytest.raises(ValueError,match='INPUT_FILE_CHANGED'):validate_stage(result,request,tmp_path)


def test_atomic_failure_cleans_temporary_file(tmp_path,monkeypatch):
    import feature_selector.io as io
    monkeypatch.setattr(io.os,'replace',lambda *a:(_ for _ in ()).throw(OSError('test')))
    with pytest.raises(OSError):atomic(tmp_path/'receipt.json',{'x':1})
    assert list(tmp_path.iterdir())==[]


def test_duplicate_json_keys_rejected(tmp_path):
    p=tmp_path/'invalid.json';p.write_text('{"x":1,"x":2}')
    with pytest.raises(ValueError,match='DUPLICATE_JSON_KEY'):read(p)
