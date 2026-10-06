import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest

source=Path(__file__).resolve().parents[1]/'evals/global_evals/ingestion.py'
spec=importlib.util.spec_from_file_location('global_ingestion',source)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def envelope(consent='consent_a'):
    return {'schema_version':1,'consent_id':consent,'agent_version':'sha256:'+'a'*64,
            'records':[{'id':'same_conversation','messages':[{'role':'user','content':'Email ana@example.com em /Users/ana/private.txt token=abc123'}],'events':[]}]}


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name).resolve()
        self.store=mod.Store(self.root/'hub')
        self.token=self.store.register('tenant_a','consent_a',time.time()+86400,'proof_a')

    def tearDown(self):
        self.tmp.cleanup()

    def test_unauthenticated_or_forged_tenant_rejected(self):
        with self.assertRaises(mod.IntakeError):
            self.store.ingest('invalid-token-with-required-length',envelope())
        data=envelope()
        data['tenant_id']='tenant_b'
        with self.assertRaises(mod.IntakeError):
            self.store.ingest(self.token,data)
        with self.assertRaises(mod.IntakeError):
            self.store.ingest(self.token,envelope('consent_b'))

    def test_redaction_idempotency_and_private_modes(self):
        first=self.store.ingest(self.token,envelope())
        second=self.store.ingest(self.token,envelope())
        self.assertEqual(first['batch_id'],second['batch_id'])
        self.assertTrue(second['duplicate'])
        rows=self.store.export('tenant_a')
        self.assertEqual(len(rows),1)
        text=json.dumps(rows)
        for value in ('ana@example.com','/Users/ana','abc123','same_conversation'):
            self.assertNotIn(value,text)
        self.assertEqual(self.store.path.stat().st_mode&0o777,0o600)
        self.assertEqual(self.store.root.stat().st_mode&0o777,0o700)

    def test_tenant_isolation_and_consent_ledger(self):
        token_b=self.store.register('tenant_b','consent_b',time.time()+86400,'proof_b')
        self.store.ingest(self.token,envelope())
        self.store.ingest(token_b,envelope('consent_b'))
        a=self.store.export('tenant_a'); b=self.store.export('tenant_b')
        self.assertNotEqual(a[0]['id'],b[0]['id'])
        ledger=self.store.consent_ledger()
        self.assertEqual(len(ledger['sources']),2)
        self.assertTrue(all(row['allowed'] for row in ledger['sources']))
        self.assertNotIn('messages',json.dumps(ledger))
        self.store.revoke('tenant_a')
        self.assertEqual(len(self.store.export('tenant_b')),1)
        revoked=next(row for row in self.store.consent_ledger()['sources'] if row['source_id']==a[0]['id'])
        self.assertFalse(revoked['allowed'])

    def test_revocation_blocks_intake_export_and_erases_records(self):
        self.store.ingest(self.token,envelope())
        self.store.revoke('tenant_a')
        with self.assertRaises(mod.IntakeError): self.store.ingest(self.token,envelope())
        with self.assertRaises(mod.IntakeError): self.store.export('tenant_a')
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM batches').fetchone()[0],0)

    def test_expiration_and_retention_fail_closed(self):
        self.store.ingest(self.token,envelope())
        with self.store.connect() as db:
            db.execute('UPDATE tenants SET expires=?',(time.time()-1,))
        with self.assertRaises(mod.IntakeError): self.store.ingest(self.token,envelope())
        with self.assertRaises(mod.IntakeError): self.store.export('tenant_a')
        self.assertEqual(self.store.purge_expired(),1)
        self.assertFalse(self.store.consent_ledger()['sources'][0]['allowed'])

    def test_provider_consent_is_explicit_and_exact(self):
        endpoint='https://provider.example/v1/chat/completions'
        token_b=self.store.register('tenant_b','consent_b',time.time()+86400,'proof_b',provider_endpoints=[endpoint])
        self.store.ingest(self.token,envelope())
        self.store.ingest(token_b,envelope('consent_b'))
        ledger=self.store.consent_ledger()
        a=next(row for row in ledger['sources'] if row['consent_id']=='consent_a')
        b=next(row for row in ledger['sources'] if row['consent_id']=='consent_b')
        self.assertEqual(a['provider_endpoints'],[])
        self.assertEqual(b['provider_endpoints'],[endpoint])
        with self.assertRaises(mod.IntakeError):
            self.store.register('tenant_bad','consent_bad',time.time()+86400,'proof_bad',provider_endpoints=['http://provider.example/v1'])

    def test_bad_schema_duplicate_ids_and_oversize_rejected(self):
        data=envelope(); data['records']*=2
        with self.assertRaises(mod.IntakeError): self.store.ingest(self.token,data)
        data=envelope(); data['schema_version']=True
        with self.assertRaises(mod.IntakeError): self.store.ingest(self.token,data)
        data=envelope(); data['records'][0]['messages'][0]['content']='a'*mod.MAX_REQUEST
        with self.assertRaises(mod.IntakeError): self.store.ingest(self.token,data)

    def test_linked_root_and_existing_export_refused(self):
        (self.root/'link').symlink_to(self.root/'hub',target_is_directory=True)
        with self.assertRaises(mod.IntakeError): mod.Store(self.root/'link')
        path=self.root/'export.json'; path.write_text('keep')
        with self.assertRaises(FileExistsError): mod.private_file(path,'replace')
        self.assertEqual(path.read_text(),'keep')


if __name__=='__main__': unittest.main()
