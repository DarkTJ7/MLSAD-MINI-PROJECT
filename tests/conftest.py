import pytest

@pytest.fixture(autouse=True)
def explicit_unit_only_safety_mode(monkeypatch):
    # Unit tests do not silently pretend pretrained models were executed.
    # The independent real-model suite is evaluation.safety_evaluate.
    monkeypatch.setenv('SAFETY_REQUIRED','false')
    monkeypatch.delenv('SAFETY_URL',raising=False)
