"""
Agent Validation — vérifie la cohérence mathématique d'une facture extraite.
Règle : amount_ht + amount_tva + timbre_fiscal ≈ amount_ttc (tolérance ±0.005 DT, arrondis).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

TOLERANCE = Decimal("0.01")


@dataclass
class ValidationResult:
    status: str          # "ok" | "mismatch" | "skipped"
    delta: Decimal | None
    reason: str | None = None


def validate_amounts(
    amount_ht: Decimal | None,
    amount_tva: Decimal | None,
    amount_ttc: Decimal | None,
    timbre_fiscal: Decimal | None,
) -> ValidationResult:
    if amount_ht is None or amount_tva is None or amount_ttc is None:
        return ValidationResult(status="skipped", delta=None, reason="Montants manquants pour validation")

    timbre = timbre_fiscal or Decimal("0")
    expected_ttc = amount_ht + amount_tva + timbre
    delta = (amount_ttc - expected_ttc).copy_abs()

    if delta <= TOLERANCE:
        return ValidationResult(status="ok", delta=delta)

    return ValidationResult(
        status="mismatch",
        delta=delta,
        reason=f"HT+TVA+Timbre={expected_ttc} ≠ TTC déclaré={amount_ttc} (écart={delta})",
    )
