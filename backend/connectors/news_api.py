"""News API (newsapi.org) connector — free tier supports up to 100 reqs/day."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .base import DataConnector

log = logging.getLogger("e_ai.connectors.news_api")

BASE_URL = "https://newsapi.org/v2"
# newsapi.org caps page size at 100 — we paginate to support higher limits.
MAX_PAGE_SIZE = 100


class NewsAPIConnector(DataConnector):
    """News API connector — hits /v2/everything."""

    platform = "news"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("News API connector requires an api_key")
        self.api_key = api_key

    # ── public API ───────────────────────────────────────────────────────

    def test_connection(self) -> tuple[bool, str]:
        try:
            # A tiny query against /everything is the cheapest auth probe.
            r = requests.get(
                f"{BASE_URL}/everything",
                params={"q": "test", "pageSize": 1, "language": "en"},
                headers={"X-Api-Key": self.api_key},
                timeout=10,
            )
            if r.status_code == 200:
                return True, "News API credentials accepted."
            # newsapi returns a JSON body with a `message` field for errors.
            try:
                msg = r.json().get("message", r.text)
            except ValueError:
                msg = r.text
            return False, f"News API auth failed ({r.status_code}): {msg}"
        except requests.RequestException as e:
            log.warning("News API test_connection failed: %s", e)
            return False, f"News API request failed: {e}"

    def search(
        self,
        query: str,
        limit: int = 100,
        from_date: str | None = None,
        to_date: str | None = None,
        language: str = "en",
        sort_by: str = "publishedAt",
        **_: Any,
    ) -> list[dict]:
        if not query:
            return []

        rows: list[dict] = []
        remaining = limit
        page = 1
        while remaining > 0:
            page_size = min(MAX_PAGE_SIZE, remaining)
            params: dict[str, Any] = {
                "q": query,
                "pageSize": page_size,
                "page": page,
                "language": language,
                "sortBy": sort_by,
            }
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date

            try:
                r = requests.get(
                    f"{BASE_URL}/everything",
                    params=params,
                    headers={"X-Api-Key": self.api_key},
                    timeout=20,
                )
            except requests.RequestException as e:
                log.error("News API request failed on page %d: %s", page, e)
                raise

            if r.status_code != 200:
                try:
                    err_msg = r.json().get("message", r.text)
                except ValueError:
                    err_msg = r.text
                raise RuntimeError(f"News API error {r.status_code}: {err_msg}")

            payload = r.json()
            articles = payload.get("articles", []) or []
            if not articles:
                break

            for art in articles:
                rows.append(self._article_row(art))
                if len(rows) >= limit:
                    break

            remaining = limit - len(rows)
            # Stop when we've exhausted the total result set or finished a partial page.
            total = int(payload.get("totalResults", 0) or 0)
            if len(rows) >= total or len(articles) < page_size:
                break
            page += 1

        return rows[:limit]

    # ── helpers ──────────────────────────────────────────────────────────

    def _article_row(self, art: dict) -> dict:
        title = (art.get("title") or "").strip()
        description = (art.get("description") or "").strip()
        if title and description:
            text = f"{title} — {description}"
        else:
            text = title or description
        source = (art.get("source") or {}).get("name") or ""
        return {
            "text": text,
            "url": art.get("url") or "",
            "platform": self.platform,
            "date": art.get("publishedAt") or "",
            "author": art.get("author") or source,
            "metadata": {
                "source": source,
                "urlToImage": art.get("urlToImage") or "",
                "title": title,
                "description": description,
                "content_snippet": (art.get("content") or "")[:500],
            },
        }
