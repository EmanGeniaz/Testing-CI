"""Supabase client wrapper + JWT verification helpers."""
from __future__ import annotations

import os
from typing import Optional

import jwt
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")  # for verifying tokens

_client: Optional[Client] = None


def is_configured() -> bool:
    """True if Supabase environment is configured."""
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("Supabase not configured")
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def verify_jwt(token: str) -> dict:
    """Verify a Supabase JWT and return the decoded payload (includes user_id as 'sub')."""
    # Supabase JWTs are signed with HS256 using the JWT secret
    # If no secret available, fall back to calling Supabase to verify
    if SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
            return payload
        except jwt.PyJWTError as e:
            raise ValueError(f"Invalid token: {e}")
    else:
        # Fallback: call Supabase to validate
        client = get_client()
        user = client.auth.get_user(token)
        if user is None or user.user is None:
            raise ValueError("Invalid token")
        return {"sub": user.user.id, "email": user.user.email}


def get_user_id_from_request(authorization: Optional[str]) -> str:
    """Extract user_id from the Authorization header. Raises ValueError if invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise ValueError("Missing or invalid Authorization header")
    token = authorization[7:]
    payload = verify_jwt(token)
    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Token has no user_id")
    return user_id
