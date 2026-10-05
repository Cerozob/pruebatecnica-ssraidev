"""Publicación del frontend y de su configuración de runtime en el bucket de CloudFront (paso 1)."""

import shutil
import subprocess
from pathlib import Path

import jsii
from aws_cdk import BundlingOptions, DockerImage, ILocalBundling, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

from pruebatecnica.config import AppConfig
from pruebatecnica.constructs.assets import FRONTEND_DIR
from pruebatecnica.stacks.web_hosting_stack import site_bucket_name

_FRONTEND_EXCLUDES = ["node_modules", "dist", ".vite", "coverage"]


@jsii.implements(ILocalBundling)
class _PnpmBuild:
    """Compila el frontend con pnpm en la máquina local, sin depender de Docker."""

    def try_bundle(self, output_dir: str, *, image, **_kwargs) -> bool:
        pnpm = shutil.which("pnpm")
        if pnpm is None:
            return False
        # Comandos fijos sobre el ejecutable de pnpm encontrado en el PATH; no hay entrada externa.
        subprocess.run([pnpm, "install", "--frozen-lockfile"], cwd=FRONTEND_DIR, check=True)  # noqa: S603
        subprocess.run([pnpm, "run", "build"], cwd=FRONTEND_DIR, check=True)  # noqa: S603
        shutil.copytree(FRONTEND_DIR / "dist", Path(output_dir), dirs_exist_ok=True)
        return True


class WebContentStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        distribution: cloudfront.IDistribution,
        runtime_config: dict,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # Importado por nombre para que la política del despliegue no dependa de una exportación.
        site_bucket = s3.Bucket.from_bucket_name(self, "SiteBucket", site_bucket_name(config, self))

        frontend = s3deploy.Source.asset(
            str(FRONTEND_DIR),
            exclude=_FRONTEND_EXCLUDES,
            bundling=BundlingOptions(
                local=_PnpmBuild(),
                # Alternativa si pnpm no está instalado localmente.
                image=DockerImage.from_registry("public.ecr.aws/docker/library/node:22-alpine"),
                command=[
                    "sh",
                    "-c",
                    "corepack enable && pnpm install --frozen-lockfile && pnpm run build"
                    " && cp -r dist/. /asset-output/",
                ],
                user="root",
            ),
        )

        # La configuración del frontend se genera en el despliegue con los valores reales de los otros stacks.
        s3deploy.BucketDeployment(
            self,
            "FrontendDeployment",
            sources=[frontend, s3deploy.Source.json_data("config.json", runtime_config)],
            destination_bucket=site_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
            memory_limit=512,
        )
