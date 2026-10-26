"""Single-writer sequential driver with identity-bound resume."""
from .contracts import require, validate_dataset
from .io import RunStore, digest
from .stages import checked_files


def verify_config_pins(config, base):
    specs = [config[k] for k in ('dataset','pipeline','methodology','selector','evaluator')]
    specs += list(config['stages'].values())
    for spec in specs:
        params = spec['params']
        if params.get('source_pins'):
            checked_files(params['source_pins'],base)
        if params.get('path') and params.get('sha256'):
            checked_files([dict(path=params['path'],sha256=params['sha256'])],base)


class SequentialPipeline:
    api_version = 1
    plugin_params = {}

    def run(self, config, plugins, witnesses, base):
        verify_config_pins(config,base)
        context = validate_dataset(plugins['dataset'].load(config['dataset']['params'],base))
        identity = dict(config=config, plugins=witnesses, dataset_sha256=digest(context))
        run_id = digest(identity)
        store = RunStore(config['output'])
        with store.lock():
            store.immutable('RUN.json',dict(run_id=run_id,**identity))
            store.immutable('effective_config.json',config)
            try:
                result = plugins['methodology'].run(config,plugins,store,context,base,run_id)
                verify_config_pins(config,base)
                store.immutable('RESULT.json',result)
                store.save('STATUS.json',dict(state='COMPLETE',run_id=run_id,
                    final_selection=result['final_selection'],selected=result['selected'],
                    search_complete=result['search_complete']))
                return result
            except Exception as exc:
                store.save('STATUS.json',dict(state='FAILED',run_id=run_id,
                    error_type=type(exc).__name__,error=str(exc)))
                raise
