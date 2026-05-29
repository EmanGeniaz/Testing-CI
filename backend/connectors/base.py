"""
Abstract connector interface.

All concrete connectors (Reddit, News API, ...) return rows in the same
shape so the rest of the pipeline (cleansing, schema, tagging) can treat
them identically to an uploaded file.

Standard row schema:
    {
        "text":     str,           # primary text to analyze
        "url":      str,           # canonical URL of the source
        "platform": str,           # "reddit" | "news" | ...
        "date":     str,           # ISO 8601 timestamp
        "author":   str,           # username / source name
        "metadata": dict,          # connector-specific extras
    }
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DataConnector(ABC):
    """Abstract base class for external data source connectors."""

    # Subclasses should set this to the platform identifier used in row["platform"]
    platform: str = "unknown"

    @abstractmethod
    def search(self, query: str, limit: int = 100, **kwargs: Any) -> list[dict]:
        """Search the underlying API and return a list of standardized rows.

        Args:
            query:  Search query string.
            limit:  Maximum number of rows to return.
            **kwargs: Connector-specific filters (e.g. subreddit, from_date).

        Returns:
            A list of dicts conforming to the standard row schema described
            in the module docstring.
        """
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Verify the connector's credentials work.

        Returns:
            (success, message). `message` should be a short human-readable
            description suitable for displaying to the user.
        """
        raise NotImplementedError
