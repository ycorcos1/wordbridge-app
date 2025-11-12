import os

from config.settings import get_settings


def test_env_settings_load():
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"

    settings = get_settings()

    assert settings.SECRET_KEY == "test-secret"
    assert settings.DATABASE_URL.startswith("postgresql://")

