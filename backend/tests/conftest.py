import pytest

from sentinel.db import make_engine, make_session_factory
from sentinel.db.models import Session


@pytest.fixture()
def db():
    engine = make_engine("sqlite://")
    s = make_session_factory(engine)()
    yield s
    s.close()


@pytest.fixture()
def sess(db):
    s = Session(kind="simulation")
    db.add(s)
    db.flush()
    return s