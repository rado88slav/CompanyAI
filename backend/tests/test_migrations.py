"""Tests for the Alembic migration configuration."""

from pathlib import Path
import ast

from alembic.config import Config
from alembic.script import ScriptDirectory
import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app.models.approval import ApprovalDecision, ApprovalRequest, AuthorizationPolicy, AuthorizationUsage
from app.models.agent import Agent, AgentCredential, AgentPermission
from app.models.tool_registry import AgentToolGrant, CompanyTool, ToolDefinition
from app.models.provider_connection import ProviderConnection, ProviderCredential

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def create_alembic_config() -> Config:
    """Create an Alembic configuration for file-based validation."""

    return Config(str(BACKEND_ROOT / "alembic.ini"))


def test_migration_history_has_one_head() -> None:
    """The migration graph must never contain multiple heads."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    assert script_directory.get_heads() == [
        "0011_provider_execution"
    ]


def test_initial_migration_is_available() -> None:
    """The initial migration must remain discoverable."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0001_initial"
    )

    assert revision is not None
    assert revision.down_revision is None


def test_company_migration_follows_initial_revision() -> None:
    """The Company migration must follow the baseline."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0002_companies"
    )

    assert revision is not None
    assert revision.down_revision == "0001_initial"


def test_company_settings_migration_follows_company_revision() -> None:
    """Company settings must follow the Company migration."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0003_company_settings"
    )

    assert revision is not None
    assert revision.down_revision == "0002_companies"


def test_administrator_migration_follows_settings_revision() -> None:
    """Administrator storage must follow company settings."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0004_administrators"
    )

    assert revision is not None
    assert revision.down_revision == "0003_company_settings"


def test_audit_log_migration_follows_administrator_revision() -> None:
    """Append-only audit storage must follow administrators."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )
    revision = script_directory.get_revision("0005_audit_logs")
    assert revision is not None
    assert revision.down_revision == "0004_administrators"


def test_membership_migration_follows_audit_revision() -> None:
    """Company membership storage must follow audit logging."""

    script_directory = ScriptDirectory.from_config(create_alembic_config())
    revision = script_directory.get_revision("0006_company_memberships")
    assert revision is not None
    assert revision.down_revision == "0005_audit_logs"


def test_approval_manager_migration_follows_membership_revision() -> None:
    revision = ScriptDirectory.from_config(create_alembic_config()).get_revision("0007_approval_manager")
    assert revision is not None
    assert revision.down_revision == "0006_company_memberships"


def test_agent_identity_migration_follows_approval_manager() -> None:
    revision = ScriptDirectory.from_config(create_alembic_config()).get_revision("0008_agent_identity")
    assert revision is not None and revision.down_revision == "0007_approval_manager"


def test_tool_registry_migration_follows_agent_identity() -> None:
    revision = ScriptDirectory.from_config(create_alembic_config()).get_revision("0009_tool_registry")
    assert revision is not None and revision.down_revision == "0008_agent_identity"


def test_provider_connections_migration_follows_tool_registry() -> None:
    revision = ScriptDirectory.from_config(create_alembic_config()).get_revision("0010_provider_connections")
    assert revision is not None and revision.down_revision == "0009_tool_registry"


def test_provider_connections_migration_static_parity_and_identifier_safety() -> None:
    source = (BACKEND_ROOT / "migrations/versions/0010_create_provider_connections.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not any(module == "app" or module.startswith("app.") for module in imports)
    assert "op.get_bind" not in source and "__table__" not in source
    for model in (ProviderConnection, ProviderCredential):
        for constraint in model.__table__.constraints:
            if constraint.name: assert constraint.name in source
        for index in model.__table__.indexes: assert index.name in source
    names = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value,str) and node.value.startswith(("ck_","fk_","ix_","uq_"))]
    assert names and all(len(name.encode()) <= 63 for name in names)
    assert source.index('op.drop_table("provider_credentials")') < source.index('op.drop_table("provider_connections")')


