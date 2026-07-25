"""Persistence for the company-isolated email workflow."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.email import EmailReplyProposal, InboundEmail, OutboundEmail


class EmailRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, item):
        self.session.add(item)
        self.session.flush()
        self.session.refresh(item)
        return item

    def inbound_by_external(self, company_id: UUID, external_message_id: str):
        return self.session.scalar(select(InboundEmail).where(InboundEmail.company_id == company_id, InboundEmail.external_message_id == external_message_id))

    def inbound(self, company_id: UUID, email_id: UUID, *, lock: bool = False):
        query = select(InboundEmail).where(InboundEmail.company_id == company_id, InboundEmail.id == email_id)
        return self.session.scalar(query.with_for_update() if lock else query)

    def list_inbound(self, company_id: UUID, limit: int, offset: int):
        return list(self.session.scalars(select(InboundEmail).where(InboundEmail.company_id == company_id).order_by(InboundEmail.received_at.desc(), InboundEmail.id.desc()).limit(limit).offset(offset)).all())

    def count_inbound(self, company_id: UUID) -> int:
        return int(self.session.scalar(select(func.count()).select_from(InboundEmail).where(InboundEmail.company_id == company_id)) or 0)

    def proposal_for_inbound(self, company_id: UUID, inbound_email_id: UUID):
        return self.session.scalar(select(EmailReplyProposal).where(EmailReplyProposal.company_id == company_id, EmailReplyProposal.inbound_email_id == inbound_email_id))

    def proposal(self, company_id: UUID, proposal_id: UUID, *, lock: bool = False):
        query = select(EmailReplyProposal).where(EmailReplyProposal.company_id == company_id, EmailReplyProposal.id == proposal_id)
        return self.session.scalar(query.with_for_update() if lock else query)

    def outbound_for_proposal(self, company_id: UUID, proposal_id: UUID):
        return self.session.scalar(select(OutboundEmail).where(OutboundEmail.company_id == company_id, OutboundEmail.reply_proposal_id == proposal_id))

