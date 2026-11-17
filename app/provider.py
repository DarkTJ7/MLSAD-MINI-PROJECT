"""Bounded provider gateway. Supports deterministic stub, local model, and Google Gemini API."""
from __future__ import annotations
import json
import os
import time
import httpx
from .http_client import post
from .config import required
from .telemetry import COST, RETRIES

class ProviderUnavailable(RuntimeError):
    pass

class Gateway:
    def __init__(self, connection=None):
        self.connection = connection
        self.failures = 0
        self.open_until = 0

    def is_gemini(self) -> bool:
        provider = os.getenv('MODEL_PROVIDER', '').strip().lower()
        if provider == 'gemini':
            return True
        mode = os.getenv('MODEL_MODE', '').strip().lower()
        if mode == 'gemini':
            return True
        return False

    def call(self, state, agent, payload):
        if self.is_gemini():
            return self._call_gemini(state, agent, payload)
        return self._call_http(state, agent, payload)

    @staticmethod
    def _sanitize_gemini_schema(schema):
        """Recursively strip JSON Schema fields rejected by Gemini's OpenAPI responseSchema."""
        if not isinstance(schema, dict):
            return schema
        unsupported = {'additionalProperties', '$schema', '$defs', 'title', 'default', 'minLength', 'maxLength'}
        cleaned = {}
        for k, v in schema.items():
            if k in unsupported:
                continue
            if k == 'properties' and isinstance(v, dict):
                cleaned[k] = {pk: Gateway._sanitize_gemini_schema(pv) for pk, pv in v.items()}
            elif isinstance(v, dict):
                cleaned[k] = Gateway._sanitize_gemini_schema(v)
            elif isinstance(v, list):
                cleaned[k] = [Gateway._sanitize_gemini_schema(item) for item in v]
            else:
                cleaned[k] = v
        return cleaned

    def _call_gemini(self, state, agent, payload):
        started = time.monotonic()
        api_key = os.getenv('GEMINI_API_KEY', '').strip()
        if not api_key:
            raise ProviderUnavailable('GEMINI_API_KEY is not configured in environment variables. Please set GEMINI_API_KEY in your .env file.')

        model = os.getenv('GEMINI_MODEL') or os.getenv('MODEL_ID') or 'gemini-2.5-flash'
        remaining = max(0.5, min(float(os.getenv('MODEL_TIMEOUT_SECONDS', '30')), state['deadline'] - time.time()))

        messages = payload.get('messages', [])
        system_instruction = ''
        user_content = ''
        for m in messages:
            if m.get('role') == 'system':
                system_instruction = m.get('content', '')
            elif m.get('role') == 'user':
                user_content = m.get('content', '')

        response_format = payload.get('response_format')
        schema = None
        if isinstance(response_format, dict) and response_format.get('type') == 'json_schema':
            raw_schema = response_format.get('json_schema', {}).get('schema')
            schema = self._sanitize_gemini_schema(raw_schema)

        max_tokens = max(512, int(payload.get('max_tokens', 250)))
        content_text = None
        prompt_tokens = 0
        completion_tokens = 0
        errors = []

        # Attempt call via official google-genai SDK
        sdk_succeeded = False
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            config_kwargs = {
                'temperature': float(payload.get('temperature', 0.0)),
                'max_output_tokens': max_tokens,
                'response_mime_type': 'application/json',
            }
            if '2.5' in model and hasattr(types, 'ThinkingConfig'):
                config_kwargs['thinking_config'] = types.ThinkingConfig(thinking_budget=0)
            if system_instruction:
                config_kwargs['system_instruction'] = system_instruction
            if schema:
                config_kwargs['response_schema'] = schema

            gen_config = types.GenerateContentConfig(**config_kwargs)
            res = client.models.generate_content(
                model=model,
                contents=user_content,
                config=gen_config,
            )
            content_text = res.text
            usage = getattr(res, 'usage_metadata', None)
            if usage:
                prompt_tokens = getattr(usage, 'prompt_token_count', 0) or 0
                completion_tokens = getattr(usage, 'candidates_token_count', 0) or 0
            sdk_succeeded = True
        except Exception as exc:
            errors.append(f'sdk_error:{type(exc).__name__}:{str(exc)[:100]}')

        # Fallback to direct Gemini REST API if SDK call was unsuccessful
        if not sdk_succeeded or not content_text:
            try:
                rest_url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
                body = {
                    'contents': [{'parts': [{'text': user_content}]}],
                    'generationConfig': {
                        'temperature': float(payload.get('temperature', 0.0)),
                        'maxOutputTokens': max_tokens,
                        'responseMimeType': 'application/json'
                    }
                }
                if '2.5' in model:
                    body['generationConfig']['thinkingConfig'] = {'thinkingBudget': 0}
                if system_instruction:
                    body['system_instruction'] = {'parts': [{'text': system_instruction}]}
                if schema:
                    body['generationConfig']['responseSchema'] = schema

                with httpx.Client(timeout=remaining) as client:
                    resp = client.post(rest_url, json=body)
                    if resp.status_code == 400:
                        raise ProviderUnavailable(f'Gemini API bad request (400): {resp.text[:200]}')
                    if resp.status_code == 403 or resp.status_code == 401:
                        raise ProviderUnavailable('Gemini API authentication failed: Check GEMINI_API_KEY.')
                    if resp.status_code == 429:
                        raise ProviderUnavailable('Gemini API rate limit exceeded (429).')
                    resp.raise_for_status()
                    data = resp.json()
                    candidates = data.get('candidates', [])
                    if candidates and 'content' in candidates[0]:
                        parts = candidates[0]['content'].get('parts', [])
                        if parts:
                            content_text = parts[0].get('text', '')
                    usage = data.get('usageMetadata', {})
                    prompt_tokens = usage.get('promptTokenCount', 0)
                    completion_tokens = usage.get('candidatesTokenCount', 0)
            except Exception as exc:
                errors.append(f'rest_error:{type(exc).__name__}:{str(exc)[:100]}')
                if not content_text:
                    raise ProviderUnavailable(f'Gemini provider failure: {str(exc)[:150]}')

        # Validate that content_text is JSON
        try:
            parsed = json.loads(content_text)
        except Exception as exc:
            raise ProviderUnavailable(f'Gemini returned non-JSON output: {content_text[:120]}')

        # Pricing calculation
        input_rate = float(os.getenv('INPUT_USD_PER_MILLION', '0.075'))
        output_rate = float(os.getenv('OUTPUT_USD_PER_MILLION', '0.30'))
        cost_usd = (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000

        event = {
            'agent': agent,
            'step': 'provider',
            'seconds': time.monotonic() - started,
            'attempts': 1,
            'errors': errors,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'cost_usd': cost_usd,
            'usage_source': 'gemini',
            'model': model,
            'prompt_version': payload.get('prompt_version', state['fnol']['retrieval_version'])
        }
        COST.labels(agent).inc(cost_usd)
        state.setdefault('events', []).append(event)

        return {
            'choices': [{'message': {'content': json.dumps(parsed)}}],
            'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens},
            'model': model,
            'provider': 'gemini'
        }

    def _call_http(self, state, agent, payload):
        key = 'provider:circuit'
        open_until = float(self.connection.get(key) or 0) if self.connection else self.open_until
        if open_until > time.time():
            raise ProviderUnavailable('circuit_open')
        response = None
        started = time.monotonic()
        errors = []
        attempts = 0
        for attempt in range(3):
            attempts += 1
            if time.time() > state['deadline']:
                raise ProviderUnavailable('run_deadline')
            try:
                remaining = max(.01, min(float(os.getenv('MODEL_TIMEOUT_SECONDS', '8')), state['deadline'] - time.time()))
                api_key = os.getenv('MODEL_API_KEY', '')
                headers = {'Authorization': 'Bearer ' + api_key} if api_key else {}
                wire = payload
                if os.getenv('MODEL_MODE', 'stub') != 'stub':
                    wire = {k: v for k, v in payload.items() if k in ('model', 'messages', 'temperature', 'max_tokens', 'response_format')}
                response = post(required('MODEL_URL'), json=wire, timeout=remaining, headers=headers)
                response.raise_for_status()
                response = response.json()
                if self.connection:
                    self.connection.delete('provider:failures', key)
                self.failures = 0
                break
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(type(exc).__name__)
                if attempt < 2:
                    RETRIES.labels(agent).inc()
                    time.sleep(min(.1 * 2**attempt, max(0, state['deadline'] - time.time())))
        event = {
            'agent': agent,
            'step': 'provider',
            'seconds': time.monotonic() - started,
            'attempts': attempts,
            'errors': errors,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'cost_usd': 0.0,
            'usage_source': 'stub' if os.getenv('MODEL_MODE', 'stub') == 'stub' else 'provider',
            'prompt_version': payload.get('prompt_version', state['fnol']['retrieval_version'])
        }
        if response is None or not isinstance(response, dict):
            failures = int(self.connection.incr('provider:failures')) if self.connection else self.failures + 1
            self.failures = failures
            if failures >= int(os.getenv('CIRCUIT_FAILURE_THRESHOLD', '2')):
                until = time.time() + float(os.getenv('CIRCUIT_COOLDOWN_SECONDS', '20'))
                if self.connection:
                    self.connection.set(key, until, ex=60)
                self.open_until = until
            state.setdefault('events', []).append(event)
            raise ProviderUnavailable('provider_unavailable')
        usage = response.get('usage', {})
        event['prompt_tokens'] = int(usage.get('prompt_tokens', 0))
        event['completion_tokens'] = int(usage.get('completion_tokens', 0))
        if os.getenv('MODEL_MODE', 'stub') != 'stub':
            if not usage or 'INPUT_USD_PER_MILLION' not in os.environ or 'OUTPUT_USD_PER_MILLION' not in os.environ:
                raise ProviderUnavailable('live usage or runtime prices unavailable')
            event['cost_usd'] = (event['prompt_tokens'] * float(os.environ['INPUT_USD_PER_MILLION']) +
                                 event['completion_tokens'] * float(os.environ['OUTPUT_USD_PER_MILLION'])) / 1000000
        COST.labels(agent).inc(event['cost_usd'])
        state.setdefault('events', []).append(event)
        return response
