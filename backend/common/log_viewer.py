"""Visor básico de CloudWatch: solo log groups con las etiquetas de la aplicación (ADR-037)."""

import base64
import binascii
import json

import boto3
from botocore.exceptions import ParamValidationError

from common.settings import param

_logs = None


def logs_client():
    global _logs
    if _logs is None:
        _logs = boto3.client("logs")
    return _logs


def log_group_id(name: str) -> str:
    """Id seguro para la ruta: base64url sin relleno, sin barras ni caracteres que API Gateway decodifique."""
    return base64.urlsafe_b64encode(name.encode()).decode().rstrip("=")


def log_group_name(group_id: str) -> str | None:
    try:
        return base64.urlsafe_b64decode(group_id + "=" * (-len(group_id) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError):
        return None


def app_tags() -> dict[str, str]:
    return json.loads(param("LOG_TAG_FILTERS_PARAM"))


def has_app_tags(tags: dict[str, str], required: dict[str, str]) -> bool:
    return all(tags.get(key) == value for key, value in required.items())


def _tags_of(log_group_arn: str) -> dict[str, str]:
    # ListTagsForResource no acepta el sufijo ":*" del ARN que devuelve DescribeLogGroups.
    arn = log_group_arn.removesuffix(":*")
    return logs_client().list_tags_for_resource(resourceArn=arn).get("tags", {})


def list_tagged_log_groups() -> list[str]:
    required = app_tags()
    client = logs_client()
    names: list[str] = []
    try:
        kwargs = {"logGroupTags": [{"key": key, "values": [value]} for key, value in required.items()]}
        while True:
            page = client.list_log_groups(**kwargs)
            names.extend(group["logGroupName"] for group in page.get("logGroups", []))
            if not page.get("nextToken"):
                break
            kwargs["nextToken"] = page["nextToken"]
    except ParamValidationError:
        # El SDK incluido en el runtime de Lambda puede no conocer aún el filtro por etiquetas.
        names = []
        for page in client.get_paginator("describe_log_groups").paginate():
            for group in page.get("logGroups", []):
                if has_app_tags(_tags_of(group["arn"]), required):
                    names.append(group["logGroupName"])
    return sorted(names)


def is_app_log_group(log_group_name: str, region: str, account: str) -> bool:
    arn = f"arn:aws:logs:{region}:{account}:log-group:{log_group_name}"
    try:
        return has_app_tags(_tags_of(arn), app_tags())
    except logs_client().exceptions.ResourceNotFoundException:
        return False
