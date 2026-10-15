from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base


def normalize_url(url: str) -> str:
    """Hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str) -> Engine:
    url = normalize_url(url)
    kwargs: dict = {}
    if url.startswith("postgresql"):
        kwargs.update(pool_pre_ping=True, pool_recycle=300, pool_size=5, max_overflow=5)   # free hosts drop idle connections
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        else:
            Path(url.split("///", 1)[-1]).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, future=True, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _):  # WAL: readers never block the single writer; busy_timeout absorbs short write contention
            cur = dbapi_conn.cursor()
            if url not in ("sqlite://", "sqlite:///:memory:"):
                cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=15000")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    if url.startswith("sqlite"):          # local/dev/tests; Postgres schemas are managed by `alembic upgrade head`
        Base.metadata.create_all(engine)
    return engine


def make_session_factory(engine: Engine):
    return sessionmaker(engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory):
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
