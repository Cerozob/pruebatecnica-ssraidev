"""Rutas de los assets del repositorio que se despliegan con CDK."""

from aws_cdk import aws_lambda as lambda_

from pruebatecnica.config import ROOT_DIR

BACKEND_DIR = ROOT_DIR / "backend"
AGENTS_DIR = ROOT_DIR / "agents"
FRONTEND_DIR = ROOT_DIR / "frontend"
ASSETS_DIR = ROOT_DIR / "assets"

_BACKEND_EXCLUDES = ["tests", "**/__pycache__", "**/*.pyc", ".pytest_cache", ".ruff_cache"]


def backend_code() -> lambda_.Code:
    """Código de todos los Lambdas: un solo asset con un handler distinto por función."""
    return lambda_.Code.from_asset(str(BACKEND_DIR), exclude=_BACKEND_EXCLUDES)
