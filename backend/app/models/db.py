from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# Columns added to already-shipped tables. create_all only creates missing
# *tables*, so anything here must be applied via ALTER on existing databases.
# Additive + nullable only; anything fancier deserves real migration tooling.
_LIGHT_MIGRATIONS: dict[str, dict[str, str]] = {
    "scheme_metrics": {
        "alpha_3y": "FLOAT",
        "beta_3y": "FLOAT",
        "benchmark_code": "VARCHAR",
        "benchmark_name": "VARCHAR",
    },
}


def run_light_migrations() -> None:
    """Idempotently add any missing columns listed above. Call after
    Base.metadata.create_all (fresh tables already have the columns)."""
    with engine.begin() as conn:
        for table, columns in _LIGHT_MIGRATIONS.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if not existing:  # table doesn't exist yet; create_all owns it
                continue
            for name, ddl_type in columns.items():
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}")
