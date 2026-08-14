"""Add is_continuation to bookings

Revision ID: c2d3e4f5a6b7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c2d3e4f5a6b7'
down_revision = 'b3f1c9e2d4a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('bookings') as batch_op:
        batch_op.add_column(sa.Column('is_continuation', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('bookings') as batch_op:
        batch_op.drop_column('is_continuation')
