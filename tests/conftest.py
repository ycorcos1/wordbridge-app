import os
from collections.abc import Iterator

import pytest

from app import create_app
from models import reset_engine


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    reset_engine()

    application = create_app()
    application.config.update(TESTING=True)

    yield application


@pytest.fixture()
def client(app) -> Iterator:
    with app.test_client() as client:
        yield client


@pytest.fixture()
def app_context(app):
    with app.app_context():
        yield


