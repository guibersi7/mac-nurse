"""Explicit opt-in package/send helper. No automatic tenant sharing in the agent runtime."""
import argparse
import json
import sys
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from .ingestion import IntakeError, MAX_REQUEST, private_file, safe_path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*_args,**_kwargs):
        raise IntakeError('redirect refused')


def destination(url):
    parts=urllib.parse.urlsplit(url)
    loopback=parts.hostname in {'127.0.0.1','localhost','::1'}
    if (parts.scheme!='https' and not (parts.scheme=='http' and loopback)) or parts.path!='/v1/intake':
        raise IntakeError('use explicit HTTPS intake or loopback development endpoint')
    if parts.username or parts.password or parts.query or parts.fragment or not parts.hostname:
        raise IntakeError('invalid destination')
    return url


def package(corpus,consent_id,agent_version):
    # Preserve already-normalized records; receiver validates and redacts again.
    path=safe_path(corpus)
    if path.stat().st_size>MAX_REQUEST:
        raise IntakeError('choose smaller reviewed batch')
    records=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not 1<=len(records)<=100:
        raise IntakeError('choose 1..100 records')
    return {'schema_version':1,'consent_id':consent_id,'agent_version':agent_version,'records':records}


def send(url,token,envelope):
    url=destination(url)
    if not isinstance(token,str) or not 20<=len(token)<=256 or any(c in token for c in '\r\n'):
        raise IntakeError('invalid credential')
    payload=json.dumps(envelope,ensure_ascii=False).encode()
    if len(payload)>MAX_REQUEST:
        raise IntakeError('batch exceeds request bound')
    req=urllib.request.Request(url,data=payload,method='POST',headers={
        'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    opener=urllib.request.build_opener(NoRedirect())
    try:
        response=opener.open(req,timeout=10)
    except urllib.error.HTTPError as error:
        error.close()
        raise IntakeError('intake rejected request') from None
    with response as result:
        if result.status!=202:
            raise IntakeError('intake did not acknowledge')
        raw=result.read(4097)
        if len(raw)>4096:
            raise IntakeError('invalid acknowledgement')
        ack=json.loads(raw)
        if not isinstance(ack,dict) or set(ack)!={'batch_id','accepted','duplicate'}:
            raise IntakeError('invalid acknowledgement')
        return ack


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    pack=sub.add_parser('package')
    pack.add_argument('--corpus',type=Path,required=True)
    pack.add_argument('--consent-id',required=True)
    pack.add_argument('--agent-version',required=True)
    pack.add_argument('--output',type=Path,required=True)
    post=sub.add_parser('send')
    post.add_argument('--input',type=Path,required=True)
    post.add_argument('--token-file',type=Path,required=True)
    post.add_argument('--destination',required=True)
    post.add_argument('--confirm-consented-transfer',action='store_true',required=True,
                      help='Operator verified user consent for this exact destination and data scope')
    args=parser.parse_args()
    try:
        if args.action=='package':
            payload=package(args.corpus,args.consent_id,args.agent_version)
            private_file(args.output,json.dumps(payload,ensure_ascii=False)+'\n')
            print('Private batch prepared. This does not authorize transfer or public release.')
        else:
            path=safe_path(args.input)
            if path.stat().st_size>MAX_REQUEST: raise IntakeError('oversize')
            result=send(args.destination,safe_path(args.token_file).read_text().strip(),json.loads(path.read_text()))
            print(json.dumps(result))
    except (IntakeError,ValueError,TypeError,OSError,urllib.error.URLError):
        print('Transfer rejected; verify destination, consent and credential privately.',file=sys.stderr)
        return 2
    return 0


if __name__=='__main__': sys.exit(main())
