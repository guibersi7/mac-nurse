"""Execute with python3 -m evals.global_evals; inputs and outputs stay private."""
import argparse
import json
from pathlib import Path
import sys
import os
from .harness import replay

from evals.pipeline import private_write
from .core import compare, release_plan, validate_dataset


def load(path):
    path = Path(path)
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('input too large')
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('curate', 'compare', 'release-plan'):
        command = sub.add_parser(name)
        command.add_argument('--dataset', required=True)
        command.add_argument('--output', required=True)
        if name != 'curate':
            command.add_argument('--baseline', required=True)
            command.add_argument('--candidate', required=True)
        if name == 'release-plan':
            command.add_argument('--image', required=True)
            command.add_argument('--approval', required=True)
            command.add_argument('--consent-ledger')
    command = sub.add_parser('replay')
    for flag in ('dataset', 'output', 'endpoint', 'model', 'key-env', 'agent-version', 'instructions-file'):
        command.add_argument('--' + flag, required=True)
    command.add_argument('--allow-provider-transfer', action='store_true')
    command.add_argument('--consent-ledger')
    command.add_argument('--max-calls', type=int, default=20)
    command.add_argument('--max-tokens', type=int, default=1024)
    command.add_argument('--timeout', type=float, default=60)
    command.add_argument('--max-input-chars', type=int, default=20000)
    args = parser.parse_args()
    try:
        dataset = load(args.dataset)
        if args.command == 'replay':
            result = replay(dataset, Path(args.instructions_file).read_text(encoding='utf-8'), args.agent_version, args.endpoint, args.model, os.environ.get(args.key_env, ''), args.allow_provider_transfer, load(args.consent_ledger) if args.consent_ledger else None, args.max_calls, args.max_tokens, args.timeout, max_input_chars=args.max_input_chars)
        elif args.command == 'curate':
            result = validate_dataset(dataset)
        else:
            baseline, candidate = load(args.baseline), load(args.candidate)
            result = compare(dataset, baseline, candidate) if args.command == 'compare' else release_plan(dataset, baseline, candidate, args.image, load(args.approval), load(args.consent_ledger) if args.consent_ledger else None)
        private_write(Path(args.output), json.dumps(result, indent=2, ensure_ascii=False) + '\n')
        print('Private result written; no deployment performed.')
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print('Invalid or unavailable input; inspect locally without publishing private data.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
