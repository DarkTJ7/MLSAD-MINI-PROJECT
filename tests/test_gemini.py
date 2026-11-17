import json
import pytest
from app.provider import Gateway, ProviderUnavailable

def test_gemini_missing_api_key(monkeypatch):
    monkeypatch.setenv('MODEL_PROVIDER', 'gemini')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    g = Gateway()
    state = {'deadline': 9999999999, 'events': [], 'fnol': {'retrieval_version': 'v5'}}
    with pytest.raises(ProviderUnavailable, match='GEMINI_API_KEY is not configured'):
        g.call(state, 'analysis', {'messages': []})

def test_gemini_provider_flag(monkeypatch):
    g = Gateway()
    monkeypatch.delenv('MODEL_PROVIDER', raising=False)
    monkeypatch.setenv('MODEL_MODE', 'stub')
    assert not g.is_gemini()

    monkeypatch.setenv('MODEL_PROVIDER', 'gemini')
    assert g.is_gemini()

    monkeypatch.delenv('MODEL_PROVIDER', raising=False)
    monkeypatch.setenv('MODEL_MODE', 'gemini')
    assert g.is_gemini()

def test_gemini_mocked_success(monkeypatch):
    monkeypatch.setenv('MODEL_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-fake-key')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    
    mock_response = {'action': 'finish', 'argument': '', 'purpose': 'Hand gathered evidence to verifier'}
    
    # Mock google.genai client
    class MockRes:
        text = json.dumps(mock_response)
        class Usage:
            prompt_token_count = 120
            candidates_token_count = 45
        usage_metadata = Usage()
        
    class MockModels:
        def generate_content(self, *args, **kwargs):
            return MockRes()
            
    class MockClient:
        def __init__(self, *args, **kwargs):
            self.models = MockModels()

    import google.genai
    monkeypatch.setattr(google.genai, 'Client', MockClient)

    g = Gateway()
    state = {'deadline': 9999999999, 'events': [], 'fnol': {'retrieval_version': 'v5'}}
    payload = {
        'messages': [{'role': 'system', 'content': 'You are an agent'}, {'role': 'user', 'content': 'Do work'}],
        'temperature': 0,
        'max_tokens': 150,
        'prompt_version': 'v5'
    }
    result = g.call(state, 'analysis', payload)
    assert 'choices' in result
    content = json.loads(result['choices'][0]['message']['content'])
    assert content['action'] == 'finish'
    assert result['usage']['prompt_tokens'] == 120
    assert result['usage']['completion_tokens'] == 45
    assert state['events'][-1]['usage_source'] == 'gemini'
