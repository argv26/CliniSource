"""Object Storage Provider Abstraction for Textbook Figures & Visual Plates.

Supports:
1. S3 / MinIO (open-source self-hosted or cloud S3-compatible storage like Cloudflare R2).
2. Local File System fallback (default zero-setup local cache in ui/static/figures_cache).
"""
from __future__ import annotations

import io
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
LOCAL_FIGURES_CACHE = ROOT_DIR / "ui" / "static" / "figures_cache"
LOCAL_FIGURES_CACHE.mkdir(parents=True, exist_ok=True)


class StorageProvider(ABC):
    """Abstract interface for storing and serving textbook diagram images."""

    @abstractmethod
    def save_figure(self, book_slug: str, chunk_id: str, image_bytes: bytes) -> str:
        """Stores a figure image and returns its storage reference/path."""
        pass

    @abstractmethod
    def get_figure_bytes(self, chunk_id: str) -> bytes | None:
        """Retrieves raw JPEG image bytes for a chunk."""
        pass

    @abstractmethod
    def get_figure_path(self, chunk_id: str) -> Path | None:
        """Returns local filesystem path if available, or None."""
        pass

    @abstractmethod
    def figure_exists(self, chunk_id: str) -> bool:
        """Returns True if the figure image is already stored."""
        pass

    @abstractmethod
    def get_figure_url(self, chunk_id: str) -> str:
        """Returns the public or gateway URL to access the figure."""
        pass


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider storing JPEGs in ui/static/figures_cache."""

    def __init__(self, cache_dir: Path | str | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else LOCAL_FIGURES_CACHE
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, chunk_id: str) -> Path:
        return self.cache_dir / f"{chunk_id}.jpg"

    def save_figure(self, book_slug: str, chunk_id: str, image_bytes: bytes) -> str:
        target = self._file_path(chunk_id)
        target.write_bytes(image_bytes)
        return str(target)

    def get_figure_bytes(self, chunk_id: str) -> bytes | None:
        target = self._file_path(chunk_id)
        if target.exists() and target.stat().st_size > 0:
            return target.read_bytes()
        return None

    def get_figure_path(self, chunk_id: str) -> Path | None:
        target = self._file_path(chunk_id)
        if target.exists() and target.stat().st_size > 0:
            return target
        return None

    def figure_exists(self, chunk_id: str) -> bool:
        target = self._file_path(chunk_id)
        return target.exists() and target.stat().st_size > 0

    def get_figure_url(self, chunk_id: str) -> str:
        return f"/api/figure/{chunk_id}/image"


class S3StorageProvider(StorageProvider):
    """S3-compatible storage provider for MinIO, AWS S3, or Cloudflare R2."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        bucket_name: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region_name: str | None = None,
        local_fallback_dir: Path | str | None = None,
    ):
        import boto3
        from botocore.client import Config

        self.endpoint_url = endpoint_url or os.environ.get("S3_ENDPOINT_URL") or os.environ.get("MINIO_ENDPOINT")
        self.bucket_name = bucket_name or os.environ.get("S3_BUCKET_NAME", "textbook-figures")
        self.access_key = access_key or os.environ.get("S3_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
        self.secret_key = secret_key or os.environ.get("S3_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin")
        self.region_name = region_name or os.environ.get("S3_REGION_NAME", "us-east-1")

        self.local_cache = Path(local_fallback_dir) if local_fallback_dir else LOCAL_FIGURES_CACHE
        self.local_cache.mkdir(parents=True, exist_ok=True)

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except Exception:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            except Exception as e:
                print(f"[S3StorageProvider] Note: Bucket check/create: {e}")

    def _s3_key(self, chunk_id: str) -> str:
        return f"figures/{chunk_id}.jpg"

    def save_figure(self, book_slug: str, chunk_id: str, image_bytes: bytes) -> str:
        key = self._s3_key(chunk_id)
        # Upload to S3
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=image_bytes,
            ContentType="image/jpeg",
        )
        # Also cache locally for speed
        local_file = self.local_cache / f"{chunk_id}.jpg"
        local_file.write_bytes(image_bytes)
        return f"s3://{self.bucket_name}/{key}"

    def get_figure_bytes(self, chunk_id: str) -> bytes | None:
        # Check local cache first
        local_file = self.local_cache / f"{chunk_id}.jpg"
        if local_file.exists() and local_file.stat().st_size > 0:
            return local_file.read_bytes()

        # Fetch from S3
        key = self._s3_key(chunk_id)
        try:
            resp = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            data = resp["Body"].read()
            local_file.write_bytes(data)
            return data
        except Exception:
            return None

    def get_figure_path(self, chunk_id: str) -> Path | None:
        local_file = self.local_cache / f"{chunk_id}.jpg"
        if local_file.exists() and local_file.stat().st_size > 0:
            return local_file

        data = self.get_figure_bytes(chunk_id)
        if data:
            local_file.write_bytes(data)
            return local_file
        return None

    def figure_exists(self, chunk_id: str) -> bool:
        local_file = self.local_cache / f"{chunk_id}.jpg"
        if local_file.exists() and local_file.stat().st_size > 0:
            return True

        key = self._s3_key(chunk_id)
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False

    def get_figure_url(self, chunk_id: str) -> str:
        return f"/api/figure/{chunk_id}/image"


_PROVIDER_INSTANCE: StorageProvider | None = None


def get_storage_provider() -> StorageProvider:
    """Returns the active storage provider (MinIO/S3 if configured, else Local Disk)."""
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is not None:
        return _PROVIDER_INSTANCE

    s3_endpoint = os.environ.get("S3_ENDPOINT_URL") or os.environ.get("MINIO_ENDPOINT")
    if s3_endpoint:
        try:
            _PROVIDER_INSTANCE = S3StorageProvider(endpoint_url=s3_endpoint)
            return _PROVIDER_INSTANCE
        except Exception as e:
            print(f"[get_storage_provider] S3 initialization failed, falling back to local: {e}")

    _PROVIDER_INSTANCE = LocalStorageProvider()
    return _PROVIDER_INSTANCE

