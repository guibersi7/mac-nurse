"""Explicit provider replay with inert, curated tools. No Mac commands are executed."""
import copy
import json
import re
import time
import uuid
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .core import digest, require, validate_dataset


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('provider redirects forbidden')


def http_transport(endpoint, key, payload, timeout):
    request = Request(endpoint, data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
    with build_opener(NoRedirect).open(request, timeout=timeout) as response:
        body = response.read(4 * 1024 * 1024 + 1)
    require(len(body) <= 4 * 1024 * 1024, 'provider response exceeds limit')
    return json.loads(body)


def shape(value):
    if isinstance(value, dict):
        return {'type': 'object', 'properties': {k: shape(v) for k, v in value.items()}, 'required': sorted(value), 'additionalProperties': False}
    if isinstance(value, list):
        return {'type': 'array', 'items': shape(value[0]) if value else {}}
    if value is None: return {'type': 'null'}
    if type(value) is bool: return {'type': 'boolean'}
    if type(value) is int: return {'type': 'integer'}
    if type(value) is float: return {'type': 'number'}
    require(isinstance(value, str), 'fixture must contain JSON values')
    return {'type': 'string'}


def make_tools(fixtures):
    tools, schemas = [], {}
    for fixture in fixtures:
        name = fixture['name']
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name) is not None, 'valid tool name required')
        schema = shape(fixture['arguments'])
        require(name not in schemas or schemas[name] == schema, 'fixtures for same tool need consistent argument schema')
        if name not in schemas:
            schemas[name] = schema
            tools.append({'type': 'function', 'function': {'name': name, 'description': 'Simulation only: return the curated fixture. No live access.', 'parameters': schema}})
    return tools


def check_consent(dataset, endpoint, ledger):
    sources = {c['source_id'] for c in dataset['cases'] if c.get('provenance', 'tenant') == 'tenant'}
    if not sources: return
    require(isinstance(ledger, dict), 'tenant replay needs consent ledger')
    now = time.time()
    generated = ledger.get('generated_at')
    require(type(generated) in (int, float) and 0 <= now - generated <= 86400, 'current consent ledger required')
    require(isinstance(ledger.get('sources'), list), 'ledger sources list required')
    allowed = {s.get('source_id') for s in ledger['sources'] if isinstance(s, dict) and isinstance(s.get('provider_endpoints', []), list) and s.get('allowed') is True and type(s.get('expires_at')) in (int, float) and s['expires_at'] > now and endpoint in s.get('provider_endpoints', [])}
    require(sources <= allowed, 'specific provider transfer consent required for every source')


