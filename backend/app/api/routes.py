import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.auth.dependencies import require_session
from app.auth.oidc import OidcClient
from app.auth.session import Session
from app.config import Settings, get_settings
from app.database.oracle import OracleAdapter
from app.database.oracle_access_provisioning import OracleAccessProvisioner
from app.database.oracle_temporary_proxy import OracleTemporaryProxyQueryService
from app.models.contracts import AccessRequestCreate, AccessRequestCreated, AccessRequestDetail, AccessRevocation, CatalogPage, CatalogTable, GrantedAccessPage, HardDeletedTask, MeResponse, QueryRequest, QueryResult, Task, TaskPage, TaskResolutionRequest, UserAccessAudit
from app.openmetadata.access_requests import OpenMetadataAccessRequestService
from app.openmetadata.authorization import OpenMetadataAuthorizationService
from app.openmetadata.catalog import OpenMetadataCatalogService
from app.openmetadata.grants import OpenMetadataGrantedAccessService
from app.openmetadata.client import OpenMetadataClient
from app.openmetadata.tasks import OpenMetadataTaskService

router = APIRouter()
logger = logging.getLogger(__name__)
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
    request: Request,
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
        return await OpenMetadataTaskService(client, user.identity.id, request.app.state.user_name_cache).list_tasks(page, page_size, status_filter, task_type)
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


@router.post("/api/tasks/{task_id}/resolve", response_model=Task)
async def resolve_task(task_id: str, resolution: TaskResolutionRequest, request: Request, authz: AuthzDep, settings: SettingsDep):
    try:
        user = await authz.get_current_user()
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    client = OpenMetadataClient(settings)
    try:
        return await OpenMetadataTaskService(client, user.identity.id, request.app.state.user_name_cache, settings).resolve_assigned_task(task_id, resolution)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    finally:
        await client.close()


