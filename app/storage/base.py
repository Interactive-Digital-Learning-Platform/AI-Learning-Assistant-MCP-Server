class ObjectStoreError(Exception):
    """Base class for object-store failures."""


class ObjectStoreConfigError(ObjectStoreError):
    """Object storage is enabled but not fully configured."""
