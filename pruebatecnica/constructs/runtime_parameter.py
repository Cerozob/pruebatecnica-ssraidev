"""Parámetros de configuración de runtime en SSM Parameter Store (ADR-036)."""

from aws_cdk import aws_iam as iam
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from pruebatecnica.config import AppConfig


class RuntimeParameter(Construct):
    """Un parámetro String bajo el prefijo del proyecto, con un helper para dar acceso de lectura.

    Los componentes reciben el nombre del parámetro en una variable de entorno y leen el valor
    en tiempo de ejecución, así se puede cambiar sin redesplegar.
    """

    def __init__(
        self, scope: Construct, construct_id: str, *, config: AppConfig, name: str, value: str, description: str
    ) -> None:
        super().__init__(scope, construct_id)
        self.parameter_name = f"{config.ssm_prefix}/{name}"
        self.parameter = ssm.StringParameter(
            self,
            "Parameter",
            parameter_name=self.parameter_name,
            string_value=value,
            description=description,
            tier=ssm.ParameterTier.STANDARD,
        )

    def grant_read(self, grantee: iam.IGrantable) -> None:
        self.parameter.grant_read(grantee)
