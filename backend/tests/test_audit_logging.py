"""Tests for append-only audit logging and company activity."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_context import require_matching_active_company
from app.api.dependencies.company_context import require_active_company_context
from app.main import app
from app.models.audit_log import AuditAction, AuditLog
from app.models.company import CompanyStatus
from app.repositories.audit_log import AuditLogRepository
from app.schemas.audit_log import AuditLogResponse
from app.schemas.company_context import ActiveCompanyContext
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.audit_log import AuditLogService, get_audit_log_service
from app.services.company import (
    CompanyNotFoundError,
    CompanyService,
    CompanySlugConflictError,
)
from app.services.company import get_company_service

NOW = datetime.now(timezone.utc)


class FakeSession:
    """Record transaction and persistence operations."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0
        self.refresh_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flush_count += 1

    def refresh(self, _value: object) -> None:
        self.refresh_count += 1

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


class QuerySession:
    """Capture repository SELECT statements."""

    def __init__(self) -> None:
        self.statements: list[object] = []

    def scalars(self, statement: object) -> SimpleNamespace:
        self.statements.append(statement)
        return SimpleNamespace(all=lambda: [])

    def scalar(self, statement: object) -> int:
        self.statements.append(statement)
        return 0


class FakeCompany:
    """Mutable company used by service tests."""

    def __init__(
        self,
        *,
        company_id: UUID | None = None,
        name: str = "Example Company",
        slug: str = "example-company",
        status: str = CompanyStatus.ACTIVE.value,
    ) -> None:
        self.id = company_id or uuid4()
        self.name = name
        self.slug = slug
        self.status = status
        self.is_active = status == CompanyStatus.ACTIVE.value


class FakeCompanyRepository:
    """Company mutation repository without a database."""

    def __init__(self, company: FakeCompany | None = None) -> None:
        self.company = company
        self.fail_mutation = False

    def get_by_slug(self, slug: str) -> FakeCompany | None:
        if self.company is not None and self.company.slug == slug:
            return self.company
        return None

    def get_by_id(self, _company_id: UUID) -> FakeCompany | None:
        return self.company

    def create(self, data: CompanyCreate) -> FakeCompany:
        if self.fail_mutation:
            raise RuntimeError("mutation failed")
        self.company = FakeCompany(name=data.name, slug=data.slug)
        return self.company

    def update(
        self,
        company: FakeCompany,
        data: CompanyUpdate,
    ) -> FakeCompany:
        if self.fail_mutation:
            raise RuntimeError("mutation failed")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(company, key, value)
        return company

    def set_active(
        self,
        company: FakeCompany,
        *,
        is_active: bool,
    ) -> FakeCompany:
        if self.fail_mutation:
            raise RuntimeError("mutation failed")
        company.is_active = is_active
        company.status = (
            CompanyStatus.ACTIVE.value
            if is_active
            else CompanyStatus.INACTIVE.value
        )
        return company


class RecordingAuditService:
    """Capture audit events or fail before commit."""

    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.events: list[dict[str, Any]] = []

    def append_company_event(self, **event: Any) -> object:
        if self.failure is not None:
            raise self.failure
        self.events.append(event)
        return object()


class FakeMembershipRepository:
    """Create owner memberships without database access."""

    def create(self, *, company_id: UUID, administrator_id: UUID, role: str) -> object:
        return SimpleNamespace(
            id=uuid4(),
            company_id=company_id,
            administrator_id=administrator_id,
            role=role,
            is_active=True,
        )


def create_company_service(
    *,
    company: FakeCompany | None = None,
    audit_fail: bool = False,
) -> tuple[CompanyService, FakeSession, FakeCompanyRepository, RecordingAuditService]:
    session = FakeSession()
    repository = FakeCompanyRepository(company)
    audit_service = RecordingAuditService(
        failure=(RuntimeError("audit append failed") if audit_fail else None)
    )
    service = CompanyService(
        repository=repository,  # type: ignore[arg-type]
        audit_service=audit_service,  # type: ignore[arg-type]
        membership_repository=FakeMembershipRepository(),  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )
    return service, session, repository, audit_service


