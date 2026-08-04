"""
Q7 Backend - Database
"""
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=False,
    pool_pre_ping=True
)

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.database_url:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_migrations():
    """Add missing columns without deleting data"""
    if "sqlite" not in settings.database_url:
        return

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    conn = engine.connect()

    # Migrations for accounts table
    if "accounts" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("accounts")]

        migrations = {
            "tpc": "ALTER TABLE accounts ADD COLUMN tpc FLOAT DEFAULT 1500.0",
            "slc": "ALTER TABLE accounts ADD COLUMN slc FLOAT DEFAULT 2000.0",
            "max_positions": "ALTER TABLE accounts ADD COLUMN max_positions INTEGER DEFAULT 6",
            "round_start_realized": "ALTER TABLE accounts ADD COLUMN round_start_realized FLOAT DEFAULT 0.0",
            "daily_start_realized": "ALTER TABLE accounts ADD COLUMN daily_start_realized FLOAT DEFAULT 0.0",
            "daily_baseline_set": "ALTER TABLE accounts ADD COLUMN daily_baseline_set INTEGER DEFAULT 0",
            "last_realized": "ALTER TABLE accounts ADD COLUMN last_realized FLOAT DEFAULT 0.0",
            "round_pnl": "ALTER TABLE accounts ADD COLUMN round_pnl FLOAT DEFAULT 0.0",
        }

        # Check if old columns exist (tp/sl) → rename them
        if "tp" in cols and "tpc" not in cols:
            try:
                conn.execute(text(f"ALTER TABLE accounts RENAME COLUMN tp TO tpc"))
            except:
                pass
        if "sl" in cols and "slc" not in cols:
            try:
                conn.execute(text(f"ALTER TABLE accounts RENAME COLUMN sl TO slc"))
            except:
                pass

        # Add missing columns
        for col, sql in migrations.items():
            if col not in cols:
                try:
                    conn.execute(text(sql))
                except:
                    pass

    # Migrations for groups table
    if "groups" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("groups")]

        group_migrations = {
            "default_tpc": "ALTER TABLE groups ADD COLUMN default_tpc FLOAT DEFAULT 1500.0",
            "default_slc": "ALTER TABLE groups ADD COLUMN default_slc FLOAT DEFAULT 2000.0",
            "default_max_positions": "ALTER TABLE groups ADD COLUMN default_max_positions INTEGER DEFAULT 6",
            "reset_mode": "ALTER TABLE groups ADD COLUMN reset_mode TEXT DEFAULT 'diario'",
        }

        # Rename old columns
        if "default_tp" in cols and "default_tpc" not in cols:
            try:
                conn.execute(text(f"ALTER TABLE groups RENAME COLUMN default_tp TO default_tpc"))
            except:
                pass
        if "default_sl" in cols and "default_slc" not in cols:
            try:
                conn.execute(text(f"ALTER TABLE groups RENAME COLUMN default_sl TO default_slc"))
            except:
                pass

        for col, sql in group_migrations.items():
            if col not in cols:
                try:
                    conn.execute(text(sql))
                except:
                    pass

        # Migrate stop_on_reset -> reset_mode (one-time data conversion)
        if "stop_on_reset" in cols and "reset_mode" in [c["name"] for c in inspector.get_columns("groups")]:
            try:
                conn.execute(text(
                    "UPDATE groups SET reset_mode = CASE WHEN stop_on_reset THEN 'manual' ELSE 'diario' END WHERE reset_mode IS NULL OR reset_mode = ''"
                ))
            except:
                pass

    conn.commit()
    conn.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations()

