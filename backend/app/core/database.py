"""Database engine/session. Works with PostgreSQL (primary) and SQLite (local fallback)."""
from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

from sqlalchemy import Numeric, String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import settings


class Base(DeclarativeBase):
    pass


class Money(TypeDecorator):
    """Exact decimal money column.

    PostgreSQL: NUMERIC(18, 2). SQLite has no real decimal type, so values are
    stored as TEXT to avoid binary floating-point rounding.
    """

    impl = Numeric(18, 2)
    cache_ok = True

    def __init__(self, scale: int = 2, precision: int = 18, **_):
        super().__init__()
        self.scale = scale
        self.precision = precision

    def __repr__(self) -> str:  # rendered into Alembic migrations
        return f"Money(scale={self.scale})"

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(40))
        return dialect.type_descriptor(Numeric(self.precision, self.scale))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        d = value if isinstance(value, Decimal) else Decimal(str(value))
        return str(d) if dialect.name == "sqlite" else d

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(str(value))


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):  # enforce foreign keys in SQLite
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        return eng
    # Small pool: free-tier Postgres has tight connection limits.
    return create_engine(url, pool_size=5, max_overflow=2, pool_pre_ping=True, pool_recycle=1800)


engine = _make_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def money_sort(col):
    """Numeric ordering for Money columns (SQLite stores them as TEXT)."""
    from sqlalchemy import Float, cast
    return cast(col, Float) if settings.is_sqlite else col
