"""Focused security, schema, API and authorization tests for Agent Identity."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.api.dependencies.agent_authentication import authorization_action_for_agent, require_current_agent
from app.api.dependencies.company_authorization import require_agents_manage, require_agents_read
from app.core.agent_security import CREDENTIAL_PREFIX, InvalidAgentCredentialError, InvalidAgentTokenError, create_agent_token, decode_agent_token, generate_agent_credential, parse_agent_credential, verify_agent_credential
from app.core.security import InvalidAccessTokenError, create_access_token, decode_access_token
from app.main import app
from app.models.agent import Agent, AgentCredential, AgentPermission
from app.schemas.agent import AgentCreate, AgentCredentialResponse, AgentPermissionCreate, AgentResponse
from app.schemas.company_context import ActiveCompanyContext
from app.services.agent_identity import AgentLifecycleError, AuthenticatedAgent, AgentIdentityService, InvalidAgentAuthenticationError, get_agent_identity_service

PEPPER = "p" * 64
JWT_SECRET = "j" * 64
NOW = datetime.now(UTC)


def agent(**overrides):
    values = dict(id=uuid4(), company_id=uuid4(), name="Email Agent", slug="email-agent", agent_type="email_outreach", description=None, status="active", is_system=False, metadata_={}, auth_version=1, revoked_at=None, revocation_reason=None, created_at=NOW, updated_at=NOW)
    values.update(overrides); return SimpleNamespace(**values)


def credential(agent_value=None, **overrides):
    agent_value = agent_value or agent()
    values = dict(id=uuid4(), company_id=agent_value.company_id, agent_id=agent_value.id, name="primary", public_id="a" * 24, secret_prefix="cai_agent_v1_aaaaaaaaaa", secret_last_four="last", status="active", expires_at=None, last_used_at=None, revoked_at=None, rotated_from_credential_id=None, created_at=NOW)
    values.update(overrides); return SimpleNamespace(**values)


def test_machine_credential_has_versioned_parseable_high_entropy_format() -> None:
    generated = generate_agent_credential(pepper=PEPPER)
    public_id, secret = parse_agent_credential(generated.plaintext)
    assert generated.plaintext.startswith(CREDENTIAL_PREFIX)
    assert public_id == generated.public_id and len(secret) >= 43
    assert generated.plaintext not in generated.secret_hash
    assert len(generated.secret_hash) == 64


def test_machine_credential_hmac_verification_and_constant_time_comparison(monkeypatch) -> None:
    generated = generate_agent_credential(pepper=PEPPER); called = False
    original = __import__("hmac").compare_digest
    def compare(first, second):
        nonlocal called; called = True; return original(first, second)
    monkeypatch.setattr("app.core.agent_security.hmac.compare_digest", compare)
    assert verify_agent_credential(generated.plaintext, generated.secret_hash, pepper=PEPPER)
    assert called


@pytest.mark.parametrize("raw", ["", "Bearer x", "cai_agent_v1_x", "cai_agent_v1_short.secret", "cai_agent_v2_" + "a" * 24 + "." + "x" * 43])
def test_malformed_credentials_are_rejected(raw) -> None:
    with pytest.raises(InvalidAgentCredentialError): parse_agent_credential(raw)


def test_wrong_machine_secret_is_rejected() -> None:
    generated = generate_agent_credential(pepper=PEPPER)
    public_id, _ = parse_agent_credential(generated.plaintext)
    wrong = f"{CREDENTIAL_PREFIX}{public_id}.{'x' * 43}"
    assert not verify_agent_credential(wrong, generated.secret_hash, pepper=PEPPER)


def test_agent_jwt_round_trip_contains_authoritative_identity() -> None:
    ids = (uuid4(), uuid4(), uuid4())
    token = create_agent_token(agent_id=ids[0], company_id=ids[1], credential_id=ids[2], auth_version=4, secret=JWT_SECRET, algorithm="HS256", ttl_seconds=300, issuer="issuer", audience="audience")
    claims = decode_agent_token(token, secret=JWT_SECRET, algorithm="HS256", issuer="issuer", audience="audience")
    assert (claims.agent_id, claims.company_id, claims.credential_id, claims.auth_version) == (*ids, 4)


class ResolutionRepository:
    def __init__(self, agent_value, credential_value, permissions=()): self.agent=agent_value; self.credential=credential_value; self.permissions=permissions
    def get_agent(self, *, company_id, agent_id): return self.agent if self.agent.company_id == company_id and self.agent.id == agent_id else None
    def get_credential(self, *, company_id, agent_id, credential_id): return self.credential if (self.credential.company_id, self.credential.agent_id, self.credential.id) == (company_id, agent_id, credential_id) else None
    def list_permissions(self, *, company_id, agent_id, active_only=False): return list(self.permissions)


def resolution_service(item, key, company=None, permissions=()):
    settings=SimpleNamespace(agent_jwt_secret=JWT_SECRET, agent_jwt_algorithm="HS256", agent_jwt_ttl_seconds=300, agent_jwt_issuer="issuer", agent_jwt_audience="audience")
    companies=SimpleNamespace(get_by_id=lambda company_id: company or SimpleNamespace(id=company_id, is_active=True, status="active"))
    return AgentIdentityService(ResolutionRepository(item, key, permissions), companies, SimpleNamespace(), SimpleNamespace(), settings)


@pytest.mark.parametrize(("agent_status", "credential_status", "version", "company_active"), [("inactive", "active", 1, True), ("revoked", "active", 1, True), ("active", "revoked", 1, True), ("active", "rotated", 1, True), ("active", "active", 2, True), ("active", "active", 1, False)])
def test_database_revalidation_immediately_rejects_security_state_changes(agent_status, credential_status, version, company_active) -> None:
    item=agent(status=agent_status, auth_version=version); key=credential(item, status=credential_status)
    token=create_agent_token(agent_id=item.id, company_id=item.company_id, credential_id=key.id, auth_version=1, secret=JWT_SECRET, algorithm="HS256", ttl_seconds=300, issuer="issuer", audience="audience")
    company=SimpleNamespace(id=item.company_id, is_active=company_active, status="active" if company_active else "inactive")
    with pytest.raises(InvalidAgentAuthenticationError): resolution_service(item, key, company).resolve_token(token)


def test_database_revalidation_returns_only_active_exact_permissions() -> None:
    item=agent(); key=credential(item); permissions=[SimpleNamespace(permission_key="lead.read"), SimpleNamespace(permission_key="campaign.read")]
    token=create_agent_token(agent_id=item.id, company_id=item.company_id, credential_id=key.id, auth_version=1, secret=JWT_SECRET, algorithm="HS256", ttl_seconds=300, issuer="issuer", audience="audience")
    identity=resolution_service(item, key, permissions=permissions).resolve_token(token)
    assert identity.permissions == ("campaign.read", "lead.read")


@pytest.mark.parametrize(("issuer", "audience"), [("wrong", "audience"), ("issuer", "wrong")])
def test_agent_jwt_rejects_wrong_issuer_or_audience(issuer, audience) -> None:
    token = create_agent_token(agent_id=uuid4(), company_id=uuid4(), credential_id=uuid4(), auth_version=1, secret=JWT_SECRET, algorithm="HS256", ttl_seconds=300, issuer="issuer", audience="audience")
    with pytest.raises(InvalidAgentTokenError): decode_agent_token(token, secret=JWT_SECRET, algorithm="HS256", issuer=issuer, audience=audience)


def test_expired_agent_jwt_is_rejected() -> None:
    now = datetime.now(UTC)
    payload = {"sub": str(uuid4()), "token_type": "agent", "company_id": str(uuid4()), "credential_id": str(uuid4()), "auth_version": 1, "iss": "issuer", "aud": "audience", "iat": now - timedelta(minutes=2), "exp": now - timedelta(minutes=1), "jti": str(uuid4())}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    with pytest.raises(InvalidAgentTokenError): decode_agent_token(token, secret=JWT_SECRET, algorithm="HS256", issuer="issuer", audience="audience")


def test_administrator_and_agent_tokens_are_semantically_distinct() -> None:
    administrator_token = create_access_token(uuid4(), secret_key=JWT_SECRET, expires_minutes=5)
    with pytest.raises(InvalidAgentTokenError): decode_agent_token(administrator_token, secret=JWT_SECRET, algorithm="HS256", issuer="issuer", audience="audience")
    agent_token = create_agent_token(agent_id=uuid4(), company_id=uuid4(), credential_id=uuid4(), auth_version=1, secret=JWT_SECRET, algorithm="HS256", ttl_seconds=300, issuer="issuer", audience="audience")
    with pytest.raises(InvalidAccessTokenError): decode_access_token(agent_token, secret_key=JWT_SECRET)


def test_agent_models_enforce_company_scoped_relations_and_no_hard_delete_api() -> None:
    assert {table.name for table in (Agent.__table__, AgentCredential.__table__, AgentPermission.__table__)} == {"agents", "agent_credentials", "agent_permissions"}
    assert any(set(fk.column_keys) == {"company_id", "agent_id"} for fk in AgentCredential.__table__.foreign_key_constraints)
    assert any(set(fk.column_keys) == {"company_id", "agent_id"} for fk in AgentPermission.__table__.foreign_key_constraints)


def test_credential_rotation_lineage_is_company_and_agent_scoped() -> None:
    lineage = next(
        constraint
        for constraint in AgentCredential.__table__.foreign_key_constraints
        if constraint.name == "fk_agent_credentials_rotation_lineage"
    )
    assert tuple(lineage.column_keys) == ("company_id", "agent_id", "rotated_from_credential_id")
    assert tuple(element.target_fullname for element in lineage.elements) == (
        "agent_credentials.company_id",
        "agent_credentials.agent_id",
        "agent_credentials.id",
    )
    assert lineage.ondelete == "RESTRICT"
    assert any(
        constraint.name == "uq_agent_credentials_company_agent_id"
        and tuple(column.name for column in constraint.columns) == ("company_id", "agent_id", "id")
        for constraint in AgentCredential.__table__.constraints
    )


def test_credential_rotation_lineage_rejects_cross_agent_and_cross_company() -> None:
    engine = sa.create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    metadata = sa.MetaData()
    administrators = sa.Table("administrators", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    agents = sa.Table(
        "agents",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.UniqueConstraint("company_id", "id"),
    )
    credentials = AgentCredential.__table__.to_metadata(metadata)
    metadata.create_all(engine)

    administrator_id = uuid4()
    company_a, company_b = uuid4(), uuid4()
    agent_a, agent_b, agent_c = uuid4(), uuid4(), uuid4()
    parent_id = uuid4()

    def credential_values(*, item_id, company_id, agent_id, public_id, rotated_from=None):
        return {
            "id": item_id,
            "company_id": company_id,
            "agent_id": agent_id,
            "name": "test",
            "public_id": public_id,
            "secret_hash": "a" * 64,
            "secret_prefix": "cai_agent_v1_test",
            "secret_last_four": "test",
            "status": "active",
            "created_by_administrator_id": administrator_id,
            "rotated_from_credential_id": rotated_from,
        }

    with engine.begin() as connection:
        connection.execute(administrators.insert().values(id=administrator_id))
        connection.execute(
            agents.insert(),
            [
                {"id": agent_a, "company_id": company_a},
                {"id": agent_b, "company_id": company_a},
                {"id": agent_c, "company_id": company_b},
            ],
        )
        connection.execute(
            credentials.insert().values(
                **credential_values(
                    item_id=parent_id,
                    company_id=company_a,
                    agent_id=agent_a,
                    public_id="parent-credential-id",
                )
            )
        )
        connection.execute(
            credentials.insert().values(
                **credential_values(
                    item_id=uuid4(),
                    company_id=company_a,
                    agent_id=agent_a,
                    public_id="valid-rotated-id",
                    rotated_from=parent_id,
                )
            )
        )

        with pytest.raises(IntegrityError):
            connection.execute(
                credentials.insert().values(
                    **credential_values(
                        item_id=uuid4(),
                        company_id=company_a,
                        agent_id=agent_b,
                        public_id="cross-agent-id",
                        rotated_from=parent_id,
                    )
                )
            )
        with pytest.raises(IntegrityError):
            connection.execute(
                credentials.insert().values(
                    **credential_values(
                        item_id=uuid4(),
                        company_id=company_b,
                        agent_id=agent_c,
                        public_id="cross-company-id",
                        rotated_from=parent_id,
                    )
                )
            )


class PermissionGrantRepository:
    def __init__(self, item) -> None:
        self.item = item
        self.get_agent_calls = []
        self.duplicate_checked = False
        self.created = False

    def get_agent(self, *, company_id, agent_id, for_update=False):
        self.get_agent_calls.append((company_id, agent_id, for_update))
        return self.item

    def get_active_permission(self, **_kwargs):
        self.duplicate_checked = True
        return None

    def create_permission(self, **values):
        self.created = True
        return SimpleNamespace(id=uuid4(), **values)


class RecordingTransaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def permission_grant_service(item):
    repository = PermissionGrantRepository(item)
    transaction = RecordingTransaction()
    audit = SimpleNamespace(events=[], append_company_event=lambda **values: audit.events.append(values))
    service = AgentIdentityService(repository, SimpleNamespace(), audit, transaction, SimpleNamespace())
    return service, repository, transaction, audit


def test_grant_permission_locks_agent_before_validation_and_insert() -> None:
    item = agent()
    service, repository, transaction, audit = permission_grant_service(item)
    actor = SimpleNamespace(id=uuid4(), is_superuser=False)

    result = service.grant_permission(
        company_id=item.company_id,
        agent_id=item.id,
        permission_key="lead.read",
        reason="Required for research.",
        actor=actor,
        membership=None,
    )

    assert repository.get_agent_calls == [(item.company_id, item.id, True)]
    assert repository.duplicate_checked and repository.created
    assert result.permission_key == "lead.read"
    assert transaction.commits == 1 and transaction.rollbacks == 0
    assert len(audit.events) == 1


def test_grant_permission_cannot_insert_after_locked_agent_is_revoked() -> None:
    item = agent(status="revoked")
    service, repository, transaction, audit = permission_grant_service(item)

    with pytest.raises(AgentLifecycleError):
        service.grant_permission(
            company_id=item.company_id,
            agent_id=item.id,
            permission_key="lead.read",
            reason=None,
            actor=SimpleNamespace(id=uuid4(), is_superuser=False),
            membership=None,
        )

    assert repository.get_agent_calls == [(item.company_id, item.id, True)]
    assert not repository.duplicate_checked
    assert not repository.created
    assert transaction.commits == transaction.rollbacks == 0
    assert audit.events == []


def test_agent_schemas_reject_slug_and_permission_wildcards() -> None:
    with pytest.raises(ValidationError): AgentCreate(name="Agent", slug="Bad Slug", agent_type="general")
    with pytest.raises(ValidationError): AgentCreate(name="Agent", slug="agent", agent_type="general", status="revoked")
    with pytest.raises(ValidationError): AgentPermissionCreate(permission_key="provider.*")
    assert AgentPermissionCreate(permission_key="LEAD.READ").permission_key == "lead.read"


def test_credential_metadata_response_cannot_expose_hash_or_plaintext() -> None:
    fields = set(AgentCredentialResponse.model_fields)
    assert "secret_hash" not in fields and "credential" not in fields


def test_authorization_action_uses_authenticated_agent_identity() -> None:
    item = agent(); identity = AuthenticatedAgent(item, credential(item), ("lead.read",))
    action = authorization_action_for_agent(identity, action_type="metadata.read", scope_type="company")
    assert action.actor_type == "agent" and action.actor_agent_id == item.id and action.company_id == item.company_id
    with pytest.raises(ValueError): authorization_action_for_agent(identity, company_id=uuid4(), action_type="metadata.read", scope_type="company")


def test_internal_me_returns_active_exact_permissions() -> None:
    item = agent(); auth = AuthenticatedAgent(item, credential(item), ("campaign.read", "lead.read"))
    app.dependency_overrides[require_current_agent] = lambda: auth
    try:
        with TestClient(app) as client: response = client.get("/api/v1/internal/agent-auth/me", headers={"Authorization": "Bearer test"})
    finally: app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["permissions"] == ["campaign.read", "lead.read"]
    assert response.json()["company_id"] == str(item.company_id)


def test_internal_me_rejects_missing_authentication() -> None:
    with TestClient(app) as client: response = client.get("/api/v1/internal/agent-auth/me")
    assert response.status_code == 401 and response.json() == {"detail": "Valid agent authentication is required."}


class FakeAgentService:
    def __init__(self, item): self.item=item; self.calls=[]
    def list_agents(self, **kwargs): self.calls.append(kwargs); return [self.item], 1
    def get_agent(self, **kwargs): self.calls.append(kwargs); return self.item


def context_for(item):
    administrator = SimpleNamespace(id=uuid4(), is_superuser=True)
    company = SimpleNamespace(id=item.company_id)
    return ActiveCompanyContext(administrator, company, None, True)


def test_administrator_agent_list_is_company_scoped_and_paginated() -> None:
    item=agent(); service=FakeAgentService(item); context=context_for(item)
    app.dependency_overrides[require_agents_read] = lambda: context
    app.dependency_overrides[get_agent_identity_service] = lambda: service
    try:
        with TestClient(app) as client: response=client.get(f"/api/v1/companies/{item.company_id}/agents?limit=1&offset=0", headers={"X-Company-ID": str(item.company_id)})
    finally: app.dependency_overrides.clear()
    assert response.status_code == 200 and response.json()["total"] == 1
    assert service.calls[0]["company_id"] == item.company_id and service.calls[0]["limit"] == 1


def test_agent_response_never_contains_security_fields() -> None:
    fields=set(AgentResponse.model_fields)
    assert fields.isdisjoint({"secret_hash", "credential", "created_by_administrator_id", "revoked_by_administrator_id"})


def test_openapi_registers_all_agent_endpoints_without_runtime_authorization_route() -> None:
    paths=app.openapi()["paths"]
    expected={"/api/v1/internal/agent-auth/token", "/api/v1/internal/agent-auth/me", "/api/v1/companies/{company_id}/agents", "/api/v1/companies/{company_id}/agents/{agent_id}/credentials", "/api/v1/companies/{company_id}/agents/{agent_id}/permissions"}
    assert expected <= set(paths)
    assert not any("authorization/evaluate" in path for path in paths)
