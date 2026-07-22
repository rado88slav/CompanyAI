"""Database repository for administrator accounts."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.administrator import Administrator
from app.schemas.authentication import AdministratorCreate


class AdministratorRepository:
    """Persist and retrieve administrator accounts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(
        self,
        administrator_id: UUID,
    ) -> Administrator | None:
        """Return one administrator by UUID."""

        return self._session.get(
            Administrator,
            administrator_id,
        )

    def get_by_email(
        self,
        email: str,
    ) -> Administrator | None:
        """Return one administrator by normalized email."""

        statement = select(Administrator).where(
            Administrator.email == email
        )

        return self._session.scalar(statement)

    def create(
        self,
        administrator_data: AdministratorCreate,
        *,
        password_hash: str,
    ) -> Administrator:
        """Create an administrator without committing."""

        administrator = Administrator(
            email=administrator_data.email,
            full_name=administrator_data.full_name,
            password_hash=password_hash,
            is_superuser=administrator_data.is_superuser,
        )

        self._session.add(administrator)
        self._session.flush()
        self._session.refresh(administrator)

        return administrator

    def record_successful_login(
        self,
        administrator: Administrator,
        *,
        login_time: datetime,
    ) -> Administrator:
        """Update the last successful login timestamp."""

        administrator.last_login_at = login_time

        self._session.flush()
        self._session.refresh(administrator)

        return administrator
