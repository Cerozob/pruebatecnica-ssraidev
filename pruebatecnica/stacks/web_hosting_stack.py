"""Hosting del frontend: bucket privado servido por CloudFront con OAC (paso 1).

El contenido se publica en WebContentStack, porque depende de la autenticación y de la API,
que a su vez necesitan el dominio de CloudFront para CORS y para las URLs de retorno de Cognito.
"""

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from constructs import Construct

from pruebatecnica.config import AppConfig
from pruebatecnica.constructs.nag import acknowledge


def site_bucket_name(config: AppConfig, stack: Stack) -> str:
    """Nombre determinista: WebContentStack importa el bucket sin una referencia entre stacks."""
    return f"{config.project_name}-web-{stack.account}-{stack.region}"


class WebHostingStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        access_logs_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.site_bucket = s3.Bucket(
            self,
            "SiteBucket",
            bucket_name=site_bucket_name(config, self),
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            server_access_logs_bucket=access_logs_bucket,
            server_access_logs_prefix="site-bucket/",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        security_headers = cloudfront.ResponseHeadersPolicy(
            self,
            "SecurityHeaders",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.days(365), include_subdomains=True, override=True
                ),
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(override=True),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.DENY, override=True
                ),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                    referrer_policy=cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN, override=True
                ),
            ),
        )

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment=f"Frontend de {config.project_name}",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(self.site_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=security_headers,
            ),
            # SPA: las rutas del cliente se resuelven en index.html.
            error_responses=[
                cloudfront.ErrorResponse(http_status=403, response_http_status=200, response_page_path="/index.html"),
                cloudfront.ErrorResponse(http_status=404, response_http_status=200, response_page_path="/index.html"),
            ],
        )
        self.site_url = f"https://{self.distribution.distribution_domain_name}"

        acknowledge(
            self.distribution,
            "AwsSolutions-CFR1",
            "Es una herramienta interna sin restricciones geográficas de negocio.",
        )
        acknowledge(self.distribution, "AwsSolutions-CFR2", "AWS WAF queda fuera del alcance por costo (ADR-039).")
        acknowledge(
            self.distribution,
            "AwsSolutions-CFR3",
            "Los logs estándar de CloudFront requieren un bucket con ACLs; se omiten por simplicidad (ADR-039).",
        )
        acknowledge(
            self.distribution,
            "AwsSolutions-CFR4",
            "Sin dominio propio (ADR-039), CloudFront usa su certificado por defecto, que admite TLSv1.",
        )

        CfnOutput(self, "SiteUrl", value=self.site_url)
