"""Políticas de IAM para invocar un modelo de Bedrock por ID de modelo o de perfil de inferencia.

Orden de preferencia de los IDs en config.json: perfil global (`global.`), perfil geográfico (`us.`)
y, si el modelo no tiene perfiles, el ID del modelo base.
"""

from aws_cdk import Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

GLOBAL_PREFIX = "global."
_GEO_PREFIXES = ("us.", "eu.", "apac.", "jp.", "au.", "ca.", "in.")


def model_invoke_statements(scope: Construct, model_id: str, actions: list[str]) -> list[iam.PolicyStatement]:
    """Sentencias mínimas para invocar `model_id`, según la documentación de cross-Region inference.

    El modelo base solo se puede invocar a través del perfil (condición `bedrock:InferenceProfileArn`).
    """
    stack = Stack.of(scope)
    partition, region, account = stack.partition, stack.region, stack.account

    if model_id.startswith(GLOBAL_PREFIX):
        base_model = model_id.removeprefix(GLOBAL_PREFIX)
        profile_arn = f"arn:{partition}:bedrock:{region}:{account}:inference-profile/{model_id}"
        through_profile = {"StringEquals": {"bedrock:InferenceProfileArn": profile_arn}}
        return [
            iam.PolicyStatement(actions=actions, resources=[profile_arn]),
            iam.PolicyStatement(
                actions=actions,
                resources=[f"arn:{partition}:bedrock:{region}::foundation-model/{base_model}"],
                conditions=through_profile,
            ),
            # El perfil global enruta a cualquier región comercial; ese destino se autoriza con el ARN sin región.
            iam.PolicyStatement(
                actions=actions,
                resources=[f"arn:{partition}:bedrock:::foundation-model/{base_model}"],
                conditions={
                    "StringEquals": {
                        "aws:RequestedRegion": "unspecified",
                        "bedrock:InferenceProfileArn": profile_arn,
                    }
                },
            ),
        ]

    for prefix in _GEO_PREFIXES:
        if model_id.startswith(prefix):
            base_model = model_id.removeprefix(prefix)
            profile_arn = f"arn:{partition}:bedrock:{region}:{account}:inference-profile/{model_id}"
            return [
                iam.PolicyStatement(actions=actions, resources=[profile_arn]),
                # Las regiones de destino del perfil geográfico las decide Bedrock; se limita al perfil.
                iam.PolicyStatement(
                    actions=actions,
                    resources=[f"arn:{partition}:bedrock:*::foundation-model/{base_model}"],
                    conditions={"StringEquals": {"bedrock:InferenceProfileArn": profile_arn}},
                ),
            ]

    return [
        iam.PolicyStatement(
            actions=actions, resources=[f"arn:{partition}:bedrock:{region}::foundation-model/{model_id}"]
        )
    ]
