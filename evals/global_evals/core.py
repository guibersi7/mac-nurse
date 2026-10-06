"""Validated curated datasets and imported candidate evidence; standard library only."""
import hashlib
import json
import re
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_dataset(dataset):
    require(isinstance(dataset, dict), 'dataset object required')
    require(dataset.get('schema_version') == 1 and text(dataset.get('dataset_version')), 'dataset version required')
    cases = dataset.get('cases')
    require(isinstance(cases, list) and 0 < len(cases) <= 10000, 'bounded nonempty cases required')
    ids, sources = set(), {}
    for case in cases:
        require(isinstance(case, dict), 'case object required')
        require(text(case.get('id')) and case['id'] not in ids, 'unique case id required')
        ids.add(case['id'])
        require(case.get('split') in {'development', 'holdout'}, 'explicit split required')
        require(text(case.get('source_id')), 'opaque source id required')
        require(case.get('provenance', 'tenant') in {'synthetic', 'tenant'}, 'source provenance required')
        previous = sources.setdefault(case['source_id'], case['split'])
        require(previous == case['split'], 'source leakage across development and holdout')
        require(text(case.get('category')), 'category required')
        review = case.get('review', {})
        require(isinstance(review, dict), 'review object required')
        require(all(review.get(k) is True for k in ('approved', 'redaction_reviewed', 'evidence_reviewed')) and text(review.get('reviewer')), 'human evidence/redaction review required')
        require(isinstance(case.get('context'), list) and case['context'], 'context required')
        for message in case['context']:
            require(isinstance(message, dict), 'message object required')
            require(message.get('role') in {'user', 'assistant', 'tool'} and isinstance(message.get('content'), str), 'valid context message required')
        require(case['context'][-1]['role'] == 'user', 'context must end before target answer with user message')
        fixtures = case.get('tool_fixtures')
        require(isinstance(fixtures, list), 'explicit tool fixtures required')
        for fixture in fixtures:
            require(isinstance(fixture, dict), 'fixture object required')
            require(text(fixture.get('name')) and isinstance(fixture.get('arguments'), dict) and 'result' in fixture, 'structured fixture required')
        criteria = case.get('criteria')
        require(isinstance(criteria, list) and criteria, 'criteria required')
        criterion_ids = set()
        for criterion in criteria:
            require(isinstance(criterion, dict), 'criterion object required')
            require(text(criterion.get('id')) and criterion['id'] not in criterion_ids, 'unique criterion required')
            criterion_ids.add(criterion['id'])
            require(criterion.get('kind') in {'task', 'safety'} and text(criterion.get('description')), 'task/safety criterion required')
        require(any(c['kind'] == 'safety' for c in criteria), 'safety criterion required per case')
    require({c['split'] for c in cases} == {'development', 'holdout'}, 'both splits required')
    return {'dataset_version': dataset['dataset_version'], 'dataset_digest': digest(dataset), 'cases': len(cases), 'splits': {s: sum(c['split'] == s for c in cases) for s in ('development', 'holdout')}}


def validate_run(dataset, run):
    require(isinstance(run, dict), 'run object required')
    metadata = validate_dataset(dataset)
    require(run.get('schema_version') == 1 and run.get('dataset_digest') == metadata['dataset_digest'], 'run dataset digest mismatch')
    require(text(run.get('agent_version')) and text(run.get('run_id')), 'agent version and run id required')
    require(run.get('execution') in {'fixture', 'model_replay'} and run.get('environment') == 'simulated', 'simulated environment required')
    if run['execution'] == 'model_replay':
        require(text(run.get('model')) and text(run.get('harness_version')) and text(run.get('provenance')), 'model replay provenance required')
    cases = run.get('cases')
    require(isinstance(cases, list), 'run cases required')
    expected = {c['id']: c for c in dataset['cases']}
    seen, scores = set(), {}
    for result in cases:
        require(isinstance(result, dict), 'run result object required')
        case_id = result.get('case_id')
        require(case_id in expected and case_id not in seen, 'unknown or duplicate run case')
        seen.add(case_id)
        require(isinstance(result.get('response'), str), 'actual response required')
        require(isinstance(result.get('tool_calls'), list) and isinstance(result.get('trace'), list), 'tool calls and trace required')
        for call in result['tool_calls']:
            require(isinstance(call, dict) and any(call == {'name': f['name'], 'arguments': f['arguments'], 'result': f['result']} for f in expected[case_id]['tool_fixtures']), 'tool call does not match approved simulation fixture')
        require(result.get('evidence_reviewed') is True and text(result.get('reviewer')), 'run response/trace review required')
        grades = result.get('grades')
        require(isinstance(grades, list), 'grades required')
        criteria = {c['id']: c for c in expected[case_id]['criteria']}
        grade_ids = set()
        for grade in grades:
            require(isinstance(grade, dict), 'grade object required')
            key = grade.get('criterion_id')
            require(key in criteria and key not in grade_ids, 'unknown/duplicate grade')
            grade_ids.add(key)
            require(type(grade.get('passed')) is bool and text(grade.get('evidence')) and text(grade.get('reviewer')) and grade.get('method') == 'human_review', 'reviewed boolean grade with evidence required')
            scores[(case_id, key)] = grade['passed']
        require(grade_ids == set(criteria), 'missing criterion grade')
    require(seen == set(expected), 'every dataset case must be evaluated')
    return scores


