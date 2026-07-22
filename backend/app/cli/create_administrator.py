"""Create a local administrator from data received through stdin."""

import sys

from pydantic import ValidationError

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.repositories.administrator import (
    AdministratorRepository,
)
from app.schemas.authentication import AdministratorCreate
from app.services.authentication import (
    AdministratorEmailConflictError,
    AuthenticationService,
)


def read_input() -> AdministratorCreate:
    """Read administrator fields without exposing the password."""

    input_lines = sys.stdin.read().splitlines()

    if len(input_lines) != 4:
        raise ValueError(
            "Expected email, full name, password and superuser flag."
        )

    email, full_name, password, superuser_value = input_lines

    return AdministratorCreate(
        email=email,
        full_name=full_name,
        password=password,
        is_superuser=(
            superuser_value.strip().lower() == "true"
        ),
    )


def main() -> int:
    """Create one administrator and return a process exit code."""

    try:
        administrator_data = read_input()
    except (ValueError, ValidationError):
        print(
            (
                "Invalid administrator data. "
                "Use a valid email, a name of at least two "
                "characters and a password of at least "
                "twelve characters."
            ),
            file=sys.stderr,
        )
        return 2

    with SessionFactory() as session:
        service = AuthenticationService(
            repository=AdministratorRepository(session),
            session=session,
            settings=get_settings(),
        )

        try:
            administrator = service.create_administrator(
                administrator_data
            )
        except AdministratorEmailConflictError:
            print(
                (
                    "An administrator with this email "
                    "already exists."
                ),
                file=sys.stderr,
            )
            return 3

    print("Administrator created successfully.")
    print(f"ID: {administrator.id}")
    print(f"Email: {administrator.email}")
    print(f"Full name: {administrator.full_name}")
    print(f"Superuser: {administrator.is_superuser}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
