"""Schemas for safe first-run setup detection."""

from pydantic import BaseModel


class FirstRunStatusResponse(BaseModel):
    """Public first-run initialization status."""

    initialized: bool
    setup_required: bool
    administrator_count: int
    company_count: int
    bootstrap_method: str
