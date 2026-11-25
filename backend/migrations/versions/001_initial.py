"""Esquema inicial PostgreSQL, congelado en schema.sql junto a esta revisión."""
from pathlib import Path
from alembic import op

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    schema = (Path(__file__).with_name('001_schema.sql')).read_text(encoding='utf-8')
    for statement in schema.split(';'):
        if statement.strip():
            op.execute(statement)


def downgrade():
    for table in ('observations', 'calibrations', 'study_ads', 'studies', 'ads', 'users'):
        op.drop_table(table)
