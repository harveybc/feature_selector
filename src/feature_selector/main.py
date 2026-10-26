"""Command-line entry point, strict merge and reproducible plugin witnesses."""
import argparse
import json
from pathlib import Path
import sys

from .config import prepare, overrides
from .io import read
from .plugins import installed
from .stages import STAGES


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action',choices=('run','plan','status','plugins'),default='run')
    parser.add_argument('--load_config')
    parser.add_argument('--output')
    parser.add_argument('--set',action='append',default=[],metavar='PATH=JSON')
    args=parser.parse_args(argv)
    try:
        if args.action=='plugins':
            print(json.dumps(installed(),indent=2));return 0
        if args.action=='status' and args.output:
            print(json.dumps(read(Path(args.output)/'STATUS.json'),indent=2));return 0
        if not args.load_config:
            parser.error('--load_config is required')
        cli=overrides(args.set)
        if args.output:cli['output']=args.output
        config,plugins,witnesses,base=prepare(args.load_config,cli)
        if args.action=='status':
            print(json.dumps(read(Path(config['output'])/'STATUS.json'),indent=2));return 0
        if args.action=='plan':
            required=set(STAGES)|{'confirmation'}
            missing=sorted(required-set(config['stages']))
            print(json.dumps(dict(effective_config=config,plugins=witnesses,
                                  missing_stages=missing,execution_started=False),indent=2))
            return 2 if missing else 0
        result=plugins['pipeline'].run(config,plugins,witnesses,base)
        print(json.dumps({k:result[k] for k in ('run_id','scope','selected','search_complete','final_selection')},indent=2))
        return 0
    except (ValueError,KeyError,OSError,TypeError) as exc:
        print(json.dumps(dict(error=type(exc).__name__,detail=str(exc))),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
