"""Permite eliminar el original manteniendo la copia exhibida en cada sesión."""
from alembic import op
import sqlalchemy as sa

revision = '003_delete_ads'
down_revision = '002_study_layout'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('study_ads_ad_id_fkey', 'study_ads', type_='foreignkey')
    op.alter_column('study_ads', 'ad_id', nullable=True)
    op.create_foreign_key('study_ads_ad_id_fkey', 'study_ads', 'ads', ['ad_id'], ['id'], ondelete='SET NULL')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS (SELECT 1 FROM study_ads WHERE ad_id IS NULL)')):
        raise RuntimeError('Hay sesiones con anuncios eliminados que necesitan el esquema nuevo.')
    op.drop_constraint('study_ads_ad_id_fkey', 'study_ads', type_='foreignkey')
    op.alter_column('study_ads', 'ad_id', nullable=False)
    op.create_foreign_key('study_ads_ad_id_fkey', 'study_ads', 'ads', ['ad_id'], ['id'])
