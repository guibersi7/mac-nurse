import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import json
import urllib.request
import urllib.error

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from evals.global_evals.ingestion import Store, IntakeError, make_server
from evals.global_evals.transfer import destination, package, send


class TransferTests(unittest.TestCase):
    def test_destination_rejects_insecure_remote_and_embedded_credentials(self):
        for url in ('http://external.example/v1/intake','https://token@example.com/v1/intake',
                    'https://example.com/v1/intake?secret=x','https://example.com/other'):
            with self.assertRaises(IntakeError): destination(url)
        self.assertEqual(destination('http://127.0.0.1:8789/v1/intake'),'http://127.0.0.1:8789/v1/intake')

    def test_authenticated_loopback_intake_and_no_http_exports(self):
        with tempfile.TemporaryDirectory() as temp:
            hub=Store(Path(temp).resolve()/'hub')
            token=hub.register('test_tenant','consent_test',time.time()+86400,'proof_test')
            server=make_server(hub,0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                envelope={'schema_version':1,'consent_id':'consent_test','agent_version':'a'*40,
                          'records':[{'id':'synthetic','messages':[{'role':'user','content':'Avaliação sintética'}],'events':[]}]}
                url='http://127.0.0.1:'+str(server.server_port)+'/v1/intake'
                with urllib.request.urlopen(url.replace('/v1/intake','/healthz')) as response:
                    self.assertEqual(json.load(response),{'service':'mac-nurse-eval-intake','local_pilot':True})
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    urllib.request.urlopen(url.replace('/v1/intake','/v1/export'))
                rejected.exception.close()
                ack=send(url,token,envelope)
                self.assertEqual(ack['accepted'],1)
                self.assertEqual(len(hub.export('test_tenant')),1)
                with self.assertRaises(IntakeError): send(url,'bad-token-with-long-enough-length',envelope)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=2)

    def test_package_does_not_mutate_corpus(self):
        with tempfile.TemporaryDirectory() as temp:
            corpus=Path(temp).resolve()/'corpus.jsonl'
            original='{"id":"synthetic","messages":[{"role":"user","content":"Teste"}],"events":[]}\n'
            corpus.write_text(original)
            out=package(corpus,'consent_test','a'*40)
            self.assertEqual(len(out['records']),1)
            self.assertEqual(corpus.read_text(),original)


if __name__=='__main__':unittest.main()
