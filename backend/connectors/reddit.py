"""
Reddit connector — uses praw (read-only app auth).

A single search returns both submissions AND their top comments as separate
rows so analysts get the full conversation around a query, not just titles.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .base import DataConnector

log = logging.getLogger("e_ai.connectors.reddit")

# User-Agent string Reddit asks API consumers to send.
USER_AGENT = "e-ai-research/0.1 (by /u/e-ai-research)"


class RedditConnector(DataConnector):
    """Reddit data connector backed by praw."""

    platform = "reddit"

    def __init__(self, client_id: str, client_secret: str, subreddits: str = ""):
        if not client_id or not client_secret:
            raise ValueError("Reddit connector requires client_id and client_secret")
        self.client_id = client_id
        self.client_secret = client_secret
        # Comma-separated default subreddit hints (used by orchestrator hints, not enforced here).
        self.default_subreddits = [s.strip() for s in (subreddits or "").split(",") if s.strip()]
        self._reddit = None  # lazy

    # ── praw client ──────────────────────────────────────────────────────

    def _client(self):
        if self._reddit is not None:
            return self._reddit
        try:
            import praw  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "praw is not installed. Add `praw>=7.7` to requirements.txt"
            ) from e
        self._reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=USER_AGENT,
            check_for_async=False,
        )
        # read-only app auth
        self._reddit.read_only = True
        return self._reddit

    # ── public API ───────────────────────────────────────────────────────

    def test_connection(self) -> tuple[bool, str]:
        try:
            client = self._client()
            # Cheap probe — hit a tiny public subreddit listing.
            sub = client.subreddit("announcements")
            # praw is lazy; force a network call by reading one attribute
            _ = sub.display_name
            return True, "Reddit credentials accepted."
        except Exception as e:  # noqa: BLE001
            msg = str(e) or e.__class__.__name__
            log.warning("Reddit test_connection failed: %s", msg)
            return False, f"Reddit auth failed: {msg}"

    def search(
        self,
        query: str,
        limit: int = 100,
        subreddit: str = "all",
        time_filter: str = "year",
        include_comments: bool = True,
        max_comments_per_post: int = 10,
        **_: Any,
    ) -> list[dict]:
        """Search Reddit and return submissions plus top comments as rows.

        We cap submissions at roughly limit / (1 + comments_per_post) so the
        total row count stays close to the user-requested `limit`.
        """
        client = self._client()

        # Decide how many submissions we need to pull.
        if include_comments and max_comments_per_post > 0:
            sub_cap = max(1, limit // (1 + max_comments_per_post))
        else:
            sub_cap = limit

        rows: list[dict] = []
        try:
            sr = client.subreddit(subreddit or "all")
            for submission in sr.search(query, limit=sub_cap, time_filter=time_filter):
                rows.append(self._submission_row(submission))
                if include_comments and max_comments_per_post > 0:
                    rows.extend(self._comment_rows(submission, max_comments_per_post))
                if len(rows) >= limit:
                    break
        except Exception as e:  # noqa: BLE001
            log.error("Reddit search failed: %s", e)
            raise

        return rows[:limit]

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _iso(epoch: float | int | None) -> str:
        if not epoch:
            return ""
        try:
            return datetime.utcfromtimestamp(float(epoch)).isoformat() + "Z"
        except (ValueError, OSError):
            return ""

    @staticmethod
    def _author_name(author) -> str:
        if author is None:
            return "[deleted]"
        # praw author objects expose .name; strings just pass through.
        return getattr(author, "name", str(author)) or "[deleted]"

    def _submission_row(self, submission) -> dict:
        title = (submission.title or "").strip()
        body = (getattr(submission, "selftext", "") or "").strip()
        text = title if not body else f"{title}\n\n{body}"
        return {
            "text": text,
            "url": f"https://reddit.com{submission.permalink}",
            "platform": self.platform,
            "date": self._iso(getattr(submission, "created_utc", None)),
            "author": self._author_name(getattr(submission, "author", None)),
            "metadata": {
                "type": "submission",
                "subreddit": getattr(getattr(submission, "subreddit", None), "display_name", ""),
                "score": int(getattr(submission, "score", 0) or 0),
                "num_comments": int(getattr(submission, "num_comments", 0) or 0),
                "id": getattr(submission, "id", ""),
                "title": title,
            },
        }

    def _comment_rows(self, submission, max_comments: int) -> list[dict]:
        rows: list[dict] = []
        try:
            # Don't expand MoreComments — we only want already-loaded top-level comments,
            # which is cheap and avoids extra round-trips.
            submission.comments.replace_more(limit=0)
            comments = list(submission.comments)[:max_comments]
        except Exception as e:  # noqa: BLE001
            log.debug("Failed to load comments for %s: %s", getattr(submission, "id", "?"), e)
            return rows

        for c in comments:
            body = (getattr(c, "body", "") or "").strip()
            if not body:
                continue
            rows.append({
                "text": body,
                "url": f"https://reddit.com{getattr(c, 'permalink', '')}",
                "platform": self.platform,
                "date": self._iso(getattr(c, "created_utc", None)),
                "author": self._author_name(getattr(c, "author", None)),
                "metadata": {
                    "type": "comment",
                    "subreddit": getattr(getattr(submission, "subreddit", None), "display_name", ""),
                    "score": int(getattr(c, "score", 0) or 0),
                    "parent_id": getattr(submission, "id", ""),
                    "id": getattr(c, "id", ""),
                },
            })
        return rows
