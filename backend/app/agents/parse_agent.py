"""
Agent Parse — extrait les données structurées d'une facture.
S'appuie sur le pipeline OCR + Groq (+ fallback Gemini Vision) déjà construit en S2.
Relance automatiquement jusqu'à max_attempts en cas d'échec (erreur réseau, JSON invalide, etc.).
"""
from __future__ import annotations

import logging

from app.agents.state import InvoiceGraphState
from app.services.extraction import extract_invoice

logger = logging.getLogger(__name__)


def parse_node(state: InvoiceGraphState) -> InvoiceGraphState:
    attempt = state.get("attempt", 0) + 1

    try:
        data = extract_invoice(state["file_bytes"], state["mime_type"])
        logger.info("Agent Parse réussi (tentative %d), méthode=%s", attempt, data.get("_ocr_method"))
        return {**state, "attempt": attempt, "extracted": data, "error": None}
    except Exception as exc:
        logger.warning("Agent Parse échoué (tentative %d/%d) : %s",
                        attempt, state.get("max_attempts", 2), exc)
        return {**state, "attempt": attempt, "extracted": None, "error": str(exc)}


def route_after_parse(state: InvoiceGraphState) -> str:
    if state.get("extracted") is not None:
        return "validate"
    if state.get("attempt", 0) < state.get("max_attempts", 2):
        return "retry"
    return "fail"
