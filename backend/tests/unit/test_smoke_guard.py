import pytest

from app.core.config import Settings
from app.db import smoke_check


def test_smoke_check_rejects_non_test_database(monkeypatch):
    unsafe = Settings(_env_file=None, mongodb_test_database="survey_system")
    monkeypatch.setattr(smoke_check, "get_settings", lambda: unsafe)
    with pytest.raises(RuntimeError, match="must end with '_test'"):
        smoke_check.run()
