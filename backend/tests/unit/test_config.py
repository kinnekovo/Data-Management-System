from pathlib import Path

from app.core import config
from app.core.config import DEFAULT_ENV_FILE, Settings


def test_local_mongodb_is_the_default_when_no_env_file_is_loaded():
    settings = Settings(_env_file=None)
    assert settings.mongodb_uri == "mongodb://127.0.0.1:27017"
    assert settings.mongodb_database == "survey_system"


def test_root_env_file_location_is_independent_of_working_directory():
    assert DEFAULT_ENV_FILE.name == ".env"
    assert DEFAULT_ENV_FILE == Path(config.__file__).resolve().parents[3] / ".env"
