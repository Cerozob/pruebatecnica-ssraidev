"""Lectura de configuración de runtime desde SSM Parameter Store, con caché (ADR-036)."""

import os

from aws_lambda_powertools.utilities import parameters

# Los cambios en SSM se ven en, como mucho, cinco minutos sin redesplegar.
CACHE_SECONDS = 300


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Falta la variable de entorno {name}")
    return value


def param(env_name: str) -> str:
    """Lee el parámetro de SSM cuyo nombre está en la variable de entorno `env_name`."""
    return parameters.get_parameter(env(env_name), max_age=CACHE_SECONDS)
