"""Explicitly bootstrap one company's initial owner membership."""

import argparse
from uuid import UUID

from app.db.session import SessionFactory
from app.repositories.administrator import AdministratorRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.company import CompanyRepository
from app.repositories.company_membership import CompanyMembershipRepository
from app.services.audit_log import AuditLogService
from app.services.company_membership import CompanyMembershipService, CompanyRole


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-id", required=True, type=UUID)
    parser.add_argument("--administrator-id", required=True, type=UUID)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionFactory() as session:
        companies = CompanyRepository(session)
        administrators = AdministratorRepository(session)
        memberships = CompanyMembershipRepository(session)
        company = companies.get_by_id(args.company_id)
        administrator = administrators.get_by_id(args.administrator_id)
        if company is None or administrator is None:
            print("Company or administrator was not found.")
            return 2
        existing = memberships.get_for_administrator(company_id=args.company_id, administrator_id=args.administrator_id)
        if existing is not None:
            if existing.role == CompanyRole.OWNER.value and existing.is_active:
                print("Active owner membership already exists; no change made.")
                return 0
            print("An existing membership will not be altered.")
            return 3
        service = CompanyMembershipService(memberships, companies, administrators, AuditLogService(AuditLogRepository(session)), session)
        service.create_membership(company_id=args.company_id, administrator_id=args.administrator_id, role=CompanyRole.OWNER.value, actor=administrator, actor_membership=None)
    print("Active owner membership created successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