def test_tool_registry_migration_is_static_complete_and_identifier_safe() -> None:
    source = (BACKEND_ROOT / "migrations/versions/0009_create_tool_registry.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not any(module == "app" or module.startswith("app.") for module in imports)
    assert "op.get_bind" not in source and "__table__" not in source
    for name in {"tool_definitions", "company_tools", "agent_tool_grants", "uq_tool_definitions_key", "uq_company_tools_company_tool", "fk_agent_tool_grants_company_agent", "fk_agent_tool_grants_company_tool", "uq_agent_tool_grants_active"}:
        assert f'"{name}"' in source
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    names.append(keyword.value.value)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "create_index" and isinstance(node.args[0], ast.Constant):
                names.append(node.args[0].value)
    assert names and all(len(name.encode()) <= 63 for name in names)
    assert source.index('op.drop_table("agent_tool_grants")') < source.index('op.drop_table("company_tools")') < source.index('op.drop_table("tool_definitions")')


def test_tool_registry_static_snapshot_matches_orm_constraints() -> None:
    source = (BACKEND_ROOT / "migrations/versions/0009_create_tool_registry.py").read_text(encoding="utf-8")
    for model in (ToolDefinition, CompanyTool, AgentToolGrant):
        for constraint in model.__table__.constraints:
            if constraint.name:
                assert f'"{constraint.name}"' in source
        for index in model.__table__.indexes:
            assert f'"{index.name}"' in source
        assert all(fk.ondelete == "RESTRICT" for fk in model.__table__.foreign_key_constraints)


def test_agent_identity_migration_is_static_complete_and_identifier_safe() -> None:
    migration = BACKEND_ROOT / "migrations/versions/0008_create_agent_identity.py"
    source = migration.read_text(encoding="utf-8"); tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not any(module == "app" or module.startswith("app.") for module in imports)
    assert "op.get_bind" not in source and "__table__" not in source
    for name in {"agents", "agent_credentials", "agent_permissions", "fk_approval_requests_requester_agent", "fk_auth_policies_subject_agent", "fk_auth_usages_actor_agent", "uq_agent_permissions_active_key", "uq_agents_company_slug", "uq_agent_credentials_public_id", "uq_agent_credentials_company_agent_id", "fk_agent_credentials_rotation_lineage"}: assert f'"{name}"' in source
    assert source.count('ondelete="RESTRICT"') == 15
    names=[]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant): names.append(keyword.value.value)
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"create_index", "create_foreign_key"} and node.args and isinstance(node.args[0], ast.Constant): names.append(node.args[0].value)
    assert names and all(len(name.encode()) <= 63 for name in names)
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
    assert '["company_id", "agent_id", "rotated_from_credential_id"], ["agent_credentials.company_id", "agent_credentials.agent_id", "agent_credentials.id"]' in source
    assert source.index('op.drop_constraint("fk_auth_usages_actor_agent"') < source.index('op.drop_table("agents")')
    assert source.index('op.drop_table("agent_credentials")') < source.index('op.drop_table("agents")')


def test_agent_orm_contains_expected_uniqueness_indexes_and_restrict_fks() -> None:
    assert {"agents", "agent_credentials", "agent_permissions"} == {Agent.__tablename__, AgentCredential.__tablename__, AgentPermission.__tablename__}
    for model in (Agent, AgentCredential, AgentPermission):
        assert all(fk.ondelete == "RESTRICT" for fk in model.__table__.foreign_key_constraints)
    assert any(index.name == "uq_agent_permissions_active_key" and index.unique for index in AgentPermission.__table__.indexes)


def test_approval_manager_migration_is_static_and_application_independent() -> None:
    """Historical schema snapshots must never import mutable application models."""

    migration = BACKEND_ROOT / "migrations/versions/0007_create_approval_manager.py"
    source = migration.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(module == "app" or module.startswith("app.") for module in imports)
    assert "__table__" not in source
    assert "op.get_bind" not in source
    assert source.count("op.create_table(") == 4


