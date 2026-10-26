from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.auth.dependencies import require_session
from app.auth.oidc import OidcClient
from app.auth.session import Session
from app.config import Settings, get_settings
from app.database.oracle import OracleAdapter
from app.models.contracts import AccessRequestCreate, AccessRequestCreated, CatalogPage, CatalogTable, GrantedAccessPage, MeResponse, QueryRequest, TaskPage
from app.openmetadata.access_requests import OpenMetadataAccessRequestService
from app.openmetadata.authorization import OpenMetadataAuthorizationService
from app.openmetadata.catalog import OpenMetadataCatalogService
from app.openmetadata.grants import OpenMetadataGrantedAccessService
from app.openmetadata.client import OpenMetadataClient
from app.openmetadata.tasks import OpenMetadataTaskService

router = APIRouter()
SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(require_session)]


def set_session_cookie(response: Response, session_id: str, request: Request, settings: Settings) -> None:
    response.set_cookie(
        "portal_session",
        request.app.state.sessions.signed_id(session_id),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=600,
        path="/",
    )


@router.get("/auth/login")
async def login(request: Request, settings: SettingsDep):
    session = request.app.state.sessions.create_pending()
    url = await OidcClient(settings).authorization_url(session)
    response = RedirectResponse(url)
    set_session_cookie(response, session.id, request, settings)
    return response


@router.get("/auth/callback")
async def callback(request: Request, code: str, state: str, settings: SettingsDep):
    session = request.app.state.sessions.get(request.cookies.get("portal_session"))
    if not session or session.state != state:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid OIDC login state")
    claims = await OidcClient(settings).exchange_code(code, session)
    email = claims.get(settings.oidc_email_claim)
    client = OpenMetadataClient(settings)
    try:
        username = claims.get(settings.oidc_username_claim) if settings.oidc_username_claim else None
        await OpenMetadataAuthorizationService(client, email, username).get_current_user()
    except PermissionError:
        request.app.state.sessions.delete(request.cookies.get("portal_session"))
        response = RedirectResponse(f"{settings.portal_public_url.rstrip('/')}/access-denied", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie("portal_session", path="/")
        return response
    finally:
        await client.close()
    request.app.state.sessions.complete(session, claims)
    return RedirectResponse(settings.portal_public_url)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response):
    request.app.state.sessions.delete(request.cookies.get("portal_session"))
    response.delete_cookie("portal_session", path="/")


@router.get("/api/health")
async def health():
    return {"status": "ok"}


async def authorization_service(session: SessionDep, settings: SettingsDep):
    email = session.claims.get(settings.oidc_email_claim)
    username = session.claims.get(settings.oidc_username_claim) if settings.oidc_username_claim else None
    client = OpenMetadataClient(settings)
    try:
        yield OpenMetadataAuthorizationService(client, email, username)
    finally:
        await client.close()


AuthzDep = Annotated[OpenMetadataAuthorizationService, Depends(authorization_service)]


@router.get("/api/me", response_model=MeResponse)
async def me(authz: AuthzDep):
    try:
        return await authz.get_current_user()
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc


@router.get("/api/me/roles")
async def roles(authz: AuthzDep):
    return (await me(authz)).roles


@router.get("/api/me/policies")
async def policies(authz: AuthzDep):
    return {"items": (await me(authz)).policies}


@router.get("/api/tasks", response_model=TaskPage)
async def tasks(
    session: SessionDep,
    authz: AuthzDep,
    settings: SettingsDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    task_type: str | None = Query(None, alias="type"),
):
    try:
        user = await authz.get_current_user()
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    client = OpenMetadataClient(settings)
    try:
        return await OpenMetadataTaskService(client, user.identity.id).list_tasks(page, page_size, status_filter, task_type)
    finally:
        await client.close()


@router.get("/api/catalog/tables", response_model=CatalogPage)
async def catalog_tables(
    authz: AuthzDep,
    settings: SettingsDep,
    after: str | None = Query(None, max_length=512),
    page_size: int | None = Query(None, ge=1, le=100),
):
    # Resolve the authenticated OpenMetadata identity first. This keeps the
    # bot-token catalogue read behind the same admission boundary as all BFF APIs.
    try:
        await authz.get_current_user()
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    client = OpenMetadataClient(settings)
    try:
        return await OpenMetadataCatalogService(client).list_tables(page_size or settings.openmetadata_catalog_page_size, after)
    finally:
        await client.close()


@router.get("/api/catalog/tables/{table_id}", response_model=CatalogTable)
async def catalog_table(table_id: str, authz: AuthzDep, settings: SettingsDep):
    try:
        await authz.get_current_user()
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    client = OpenMetadataClient(settings)
    try:
        return await OpenMetadataCatalogService(client).get_table(table_id)
    finally:
        await client.close()


@router.post("/api/access-requests", response_model=AccessRequestCreated, status_code=status.HTTP_201_CREATED)
async def create_access_request(request: AccessRequestCreate, authz: AuthzDep, settings: SettingsDep):
    try:
        user = await authz.get_current_user()
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    client = OpenMetadataClient(settings)
    try:
        return await OpenMetadataAccessRequestService(client, settings).create(user.identity, request)
    finally:
        await client.close()


@router.get("/api/tasks/{task_id}")
async def task_by_id(task_id: str, session: SessionDep, settings: SettingsDep):
    # Task retrieval is intentionally delegated to OpenMetadata with the user's token.
    client = OpenMetadataClient(settings)
    try:
        return await client.get(f"{settings.openmetadata_tasks_path.rstrip('/')}/{task_id}")
    finally:
        await client.close()


@router.get("/api/requests", response_model=TaskPage)
async def my_requests(
    authz: AuthzDep,
    settings: SettingsDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        user = await authz.get_current_user()
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    client = OpenMetadataClient(settings)
    try:
        return await OpenMetadataTaskService(client, user.identity.id).list_created_tasks(page, page_size)
    finally:
        await client.close()


@router.get("/api/me/granted-access", response_model=GrantedAccessPage)
async def granted_access(authz: AuthzDep, settings: SettingsDep):
    try:
        user = await authz.get_current_user()
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    client = OpenMetadataClient(settings)
    try:
        return await OpenMetadataGrantedAccessService(client, user.identity.id).list_granted()
    finally:
        await client.close()


@router.post("/api/database/query")
async def database_query(request: QueryRequest, authz: AuthzDep, settings: SettingsDep):
    if not settings.database_queries_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Database query endpoint is disabled")
    user = await authz.get_current_user()
    identity = user.identity.email or user.identity.username
    adapter = OracleAdapter(settings)
    try:
        await adapter.connect(identity)
        return {"items": await adapter.execute_query(request.sql, request.parameters)}
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    finally:
        await adapter.disconnect()
