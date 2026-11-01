"""Storage package for CliniSource object storage and figure persistence."""
from storage.object_store import get_storage_provider, StorageProvider

__all__ = ["get_storage_provider", "StorageProvider"]

