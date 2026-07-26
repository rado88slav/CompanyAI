"""Company-isolated Provider Connections persistence without transaction ownership."""

from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.provider_connection import ProviderConnection, ProviderCredential


class ProviderConnectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def company(self, company_id: UUID) -> Company | None:
        return self._session.get(Company, company_id)

    def create_connection(self, **values: object) -> ProviderConnection:
        item = ProviderConnection(**values)
        self._session.add(item); self._session.flush(); self._session.refresh(item)
        return item

    def connection(self, *, company_id: UUID, connection_id: UUID, for_update: bool = False) -> ProviderConnection | None:
        statement = select(ProviderConnection).where(ProviderConnection.company_id == company_id, ProviderConnection.id == connection_id)
        if for_update: statement = statement.with_for_update()
        return self._session.scalar(statement)

    def connection_by_slug(self, *, company_id: UUID, slug: str, for_update: bool = False) -> ProviderConnection | None:
        statement = select(ProviderConnection).where(ProviderConnection.company_id == company_id, ProviderConnection.slug == slug)
        if for_update: statement = statement.with_for_update()
        return self._session.scalar(statement)

    def list_connections(self, *, company_id: UUID, limit: int, offset: int) -> list[ProviderConnection]:
        return list(self._session.scalars(select(ProviderConnection).where(ProviderConnection.company_id == company_id).order_by(ProviderConnection.created_at.desc(), ProviderConnection.id.desc()).limit(limit).offset(offset)).all())

    def count_connections(self, *, company_id: UUID) -> int:
        return int(self._session.scalar(select(func.count()).select_from(ProviderConnection).where(ProviderConnection.company_id == company_id)) or 0)

    def save_connection(self, item: ProviderConnection) -> ProviderConnection:
        self._session.flush(); self._session.refresh(item); return item

    def active_credential(self, *, company_id: UUID, connection_id: UUID, for_update: bool = False) -> ProviderCredential | None:
        statement = select(ProviderCredential).where(ProviderCredential.company_id == company_id, ProviderCredential.provider_connection_id == connection_id, ProviderCredential.status == "active")
        if for_update: statement = statement.with_for_update()
        return self._session.scalar(statement)

    def credential(self, *, company_id: UUID, connection_id: UUID, credential_id: UUID, for_update: bool = False) -> ProviderCredential | None:
        statement = select(ProviderCredential).where(ProviderCredential.company_id == company_id, ProviderCredential.provider_connection_id == connection_id, ProviderCredential.id == credential_id)
        if for_update: statement = statement.with_for_update()
        return self._session.scalar(statement)

    def create_credential(self, **values: object) -> ProviderCredential:
        item = ProviderCredential(**values)
        self._session.add(item); self._session.flush(); self._session.refresh(item); return item

    def save_credential(self, item: ProviderCredential) -> ProviderCredential:
        self._session.flush(); self._session.refresh(item); return item

    def list_credentials(self, *, company_id: UUID, connection_id: UUID, limit: int, offset: int) -> list[ProviderCredential]:
        return list(self._session.scalars(select(ProviderCredential).where(ProviderCredential.company_id == company_id, ProviderCredential.provider_connection_id == connection_id).order_by(ProviderCredential.created_at.desc(), ProviderCredential.id.desc()).limit(limit).offset(offset)).all())

    def count_credentials(self, *, company_id: UUID, connection_id: UUID) -> int:
        return int(self._session.scalar(select(func.count()).select_from(ProviderCredential).where(ProviderCredential.company_id == company_id, ProviderCredential.provider_connection_id == connection_id)) or 0)
