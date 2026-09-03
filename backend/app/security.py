"""
Password hashing + session token helpers.

Passwords are hashed with Argon2 (via argon2-cffi). Plaintext passwords are
never stored or logged.
"""
import secrets
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Very small in-memory login rate limiter (per-process). This is a
# best-effort brute-force mitigation suitable for a single-instance small
# shop deployment; for multi-instance production deployments back this with
# Redis or similar instead.
# ---------------------------------------------------------------------------
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 15 * 60
_attempts: dict[str, deque] = defaultdict(deque)


def is_rate_limited(identifier: str) -> bool:
    now = time.time()
    q = _attempts[identifier]
    while q and now - q[0] > _WINDOW_SECONDS:
        q.popleft()
    return len(q) >= _MAX_ATTEMPTS


def record_failed_attempt(identifier: str) -> None:
    _attempts[identifier].append(time.time())


def clear_attempts(identifier: str) -> None:
    _attempts.pop(identifier, None)
