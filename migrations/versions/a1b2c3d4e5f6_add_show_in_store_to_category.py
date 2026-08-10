"""Add show_in_store to Category

Revision ID: a1b2c3d4e5f6
Revises: 49236b465d9c
Create Date: 2026-08-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '49236b465d9c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('show_in_store', sa.Boolean(), nullable=True, server_default=sa.text('1')))


def downgrade():
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_column('show_in_store')