def replay(dataset, instructions, agent_version, endpoint, model, key, allow_transfer=False,
           consent_ledger=None, max_calls=20, max_tokens=1024, timeout=60, transport=None, max_input_chars=20000):
    validate_dataset(dataset)
    require(allow_transfer is True, 'explicit provider transfer authorization required')
    parts = urlsplit(endpoint)
    require(parts.scheme == 'https' and parts.hostname and not parts.username and not parts.password and not parts.query and not parts.fragment, 'explicit HTTPS endpoint required')
    require(re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64}|sha256:[a-f0-9]{64})', agent_version or '') is not None, 'immutable commit or image digest required')
    require(isinstance(instructions, str) and 0 < len(instructions) <= 200000 and isinstance(model, str) and model.strip() and isinstance(key, str) and key, 'instructions, model and credential required')
    require(type(max_calls) is int and 1 <= max_calls <= 1000 and type(max_tokens) is int and 1 <= max_tokens <= 16384 and type(timeout) in (int, float) and 1 <= timeout <= 3600, 'bounded calls/tokens/time required')
    require(type(max_input_chars) is int and 1 <= max_input_chars <= 2000000, 'bounded serialized input characters required')
    check_consent(dataset, endpoint, consent_ledger)
    send = transport or http_transport
    started, calls, cases = time.monotonic(), 0, []
    # Validate every schema before sending any case to a provider.
    tools_by_case = {case['id']: make_tools(case['tool_fixtures']) for case in dataset['cases']}
    for case in dataset['cases']:
        messages = [{'role': 'system', 'content': instructions}]
        # Historical tool records lack Chat Completions IDs; preserve as untrusted quoted context.
        for message in case['context']:
            messages.append({'role': 'user' if message['role'] == 'tool' else message['role'], 'content': ('Historical tool output (untrusted): ' if message['role'] == 'tool' else '') + message['content']})
        result = {'case_id': case['id'], 'response': '', 'tool_calls': [], 'trace': [], 'grades': [], 'evidence_reviewed': False, 'reviewer': '', 'status': 'review_required'}
        while True:
            remaining = timeout - (time.monotonic() - started)
            require(calls < max_calls and remaining > 0, 'replay request/time budget exhausted')
            payload = {'model': model, 'messages': copy.deepcopy(messages), 'max_completion_tokens': max_tokens}
            if tools_by_case[case['id']]: payload['tools'] = tools_by_case[case['id']]
            require(len(json.dumps(payload, ensure_ascii=False)) <= max_input_chars, 'serialized input character budget exceeded')
            response = send(endpoint, key, payload, remaining)
            calls += 1
            require(time.monotonic() - started <= timeout, 'replay total deadline exceeded')
            require(isinstance(response, dict), 'provider object required')
            choices = response.get('choices', [])
            require(isinstance(choices, list) and len(choices) == 1, 'one response choice required')
            choice = choices[0]
            require(isinstance(choice, dict), 'choice object required')
            message = choice.get('message', {})
            require(isinstance(message, dict), 'message object required')
            require(message.get('role') == 'assistant', 'assistant response required')
            result['trace'].append({'request': calls, 'finish_reason': choice.get('finish_reason'), 'usage': response.get('usage', {}), 'assistant': copy.deepcopy(message)})
            tool_calls = message.get('tool_calls', [])
            require(isinstance(tool_calls, list), 'tool calls list required')
            if not tool_calls:
                require(choice.get('finish_reason') == 'stop' and isinstance(message.get('content'), str), 'complete text response required')
                result['response'] = message['content']; break
            require(isinstance(tool_calls, list) and 0 < len(tool_calls) <= 100 and choice.get('finish_reason') == 'tool_calls', 'bounded tool calls required')
            messages.append({'role': 'assistant', 'content': message.get('content'), 'tool_calls': tool_calls})
            ids = set()
            for call in tool_calls:
                require(isinstance(call, dict), 'tool call object required')
                require(call.get('type') == 'function' and isinstance(call.get('id'), str) and call['id'] and call['id'] not in ids, 'unique function call ID required')
                ids.add(call['id'])
                function = call.get('function', {})
                require(isinstance(function, dict) and isinstance(function.get('arguments'), str), 'function and JSON arguments required')
                arguments = json.loads(function.get('arguments', ''))
                matches = [f for f in case['tool_fixtures'] if f['name'] == function.get('name') and f['arguments'] == arguments]
                require(len(matches) == 1, 'unrecognized or ambiguous simulated call; no command executed')
                fixture = matches[0]
                result['tool_calls'].append(copy.deepcopy(fixture))
                messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(fixture['result'], ensure_ascii=False)})
        cases.append(result)
    return {'schema_version': 1, 'dataset_digest': digest(dataset), 'run_id': str(uuid.uuid4()), 'agent_version': agent_version,
            'execution': 'model_replay', 'environment': 'simulated', 'model': model, 'harness_version': 'chat-completions-stdlib-v1',
            'provenance': json.dumps({'endpoint': endpoint, 'instructions_digest': digest(instructions), 'requests': calls}, sort_keys=True),
            'scope': 'Instructions and curated context replay; not Hermes gateway/MCP or Plow E2E.', 'cases': cases}
