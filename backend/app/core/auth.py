"""Mock auth: identity from X-User-Email / X-User-Name headers.

In dev mode (AUTH_MODE=mock, the default), the backend trusts these headers.
In production, swap this for Auth.js session decryption via fastapi-nextauth-jwt.
"""

from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass
class CurrentUser:
    email: str
    name: str


MOCK_USERS = [
    CurrentUser(email="alice@changebook.dev", name="Alice Engineer"),
    CurrentUser(email="bob@changebook.dev", name="Bob Reviewer"),
    CurrentUser(email="carol@changebook.dev", name="Carol Operator"),
    CurrentUser(email="dave@changebook.dev", name="Dave Manager"),
]


def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency — extract identity from request headers."""
    email = request.headers.get("X-User-Email")
    name = request.headers.get("X-User-Name")

    if not email:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide X-User-Email header.",
        )

    return CurrentUser(email=email, name=name or email)
