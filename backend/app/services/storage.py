from __future__ import annotations

import boto3
from botocore.config import Config

from app.core.config import settings


def s3_endpoint_url() -> str:
    return f"https://s3.{settings.AWS_REGION}.amazonaws.com"


def build_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        endpoint_url=s3_endpoint_url(),
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


def build_s3_object_url(key: str) -> str:
    return f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
