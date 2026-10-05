"""Configuración de runtime leída de SSM Parameter Store, con caché corta (ADR-036)."""

import os
import time
from dataclasses import dataclass

import boto3

CACHE_SECONDS = 300

_cache: dict[str, tuple[float, str]] = {}
_ssm = None


def _client():
    global _ssm
    if _ssm is None:
        _ssm = boto3.client("ssm")
    return _ssm


def param(env_name: str) -> str:
    """Lee el parámetro cuyo nombre está en la variable de entorno `env_name`."""
    name = os.environ[env_name]
    cached = _cache.get(name)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    value = _client().get_parameter(Name=name)["Parameter"]["Value"]
    _cache[name] = (time.monotonic(), value)
    return value


@dataclass(frozen=True)
class AgentSettings:
    model_id: str
    guardrail_id: str
    guardrail_version: str
    gateway_url: str
    blocked_message: str
    region: str
    knowledge_target: str
    web_search_target: str
    requests_target_prefix: str

    @classmethod
    def load(cls) -> AgentSettings:
        return cls(
            model_id=param("MODEL_ID_PARAM"),
            guardrail_id=param("GUARDRAIL_ID_PARAM"),
            guardrail_version=param("GUARDRAIL_VERSION_PARAM"),
            gateway_url=param("GATEWAY_URL_PARAM"),
            blocked_message=param("BLOCKED_MESSAGE_PARAM"),
            region=os.environ.get("AWS_REGION", "us-east-1"),
            knowledge_target=os.environ["KNOWLEDGE_TARGET"],
            web_search_target=os.environ["WEB_SEARCH_TARGET"],
            requests_target_prefix=os.environ["REQUESTS_TARGET_PREFIX"],
        )
