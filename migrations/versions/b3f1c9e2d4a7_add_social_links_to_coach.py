"""Add social media links to Coach

Revision ID: b3f1c9e2d4a7
Revises: 49236b465d9c
Create Date: 2026-08-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b3f1c9e2d4a7'
down_revision = '49236b465d9c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('coaches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('instagram', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('facebook',  sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('whatsapp',  sa.String(length=30),  nullable=True))
        batch_op.add_column(sa.Column('tiktok',    sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('coaches', schema=None) as batch_op:
        batch_op.drop_column('tiktok')
        batch_op.drop_column('whatsapp')
        batch_op.drop_column('facebook')
        batch_op.drop_column('instagram')
