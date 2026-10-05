"""Identidad: user pool de Cognito con managed login y registro restringido (pasos 1, 2 y 27)."""

import json

from aws_cdk import CfnOutput, Duration, RemovalPolicy, SecretValue, Stack
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from pruebatecnica.config import AppConfig
from pruebatecnica.constructs.assets import backend_code
from pruebatecnica.constructs.nag import acknowledge
from pruebatecnica.constructs.python_function import PythonFunction

LOCAL_DEV_URL = "http://localhost:5173"

# ADR-043: grupos de Cognito. Todo registro nuevo entra a USERS_GROUP; ADMINS_GROUP se asigna a mano.
ADMINS_GROUP = "admins"
USERS_GROUP = "users"


class AuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, config: AppConfig, site_url: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ADR-027: los correos y dominios permitidos viven en Secrets Manager, no en el código.
        allowlist = secretsmanager.Secret(
            self,
            "SignUpAllowlist",
            description="Correos y dominios autorizados para registrarse en el asistente",
            secret_string_value=SecretValue.unsafe_plain_text(
                json.dumps({"emails": config.allowed_emails, "domains": config.allowed_domains})
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        acknowledge(
            allowlist,
            "AwsSolutions-SMG4",
            "No es una credencial: es una lista de correos y dominios que no admite rotación.",
        )

        pre_signup = PythonFunction(
            self,
            "PreSignUp",
            code=backend_code(),
            handler="triggers.pre_signup.handler",
            service_name="pre-signup",
            description="Rechaza registros de correos o dominios no autorizados (ADR-007)",
            log_retention_days=config.log_retention_days,
            environment={"ALLOWLIST_SECRET_ARN": allowlist.secret_arn},
            timeout=Duration.seconds(10),
            memory_size=256,
        )
        allowlist.grant_read(pre_signup.function)

        post_confirmation = PythonFunction(
            self,
            "PostConfirmation",
            code=backend_code(),
            handler="triggers.post_confirmation.handler",
            service_name="post-confirmation",
            description="Agrega cada usuario nuevo al grupo de usuarios normales (ADR-043)",
            log_retention_days=config.log_retention_days,
            environment={"DEFAULT_GROUP": USERS_GROUP},
            timeout=Duration.seconds(10),
            memory_size=256,
        )

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            feature_plan=cognito.FeaturePlan.ESSENTIALS,
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_digits=True,
                require_lowercase=True,
                require_uppercase=True,
                require_symbols=True,
            ),
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(sms=False, otp=True),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            lambda_triggers=cognito.UserPoolTriggers(
                pre_sign_up=pre_signup.function, post_confirmation=post_confirmation.function
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        acknowledge(
            self.user_pool, "AwsSolutions-COG2", "MFA opcional con TOTP: obligatoria complicaría la demostración."
        )
        acknowledge(
            self.user_pool,
            "AwsSolutions-COG3",
            "La protección contra amenazas requiere el plan Plus de Cognito; queda fuera por costo (ADR-039).",
        )

        acknowledge(
            self.user_pool,
            "AwsSolutions-COG8",
            "El plan Plus de Cognito tiene costo por usuario; el plan Essentials cubre el managed login (ADR-039).",
        )

        cognito.CfnUserPoolGroup(
            self,
            "AdminsGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name=ADMINS_GROUP,
            description="Administradores: visor de logs y evaluaciones. Se asigna a mano en la consola.",
            precedence=0,
        )
        cognito.CfnUserPoolGroup(
            self,
            "UsersGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name=USERS_GROUP,
            description="Usuarios normales: conversaciones y carga de documentos. Grupo por defecto.",
            precedence=10,
        )
        # Política aparte, adjunta al rol después de crear el pool: dentro del rol de la función crearía un
        # ciclo (el pool depende de la función y el permiso, del ARN del pool).
        iam.Policy(
            self,
            "PostConfirmationGroupPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["cognito-idp:AdminAddUserToGroup"], resources=[self.user_pool.user_pool_arn]
                )
            ],
        ).attach_to_role(post_confirmation.function.role)

        self.domain = self.user_pool.add_domain(
            "ManagedLoginDomain",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=config.auth_domain_prefix),
            managed_login_version=cognito.ManagedLoginVersion.NEWER_MANAGED_LOGIN,
        )

        callback_urls = [f"{site_url}/", f"{LOCAL_DEV_URL}/"]
        self.client = self.user_pool.add_client(
            "WebClient",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_srp=True),
            prevent_user_existence_errors=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                callback_urls=callback_urls,
                logout_urls=callback_urls,
            ),
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO],
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(7),
        )

        # ADR-006: estilo por defecto del managed login.
        cognito.CfnManagedLoginBranding(
            self,
            "ManagedLoginBranding",
            user_pool_id=self.user_pool.user_pool_id,
            client_id=self.client.user_pool_client_id,
            use_cognito_provided_values=True,
        ).node.add_dependency(self.domain)

        self.hosted_ui_domain = f"{config.auth_domain_prefix}.auth.{self.region}.amazoncognito.com"

        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=self.client.user_pool_client_id)
        CfnOutput(self, "SignUpAllowlistSecretArn", value=allowlist.secret_arn)
