"""Single-use local first-run bootstrap for CompanyAI Local Edition."""

import sys

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionFactory
from app.models.administrator import Administrator
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.repositories.audit_log import AuditLogRepository
from app.repositories.company import CompanyRepository
from app.repositories.company_membership import CompanyMembershipRepository
from app.schemas.authentication import AdministratorCreate
from app.schemas.company import CompanyCreate
from app.services.audit_log import AuditLogService
from app.core.security import hash_password
from app.models.audit_log import AuditAction


class FirstRunBootstrapInput(BaseModel):
    """Validated first-run setup input."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: str = Field(min_length=2, max_length=200)
    company_slug: str = Field(min_length=2, max_length=100)
    administrator_email: str = Field(min_length=3, max_length=320)
    administrator_full_name: str = Field(min_length=2, max_length=200)
    administrator_password: str = Field(min_length=14, max_length=128)
    language: str = Field(default="en", pattern="^(en|bg|de|fr)$")
    timezone: str = Field(default="UTC", min_length=1, max_length=80)

    @field_validator("administrator_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if (
            not any(char.islower() for char in value)
            or not any(char.isupper() for char in value)
            or not any(char.isdigit() for char in value)
            or not any(not char.isalnum() for char in value)
        ):
            raise ValueError(
                "Password must include lowercase, uppercase, digit and symbol characters."
            )
        return value


def read_input() -> FirstRunBootstrapInput:
    lines = sys.stdin.read().splitlines()
    if len(lines) != 7:
        raise ValueError(
            "Expected company name, company slug, administrator email, administrator full name, password, language and timezone."
        )
    return FirstRunBootstrapInput(
        company_name=lines[0],
        company_slug=lines[1],
        administrator_email=lines[2],
        administrator_full_name=lines[3],
        administrator_password=lines[4],
        language=lines[5],
        timezone=lines[6],
    )


def main() -> int:
    try:
        payload = read_input()
    except (ValueError, ValidationError):
        print(
            "Invalid first-run setup data. Use valid company details, email and a strong password.",
            file=sys.stderr,
        )
        return 2

    with SessionFactory() as session:
        try:
            with session.begin():
                administrator_count = int(
                    session.scalar(select(func.count()).select_from(Administrator)) or 0
                )
                company_count = int(
                    session.scalar(select(func.count()).select_from(Company)) or 0
                )
                membership_count = int(
                    session.scalar(select(func.count()).select_from(CompanyMembership)) or 0
                )
                if administrator_count or company_count or membership_count:
                    print("First-run setup is closed because the installation is already initialized.", file=sys.stderr)
                    return 3

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
                session.add(administrator)
                session.flush()
                session.refresh(administrator)

                companies = CompanyRepository(session)
                memberships = CompanyMembershipRepository(session)
                audit = AuditLogService(AuditLogRepository(session))
                company = companies.create(
                    CompanyCreate(
                        name=payload.company_name,
                        slug=payload.company_slug,
                    )
                )
                membership = memberships.create(
                    company_id=company.id,
                    administrator_id=administrator.id,
                    role="owner",
                )
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
        except IntegrityError:
            print("First-run setup could not complete because a unique record already exists.", file=sys.stderr)
            return 4

    print("First-run setup completed successfully.")
    print(f"Company ID: {company.id}")
    print(f"Company slug: {company.slug}")
    print(f"Administrator ID: {administrator.id}")
    print(f"Administrator email: {administrator.email}")
    print("Password was stored only as a hash and was not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
