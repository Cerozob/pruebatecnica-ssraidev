"""Entorno de pruebas de los Lambdas: AWS simulado con moto y un contexto de Lambda mínimo."""

import os

import pytest
from moto import mock_aws

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "tests")


@pytest.fixture
def context():
    from apitest import LambdaContext

    return LambdaContext()


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    """Cada prueba arranca con AWS simulado y sin clientes cacheados de pruebas anteriores."""
    from aws_lambda_powertools.utilities import parameters

    from common import chat, conversations, evaluations, log_viewer, requests_repo
    from triggers import post_confirmation

    for module in (conversations, evaluations, requests_repo):
        monkeypatch.setattr(module, "_table", None)
    monkeypatch.setattr(log_viewer, "_logs", None)
    monkeypatch.setattr(chat, "_agentcore", None)
    monkeypatch.setattr(post_confirmation, "_cognito", None)
    parameters.clear_caches()
    with mock_aws():
        yield
