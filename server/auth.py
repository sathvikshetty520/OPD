"""
Staff authentication: password hashing + simple session tokens.

Deliberately not JWT -- a plain server-side session table is simpler to
reason about, easy to revoke, and sufficient at this scale (one hospital's
staff, not a distributed system).
"""

import secrets
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

SESSION_TTL_HOURS = 12


def hash_password(plain: str) -> str:
    return generate_password_hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return check_password_hash(hashed, plain)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def session_expiry() -> str:
    return (datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(hours=SESSION_TTL_HOURS)).isoformat()


def is_expired(expiry_iso: str) -> bool:
    expiry = datetime.datetime.fromisoformat(expiry_iso)
    return datetime.datetime.now(datetime.timezone.utc) > expiry