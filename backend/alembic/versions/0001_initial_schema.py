"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── vendors ──────────────────────────────────────────────────────────────
    op.create_table(
        "vendors",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True),
        sa.Column("name",          sa.String(255),     nullable=False),
        sa.Column("tax_id",        sa.String(100),     nullable=True,  unique=True),
        sa.Column("address",       sa.Text(),          nullable=True),
        sa.Column("country",       sa.String(2),       nullable=True),
        sa.Column("jurisdiction",  sa.String(5),       nullable=True),
        sa.Column("email",         sa.String(255),     nullable=True),
        sa.Column("phone",         sa.String(50),      nullable=True),
        sa.Column("is_known",      sa.Boolean(),       default=True),
        sa.Column("avg_amount",    sa.Numeric(15, 3),  nullable=True),
        sa.Column("invoice_count", sa.Integer(),       default=0),
        sa.Column("extra",         JSONB,              nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",    sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_vendors_name", "vendors", ["name"])

    # ── invoices ─────────────────────────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id",                UUID(as_uuid=True), primary_key=True),
        sa.Column("vendor_id",         UUID(as_uuid=True), sa.ForeignKey("vendors.id"), nullable=True),
        sa.Column("original_filename", sa.String(512),     nullable=False),
        sa.Column("minio_path",        sa.String(1024),    nullable=False),
        sa.Column("file_size_bytes",   sa.BigInteger(),    nullable=True),
        sa.Column("mime_type",         sa.String(100),     nullable=True),
        sa.Column("language",          sa.String(10),      default="unknown"),
        sa.Column("ocr_confidence",    sa.Numeric(5, 2),   nullable=True),
        sa.Column("raw_text",          sa.Text(),          nullable=True),
        sa.Column("invoice_number",    sa.String(100),     nullable=True),
        sa.Column("invoice_date",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date",          sa.DateTime(timezone=True), nullable=True),
        sa.Column("currency",          sa.String(10),      default="TND"),
        sa.Column("amount_ht",         sa.Numeric(15, 3),  nullable=True),
        sa.Column("amount_tva",        sa.Numeric(15, 3),  nullable=True),
        sa.Column("amount_ttc",        sa.Numeric(15, 3),  nullable=True),
        sa.Column("tva_rate",          sa.Numeric(5, 2),   nullable=True),
        sa.Column("jurisdiction",      sa.String(5),       default="TN"),
        sa.Column("status",            sa.String(30),      default="pending"),
        sa.Column("processing_log",    JSONB,              nullable=True),
        sa.Column("structured_data",   JSONB,              nullable=True),
        sa.Column("uploaded_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",        sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_invoices_vendor_id",      "invoices", ["vendor_id"])
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])
    op.create_index("ix_invoices_status",         "invoices", ["status"])

    # ── line_items ────────────────────────────────────────────────────────────
    op.create_table(
        "line_items",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id",  UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("line_number", sa.Integer(),        nullable=True),
        sa.Column("description", sa.Text(),           nullable=True),
        sa.Column("quantity",    sa.Numeric(10, 3),   nullable=True),
        sa.Column("unit_price",  sa.Numeric(15, 3),   nullable=True),
        sa.Column("tva_rate",    sa.Numeric(5, 2),    nullable=True),
        sa.Column("amount_ht",   sa.Numeric(15, 3),   nullable=True),
        sa.Column("amount_ttc",  sa.Numeric(15, 3),   nullable=True),
    )
    op.create_index("ix_line_items_invoice_id", "line_items", ["invoice_id"])

    # ── reconciliations ───────────────────────────────────────────────────────
    op.create_table(
        "reconciliations",
        sa.Column("id",                  UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id",          UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("status",              sa.String(20),      default="unmatched"),
        sa.Column("matched_po_number",   sa.String(100),     nullable=True),
        sa.Column("matched_payment_ref", sa.String(100),     nullable=True),
        sa.Column("match_score",         sa.Numeric(5, 2),   nullable=True),
        sa.Column("matched_at",          sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes",               sa.Text(),          nullable=True),
        sa.Column("extra",               JSONB,              nullable=True),
        sa.Column("created_at",          sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reconciliations_invoice_id", "reconciliations", ["invoice_id"])

    # ── anomalies ─────────────────────────────────────────────────────────────
    op.create_table(
        "anomalies",
        sa.Column("id",             UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id",     UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("anomaly_type",   sa.String(50),      nullable=False),
        sa.Column("severity",       sa.String(10),      default="medium"),
        sa.Column("description",    sa.Text(),          nullable=False),
        sa.Column("field_name",     sa.String(100),     nullable=True),
        sa.Column("expected_value", sa.String(255),     nullable=True),
        sa.Column("actual_value",   sa.String(255),     nullable=True),
        sa.Column("is_resolved",    sa.Boolean(),       default=False),
        sa.Column("resolved_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by",    sa.String(255),     nullable=True),
        sa.Column("extra",          JSONB,              nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_anomalies_invoice_id",  "anomalies", ["invoice_id"])
    op.create_index("ix_anomalies_anomaly_type","anomalies", ["anomaly_type"])


def downgrade() -> None:
    op.drop_table("anomalies")
    op.drop_table("reconciliations")
    op.drop_table("line_items")
    op.drop_table("invoices")
    op.drop_table("vendors")
