class StorageError(RuntimeError):
    """A safe storage-layer failure category."""


class UnsupportedSchemaError(StorageError):
    """The database was created by an unsupported future version."""


class CorruptCacheEntryError(StorageError):
    """A cached payload failed integrity or graph validation."""