def compare(dataset, baseline, candidate):
    before, after = validate_run(dataset, baseline), validate_run(dataset, candidate)
    require(baseline['run_id'] != candidate['run_id'] and baseline['agent_version'] != candidate['agent_version'], 'distinct runs and versions required')
    regressions, gains, safety_failures, development_gains = [], [], [], []
    for case in dataset['cases']:
        for criterion in case['criteria']:
            key = (case['id'], criterion['id'])
            item = {'case_id': key[0], 'criterion_id': key[1], 'split': case['split']}
            if before[key] and not after[key]:
                regressions.append(item)
            if not before[key] and after[key]:
                gains.append(item)
                if case['split'] == 'development':
                    development_gains.append(item)
            if criterion['kind'] == 'safety' and not after[key]:
                safety_failures.append(item)
    model_evidence = baseline['execution'] == candidate['execution'] == 'model_replay'
    gate = model_evidence and not regressions and not safety_failures and bool(development_gains)
    return {'schema_version': 1, 'dataset_digest': digest(dataset), 'baseline': baseline['agent_version'], 'candidate': candidate['agent_version'], 'baseline_run_digest': digest(baseline), 'candidate_run_digest': digest(candidate), 'execution': 'model_replay' if model_evidence else 'fixture', 'regressions': regressions, 'gains': gains, 'development_gains': development_gains, 'safety_failures': safety_failures, 'eligible_for_human_pilot_review': gate, 'limits': ['Imported evidence is not cryptographically verified.', 'Single reviewed run does not prove generalization; repeat stochastic trials.', 'Fixture executions test evaluation machinery, never model quality.', 'Holdout protects against regressions; rotate after exposure to improvement authors.']}


def release_plan(dataset, baseline, candidate, image, approval, consent_ledger=None):
    require(isinstance(approval, dict), 'approval object required')
    comparison = compare(dataset, baseline, candidate)
    tenant_sources = {c['source_id'] for c in dataset['cases'] if c.get('provenance', 'tenant') == 'tenant'}
    if tenant_sources:
        require(isinstance(consent_ledger, dict), 'current consent ledger required for tenant-derived cases')
        now = time.time()
        generated = consent_ledger.get('generated_at')
        require(type(generated) in (int, float) and 0 <= now - generated <= 86400, 'consent ledger must be current within 24 hours')
        sources = consent_ledger.get('sources')
        require(isinstance(sources, list), 'consent sources required')
        allowed = {s.get('source_id') for s in sources if isinstance(s, dict) and s.get('allowed') is True and type(s.get('expires_at')) in (int, float) and s['expires_at'] > now}
        require(tenant_sources <= allowed, 'revoked, expired or unknown dataset sources block release')
    require(re.fullmatch(r'ghcr\.io/[a-z0-9_./-]+@sha256:[a-f0-9]{64}', image or '') is not None, 'immutable GHCR digest required')
    require(comparison['eligible_for_human_pilot_review'], 'comparative pilot gate failed')
    require(approval.get('approved') is True and text(approval.get('reviewer')) and approval.get('comparison_digest') == digest(comparison) and approval.get('image') == image, 'human approval must bind comparison and image')
    return {'schema_version': 1, 'image': image, 'comparison_digest': digest(comparison), 'approval_reviewer': approval['reviewer'], 'status': 'pilot_plan_only', 'stages': ['Deploy to explicitly enrolled pilot line.', 'Verify iMessage, Latch scopes, eval collector and task outcomes.', 'Record errors and approve or roll back to previous immutable image.', 'Validate state-preserving Plow update before any fleet rollout.'], 'fleet_rollout': 'blocked_pending_verified_state_preserving_update', 'executes_deploy': False}
