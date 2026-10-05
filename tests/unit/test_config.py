"""Validación de config.json."""

import json

import pytest

from pruebatecnica.config import ROOT_DIR, ConfigError, parse_config

EXAMPLE = json.loads((ROOT_DIR / "config.json.example").read_text(encoding="utf-8"))


def test_example_config_is_valid():
    config = parse_config(EXAMPLE)
    assert config.region == "us-east-1"
    assert config.nag["aws_solutions"] and config.nag["serverless"]


def test_tags_are_required():
    with pytest.raises(ConfigError, match="tags"):
        parse_config({**EXAMPLE, "tags": {}})


def test_reserved_tag_prefix_is_rejected():
    with pytest.raises(ConfigError, match="aws:"):
        parse_config({**EXAMPLE, "tags": {"aws:x": "y"}})
