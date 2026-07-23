from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.provider_execution import ProviderExecution, ProviderExecutionAttempt

class ProviderExecutionRepository:
    def __init__(self, session: Session): self.session = session
    def get(self, company_id: UUID, execution_id: UUID, lock: bool=False):
        q=select(ProviderExecution).where(ProviderExecution.company_id==company_id, ProviderExecution.id==execution_id)
        return self.session.scalar(q.with_for_update() if lock else q)
    def by_key(self, company_id: UUID, key: str): return self.session.scalar(select(ProviderExecution).where(ProviderExecution.company_id==company_id, ProviderExecution.idempotency_key==key))
    def list(self, company_id: UUID, limit: int, offset: int): return list(self.session.scalars(select(ProviderExecution).where(ProviderExecution.company_id==company_id).order_by(ProviderExecution.created_at.desc(), ProviderExecution.id.desc()).limit(limit).offset(offset)).all())
    def count(self, company_id: UUID): return int(self.session.scalar(select(func.count()).select_from(ProviderExecution).where(ProviderExecution.company_id==company_id)) or 0)
    def add(self, item): self.session.add(item); self.session.flush(); self.session.refresh(item); return item
    def add_attempt(self, item): self.session.add(item); self.session.flush(); return item
