"""Alembic environment. The database URL always comes from DATABASE_URL (same variable the app uses)."""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from sentinel.db import normalize_url
from sentinel.db.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata
URL = normalize_url(os.environ.get("DATABASE_URL") or "sqlite:///./data/sentinel.db")


def run_migrations_offline() -> None:
    context.configure(url=URL, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(URL)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True, render_as_batch=URL.startswith("sqlite"))
        with context.begin_transaction():
            context.run_migrations()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()