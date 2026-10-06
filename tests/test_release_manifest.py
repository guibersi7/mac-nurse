import copy
import hashlib
import hmac
import time
import unittest
from evals.global_evals.release_manifest import canonical, verify


class ManifestTests(unittest.TestCase):
    key='synthetic-test-key-at-least-32-bytes-long'
    def manifest(self):
        payload={'schema_version':1,'repository':'guibersi7/mac-nurse','image':'ghcr.io/guibersi7/mac-nurse@sha256:'+'a'*64,
                 'comparison_digest':'b'*64,'issued_at':time.time()-5,'expires_at':time.time()+300,'scope':'pilot-only','fleet_rollout':False}
        return {'payload':payload,'signature':hmac.new(self.key.encode(),canonical(payload),hashlib.sha256).hexdigest()}

    def test_minimal_pilot_manifest_verified(self):
        manifest=self.manifest()
        self.assertEqual(verify(manifest,self.key,'guibersi7/mac-nurse')['scope'],'pilot-only')
        self.assertNotIn('messages',str(manifest))

    def test_image_tamper_and_wrong_key_or_repository_rejected(self):
        manifest=self.manifest()
        for key,repo in ((self.key+'wrong','guibersi7/mac-nurse'),(self.key,'someone/other')):
            with self.assertRaises(ValueError):verify(manifest,key,repo)
        manifest['payload']['image']='ghcr.io/attacker/agent@sha256:'+'c'*64
        with self.assertRaises(ValueError):verify(manifest,self.key,'guibersi7/mac-nurse')

    def test_expired_even_correctly_signed_manifest_rejected(self):
        manifest=self.manifest();manifest['payload']['issued_at']=time.time()-400;manifest['payload']['expires_at']=time.time()-20
        manifest['signature']=hmac.new(self.key.encode(),canonical(manifest['payload']),hashlib.sha256).hexdigest()
        with self.assertRaises(ValueError):verify(manifest,self.key,'guibersi7/mac-nurse')

    def test_fleet_scope_not_allowed(self):
        manifest=self.manifest();manifest['payload']['fleet_rollout']=True
        manifest['signature']=hmac.new(self.key.encode(),canonical(manifest['payload']),hashlib.sha256).hexdigest()
        with self.assertRaises(ValueError):verify(manifest,self.key,'guibersi7/mac-nurse')


if __name__=='__main__':unittest.main()
