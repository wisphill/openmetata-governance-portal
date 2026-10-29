import logging
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

from app.api.routes import router
from app.auth.session import SessionStore
from app.cache.user_names import MemoryUserNameCache
from app.config import get_settings


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="OpenMetadata Governance Portal", version="0.1.0")
    app.state.sessions = SessionStore(settings.session_secret)
    app.state.user_name_cache = MemoryUserNameCache(settings.openmetadata_user_name_cache_ttl_seconds)

    @app.middleware("http")
    async def log_api_failures(request: Request, call_next):
        """Log every failing API request without recording credentials or bodies."""
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Backend API request failed: request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            raise
        if response.status_code >= 400:
            logger.warning(
                "Backend API returned an error: request_id=%s method=%s path=%s status=%s",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
            )
        response.headers["X-Request-ID"] = request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.include_router(router)
    return app


app = create_app()
