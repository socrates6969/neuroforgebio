"""Run Alembic migrations programmatically (tests, ops scripts). CLI: `alembic -c
services/platform/alembic.ini`."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS = Path(__file__).parent / "migrations"


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    # ConfigParser interpolation: escape % in URLs (percent-encoded passwords).
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade(url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(url), revision)


def downgrade(url: str, revision: str = "base") -> None:
    command.downgrade(alembic_config(url), revision)
