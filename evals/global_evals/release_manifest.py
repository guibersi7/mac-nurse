"""Minimal signed pilot manifest. No transcript is included; no deployment is performed."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sys
import time

from evals.pipeline import private_write
from .core import release_plan, require


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def key_bytes(key):
    require(isinstance(key,str) and 32<=len(key.encode())<=1024,'configured signing key required')
    return key.encode()


def sign(dataset,baseline,candidate,image,approval,ledger,key,repository,lifetime=3600):
    plan=release_plan(dataset,baseline,candidate,image,approval,ledger)
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository or '') is not None,'repository required')
    require(type(lifetime) is int and 60<=lifetime<=86400,'bounded manifest lifetime required')
    now=time.time()
    payload={'schema_version':1,'repository':repository,'image':plan['image'],
             'comparison_digest':plan['comparison_digest'],'issued_at':now,'expires_at':now+lifetime,
             'scope':'pilot-only','fleet_rollout':False}
    signature=hmac.new(key_bytes(key),canonical(payload),hashlib.sha256).hexdigest()
    return {'payload':payload,'signature':signature}


def verify(manifest,key,repository):
    require(isinstance(manifest,dict) and set(manifest)=={'payload','signature'},'signed manifest required')
    payload,signature=manifest['payload'],manifest['signature']
    require(isinstance(payload,dict) and set(payload)=={'schema_version','repository','image','comparison_digest','issued_at','expires_at','scope','fleet_rollout'},'minimal manifest required')
    require(isinstance(signature,str),'signature required')
    expected=hmac.new(key_bytes(key),canonical(payload),hashlib.sha256).hexdigest()
    require(hmac.compare_digest(signature,expected),'signature refused')
    require(type(payload['schema_version']) is int and payload['schema_version']==1 and payload['repository']==repository,'wrong manifest audience')
    require(payload['scope']=='pilot-only' and payload['fleet_rollout'] is False,'fleet rollout cannot be authorized by this manifest')
    now=time.time()
    require(type(payload['issued_at']) in (int,float) and type(payload['expires_at']) in (int,float)
            and payload['issued_at']<=now<payload['expires_at']
            and 60<=payload['expires_at']-payload['issued_at']<=86400,'manifest expired or invalid time')
    require(re.fullmatch(r'ghcr\.io/[a-z0-9_./-]+@sha256:[a-f0-9]{64}',payload['image'] or '') is not None,'immutable image required')
    require(re.fullmatch(r'[a-f0-9]{64}',payload['comparison_digest'] or '') is not None,'comparison digest required')
    return payload


def load(path):
    path=Path(path)
    require(path.stat().st_size<=20*1024*1024,'input too large')
    return json.loads(path.read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-env',default='EVAL_RELEASE_SIGNING_KEY')
    parser.add_argument('--repository',required=True)
    sub=parser.add_subparsers(dest='action',required=True)
    signer=sub.add_parser('sign')
    for name in ('dataset','baseline','candidate','image','approval','output'):
        signer.add_argument('--'+name,required=True)
    signer.add_argument('--consent-ledger')
    checker=sub.add_parser('verify')
    checker.add_argument('--manifest',required=True)
    args=parser.parse_args()
    try:
        key=os.environ.get(args.key_env,'')
        if args.action=='sign':
            result=sign(load(args.dataset),load(args.baseline),load(args.candidate),args.image,load(args.approval),
                        load(args.consent_ledger) if args.consent_ledger else None,key,args.repository)
            private_write(Path(args.output),json.dumps(result,indent=2)+'\n')
            print('Signed pilot-only manifest written; no production update executed.')
        else:
            payload=verify(load(args.manifest),key,args.repository)
            print(json.dumps({'verified':True,'scope':payload['scope'],'image':payload['image'],'fleet_rollout':False}))
    except (OSError,ValueError,KeyError,TypeError):
        print('Release manifest refused; inspect evidence, consent, signing key and expiry privately.',file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':sys.exit(main())
