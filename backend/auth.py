"""FastAPI auth dependencies — extract the current user from a Supabase JWT."""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from supabase_client import get_user_id_from_request, is_configured


async def current_user(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency to extract the current user's ID from the auth header.

    When Supabase is not configured (local dev fallback), returns a stable
    anonymous user id so that the rest of the app can still function against
    the JSON-file fallback storage.
    """
    if not is_configured():
        return "local-anon-user"
    try:
        return get_user_id_from_request(authorization)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


async def current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Same but doesn't raise if missing — for share-link endpoints."""
    if not is_configured():
        return "local-anon-user"
    if not authorization:
        return None
    try:
        return get_user_id_from_request(authorization)
    except ValueError:
        return None