def test_approval_manager_migration_contains_all_schema_objects() -> None:
    source = (BACKEND_ROOT / "migrations/versions/0007_create_approval_manager.py").read_text(encoding="utf-8")
    tables = {"approval_requests", "approval_decisions", "authorization_policies", "authorization_usages"}
    constraints = {
        "ck_approval_requests_requester_identity", "ck_approval_requests_limits_object",
        "ck_approval_decisions_value", "uq_approval_decisions_request",
        "ck_authorization_policies_scope", "ck_authorization_policies_subject",
        "ck_authorization_policies_effect_mode", "ck_authorization_policies_positive_limits",
        "ck_authorization_policies_budget_currency", "ck_authorization_policies_revocation",
        "ck_authorization_usages_actor", "ck_authorization_usages_lifecycle",
        "ck_authorization_usages_budget_currency", "uq_authorization_usages_reservation_key",
    }
    indexes = {
        "uq_approval_requests_pending_dedup",
        "ix_approval_requests_company_status_created_id",
        "ix_approval_decisions_company_created_id",
        "ix_authorization_policies_company_status_effect_action",
        "ix_authorization_policies_status_validity",
        "uq_authorization_usages_execution",
        "ix_authorization_usages_policy_status_reserved",
        "ix_authorization_usages_company_target",
    }
    for name in tables | constraints | indexes:
        assert f'"{name}"' in source
    assert "postgresql.JSONB()" in source
    assert "sa.Numeric(precision=18, scale=6)" in source
    assert source.count('ondelete="RESTRICT"') == 14
    assert source.count("op.create_index(") == source.count("op.drop_index(") == 24
    assert source.count("op.drop_table(") == 4
    assert "postgresql_where=sa.text(\"status = 'pending'\")" in source
    assert 'postgresql_where=sa.text("execution_id IS NOT NULL")' in source


