"""Add owner_user_id to sticker_packs table.

Revision ID: add_sticker_pack_owner
Revises: 
Create Date: 2024-12-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_sticker_pack_owner'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add owner_user_id column to sticker_packs
    op.add_column(
        'sticker_packs',
        sa.Column('owner_user_id', sa.BigInteger(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('sticker_packs', 'owner_user_id')