def test_audit_response_schema_accepts_json_object_details() -> None:
    event_id = uuid4()
    company_id = uuid4()
    actor_id = uuid4()
    response = AuditLogResponse.model_validate(
        SimpleNamespace(
            id=event_id,
            scope="company",
            company_id=company_id,
            actor_type="administrator",
            actor_administrator_id=actor_id,
            action="company.created",
            resource_type="company",
            resource_id=company_id,
            details={"name": "Example"},
            created_at=NOW,
        )
    )
    assert response.details == {"name": "Example"}


def test_audit_repository_append_does_not_commit() -> None:
    session = FakeSession()
    repository = AuditLogRepository(session)  # type: ignore[arg-type]
    repository.create(
        scope="company",
        company_id=uuid4(),
        actor_type="administrator",
        actor_administrator_id=uuid4(),
        action="company.created",
        resource_type="company",
        resource_id=uuid4(),
        details={},
    )
    assert len(session.added) == 1
    assert session.flush_count == 1
    assert session.refresh_count == 1
    assert session.commit_count == 0


def test_audit_repository_filters_company_scope_and_orders_newest_first() -> None:
    company_id = uuid4()
    session = QuerySession()
    repository = AuditLogRepository(session)  # type: ignore[arg-type]
    assert repository.list_for_company(
        company_id=company_id,
        limit=25,
        offset=10,
    ) == []
    assert repository.count_for_company(company_id=company_id) == 0
    list_statement, count_statement = session.statements
    list_sql = str(list_statement)
    count_sql = str(count_statement)
    assert "audit_logs.company_id" in list_sql
    assert "audit_logs.scope" in list_sql
    assert "audit_logs.created_at DESC, audit_logs.id DESC" in list_sql
    assert "LIMIT" in list_sql and "OFFSET" in list_sql
    assert "audit_logs.company_id" in count_sql
    assert "audit_logs.scope" in count_sql


def test_audit_service_rejects_non_object_and_secret_details() -> None:
    repository = SimpleNamespace(create=lambda **_kwargs: object())
    service = AuditLogService(repository)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="JSON object"):
        service.append_company_event(
            company_id=uuid4(),
            actor_administrator_id=uuid4(),
            action="company.created",
            resource_type="company",
            resource_id=uuid4(),
            details=[],  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="Unsafe"):
        service.append_company_event(
            company_id=uuid4(),
            actor_administrator_id=uuid4(),
            action="company.created",
            resource_type="company",
            resource_id=uuid4(),
            details={"access_token": "forbidden"},
        )


def test_company_creation_is_audited_and_committed_once() -> None:
    service, session, _repository, audit = create_company_service()
    actor_id = uuid4()
    company = service.create_company(
        CompanyCreate(name="Created Company", slug="created-company"),
        actor_administrator_id=actor_id,
    )
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert len(audit.events) == 2
    assert audit.events[0] == {
        "company_id": company.id,
        "actor_administrator_id": actor_id,
        "action": AuditAction.COMPANY_CREATED.value,
        "resource_type": "company",
        "resource_id": company.id,
        "details": {"name": "Created Company", "slug": "created-company"},
    }
    assert audit.events[1]["action"] == "company_membership.created"
    assert audit.events[1]["resource_type"] == "company_membership"


def test_company_update_records_only_actual_changes() -> None:
    company = FakeCompany(name="Old Name", slug="same-slug")
    service, session, _repository, audit = create_company_service(company=company)
    service.update_company(
        company.id,
        CompanyUpdate(name="New Name", slug="same-slug"),
        actor_administrator_id=uuid4(),
    )
    assert session.commit_count == 1
    assert audit.events[0]["action"] == AuditAction.COMPANY_UPDATED.value
    assert audit.events[0]["details"] == {
        "changed": True,
        "changes": {"name": {"from": "Old Name", "to": "New Name"}},
    }


