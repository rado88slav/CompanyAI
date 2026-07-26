"""Single-use first-run setup service."""

from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.administrator import Administrator
from app.models.audit_log import AuditAction
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.repositories.audit_log import AuditLogRepository
from app.repositories.company import CompanyRepository
from app.repositories.company_membership import CompanyMembershipRepository
from app.schemas.authentication import AdministratorCreate
from app.schemas.company import CompanyCreate
from app.schemas.first_run import FirstRunInitializeRequest
from app.services.audit_log import AuditLogService

_FIRST_RUN_LOCK_KEY = 470017001


class FirstRunAlreadyInitializedError(Exception):
    """Raised when first-run setup is already closed."""


class FirstRunConflictError(Exception):
    """Raised when setup conflicts with existing unique data."""


@dataclass(frozen=True, slots=True)
class FirstRunResult:
    """Safe first-run initialization result."""

    company_id: str
    company_slug: str
    administrator_id: str
    administrator_email: str


def count_initialization_records(session: Session) -> tuple[int, int, int]:
    """Count records that close first-run setup."""

    administrator_count = int(
        session.scalar(select(func.count()).select_from(Administrator)) or 0
    )
    company_count = int(
        session.scalar(select(func.count()).select_from(Company)) or 0
    )
    membership_count = int(
        session.scalar(select(func.count()).select_from(CompanyMembership)) or 0
    )
    return administrator_count, company_count, membership_count


class FirstRunService:
    """Coordinate first-run setup with a transaction-scoped lock."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def initialize(self, payload: FirstRunInitializeRequest) -> FirstRunResult:
        """Create the first company and owner administrator exactly once."""

        try:
            with self._session.begin():
                self._session.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_key)"),
                    {"lock_key": _FIRST_RUN_LOCK_KEY},
                )
                administrator_count, company_count, membership_count = (
                    count_initialization_records(self._session)
                )
                if administrator_count or company_count or membership_count:
                    raise FirstRunAlreadyInitializedError

                administrator_data = AdministratorCreate(
                    email=payload.administrator_email,
                    full_name=payload.administrator_full_name,
                    password=payload.administrator_password,
                    is_superuser=False,
                )
                administrator = Administrator(
                    email=administrator_data.email,
                    full_name=administrator_data.full_name,
                    password_hash=hash_password(administrator_data.password),
                    is_superuser=False,
                )
                self._session.add(administrator)
                self._session.flush()
                self._session.refresh(administrator)

                company = CompanyRepository(self._session).create(
                    CompanyCreate(
                        name=payload.company_name,
                        slug=payload.company_slug,
                    )
                )
                membership = CompanyMembershipRepository(self._session).create(
                    company_id=company.id,
                    administrator_id=administrator.id,
                    role="owner",
                )
                audit = AuditLogService(AuditLogRepository(self._session))
                audit.append_company_event(
                    company_id=company.id,
                    actor_administrator_id=administrator.id,
                    action=AuditAction.COMPANY_CREATED.value,
                    resource_type="company",
                    resource_id=company.id,
                    details={"name": company.name, "slug": company.slug},
                )
                audit.append_company_event(
                    company_id=company.id,
                    actor_administrator_id=administrator.id,
                    action=AuditAction.COMPANY_MEMBERSHIP_CREATED.value,
                    resource_type="company_membership",
                    resource_id=membership.id,
                    details={
                        "administrator_id": str(administrator.id),
                        "role": "owner",
                        "is_active": True,
                    },
                )
        except IntegrityError as exc:
            raise FirstRunConflictError from exc

        return FirstRunResult(
            company_id=str(company.id),
            company_slug=company.slug,
            administrator_id=str(administrator.id),
            administrator_email=administrator.email,
        )
