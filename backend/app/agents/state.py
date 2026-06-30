from __future__ import annotations

from decimal import Decimal
from typing import Optional, TypedDict


class InvoiceGraphState(TypedDict, total=False):
    file_bytes: bytes
    mime_type: str

    attempt: int
    max_attempts: int

    extracted: Optional[dict]
    error: Optional[str]

    validation_status: Optional[str]
    validation_delta: Optional[Decimal]
    validation_reason: Optional[str]