@pytest.mark.parametrize(
    ("method_name", "initial_status", "expected_action", "changed"),
    [
        ("activate_company", "inactive", "company.activated", True),
        ("activate_company", "active", "company.activated", False),
        ("deactivate_company", "active", "company.deactivated", True),
        ("deactivate_company", "inactive", "company.deactivated", False),
    ],
)
def test_status_commands_are_always_audited(
    method_name: str,
    initial_status: str,
    expected_action: str,
    changed: bool,
) -> None:
    company = FakeCompany(status=initial_status)
    service, session, _repository, audit = create_company_service(company=company)
    getattr(service, method_name)(
        company.id,
        actor_administrator_id=uuid4(),
    )
    assert session.commit_count == 1
    assert audit.events[0]["action"] == expected_action
    assert audit.events[0]["details"]["changed"] is changed


def test_audit_failure_rolls_back_without_commit() -> None:
    service, session, _repository, audit = create_company_service(audit_fail=True)
    with pytest.raises(RuntimeError, match="audit append failed"):
        service.create_company(
            CompanyCreate(name="Rollback Company", slug="rollback-company"),
            actor_administrator_id=uuid4(),
        )
    assert audit.events == []
    assert session.commit_count == 0
    assert session.rollback_count == 1


def test_audit_integrity_error_rolls_back_company_mutation() -> None:
    session = FakeSession()
    repository = FakeCompanyRepository()
    audit = RecordingAuditService(
        failure=IntegrityError("audit insert", {}, RuntimeError("constraint"))
    )
    service = CompanyService(
        repository=repository,  # type: ignore[arg-type]
        audit_service=audit,  # type: ignore[arg-type]
        membership_repository=FakeMembershipRepository(),  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )
    with pytest.raises(IntegrityError):
        service.create_company(
            CompanyCreate(name="Atomic Company", slug="atomic-company"),
            actor_administrator_id=uuid4(),
        )
    assert session.commit_count == 0
    assert session.rollback_count == 1


def test_company_and_audit_repositories_share_request_session() -> None:
    session = FakeSession()
    service = get_company_service(session)  # type: ignore[arg-type]
    assert service._repository._session is session
    assert service._audit_service._repository._session is session
    assert service._membership_repository._session is session


def test_mutation_failure_creates_no_audit_event_and_rolls_back() -> None:
    company = FakeCompany()
    service, session, repository, audit = create_company_service(company=company)
    repository.fail_mutation = True
    with pytest.raises(RuntimeError, match="mutation failed"):
        service.activate_company(
            company.id,
            actor_administrator_id=uuid4(),
        )
    assert audit.events == []
    assert session.commit_count == 0
    assert session.rollback_count == 1


def test_slug_conflict_creates_no_audit_event() -> None:
    company = FakeCompany(slug="existing-company")
    service, session, _repository, audit = create_company_service(company=company)
    with pytest.raises(CompanySlugConflictError):
        service.create_company(
            CompanyCreate(name="Duplicate", slug="existing-company"),
            actor_administrator_id=uuid4(),
        )
    assert audit.events == []
    assert session.commit_count == 0


class FakeActivityService:
    """Return deterministic activity for API tests."""

    def __init__(self, company_id: UUID, actor_id: UUID) -> None:
        self.company_id = company_id
        self.actor_id = actor_id

    def list_company_activity(
        self,
        *,
        company_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[SimpleNamespace], int]:
        assert company_id == self.company_id
        events = [
            SimpleNamespace(
                id=uuid4(),
                scope="company",
                company_id=company_id,
                actor_type="administrator",
                actor_administrator_id=self.actor_id,
                action="company.updated",
                resource_type="company",
                resource_id=company_id,
                details={"sequence": sequence},
                created_at=NOW - timedelta(minutes=sequence),
            )
            for sequence in range(3)
        ]
        return events[offset:offset + limit], len(events)


