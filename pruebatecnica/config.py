"""Carga y validación de config.json, la única fuente de configuración del despliegue."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config.json"

NAG_FLAGS = (
    "aws_solutions",
    "hipaa_security",
    "nist_800_53_r4",
    "nist_800_53_r5",
    "pci_dss_321",
    "serverless",
)


class ConfigError(ValueError):
    """config.json falta o no es válido."""


@dataclass(frozen=True)
class AppConfig:
    project_name: str
    account: str | None
    region: str
    tags: dict[str, str]
    nag: dict[str, bool]
    auth_domain_prefix: str
    allowed_emails: list[str]
    allowed_domains: list[str]
    agent_model_id: str
    judge_model_id: str
    web_search_allowed_domains: list[str]
    api_throttle_rate_limit: int
    api_throttle_burst_limit: int
    log_retention_days: int

    @property
    def ssm_prefix(self) -> str:
        """Prefijo de los parámetros de SSM de runtime (ADR-036)."""
        return f"/{self.project_name}"


def _require(data: dict, key: str, kind: type, where: str = ""):
    value = data.get(key)
    if not isinstance(value, kind):
        raise ConfigError(f"config.json: '{where}{key}' es obligatorio y debe ser {kind.__name__}")
    return value


def _validate_tags(tags: dict) -> dict[str, str]:
    # Sin etiquetas no se despliega: el visor de logs filtra por ellas (ADR-037).
    if not tags:
        raise ConfigError("config.json: 'tags' no puede estar vacío; todos los recursos deben llevar etiquetas")
    if len(tags) > 50:
        raise ConfigError("config.json: 'tags' admite como máximo 50 etiquetas")
    for key, value in tags.items():
        if not isinstance(value, str):
            raise ConfigError(f"config.json: la etiqueta '{key}' debe tener un valor de texto")
        if key.lower().startswith("aws:"):
            raise ConfigError(f"config.json: la etiqueta '{key}' usa el prefijo reservado 'aws:'")
        if not 1 <= len(key) <= 128 or len(value) > 256:
            raise ConfigError(f"config.json: la etiqueta '{key}' supera los límites de longitud de AWS")
    return dict(tags)


def parse_config(data: dict) -> AppConfig:
    project_name = _require(data, "project_name", str)
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,30}", project_name):
        raise ConfigError("config.json: 'project_name' debe tener 3-31 caracteres en minúscula, números o guiones")

    tags = _validate_tags(_require(data, "tags", dict))

    nag_raw = _require(data, "nag", dict)
    nag = {flag: bool(nag_raw.get(flag, False)) for flag in NAG_FLAGS}

    auth = _require(data, "auth", dict)
    models = _require(data, "models", dict)
    web_search = _require(data, "web_search", dict)
    api = data.get("api", {})
    logs = data.get("logs", {})

    domain_prefix = _require(auth, "domain_prefix", str, "auth.")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", domain_prefix):
        raise ConfigError("config.json: 'auth.domain_prefix' no es un prefijo de dominio de Cognito válido")

    region = _require(data, "region", str)
    account = data.get("account") or None

    return AppConfig(
        project_name=project_name,
        account=account,
        region=region,
        tags=tags,
        nag=nag,
        auth_domain_prefix=domain_prefix,
        allowed_emails=list(auth.get("allowed_emails", [])),
        allowed_domains=list(auth.get("allowed_domains", [])),
        agent_model_id=_require(models, "agent_model_id", str, "models."),
        judge_model_id=_require(models, "judge_model_id", str, "models."),
        web_search_allowed_domains=list(_require(web_search, "allowed_domains", list, "web_search.")),
        api_throttle_rate_limit=int(api.get("throttle_rate_limit", 10)),
        api_throttle_burst_limit=int(api.get("throttle_burst_limit", 20)),
        log_retention_days=int(logs.get("retention_days", 30)),
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not path.exists():
        raise ConfigError(f"No se encontró {path}. Copia config.json.example a config.json y completa los valores.")
    with path.open(encoding="utf-8") as handle:
        return parse_config(json.load(handle))
