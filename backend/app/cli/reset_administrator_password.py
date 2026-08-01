"""Interactive local administrator password reset for CompanyAI Local Edition."""

from getpass import getpass

from pydantic import ValidationError

from app.db.session import SessionFactory
from app.repositories.administrator import AdministratorRepository
from app.repositories.audit_log import AuditLogRepository
from app.schemas.authentication import normalize_email
from app.services.audit_log import AuditLogService
from app.services.authentication import (
    AdministratorNotFoundError,
    AdministratorPasswordPolicyError,
    AdministratorPasswordResetService,
)


def _prompt_email() -> str:
    raw_email = input("Administrator email: ")
    try:
        return normalize_email(raw_email)
    except ValueError as exc:
        raise ValueError("Invalid administrator email.") from exc


def _prompt_password_pair() -> str:
    password = getpass("New password: ")
    confirmation = getpass("Confirm new password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match.")
    return password


def main() -> int:
    """Run the interactive reset flow and return a process exit code."""

    print("CompanyAI Local Edition - Reset Administrator Password")
    print("This command updates one existing administrator account.")
    print("It does not create companies, users, provider connections or credentials.")
    print()

    try:
        email = _prompt_email()
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2

    with SessionFactory() as session:
        service = AdministratorPasswordResetService(
            repository=AdministratorRepository(session),
            audit=AuditLogService(AuditLogRepository(session)),
            session=session,
        )

        try:
            administrator = service.get_administrator_by_email(email)
        except (AdministratorNotFoundError, ValidationError):
            print("Error: No administrator with that email exists. No changes were made.")
            return 3

        print()
        print("Selected administrator:")
        print(f"ID: {administrator.id}")
        print(f"Email: {administrator.email}")
        print(f"Full name: {administrator.full_name}")
        print(f"Active: {administrator.is_active}")
        print(f"Platform superuser: {administrator.is_superuser}")
        print()
        confirmation = input("Type the administrator email again to confirm: ")
        try:
            confirmed_email = normalize_email(confirmation)
        except ValueError:
            confirmed_email = ""
        if confirmed_email != administrator.email:
            print("Confirmation did not match. No changes were made.")
            return 4

        password = ""
        try:
            password = _prompt_password_pair()
            result = service.reset_password(
                email=administrator.email,
                new_password=password,
            )
        except AdministratorPasswordPolicyError:
            print(
                "Error: Password must be 14-128 characters and include lowercase, uppercase, digit and symbol characters."
            )
            return 5
        except ValueError as exc:
            print(f"Error: {exc} No changes were made.")
            return 6
        except AdministratorNotFoundError:
            print("Error: Administrator disappeared before update. No changes were made.")
            return 7
        finally:
            password = ""

    print()
    print("Administrator password reset completed.")
    print(f"Administrator ID: {result.administrator.id}")
    print(f"Email: {result.administrator.email}")
    if not result.session_revocation_supported:
        print(
            "Existing administrator access tokens cannot be centrally revoked in this version; they expire automatically."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
