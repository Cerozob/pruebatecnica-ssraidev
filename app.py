#!/usr/bin/env python3
"""Entrada de la app de CDK: stacks separados por dominio (ADR-035), etiquetas y cdk-nag (ADR-034)."""

import aws_cdk as cdk
from cdk_nag import (
    AwsSolutionsChecks,
    HIPAASecurityChecks,
    NIST80053R4Checks,
    NIST80053R5Checks,
    PCIDSS321Checks,
    ServerlessChecks,
)

from pruebatecnica.app_builder import build_app
from pruebatecnica.config import load_config

NAG_PACKS = {
    "aws_solutions": AwsSolutionsChecks,
    "hipaa_security": HIPAASecurityChecks,
    "nist_800_53_r4": NIST80053R4Checks,
    "nist_800_53_r5": NIST80053R5Checks,
    "pci_dss_321": PCIDSS321Checks,
    "serverless": ServerlessChecks,
}

config = load_config()
app = cdk.App()
build_app(app, config)

for flag, pack in NAG_PACKS.items():
    if config.nag[flag]:
        cdk.Validations.of(app).add_plugins(pack(app))

app.synth()