def test_matching_company_activity_returns_pagination_contract() -> None:
    company_id = uuid4()
    actor_id = uuid4()
    administrator = SimpleNamespace(
        id=actor_id,
        is_active=True,
        is_superuser=True,
    )
    context = ActiveCompanyContext(
        administrator=administrator,  # type: ignore[arg-type]
        company=SimpleNamespace(id=company_id),  # type: ignore[arg-type]
        membership=None,
        is_platform_superuser=True,
    )
    app.dependency_overrides[require_current_administrator] = lambda: administrator
    app.dependency_overrides[require_matching_active_company] = lambda: context
    app.dependency_overrides[get_audit_log_service] = lambda: (
        FakeActivityService(company_id, actor_id)
    )
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/companies/{company_id}/activity?limit=2&offset=1"
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["limit"] == 2
    assert response.json()["offset"] == 1
    assert [item["details"]["sequence"] for item in response.json()["items"]] == [1, 2]


def test_company_activity_without_authentication_is_unauthorized() -> None:
    app.dependency_overrides[get_audit_log_service] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/companies/{uuid4()}/activity",
                headers={"X-Company-ID": str(uuid4())},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("header", "is_superuser", "company_state", "expected_status"),
    [
        (None, True, "active", 400),
        ("invalid", True, "active", 400),
        ("selected", False, "active", 403),
        ("selected", True, "missing", 404),
        ("selected", True, "inactive", 409),
    ],
)
def test_company_activity_enforces_active_company_context(
    header: str | None,
    is_superuser: bool,
    company_state: str,
    expected_status: int,
) -> None:
    company_id = uuid4()
    company = SimpleNamespace(
        id=company_id,
        status=company_state,
        is_active=company_state == "active",
    )

    class ContextCompanyService:
        def get_company(self, _company_id: UUID) -> object:
            if company_state == "missing":
                raise CompanyNotFoundError
            return company

        def get_active_membership(
            self,
            *,
            company_id: UUID,
            administrator_id: UUID,
        ) -> None:
            return None

    app.dependency_overrides[require_current_administrator] = lambda: (
        SimpleNamespace(id=uuid4(), is_active=True, is_superuser=is_superuser)
    )
    app.dependency_overrides[get_company_service] = ContextCompanyService
    app.dependency_overrides[get_audit_log_service] = lambda: object()
    headers = {}
    if header is not None:
        headers["X-Company-ID"] = (
            str(company_id) if header == "selected" else header
        )
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/companies/{company_id}/activity",
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == expected_status


def test_company_activity_rejects_path_context_mismatch() -> None:
    context_company_id = uuid4()
    path_company_id = uuid4()
    app.dependency_overrides[require_current_administrator] = lambda: object()
    app.dependency_overrides[require_active_company_context] = lambda: (
        SimpleNamespace(company=SimpleNamespace(id=context_company_id))
    )
    app.dependency_overrides[get_audit_log_service] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/companies/{path_company_id}/activity"
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_company_activity_rejects_invalid_pagination(query: str) -> None:
    company_id = uuid4()
    administrator = SimpleNamespace(
        id=uuid4(),
        is_active=True,
        is_superuser=True,
    )
    context = ActiveCompanyContext(
        administrator=administrator,  # type: ignore[arg-type]
        company=SimpleNamespace(id=company_id),  # type: ignore[arg-type]
        membership=None,
        is_platform_superuser=True,
    )
    app.dependency_overrides[require_current_administrator] = lambda: administrator
    app.dependency_overrides[require_matching_active_company] = lambda: context
    app.dependency_overrides[get_audit_log_service] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/companies/{company_id}/activity?{query}"
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
