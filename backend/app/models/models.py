import uuid
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime,
    ForeignKey, Integer, Numeric, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


# ── Vendor ────────────────────────────────────────────────────────────────────

class Vendor(Base):
    """Fournisseur — connu ou découvert à l'extraction."""
    __tablename__ = "vendors"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name          = Column(String(255), nullable=False, index=True)
    tax_id        = Column(String(100), nullable=True, unique=True)  # MF / SIRET
    address       = Column(Text, nullable=True)
    country       = Column(String(2), nullable=True)                 # ISO-2
    jurisdiction  = Column(String(5), nullable=True)                 # TN / FR
    email         = Column(String(255), nullable=True)
    phone         = Column(String(50), nullable=True)
    is_known      = Column(Boolean, default=True)
    avg_amount    = Column(Numeric(15, 3), nullable=True)            # pour Z-score
    invoice_count = Column(Integer, default=0)
    extra         = Column(JSONB, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    invoices      = relationship("Invoice", back_populates="vendor")


# ── Invoice ───────────────────────────────────────────────────────────────────

class Invoice(Base):
    """Facture — du fichier brut jusqu'au JSON structuré validé."""
    __tablename__ = "invoices"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id         = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True, index=True)

    # Fichier
    original_filename = Column(String(512), nullable=False)
    minio_path        = Column(String(1024), nullable=False)         # bucket/object-key
    file_size_bytes   = Column(BigInteger, nullable=True)
    mime_type         = Column(String(100), nullable=True)

    # OCR
    language          = Column(String(10), default="unknown")        # fr / ar / mixed
    ocr_confidence    = Column(Numeric(5, 2), nullable=True)         # 0–100
    raw_text          = Column(Text, nullable=True)

    # Champs extraits (Agent Parse)
    invoice_number    = Column(String(100), nullable=True, index=True)
    invoice_date      = Column(DateTime(timezone=True), nullable=True)
    due_date          = Column(DateTime(timezone=True), nullable=True)
    currency          = Column(String(10), default="TND")
    amount_ht         = Column(Numeric(15, 3), nullable=True)
    amount_tva        = Column(Numeric(15, 3), nullable=True)
    amount_ttc        = Column(Numeric(15, 3), nullable=True)
    tva_rate          = Column(Numeric(5, 2), nullable=True)
    timbre_fiscal     = Column(Numeric(15, 3), nullable=True)
    jurisdiction      = Column(String(5), default="TN")

    # Validation mathématique (Agent Validation)
    validation_status = Column(String(20), nullable=True)             # ok / mismatch / skipped
    validation_delta   = Column(Numeric(15, 3), nullable=True)        # écart constaté en TTC

    # Statut & trace
    # pending / processing / validated / anomaly / rejected / reconciled
    status            = Column(String(30), default="pending", index=True)
    processing_log    = Column(JSONB, nullable=True)                 # trace des agents
    structured_data   = Column(JSONB, nullable=True)                 # JSON complet

    uploaded_at       = Column(DateTime(timezone=True), server_default=func.now())
    processed_at      = Column(DateTime(timezone=True), nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), onupdate=func.now())

    vendor            = relationship("Vendor", back_populates="invoices")
    line_items        = relationship("LineItem",       back_populates="invoice", cascade="all, delete-orphan")
    reconciliations   = relationship("Reconciliation", back_populates="invoice", cascade="all, delete-orphan")
    anomalies         = relationship("Anomaly",        back_populates="invoice", cascade="all, delete-orphan")


# ── LineItem ──────────────────────────────────────────────────────────────────

class LineItem(Base):
    """Ligne de facture — produit ou prestation."""
    __tablename__ = "line_items"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id   = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True)

    line_number  = Column(Integer, nullable=True)
    description  = Column(Text, nullable=True)
    quantity     = Column(Numeric(10, 3), nullable=True)
    unit_price   = Column(Numeric(15, 3), nullable=True)
    tva_rate     = Column(Numeric(5, 2), nullable=True)
    amount_ht    = Column(Numeric(15, 3), nullable=True)
    amount_ttc   = Column(Numeric(15, 3), nullable=True)

    invoice      = relationship("Invoice", back_populates="line_items")


# ── Reconciliation ────────────────────────────────────────────────────────────

class Reconciliation(Base):
    """Résultat du matching facture ↔ bon de commande / paiement."""
    __tablename__ = "reconciliations"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id          = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True)

    # matched / unmatched / duplicate / partial
    status              = Column(String(20), default="unmatched")
    matched_po_number   = Column(String(100), nullable=True)
    matched_payment_ref = Column(String(100), nullable=True)
    match_score         = Column(Numeric(5, 2), nullable=True)       # fuzzy score 0–100
    matched_at          = Column(DateTime(timezone=True), nullable=True)
    notes               = Column(Text, nullable=True)
    extra               = Column(JSONB, nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())

    invoice             = relationship("Invoice", back_populates="reconciliations")


# ── Anomaly ───────────────────────────────────────────────────────────────────

class Anomaly(Base):
    """Anomalie détectée par l'Agent Anomalies ou l'Agent Validation."""
    __tablename__ = "anomalies"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id     = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True)

    # Types : duplicate_invoice / wrong_vat / math_error /
    #         missing_legal_field / unknown_vendor / abnormal_amount / suspicious_date
    anomaly_type   = Column(String(50), nullable=False, index=True)
    severity       = Column(String(10), default="medium")            # low / medium / high
    description    = Column(Text, nullable=False)
    field_name     = Column(String(100), nullable=True)
    expected_value = Column(String(255), nullable=True)
    actual_value   = Column(String(255), nullable=True)
    is_resolved    = Column(Boolean, default=False)
    resolved_at    = Column(DateTime(timezone=True), nullable=True)
    resolved_by    = Column(String(255), nullable=True)
    extra          = Column(JSONB, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    invoice        = relationship("Invoice", back_populates="anomalies")
