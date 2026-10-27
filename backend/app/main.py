from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.auth.session import SessionStore
from app.cache.user_names import MemoryUserNameCache
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="OpenMetadata Governance Portal", version="0.1.0")
    app.state.sessions = SessionStore(settings.session_secret)
    app.state.user_name_cache = MemoryUserNameCache(settings.openmetadata_user_name_cache_ttl_seconds)
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
