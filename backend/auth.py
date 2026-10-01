from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from config import AUTH_MODE, JWT_ALGORITHM, JWT_EXPIRY_MINUTES, JWT_SECRET


class AuthError(Exception):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def token_issue(uid: int) -> str:
    if not JWT_SECRET:
        raise AuthError("JWT_SECRET is not configured; set it before enabling jwt auth")
    now = int(time.time())
    header = _b64(json.dumps({"alg": JWT_ALGORITHM, "typ": "JWT"}).encode())
    body = _b64(json.dumps({"sub": uid, "iat": now, "exp": now + JWT_EXPIRY_MINUTES * 60}).encode())
    signature = _b64(hmac.new(JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
    return f"{header}.{body}.{signature}"


def token_verify(token: str) -> int:
    try:
        header, body, signature = token.split(".")
        expected = _b64(hmac.new(JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            raise AuthError("bad signature")
        claims = json.loads(_unb64(body))
        if claims.get("exp", 0) < time.time():
            raise AuthError("token expired")
        return int(claims["sub"])
    except AuthError:
        raise
    except Exception as exc:
        raise AuthError(f"malformed token: {exc}") from exc


def token_user_id(authorization: str | None) -> int | None:
    """Resolve a user from an Authorization: Bearer header when jwt mode is on."""
    if AUTH_MODE != "jwt" or not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token_verify(token)


def user_id_from_request(x_user_id: int | None, authorization: str | None) -> int:
    if AUTH_MODE == "jwt":
        resolved = token_user_id(authorization)
        if resolved is None:
            raise AuthError("missing or invalid bearer token")
        return resolved
    return x_user_id or 1
