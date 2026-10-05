"""Acceso a la tabla de evaluaciones (pasos 17-19)."""

from decimal import Decimal

import boto3

from common.settings import env

_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(env("EVALUATIONS_TABLE_NAME"))
    return _table


def plain(value):
    """DynamoDB devuelve los números como Decimal; el frontend espera números JSON."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    return value


SUMMARY_FIELDS = ("evaluationId", "status", "createdAt", "startedAt", "finishedAt", "progress", "summary", "error")


def summarize(item: dict) -> dict:
    return plain({key: item[key] for key in SUMMARY_FIELDS if key in item})
