"""No network calls: controlled provider responses verify replay mechanics only."""
import copy
import time
import unittest
from test_global_evals import dataset
from evals.global_evals.harness import replay
from evals.global_evals.core import validate_run


class HarnessTests(unittest.TestCase):
    def execute(self, transport, data=None, **changes):
        kwargs = dict(dataset=data or dataset(), instructions='Preserve local work.', agent_version='a'*40,
                      endpoint='https://provider.example/v1/chat/completions', model='explicit-test-model', key='fake-key',
                      allow_transfer=True, transport=transport)
        kwargs.update(changes)
        return replay(**kwargs)

    def test_tool_loop_and_ungraded_result(self):
        requests = []
        def transport(endpoint, key, payload, timeout):
            requests.append(copy.deepcopy(payload))
            if len(requests) % 2:
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call-1', 'type': 'function', 'function': {'name': 'inventory', 'arguments': '{}'}}]}
                finish = 'tool_calls'
            else:
                self.assertEqual(payload['messages'][-1]['role'], 'tool')
                self.assertIn('true', payload['messages'][-1]['content'])
                message = {'role': 'assistant', 'content': 'Preserved dirty worktree.'}; finish = 'stop'
            return {'choices': [{'message': message, 'finish_reason': finish}], 'usage': {'total_tokens': 10}}
        result = self.execute(transport)
        self.assertEqual(len(requests), 4)
        self.assertEqual(result['execution'], 'model_replay')
        self.assertEqual(result['cases'][0]['tool_calls'][0]['name'], 'inventory')
        self.assertEqual(result['cases'][0]['grades'], [])
        with self.assertRaises(ValueError): validate_run(dataset(), result)

    def test_no_request_before_explicit_configuration(self):
        for change in ({'allow_transfer': False}, {'endpoint': 'http://provider.example'}, {'endpoint': 'https://u:p@provider.example'}, {'endpoint': 'https://provider.example?secret=x'}, {'agent_version': 'latest'}, {'key': ''}, {'model': ''}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.execute(lambda *args: self.fail('must not send'), **change)

    def test_unknown_tool_and_exhaustion_never_execute(self):
        def unknown(*args):
            return {'choices': [{'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'tool_calls': [{'id': 'x', 'type': 'function', 'function': {'name': 'shell', 'arguments': '{"command":"rm -rf /"}'}}]}}]}
        with self.assertRaises(ValueError): self.execute(unknown)
        def stop(*args): return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'ok'}}]}
        with self.assertRaises(ValueError): self.execute(stop, max_calls=1)
        def truncated(*args): return {'choices': [{'finish_reason': 'length', 'message': {'role': 'assistant', 'content': 'partial'}}]}
        with self.assertRaises(ValueError): self.execute(truncated)

    def test_tenant_provider_consent_missing_or_wrong_destination(self):
        data = dataset()
        for case in data['cases']: case['provenance'] = 'tenant'
        ledger = {'generated_at': time.time(), 'sources': [{'source_id': c['source_id'], 'allowed': True, 'expires_at': time.time()+1000, 'provider_endpoints': ['https://other.example']} for c in data['cases']]}
        with self.assertRaises(ValueError): self.execute(lambda *args: self.fail('no consent'), data=data)
        with self.assertRaises(ValueError): self.execute(lambda *args: self.fail('wrong provider'), data=data, consent_ledger=ledger)

    def test_inconsistent_fixture_schema_preflight(self):
        data = dataset(); data['cases'][1]['tool_fixtures'].append({'name': 'inventory', 'arguments': {'path': 'mock'}, 'result': {}})
        with self.assertRaises(ValueError): self.execute(lambda *args: self.fail('must validate all tools before transmission'), data=data)

    def test_malformed_provider_shapes_fail_closed(self):
        responses = [None, [], {'choices': [None]}, {'choices': [{'message': None}]},
                     {'choices': [{'message': {'role': 'assistant', 'tool_calls': {}}}]},
                     {'choices': [{'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'tool_calls': [None]}}]}]
        for response in responses:
            with self.subTest(response=response), self.assertRaises(ValueError):
                self.execute(lambda *args: response)

    def test_input_budget_blocks_before_provider_transfer(self):
        with self.assertRaises(ValueError):
            self.execute(lambda *args: self.fail('oversize request must not be sent'), max_input_chars=10)
        with self.assertRaises(ValueError):
            self.execute(lambda *args: self.fail('invalid budget must not send'), max_input_chars=True)

    def test_grading_criteria_never_sent_to_model(self):
        data = dataset()
        for case in data['cases']:
            case['criteria'][0]['description'] = 'HIDDEN_EVALUATION_MARKER'
        def transport(endpoint, key, payload, timeout):
            import json
            self.assertNotIn('HIDDEN_EVALUATION_MARKER', json.dumps(payload))
            self.assertNotIn('criteria', payload)
            return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'Preserved.'}}]}
        self.execute(transport, data=data)
