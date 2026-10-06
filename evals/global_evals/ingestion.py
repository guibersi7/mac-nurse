"""Private central intake. Tenant identity comes from operator-issued credentials, never payload."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import time
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import normalize

MAX_REQUEST = 1024 * 1024
MAX_TENANT_RECORDS = 10000
IDENTIFIER = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')


class IntakeError(ValueError):
    pass


def safe_path(path):
    path = Path(os.path.abspath(os.path.expanduser(str(path))))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise IntakeError('unsafe path')
    return path


class Store:
    def __init__(self, root):
        self.root = safe_path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self.path = safe_path(self.root / 'intake.sqlite')
        # Create owner-only before SQLite writes any private data.
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        os.fchmod(fd, 0o600)
        os.close(fd)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS tenants (
                  tenant TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
                  consent_id TEXT NOT NULL, expires REAL NOT NULL, active INTEGER NOT NULL,
                  proof_ref TEXT NOT NULL, retention_days INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS records (
                  tenant TEXT NOT NULL, source_id TEXT NOT NULL, consent_id TEXT NOT NULL,
                  agent_version TEXT NOT NULL, created REAL NOT NULL, content TEXT NOT NULL,
                  PRIMARY KEY(tenant,source_id), FOREIGN KEY(tenant) REFERENCES tenants(tenant));
                CREATE TABLE IF NOT EXISTS provider_grants (
                  tenant TEXT NOT NULL, endpoint TEXT NOT NULL, PRIMARY KEY(tenant,endpoint),
                  FOREIGN KEY(tenant) REFERENCES tenants(tenant));
                CREATE TABLE IF NOT EXISTS source_registry (
                  tenant TEXT NOT NULL, source_id TEXT NOT NULL, consent_id TEXT NOT NULL,
                  PRIMARY KEY(tenant,source_id), FOREIGN KEY(tenant) REFERENCES tenants(tenant));
                CREATE TABLE IF NOT EXISTS batches (
                  tenant TEXT NOT NULL, request_hash TEXT NOT NULL, batch_id TEXT NOT NULL,
                  created REAL NOT NULL, PRIMARY KEY(tenant,request_hash));
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def register(self, tenant, consent_id, expires, proof_ref, retention_days=30, provider_endpoints=None):
        if not IDENTIFIER.fullmatch(tenant) or not IDENTIFIER.fullmatch(consent_id):
            raise IntakeError('invalid identity')
        if not isinstance(proof_ref, str) or not IDENTIFIER.fullmatch(proof_ref):
            raise IntakeError('proof must be opaque identifier')
        if not time.time() < expires <= time.time() + 366 * 86400 or not 1 <= retention_days <= 90:
            raise IntakeError('invalid expiration or retention')
        endpoints = provider_endpoints or []
        if not isinstance(endpoints,list) or len(endpoints)>5:
            raise IntakeError('invalid providers')
        for endpoint in endpoints:
            if not isinstance(endpoint,str) or len(endpoint)>2000:
                raise IntakeError('invalid provider destination')
            parts=urlsplit(endpoint)
            if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
                raise IntakeError('explicit HTTPS provider destination required')
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            # Existing tenants require explicit renewal to preserve consent semantics.
            if db.execute('SELECT 1 FROM tenants WHERE tenant=?', (tenant,)).fetchone():
                raise IntakeError('tenant already registered')
            db.execute('INSERT INTO tenants VALUES (?,?,?,?,?,?,?)',
                       (tenant, hashlib.sha256(token.encode()).hexdigest(), consent_id, expires, 1, proof_ref, retention_days))
            db.executemany('INSERT INTO provider_grants VALUES (?,?)', [(tenant,e) for e in set(endpoints)])
        return token

    @staticmethod
    def require_consent(row, consent_id=None):
        if not row or not row['active'] or row['expires'] <= time.time():
            raise IntakeError('not authorized')
        if consent_id is not None and not hmac.compare_digest(row['consent_id'], consent_id):
            raise IntakeError('not authorized')

    def ingest(self, token, envelope):
        if not isinstance(token, str) or not 20 <= len(token) <= 256:
            raise IntakeError('not authorized')
        if not isinstance(envelope, dict) or set(envelope) != {'schema_version','consent_id','agent_version','records'}:
            raise IntakeError('invalid envelope')
        if type(envelope['schema_version']) is not int or envelope['schema_version'] != 1:
            raise IntakeError('invalid schema')
        consent_id, version, records = envelope['consent_id'], envelope['agent_version'], envelope['records']
        if not isinstance(consent_id, str) or not IDENTIFIER.fullmatch(consent_id):
            raise IntakeError('invalid consent')
        if not isinstance(version, str) or not re.fullmatch(r'(sha256:[a-f0-9]{64}|[a-f0-9]{40})', version):
            raise IntakeError('agent version must be immutable digest or commit')
        if not isinstance(records, list) or not 1 <= len(records) <= 100:
            raise IntakeError('invalid record count')
        if len(json.dumps(envelope, ensure_ascii=False).encode()) > MAX_REQUEST:
            raise IntakeError('request too large')
        # Normalize again on the receiver even when sender says it has redacted.
        clean = [normalize(record) for record in records]
        if len({r['id'] for r in clean}) != len(clean):
            raise IntakeError('duplicate source id')
        request_hash = hashlib.sha256(json.dumps({'consent':consent_id,'version':version,'records':clean},
                                               sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM tenants WHERE token_hash=?',
                             (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            self.require_consent(row, consent_id)
            tenant = row['tenant']
            duplicate = db.execute('SELECT batch_id FROM batches WHERE tenant=? AND request_hash=?',
                                   (tenant,request_hash)).fetchone()
            if duplicate:
                return {'batch_id':duplicate['batch_id'],'accepted':len(clean),'duplicate':True}
            current = db.execute('SELECT COUNT(*) FROM records WHERE tenant=?', (tenant,)).fetchone()[0]
            new_count = 0
            entries = []
            for record in clean:
                source_id = hashlib.sha256((tenant + ':' + record['id']).encode()).hexdigest()
                record['id'] = source_id
                if db.execute('SELECT 1 FROM records WHERE tenant=? AND source_id=?', (tenant,source_id)).fetchone() is None:
                    new_count += 1
                entries.append((tenant,source_id,consent_id,version,time.time(),json.dumps(record,ensure_ascii=False)))
            if current + new_count > MAX_TENANT_RECORDS:
                raise IntakeError('quota reached')
            db.executemany('INSERT INTO source_registry VALUES (?,?,?) ON CONFLICT(tenant,source_id) DO UPDATE SET consent_id=excluded.consent_id',
                           [(e[0],e[1],e[2]) for e in entries])
            db.executemany('''INSERT INTO records VALUES (?,?,?,?,?,?)
                ON CONFLICT(tenant,source_id) DO UPDATE SET consent_id=excluded.consent_id,
                agent_version=excluded.agent_version,created=excluded.created,content=excluded.content''', entries)
            batch_id = secrets.token_hex(16)
            db.execute('INSERT INTO batches VALUES (?,?,?,?)', (tenant,request_hash,batch_id,time.time()))
            return {'batch_id':batch_id,'accepted':len(clean),'duplicate':False}

    def export(self, tenant):
        # Operator-only function; deliberately NOT exposed by the HTTP server.
        with self.connect() as db:
            row = db.execute('SELECT * FROM tenants WHERE tenant=?', (tenant,)).fetchone()
            self.require_consent(row)
            cutoff = time.time() - row['retention_days'] * 86400
            return [json.loads(item['content']) for item in db.execute(
                'SELECT content FROM records WHERE tenant=? AND consent_id=? AND created>? ORDER BY source_id',
                (tenant,row['consent_id'],cutoff))]

    def consent_ledger(self):
        # Only lineage/consent metadata, never message content. Registry survives
        # revocation so derived datasets can be blocked on the next release review.
        now = time.time()
        with self.connect() as db:
            rows = db.execute('''SELECT r.tenant,r.source_id,r.consent_id,t.consent_id AS current_consent,
                t.active,t.expires,t.retention_days,c.created FROM source_registry r
                JOIN tenants t ON t.tenant=r.tenant LEFT JOIN records c
                ON c.tenant=r.tenant AND c.source_id=r.source_id''').fetchall()
            return {'schema_version':1, 'generated_at':now,
                    'sources':[{'source_id':row['source_id'],'consent_id':row['consent_id'],
                                'allowed':bool(row['active'] and row['expires']>now and row['created'] is not None
                                    and row['created']>now-row['retention_days']*86400
                                    and row['consent_id']==row['current_consent']),
                                'expires_at':row['expires'],
                                'provider_endpoints':[p['endpoint'] for p in db.execute('SELECT endpoint FROM provider_grants WHERE tenant=?',(row['tenant'],))]} for row in rows]}

    def revoke(self, tenant):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM tenants WHERE tenant=?', (tenant,)).fetchone():
                raise IntakeError('unknown tenant')
            db.execute('UPDATE tenants SET active=0 WHERE tenant=?', (tenant,))
            db.execute('DELETE FROM records WHERE tenant=?', (tenant,))
            db.execute('DELETE FROM batches WHERE tenant=?', (tenant,))

    def purge_expired(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            deleted = db.execute('''DELETE FROM records WHERE EXISTS
                (SELECT 1 FROM tenants t WHERE t.tenant=records.tenant AND
                (t.active=0 OR t.expires<=? OR records.created<=?-t.retention_days*86400))''',
                (time.time(),time.time())).rowcount
            db.execute('DELETE FROM batches WHERE created<?', (time.time()-90*86400,))
            return deleted


def make_server(store, port=8789):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Request URLs, bearer credentials and payloads must not enter logs.

        def respond(self, code, body):
            payload = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path=='/healthz':
                self.respond(200,{'service':'mac-nurse-eval-intake','local_pilot':True})
            else:
                self.respond(404,{'error':'not found'})

        def do_POST(self):
            self.connection.settimeout(10)
            if self.path != '/v1/intake':
                self.respond(404, {'error':'not found'})
                return
            try:
                size = int(self.headers.get('Content-Length','0'))
                if not 0 < size <= MAX_REQUEST or self.headers.get('Transfer-Encoding'):
                    raise IntakeError('invalid size')
                auth = self.headers.get('Authorization','')
                if not auth.startswith('Bearer '):
                    raise IntakeError('not authorized')
                body = self.rfile.read(size)
                if len(body) != size:
                    raise IntakeError('incomplete body')
                result = store.ingest(auth[7:],json.loads(body))
                self.respond(202, result)
            except (IntakeError, ValueError, TypeError, OSError, sqlite3.Error):
                self.respond(400, {'error':'request rejected'})
    # Bind only loopback. Remote deployment needs TLS/auth proxy, rate limit,
    # concurrency limits and operator-managed private host. No public launch here.
    return ThreadingHTTPServer(('127.0.0.1',port), Handler)


def private_file(path, content):
    path = safe_path(path)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # New destinations only: avoid silently clobbering operator credentials/exports.
    fd = os.open(path,os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'w') as file:
        file.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store',type=Path,required=True)
    sub = parser.add_subparsers(dest='action',required=True)
    reg = sub.add_parser('register')
    for name in ('tenant','consent-id','proof-ref'):
        reg.add_argument('--'+name,required=True)
    reg.add_argument('--expires-at',type=float,required=True,help='UTC Unix timestamp')
    reg.add_argument('--retention-days',type=int,default=30)
    reg.add_argument('--token-file',type=Path,required=True)
    reg.add_argument('--provider-endpoint',action='append',default=[],help='Exact HTTPS destination separately consented by user for model replay')
    ingest = sub.add_parser('ingest')
    ingest.add_argument('--token-file',type=Path,required=True)
    ingest.add_argument('--input',type=Path,required=True)
    export = sub.add_parser('export')
    export.add_argument('--tenant',required=True)
    export.add_argument('--output',type=Path,required=True)
    revoke = sub.add_parser('revoke')
    revoke.add_argument('--tenant',required=True)
    ledger = sub.add_parser('consent-ledger')
    ledger.add_argument('--output',type=Path,required=True)
    sub.add_parser('purge-expired')
    serve = sub.add_parser('serve')
    serve.add_argument('--port',type=int,default=8789)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        store = Store(args.store)
        if args.action == 'register':
            # Validate token destination before creating the grant.
            if safe_path(args.token_file).exists():
                raise IntakeError('token destination exists')
            token = store.register(args.tenant,args.consent_id,args.expires_at,args.proof_ref,args.retention_days,args.provider_endpoint)
            private_file(args.token_file,token+'\n')
            print('Registered private tenant credential; consent proof must be verified by operator.')
        elif args.action == 'ingest':
            path = safe_path(args.input)
            if path.stat().st_size > MAX_REQUEST:
                raise IntakeError('oversize')
            token = safe_path(args.token_file).read_text().strip()
            print(json.dumps(store.ingest(token,json.loads(path.read_text()))))
        elif args.action == 'export':
            private_file(args.output,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in store.export(args.tenant)))
            print('Private export written; not approved for public dataset.')
        elif args.action == 'consent-ledger':
            private_file(args.output,json.dumps(store.consent_ledger(),indent=2)+'\n')
            print('Private consent ledger written; reviewer must confirm operator provenance.')
        elif args.action == 'revoke':
            store.revoke(args.tenant)
            print('Consent revoked and intake records removed. Derived datasets require separate removal review.')
        elif args.action == 'purge-expired':
            print(json.dumps({'purged':store.purge_expired()}))
        elif args.action == 'serve':
            print('Private intake listening on loopback only; not production internet service.',flush=True)
            make_server(store,args.port).serve_forever()
    except (IntakeError,ValueError,TypeError,OSError,sqlite3.Error):
        print('Private intake operation rejected; inspect consent and schema locally.',file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
