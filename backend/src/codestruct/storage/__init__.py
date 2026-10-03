"""Persistent job and analysis-result repositories."""

from .sqlite_repository import SQLiteRepository

__all__ = ["SQLiteRepository"]
