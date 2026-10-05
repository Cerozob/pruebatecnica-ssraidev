"""POST /documents/upload-url: URL prefirmada para subir un documento directo a S3 (pasos 4-5, ADR-009)."""

import re
from pathlib import PurePosixPath

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths
from pydantic import BaseModel, Field, field_validator

from common.http import build_resolver
from common.ids import new_id
from common.settings import param

logger = Logger()
app = build_resolver()

UPLOAD_PREFIX = "documentos"
URL_EXPIRATION_SECONDS = 900
# Formatos de documento y tamaño máximo por archivo que admite la base de conocimiento (ADR-011).
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".html", ".htm", ".csv", ".doc", ".docx", ".xls", ".xlsx"}
MAX_SIZE_BYTES = 50 * 1024 * 1024

_s3 = None


def _s3_client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3")
    return _s3


class UploadRequest(BaseModel):
    fileName: str = Field(min_length=1, max_length=200, description="Nombre del archivo, con extensión")
    contentType: str = Field(min_length=1, max_length=200, description="Tipo MIME del archivo")
    size: int = Field(gt=0, le=MAX_SIZE_BYTES, description="Tamaño en bytes")

    @field_validator("fileName")
    @classmethod
    def _supported_extension(cls, value: str) -> str:
        if PurePosixPath(value).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Formato no admitido. Formatos permitidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
        return value


def safe_file_name(file_name: str) -> str:
    """Quita rutas y caracteres que no sirven en una clave de S3."""
    name = PurePosixPath(file_name.replace("\\", "/")).name
    stem, suffix = PurePosixPath(name).stem, PurePosixPath(name).suffix.lower()
    stem = re.sub(r"[^\w.-]+", "-", stem, flags=re.UNICODE).strip("-.") or "documento"
    return f"{stem[:150]}{suffix}"


@app.post("/documents/upload-url")
def create_upload_url(body: UploadRequest) -> tuple[dict, int]:
    key = f"{UPLOAD_PREFIX}/{new_id()}/{safe_file_name(body.fileName)}"
    url = _s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": param("DOCUMENTS_BUCKET_PARAM"), "Key": key, "ContentType": body.contentType},
        ExpiresIn=URL_EXPIRATION_SECONDS,
    )
    logger.info("URL prefirmada generada", extra={"key": key, "size": body.size})
    return {"uploadUrl": url, "key": key, "expiresIn": URL_EXPIRATION_SECONDS, "contentType": body.contentType}, 201


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