@router.get("/api/requests", response_model=TaskPage)
async def my_requests(
    request: Request,
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
        return await OpenMetadataTaskService(client, user.identity.id, request.app.state.user_name_cache).list_created_tasks(page, page_size)
    finally:
        await client.close()


@router.delete("/api/requests/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_my_request(task_id: str, authz: AuthzDep, settings: SettingsDep):
    try:
        user = await authz.get_current_user()
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    client = OpenMetadataClient(settings)
    try:
        await OpenMetadataTaskService(client, user.identity.id).cancel_created_task(task_id)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    finally:
        await client.close()


@router.get("/api/requests/{task_id}", response_model=AccessRequestDetail)
async def my_request_detail(task_id: str, request: Request, authz: AuthzDep, settings: SettingsDep):
    try:
        user = await authz.get_current_user()
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    client = OpenMetadataClient(settings)
    try:
        return await OpenMetadataTaskService(client, user.identity.id, request.app.state.user_name_cache).get_created_task(task_id)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
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


@router.get("/api/users/access", response_model=UserAccessAudit)
async def user_access_by_email(
    authz: AuthzDep,
    settings: SettingsDep,
    email: str = Query(..., min_length=3, max_length=320),
):
    # Deliberately no admin/data-owner ACL yet: the screen is currently an
    # authenticated read-only operational view. Revisit this before exposing it
    # outside the portal's trusted audience.
    try:
        await authz.get_current_user()
        user = await authz.get_user_by_email(email)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active OpenMetadata user was found for this email address")
    grants = await OpenMetadataGrantedAccessService(authz.client, user.identity.id).list_granted()
    database_account = await OracleAccessProvisioner(settings).find_client_account(user.identity.id)
    return UserAccessAudit(
        user=user,
        audited_openmetadata_grants=grants,
        associated_database_account=database_account,
    )


@router.post("/api/users/access/{user_id}/grants/{grant_id}/revoke", response_model=AccessRevocation)
async def revoke_user_access_grant(user_id: str, grant_id: str, authz: AuthzDep, settings: SettingsDep):
    # Authorization question: is the caller an OpenMetadata administrator, and
    # does this approved portal task belong to the requested OM user?
    actor = await authz.get_current_user()
    if not actor.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only OpenMetadata administrators can revoke portal-managed access")
    client = OpenMetadataClient(settings)
    try:
        task = await client.get(
            f"{settings.openmetadata_access_request_task_path.rstrip('/')}/{grant_id}",
            {"fields": "availableTransitions,about,payload"},
        )
        if not str(task.get("name", "")).startswith(f"portal-access-{user_id}-"):
            raise HTTPException(status.HTTP_409_CONFLICT, "This grant is not managed by the portal for the selected user")
        if str(task.get("status", "")).lower() not in {"approved", "granted"}:
            raise HTTPException(status.HTTP_409_CONFLICT, "Only approved data-access grants can be revoked")
        payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
        if payload.get("accessType") == "ColumnLevel" or payload.get("columns"):
            raise HTTPException(status.HTTP_409_CONFLICT, "Column-level access is not provisioned by the portal and cannot be revoked here")
        about = task.get("about") if isinstance(task.get("about"), dict) else {}
        fqn = about.get("fullyQualifiedName")
        if not isinstance(fqn, str):
            raise HTTPException(status.HTTP_409_CONFLICT, "The grant does not identify a table resource")
        parts = fqn.split(".")
        if len(parts) < 2:
            raise HTTPException(status.HTTP_409_CONFLICT, "The grant table resource is invalid")
        transitions = task.get("availableTransitions") if isinstance(task.get("availableTransitions"), list) else []
        revoke_transition = next(
            (
                transition for transition in transitions
                if isinstance(transition, dict)
                and transition.get("resolutionType") == "Revoked"
                and isinstance(transition.get("id"), str)
            ),
            None,
        )
        # The complete DataAccessRequest workflow intentionally records a
        # non-terminal ManualRevoke stage before it closes as Revoked. Advance
        # through that stage so OM retains both audit events, then resolve the
        # terminal Revoked transition.
        if not revoke_transition:
            manual_revoke_transition = next(
                (
                    transition for transition in transitions
                    if isinstance(transition, dict)
                    and transition.get("id") == "manual-revoke"
                    and transition.get("targetTaskStatus") == "ManualRevoke"
                ),
                None,
            )
            if manual_revoke_transition:
                task = await client.post(
                    f"{settings.openmetadata_access_request_task_path.rstrip('/')}/{grant_id}/resolve",
                    {
                        "transitionId": manual_revoke_transition["id"],
                        "comment": "Manual revocation started by a portal administrator.",
                    },
                )
                transitions = task.get("availableTransitions") if isinstance(task.get("availableTransitions"), list) else []
                revoke_transition = next(
                    (
                        transition for transition in transitions
                        if isinstance(transition, dict)
                        and transition.get("resolutionType") == "Revoked"
                        and isinstance(transition.get("id"), str)
                    ),
                    None,
                )
        if not revoke_transition:
            if task.get("workflowStageId") == "workflow-start-failed":
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "OpenMetadata could not start this grant's workflow. This existing task has no lifecycle transition; permanently delete it and create a new request after applying the workflow bootstrap.",
                )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "OpenMetadata does not expose a revoke transition for this grant. Configure a DataAccessRequest workflow with an Approved/Granted-to-Revoked transition.",
            )
        # Persist the revocation through the workflow supplied by OpenMetadata.
        # This produces its change event, policy-agent side effects, and
        # notifications instead of bypassing lifecycle controls.
        await client.post(
            f"{settings.openmetadata_access_request_task_path.rstrip('/')}/{grant_id}/resolve",
            {
                "transitionId": revoke_transition["id"],
                "resolutionType": "Revoked",
                "comment": "Revoked by a portal administrator.",
            },
        )
    finally:
        await client.close()
    provisioner = OracleAccessProvisioner(settings)
    try:
        account_name = provisioner.client_username(user_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    try:
        await provisioner.revoke_select(user_id, parts[-2], parts[-1])
        database_revoke_state = "revoked"
    except Exception:
        # OpenMetadata has already recorded the workflow revocation. Database
        # cleanup is best-effort: a missing or unavailable Oracle account must
        # not turn that completed revocation into a failed request.
        logger.warning("Oracle revoke skipped for portal grant %s and account %s", grant_id, account_name, exc_info=True)
        database_revoke_state = "skipped"
    return AccessRevocation(
        grant_id=grant_id,
        account_name=account_name,
        revoked_resource=fqn,
        openmetadata_state="revoked",
        database_revoke_state=database_revoke_state,
    )


@router.delete("/api/users/access/{user_id}/grants/{grant_id}/hard-delete", response_model=HardDeletedTask)
async def hard_delete_user_access_task(user_id: str, grant_id: str, authz: AuthzDep, settings: SettingsDep):
    """Permanently delete one portal-managed access task; admin only."""
    actor = await authz.get_current_user()
    if not actor.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only OpenMetadata administrators can permanently delete portal-managed access tasks")
    client = OpenMetadataClient(settings)
    try:
        task = await client.get(f"{settings.openmetadata_access_request_task_path.rstrip('/')}/{grant_id}")
        if not str(task.get("name", "")).startswith(f"portal-access-{user_id}-"):
            raise HTTPException(status.HTTP_409_CONFLICT, "This task is not managed by the portal for the selected user")
        await client.delete(
            f"{settings.openmetadata_access_request_task_path.rstrip('/')}/{grant_id}",
            {"hardDelete": "true"},
        )
    finally:
        await client.close()
    return HardDeletedTask(task_id=grant_id)


@router.post("/api/database/query")
async def database_query(request: QueryRequest, authz: AuthzDep, settings: SettingsDep):
    if not settings.database_queries_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Database query endpoint is disabled")
    user = await authz.get_current_user()
    identity = OracleAccessProvisioner.client_username(user.identity.id)
    adapter = OracleAdapter(settings)
    try:
        await adapter.connect(identity)
        return {"items": await adapter.execute_query(request.sql, request.parameters)}
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    finally:
        await adapter.disconnect()


@router.post("/api/query", response_model=QueryResult)
async def query(request: QueryRequest, authz: AuthzDep, settings: SettingsDep):
    await authz.get_current_user()
    try:
        result = await OracleTemporaryProxyQueryService(settings).execute(request.sql, request.parameters)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except Exception as exc:
        logger.exception("Oracle temporary-proxy query failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Oracle could not execute the query. The temporary proxy user was cleaned up.") from exc
    return QueryResult(
        columns=result.columns,
        items=result.items,
        row_count=len(result.items),
        message="Query completed through a temporary Oracle proxy user.",
    )
