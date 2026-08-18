"""Add discount to court_sessions and activity_sessions

Revision ID: d1e2f3a4b5c6
Revises: c2d3e4f5a6b7
Create Date: 2026-08-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd1e2f3a4b5c6'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('court_sessions') as batch_op:
        batch_op.add_column(sa.Column('discount', sa.Float(), nullable=False, server_default='0'))
    with op.batch_alter_table('activity_sessions') as batch_op:
        batch_op.add_column(sa.Column('discount', sa.Float(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('court_sessions') as batch_op:
        batch_op.drop_column('discount')
    with op.batch_alter_table('activity_sessions') as batch_op:
        batch_op.drop_column('discount')
