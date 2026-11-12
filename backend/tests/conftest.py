"""conftest.py — patches the database engine before any app module uses it."""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///./test_temp.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DEBUG"] = "true"
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["FRONTEND_URL"] = "http://localhost:3000"

from app.config import get_settings
get_settings.cache_clear()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import app.database as _db_module

_test_engine = create_engine(
    "sqlite:///./test_temp.db",
    connect_args={"check_same_thread": False},
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

_db_module.engine = _test_engine
_db_module.SessionLocal = _TestSession


def get_test_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


import pytest
from app.main import app as fastapi_app
from app.database import Base

# Import ALL models so Base.metadata knows about every table
import app.models.user       # noqa: F401
import app.models.trip       # noqa: F401
import app.models.chat       # noqa: F401
import app.models.itinerary  # noqa: F401
import app.models.place      # noqa: F401
import app.models.extra      # noqa: F401

fastapi_app.dependency_overrides[_db_module.get_db] = get_test_db


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)
