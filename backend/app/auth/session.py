import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass


@dataclass
class Session:
    id: str
    state: str
    code_verifier: str
    created_at: float
    claims: dict | None = None


class SessionStore:
    """Short-lived in-memory sessions. Replace for multi-replica deployments."""

    def __init__(self, secret: str, ttl_seconds: int = 600) -> None:
        self._secret = secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds
        self._sessions: dict[str, Session] = {}

    def create_pending(self) -> Session:
        session = Session(
            id=secrets.token_urlsafe(32),
            state=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(64),
            created_at=time.time(),
        )
        self._sessions[session.id] = session
        self._prune()
        return session

    def signed_id(self, session_id: str) -> str:
        """Create an opaque, tamper-evident browser cookie value."""
        signature = hmac.new(self._secret, session_id.encode("utf-8"), hashlib.sha256).digest()
        return f"{session_id}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"

    def get(self, signed_session_id: str | None) -> Session | None:
        session_id = self._verified_id(signed_session_id)
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if session and time.time() - session.created_at <= self._ttl_seconds:
            return session
        self._sessions.pop(session_id, None)
        return None

    def complete(self, session: Session, claims: dict) -> None:
        session.claims = claims
        session.created_at = time.time()

    def delete(self, signed_session_id: str | None) -> None:
        session_id = self._verified_id(signed_session_id)
        if session_id:
            self._sessions.pop(session_id, None)

    def _verified_id(self, value: str | None) -> str | None:
        if not value or "." not in value:
            return None
        session_id, supplied_signature = value.rsplit(".", 1)
        expected = self.signed_id(session_id).rsplit(".", 1)[1]
        return session_id if hmac.compare_digest(supplied_signature, expected) else None

    def _prune(self) -> None:
        now = time.time()
        self._sessions = {key: value for key, value in self._sessions.items() if now - value.created_at <= self._ttl_seconds}