def test_approval_manager_identifiers_fit_postgresql_and_fk_targets_are_preserved() -> None:
    """Guard PostgreSQL's 63-byte identifier limit and the corrected FK contracts."""

    source = (BACKEND_ROOT / "migrations/versions/0007_create_approval_manager.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    constraint_names_by_table: dict[str, list[str]] = {}
    index_names: list[str] = []
    foreign_keys: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "create_index":
            index_names.append(ast.literal_eval(node.args[0]))
        if node.func.attr != "create_table":
            continue
        table_name = ast.literal_eval(node.args[0])
        table_constraints = constraint_names_by_table.setdefault(table_name, [])
        for element in node.args[1:]:
            if not isinstance(element, ast.Call):
                continue
            keywords = {keyword.arg: keyword.value for keyword in element.keywords}
            if "name" in keywords:
                table_constraints.append(ast.literal_eval(keywords["name"]))
            if isinstance(element.func, ast.Attribute) and element.func.attr == "ForeignKeyConstraint":
                name = ast.literal_eval(keywords["name"])
                foreign_keys[name] = (
                    tuple(ast.literal_eval(element.args[0])),
                    tuple(ast.literal_eval(element.args[1])),
                    ast.literal_eval(keywords["ondelete"]),
                )

    explicit_names = index_names + [name for names in constraint_names_by_table.values() for name in names]
    assert explicit_names
    assert all(len(name.encode("utf-8")) <= 63 for name in explicit_names)
    assert len(index_names) == len(set(index_names))
    assert all(len(names) == len(set(names)) for names in constraint_names_by_table.values())
    assert len(foreign_keys) == 14
    assert foreign_keys["fk_auth_policies_created_by_admin"] == (("created_by_administrator_id",), ("administrators.id",), "RESTRICT")
    assert foreign_keys["fk_auth_policies_revoked_by_admin"] == (("revoked_by_administrator_id",), ("administrators.id",), "RESTRICT")
    assert foreign_keys["fk_auth_policies_source_decision"] == (("source_approval_decision_id",), ("approval_decisions.id",), "RESTRICT")
    assert foreign_keys["fk_auth_policies_source_request"] == (("source_approval_request_id",), ("approval_requests.id",), "RESTRICT")
    assert foreign_keys["fk_auth_policies_subject_admin"] == (("subject_administrator_id",), ("administrators.id",), "RESTRICT")
    assert foreign_keys["fk_auth_usages_policy"] == (("authorization_policy_id",), ("authorization_policies.id",), "RESTRICT")
    assert all(ondelete == "RESTRICT" for _, _, ondelete in foreign_keys.values())


def test_approval_manager_static_snapshot_matches_orm(monkeypatch) -> None:
    """Compare every column, named constraint, foreign key and index without a database."""

    revision = ScriptDirectory.from_config(create_alembic_config()).get_revision("0007_approval_manager")
    assert revision is not None

    class OperationsRecorder:
        def __init__(self) -> None:
            self.metadata = sa.MetaData()
            sa.Table("companies", self.metadata, sa.Column("id", sa.Uuid(), primary_key=True))
            sa.Table("administrators", self.metadata, sa.Column("id", sa.Uuid(), primary_key=True))
            self.tables: dict[str, sa.Table] = {}
            self.indexes: dict[str, tuple[str, tuple[str, ...], dict]] = {}

        def create_table(self, name: str, *elements) -> None:
            self.tables[name] = sa.Table(name, self.metadata, *elements)

        def create_index(self, name: str, table: str, columns: list[str], **kwargs) -> None:
            self.indexes[name] = (table, tuple(columns), kwargs)

    recorder = OperationsRecorder()
    monkeypatch.setattr(revision.module, "op", recorder)
    revision.module.upgrade()

    models = (ApprovalRequest, ApprovalDecision, AuthorizationPolicy, AuthorizationUsage)

    def column_signature(column) -> tuple:
        data_type = column.type
        default = None if column.server_default is None else str(column.server_default.arg)
        return (
            type(data_type).__name__, getattr(data_type, "length", None),
            getattr(data_type, "precision", None), getattr(data_type, "scale", None),
            getattr(data_type, "timezone", None), column.nullable, default,
        )

    for model in models:
        orm_table = model.__table__
        migration_table = recorder.tables[orm_table.name]
        migration_columns = {item.name: item for item in migration_table.columns}
        assert set(migration_columns) == {column.name for column in orm_table.columns}
        for orm_column in orm_table.columns:
            assert column_signature(migration_columns[orm_column.name]) == column_signature(orm_column)

        named_types = (CheckConstraint, UniqueConstraint)
        orm_constraints = {item.name for item in orm_table.constraints if isinstance(item, named_types) and item.name}
        migration_constraints = {item.name for item in migration_table.constraints if isinstance(item, named_types) and item.name}
        assert migration_constraints == orm_constraints

        orm_fks = {
            (
                tuple(item.parent.name for item in constraint.elements),
                tuple(item.target_fullname for item in constraint.elements),
                constraint.ondelete,
            )
            for constraint in orm_table.foreign_key_constraints
            if not any(
                item.target_fullname == "agents.id"
                or item.target_fullname.startswith("provider_executions.")
                for item in constraint.elements
            )
        }
        migration_fks = {(tuple(item.parent.name for item in constraint.elements), tuple(item.target_fullname for item in constraint.elements), constraint.ondelete) for constraint in migration_table.foreign_key_constraints}
        assert migration_fks == orm_fks

        orm_indexes = {index.name: (tuple(column.name for column in index.columns), index.unique, str(index.dialect_options["postgresql"].get("where"))) for index in orm_table.indexes}
        migration_indexes = {name: (columns, bool(kwargs.get("unique", False)), str(kwargs.get("postgresql_where"))) for name, (table, columns, kwargs) in recorder.indexes.items() if table == orm_table.name}
        assert migration_indexes == orm_indexes
