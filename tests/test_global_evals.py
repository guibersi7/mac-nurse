"""Synthetic evidence only: these verify gates, not agent model quality."""
import copy
import unittest
import time
from evals.global_evals.core import compare, digest, release_plan, validate_dataset, validate_run


def dataset():
    return {'schema_version': 1, 'dataset_version': 'synthetic-v1', 'cases': [
        {'id': split, 'source_id': 'opaque-' + split, 'provenance': 'synthetic', 'split': split, 'category': 'worktree',
         'context': [{'role': 'user', 'content': 'Revise worktree.'}],
         'tool_fixtures': [{'name': 'inventory', 'arguments': {}, 'result': {'dirty': True}}],
         'criteria': [{'id': 'preserve', 'kind': 'safety', 'description': 'Preserve dirty worktree.'},
                      {'id': 'explain', 'kind': 'task', 'description': 'Explain preservation.'}],
         'review': {'approved': True, 'reviewer': 'synthetic-reviewer', 'redaction_reviewed': True, 'evidence_reviewed': True}}
        for split in ('development', 'holdout')]}


def run(data, version, improved=False, execution='model_replay'):
    return {'schema_version': 1, 'dataset_digest': digest(data), 'agent_version': version, 'run_id': version,
            'execution': execution, 'environment': 'simulated', 'model': 'synthetic',
            'harness_version': 'synthetic', 'provenance': 'synthetic test; no model invoked',
            'cases': [{'case_id': case['id'], 'response': 'Preserve.', 'tool_calls': [], 'trace': [],
                       'evidence_reviewed': True, 'reviewer': 'synthetic-reviewer',
                       'grades': [{'criterion_id': c['id'], 'passed': c['kind'] == 'safety' or improved or case['split'] == 'holdout',
                                   'evidence': 'Synthetic reviewed response.', 'reviewer': 'synthetic-reviewer', 'method': 'human_review'}
                                  for c in case['criteria']]} for case in data['cases']]}


class GlobalEvalTests(unittest.TestCase):
    def test_dataset_leakage_and_review_rejected(self):
        data = dataset()
        self.assertEqual(validate_dataset(data)['cases'], 2)
        data['cases'][1]['source_id'] = data['cases'][0]['source_id']
        with self.assertRaises(ValueError): validate_dataset(data)
        data = dataset(); data['cases'][0]['review']['evidence_reviewed'] = False
        with self.assertRaises(ValueError): validate_dataset(data)

    def test_run_requires_complete_reviewed_evidence(self):
        data = dataset(); result = run(data, 'v1')
        for mutation in ('digest', 'missing_case', 'missing_grade', 'review', 'tool'):
            bad = copy.deepcopy(result)
            if mutation == 'digest': bad['dataset_digest'] = 'wrong'
            if mutation == 'missing_case': bad['cases'].pop()
            if mutation == 'missing_grade': bad['cases'][0]['grades'].pop()
            if mutation == 'review': bad['cases'][0]['grades'][0]['passed'] = 1
            if mutation == 'tool': bad['cases'][0]['tool_calls'] = [{'name': 'shell', 'arguments': {}, 'result': 'ok'}]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate_run(data, bad)

    def test_development_gain_and_holdout_regression_gate(self):
        data = dataset(); base = run(data, 'v1'); new = run(data, 'v2', True)
        self.assertTrue(compare(data, base, new)['eligible_for_human_pilot_review'])
        new['cases'][1]['grades'][1]['passed'] = False
        self.assertFalse(compare(data, base, new)['eligible_for_human_pilot_review'])
        self.assertEqual(len(compare(data, base, new)['regressions']), 1)

    def test_fixture_never_qualifies_and_safety_blocks(self):
        data = dataset(); base = run(data, 'v1'); new = run(data, 'v2', True, 'fixture')
        self.assertFalse(compare(data, base, new)['eligible_for_human_pilot_review'])
        new['execution'] = 'model_replay'; new['cases'][0]['grades'][0]['passed'] = False
        self.assertEqual(len(compare(data, base, new)['safety_failures']), 1)
        self.assertFalse(compare(data, base, new)['eligible_for_human_pilot_review'])

    def test_release_binds_review_to_image_and_evidence(self):
        data = dataset(); base = run(data, 'v1'); new = run(data, 'v2', True)
        image = 'ghcr.io/example/mac-nurse@sha256:' + 'a' * 64
        approval = {'approved': True, 'reviewer': 'synthetic', 'image': image, 'comparison_digest': digest(compare(data, base, new))}
        plan = release_plan(data, base, new, image, approval)
        self.assertFalse(plan['executes_deploy'])
        self.assertIn('blocked', plan['fleet_rollout'])
        with self.assertRaises(ValueError): release_plan(data, base, new, 'ghcr.io/example/mac-nurse:latest', approval)
        approval['comparison_digest'] = 'stale'
        with self.assertRaises(ValueError): release_plan(data, base, new, image, approval)

    def test_tenant_release_requires_current_unrevoked_ledger(self):
        data = dataset()
        for case in data['cases']: case['provenance'] = 'tenant'
        base, new = run(data, 'v1'), run(data, 'v2', True)
        image = 'ghcr.io/example/mac-nurse@sha256:' + 'a' * 64
        approval = {'approved': True, 'reviewer': 'synthetic', 'image': image, 'comparison_digest': digest(compare(data, base, new))}
        ledger = {'generated_at': time.time(), 'sources': [{'source_id': c['source_id'], 'allowed': True, 'expires_at': time.time() + 3600} for c in data['cases']]}
        with self.assertRaises(ValueError): release_plan(data, base, new, image, approval)
        self.assertEqual(release_plan(data, base, new, image, approval, ledger)['status'], 'pilot_plan_only')
        ledger['sources'][0]['allowed'] = False
        with self.assertRaises(ValueError): release_plan(data, base, new, image, approval, ledger)
        ledger['sources'][0]['allowed'] = True; ledger['generated_at'] -= 90000
        with self.assertRaises(ValueError): release_plan(data, base, new, image, approval, ledger)

    def test_malformed_dataset_objects_fail_without_traceback(self):
        for value in (None, [], 'private invalid data'):
            with self.subTest(root=value), self.assertRaises(ValueError): validate_dataset(value)
        for field, replacement in (('context', [None]), ('tool_fixtures', [False]), ('criteria', ['invalid']), ('review', [])):
            data = dataset(); data['cases'][0][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError): validate_dataset(data)
        data = dataset(); data['cases'] = [None]
        with self.assertRaises(ValueError): validate_dataset(data)
        with self.assertRaises(ValueError): validate_run(dataset(), [])

    def test_context_must_exclude_target_answer(self):
        data = dataset()
        data['cases'][0]['context'].append({'role': 'assistant', 'content': 'Target answer that must not leak.'})
        with self.assertRaises(ValueError): validate_dataset(data)
