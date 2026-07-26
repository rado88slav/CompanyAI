"""Single-use local first-run bootstrap for CompanyAI Local Edition."""

import sys

from pydantic import ValidationError

from app.db.session import SessionFactory
from app.schemas.first_run import FirstRunInitializeRequest
from app.services.first_run import FirstRunAlreadyInitializedError, FirstRunConflictError, FirstRunService


def read_input() -> FirstRunInitializeRequest:
    lines = sys.stdin.read().splitlines()
    if len(lines) != 7:
        raise ValueError(
            "Expected company name, company slug, administrator email, administrator full name, password, language and timezone."
        )
    return FirstRunInitializeRequest(
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
            result = FirstRunService(session).initialize(payload)
        except FirstRunAlreadyInitializedError:
            print("First-run setup is closed because the installation is already initialized.", file=sys.stderr)
            return 3
        except FirstRunConflictError:
            print("First-run setup could not complete because a unique record already exists.", file=sys.stderr)
            return 4

    print("First-run setup completed successfully.")
    print(f"Company ID: {result.company_id}")
    print(f"Company slug: {result.company_slug}")
    print(f"Administrator ID: {result.administrator_id}")
    print(f"Administrator email: {result.administrator_email}")
    print("Password was stored only as a hash and was not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
