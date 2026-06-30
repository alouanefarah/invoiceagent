"""
Agent Validation — vérifie la cohérence mathématique des montants extraits.
S'appuie sur services/validation.py construit en S2 (HT + TVA + Timbre ≈ TTC).
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from app.agents.state import InvoiceGraphState
from app.services.validation import validate_amounts

logger = logging.getLogger(__name__)


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def validation_node(state: InvoiceGraphState) -> InvoiceGraphState:
    data = state.get("extracted") or {}

    result = validate_amounts(
        amount_ht=_to_decimal(data.get("amount_ht")),
        amount_tva=_to_decimal(data.get("amount_tva")),
        amount_ttc=_to_decimal(data.get("amount_ttc")),
        timbre_fiscal=_to_decimal(data.get("timbre_fiscal")),
    )
    logger.info("Agent Validation : status=%s delta=%s", result.status, result.delta)

    return {
        **state,
        "validation_status": result.status,
        "validation_delta": result.delta,
        "validation_reason": result.reason,
    }
