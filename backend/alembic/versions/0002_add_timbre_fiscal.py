"""add timbre_fiscal and validation fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("timbre_fiscal", sa.Numeric(15, 3), nullable=True))
    op.add_column("invoices", sa.Column("validation_status", sa.String(20), nullable=True))
    op.add_column("invoices", sa.Column("validation_delta", sa.Numeric(15, 3), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "validation_delta")
    op.drop_column("invoices", "validation_status")
    op.drop_column("invoices", "timbre_fiscal")
