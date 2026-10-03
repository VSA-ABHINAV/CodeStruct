"""Compatibility import for existing ``uvicorn main:app`` workflows."""

from codestruct.api.app import app

__all__ = ["app"]
