"""Tests for the safe read-only dashboard foundation."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_authorization import (
    require_approvals_read,
    require_company_activity_read,
    require_provider_executions_read,
    require_providers_read,
)
from app.main import app
from app.models.audit_log import AuditActorType
from app.repositories.dashboard import (
    DashboardCountSnapshot,
    DashboardRepository,
)
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard import (
    RECENT_AUDIT_EVENT_LIMIT,
    DashboardService,
    get_dashboard_service,
)

NOW = datetime.now(timezone.utc)
COMPANY_ID = uuid4()


class RecordingSession:
    """Return isolated results while recording read-only statements."""

    def __init__(
        self,
        *,
        counts: dict[str, int] | None = None,
        events: list[object] | None = None,
    ) -> None:
        values = counts or {}
        self._row = SimpleNamespace(
            provider_connections=values.get("provider_connections", 0),
            enabled_provider_connections=values.get(
                "enabled_provider_connections",
                0,
            ),
            provider_credentials=values.get("provider_credentials", 0),
            pending_approvals=values.get("pending_approvals", 0),
            provider_executions=values.get("provider_executions", 0),
            failed_provider_executions=values.get(
                "failed_provider_executions",
                0,
            ),
            audit_events=values.get("audit_events", 0),
        )
        self._events = events or []
        self.statements: list[object] = []
        self.write_calls: list[str] = []

    def execute(self, statement: object) -> SimpleNamespace:
        self.statements.append(statement)
        return SimpleNamespace(one=lambda: self._row)

    def scalars(self, statement: object) -> SimpleNamespace:
        self.statements.append(statement)
        return SimpleNamespace(all=lambda: self._events)

    def add(self, _value: object) -> None:
        self.write_calls.append("add")

    def flush(self) -> None:
        self.write_calls.append("flush")

    def commit(self) -> None:
        self.write_calls.append("commit")


class FakeDashboardRepository:
    """Return deterministic dashboard fixtures."""

    def __init__(
        self,
        *,
        snapshot: DashboardCountSnapshot,
        events: list[object],
    ) -> None:
        self.snapshot = snapshot
        self.events = events
        self.calls: list[tuple[str, UUID, int | None]] = []

    def get_count_snapshot(
        self,
        *,
        company_id: UUID,
    ) -> DashboardCountSnapshot:
        self.calls.append(("counts", company_id, None))
        return self.snapshot

    def list_recent_audit_events(
        self,
        *,
        company_id: UUID,
        limit: int,
    ) -> list[object]:
        self.calls.append(("events", company_id, limit))
        return self.events[:limit]


def make_event(*, offset: int = 0) -> SimpleNamespace:
    """Build a safe audit object accepted by the summary service."""

    return SimpleNamespace(
        id=uuid4(),
        actor_type=AuditActorType.ADMINISTRATOR.value,
        action="provider_connection.updated",
        resource_type="provider_connection",
        resource_id=uuid4(),
        created_at=NOW - timedelta(minutes=offset),
        details={"sensitive": "must not be serialized"},
        actor_administrator_id=uuid4(),
        actor_agent_id=None,
    )


def make_service(
    *,
    snapshot: DashboardCountSnapshot | None = None,
    events: list[object] | None = None,
) -> tuple[DashboardService, FakeDashboardRepository]:
    """Construct a dashboard service without database access."""

    repository = FakeDashboardRepository(
        snapshot=snapshot
        or DashboardCountSnapshot(
            provider_connections=0,
            enabled_provider_connections=0,
            provider_credentials=0,
            pending_approvals=0,
            provider_executions=0,
            failed_provider_executions=0,
            audit_events=0,
        ),
        events=events or [],
    )
    settings = SimpleNamespace(
        app_environment="test",
        app_version="1.2.3",
    )
    service = DashboardService(
        repository=repository,  # type: ignore[arg-type]
        settings=settings,  # type: ignore[arg-type]
    )
    return service, repository


def test_summary_service_returns_zero_counts_and_runtime_metadata() -> None:
    service, repository = make_service()

    result = service.get_summary(company_id=COMPANY_ID)

    assert result.service.model_dump(mode="json") == {
        "status": "ok",
        "readiness": "reachable",
        "environment": "test",
        "version": "1.2.3",
    }
    assert set(result.counts.model_dump().values()) == {0}
    assert result.recent_audit_events == []
    assert repository.calls == [
        ("counts", COMPANY_ID, None),
        ("events", COMPANY_ID, RECENT_AUDIT_EVENT_LIMIT),
    ]


def test_summary_service_returns_fixture_counts_and_bounded_safe_events() -> None:
    events = [make_event(offset=index) for index in range(7)]
    service, _repository = make_service(
        snapshot=DashboardCountSnapshot(
            provider_connections=4,
            enabled_provider_connections=3,
            provider_credentials=2,
            pending_approvals=5,
            provider_executions=8,
            failed_provider_executions=1,
            audit_events=13,
        ),
        events=events,
    )

    result = service.get_summary(company_id=COMPANY_ID)

    assert result.counts.model_dump() == {
        "provider_connections": 4,
        "enabled_provider_connections": 3,
        "provider_credentials": 2,
        "pending_approvals": 5,
        "provider_executions": 8,
        "failed_provider_executions": 1,
        "audit_events": 13,
    }
    assert len(result.recent_audit_events) == RECENT_AUDIT_EVENT_LIMIT
    serialized = result.model_dump(mode="json")
    rendered = str(serialized).lower()
    for forbidden in (
        "details",
        "encrypted_payload",
        "nonce",
        "encryption_key_id",
        "keyring",
        "hash",
        "token",
        "credential_id",
    ):
        assert forbidden not in rendered


def test_repository_uses_two_read_only_company_scoped_queries() -> None:
    session = RecordingSession()
    repository = DashboardRepository(session)  # type: ignore[arg-type]

    snapshot = repository.get_count_snapshot(company_id=COMPANY_ID)
    events = repository.list_recent_audit_events(
        company_id=COMPANY_ID,
        limit=RECENT_AUDIT_EVENT_LIMIT,
    )

    assert snapshot == DashboardCountSnapshot(0, 0, 0, 0, 0, 0, 0)
    assert events == []
    assert len(session.statements) == 2
    assert session.write_calls == []
    compiled = [
        str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        for statement in session.statements
    ]
    normalized = " ".join(compiled).upper()
    assert normalized.count("SELECT") >= 9
    assert "INSERT " not in normalized
    assert "UPDATE " not in normalized
    assert "DELETE " not in normalized
    assert str(COMPANY_ID) in " ".join(compiled)


def test_recent_audit_query_is_bounded_and_deterministically_ordered() -> None:
    session = RecordingSession()
    repository = DashboardRepository(session)  # type: ignore[arg-type]

    repository.list_recent_audit_events(
        company_id=COMPANY_ID,
        limit=RECENT_AUDIT_EVENT_LIMIT,
    )

    compiled = str(
        session.statements[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "ORDER BY audit_logs.created_at DESC, audit_logs.id DESC" in compiled
    assert f"LIMIT {RECENT_AUDIT_EVENT_LIMIT}" in compiled
    assert "audit_logs.scope = 'company'" in compiled


class FakeDashboardService:
    """Endpoint dependency returning one explicit response."""

    def get_summary(self, *, company_id: UUID) -> DashboardSummaryResponse:
        assert company_id == COMPANY_ID
        service, _repository = make_service()
        return service.get_summary(company_id=company_id)


def test_dashboard_endpoint_success_and_openapi_schema() -> None:
    context = object()
    app.dependency_overrides[require_current_administrator] = lambda: object()
    app.dependency_overrides[require_company_activity_read] = lambda: context
    app.dependency_overrides[require_providers_read] = lambda: context
    app.dependency_overrides[require_approvals_read] = lambda: context
    app.dependency_overrides[require_provider_executions_read] = lambda: context
    app.dependency_overrides[get_dashboard_service] = FakeDashboardService

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/companies/{COMPANY_ID}/dashboard/summary"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert set(response.json()) == {
        "service",
        "counts",
        "recent_audit_events",
    }
    operation = app.openapi()["paths"][
        "/api/v1/companies/{company_id}/dashboard/summary"
    ]["get"]
    assert operation["tags"] == ["dashboard"]
    assert "DashboardSummaryResponse" in str(operation)


def test_dashboard_endpoint_requires_administrator_authentication() -> None:
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/companies/{COMPANY_ID}/dashboard/summary",
            headers={"X-Company-ID": str(COMPANY_ID)},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_dashboard_response_schema_has_only_allowlisted_fields() -> None:
    schema = DashboardSummaryResponse.model_json_schema()
    rendered = str(schema).lower()

    for forbidden in (
        "encrypted_payload",
        "nonce",
        "encryption_key_id",
        "keyring",
        "hash",
        "access_token",
        "details",
    ):
        assert forbidden not in rendered
    assert set(schema["properties"]) == {
        "service",
        "counts",
        "recent_audit_events",
    }
