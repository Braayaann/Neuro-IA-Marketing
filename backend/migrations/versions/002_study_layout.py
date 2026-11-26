"""Conserva el número de columnas usado durante la exhibición."""
from alembic import op
import sqlalchemy as sa

revision = '002_study_layout'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('studies', sa.Column('layout_columns', sa.Integer()))
    op.execute("""
        UPDATE studies SET layout_columns = CASE
            WHEN (SELECT count(*) FROM study_ads WHERE study_id = studies.id) <= 1 THEN 1
            ELSE 2 END
    """)


def downgrade():
    op.drop_column('studies', 'layout_columns')
