from typing import Optional

from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models import LoginHistory, User


def get_client_ip(request: Request) -> Optional[str]:
    """Extract the most accurate client IP by inspecting headers before falling back to the socket."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Use the first entry in case of multiple hops
        first_ip = forwarded.split(",")[0].strip()
        if first_ip:
            return first_ip
    client = getattr(request, "client", None)
    if client:
        host = getattr(client, "host", None)
        if host:
            return host
    return None


def record_login_history(
    db: Session,
    user: User,
    ip_address: Optional[str] = None,
    source: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> LoginHistory:
    """Persist a login event tied to a specific user."""
    entry = LoginHistory(
        user_id=user.user_id,
        login_id=user.login_id,
        user_name=user.name,
        role_id=user.role_id,
        ip_address=ip_address,
        source=source,
        user_agent=user_agent,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
