from alembic import command
from alembic.config import Config


def upgrade_head(cfg: Config) -> None:
    command.upgrade(cfg, "head")
