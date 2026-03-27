"""Artifact storage helpers for local disk and optional GCS mirroring."""

from __future__ import annotations

from dataclasses import dataclass

from .config import load_settings

_storage_client = None


@dataclass(frozen=True)
class GcsArtifact:
    bucket: str
    object_name: str


def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        from google.cloud import storage

        _storage_client = storage.Client()
    return _storage_client


def upload_artifact(filename: str, payload: bytes, mime_type: str) -> GcsArtifact | None:
    settings = load_settings()
    if not settings.gcs_bucket:
        return None

    object_name = "/".join(part for part in (settings.gcs_prefix, filename) if part)
    client = _get_storage_client()
    bucket = client.bucket(settings.gcs_bucket)
    blob = bucket.blob(object_name)
    blob.upload_from_string(payload, content_type=mime_type)
    return GcsArtifact(bucket=settings.gcs_bucket, object_name=object_name)


def download_artifact(filename: str) -> tuple[bytes, str | None] | None:
    settings = load_settings()
    if not settings.gcs_bucket:
        return None

    object_name = "/".join(part for part in (settings.gcs_prefix, filename) if part)
    client = _get_storage_client()
    bucket = client.bucket(settings.gcs_bucket)
    blob = bucket.blob(object_name)
    if not blob.exists():
        return None
    payload = blob.download_as_bytes()
    return payload, blob.content_type
