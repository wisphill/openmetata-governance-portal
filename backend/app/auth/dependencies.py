from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status

from app.auth.session import Session


def get_session_store(request: Request):
    return request.app.state.sessions


async def require_session(
    session_id: Annotated[str | None, Cookie(alias="portal_session")] = None,
    store=Depends(get_session_store),
) -> Session:
    session = store.get(session_id)
    if not session or not session.claims:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return session
