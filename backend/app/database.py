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

    # Seed default symbol maps if the table is empty
    if "symbol_maps" in inspector.get_table_names():
        try:
            rows = conn.execute(text("SELECT COUNT(*) FROM symbol_maps")).scalar()
            if rows == 0:
                defaults = [
                    ("USTEC", "MNQ 09-26"),
                    ("NAS100", "MNQ 09-26"),
                    ("US100", "MNQ 09-26"),
                    ("MYM", "MYM 09-26"),
                    ("MES", "MES 09-26"),
                    ("MGC", "MGC 09-26"),
                ]
                for m, n in defaults:
                    conn.execute(
                        text("INSERT OR IGNORE INTO symbol_maps (mt5_symbol, nt8_instrument) VALUES (:m, :n)"),
                        {"m": m, "n": n},
                    )
                conn.commit()
        except:
            pass

    # Seed default_instrument config if missing
    if "config" in inspector.get_table_names():
        try:
            cnt = conn.execute(text("SELECT COUNT(*) FROM config WHERE key = 'default_instrument'")).scalar()
            if cnt == 0:
                conn.execute(text("INSERT INTO config (key, value) VALUES ('default_instrument', 'MNQ 09-26')"))
                conn.commit()
        except:
            pass

    # Migrations for accounts table
    if "accounts" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("accounts")]

        migrations = {
            "tpc": "ALTER TABLE accounts ADD COLUMN tpc FLOAT DEFAULT 1500.0",
            "slc": "ALTER TABLE accounts ADD COLUMN slc FLOAT DEFAULT 2000.0",
            "max_positions": "ALTER TABLE accounts ADD COLUMN max_positions INTEGER DEFAULT 6",
            "round_start_realized": "ALTER TABLE accounts ADD COLUMN round_start_realized FLOAT DEFAULT 0.0",
            "round_baseline_set": "ALTER TABLE accounts ADD COLUMN round_baseline_set INTEGER DEFAULT 0",
            "daily_start_realized": "ALTER TABLE accounts ADD COLUMN daily_start_realized FLOAT DEFAULT 0.0",
            "daily_baseline_set": "ALTER TABLE accounts ADD COLUMN daily_baseline_set INTEGER DEFAULT 0",
            "last_realized": "ALTER TABLE accounts ADD COLUMN last_realized FLOAT DEFAULT 0.0",
            "round_pnl": "ALTER TABLE accounts ADD COLUMN round_pnl FLOAT DEFAULT 0.0",
            "round_num": "ALTER TABLE accounts ADD COLUMN round_num INTEGER DEFAULT 0",
            "tpd": "ALTER TABLE accounts ADD COLUMN tpd FLOAT DEFAULT 0.0",
            "sld": "ALTER TABLE accounts ADD COLUMN sld FLOAT DEFAULT 0.0",
            "tpg": "ALTER TABLE accounts ADD COLUMN tpg FLOAT DEFAULT 0.0",
            "slg": "ALTER TABLE accounts ADD COLUMN slg FLOAT DEFAULT 0.0",
            "total_pnl": "ALTER TABLE accounts ADD COLUMN total_pnl FLOAT DEFAULT 0.0",
            "starting_balance": "ALTER TABLE accounts ADD COLUMN starting_balance FLOAT DEFAULT 0.0",
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
            "default_tpd": "ALTER TABLE groups ADD COLUMN default_tpd FLOAT DEFAULT 0.0",
            "default_sld": "ALTER TABLE groups ADD COLUMN default_sld FLOAT DEFAULT 0.0",
            "default_tpg": "ALTER TABLE groups ADD COLUMN default_tpg FLOAT DEFAULT 0.0",
            "default_slg": "ALTER TABLE groups ADD COLUMN default_slg FLOAT DEFAULT 0.0",
            "preset_id": "ALTER TABLE groups ADD COLUMN preset_id INTEGER",
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

    # Migrations for config_snapshots table
    if "config_snapshots" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("config_snapshots")]
        snap_migrations = {
            "tpd": "ALTER TABLE config_snapshots ADD COLUMN tpd FLOAT DEFAULT 0.0",
            "sld": "ALTER TABLE config_snapshots ADD COLUMN sld FLOAT DEFAULT 0.0",
        }
        for col, sql in snap_migrations.items():
            if col not in cols:
                try:
                    conn.execute(text(sql))
                except:
                    pass

    # Backfill order_index secuencial por grupo (orden real de la cola/rotacion/turnos)
    if "accounts" in inspector.get_table_names() and "groups" in inspector.get_table_names():
        try:
            rows = conn.execute(text("SELECT id, group_id, order_index FROM accounts ORDER BY group_id, id")).fetchall()
            seq: dict = {}
            for rid, gid, oi in rows:
                n = seq.get(gid, 0) + 1
                seq[gid] = n
                if oi != n:
                    conn.execute(text("UPDATE accounts SET order_index = :n WHERE id = :rid"), {"n": n, "rid": rid})
            conn.commit()
        except:
            pass

    # Fleet: permitir un grupo en VARIAS flotas -> quitar UNIQUE simple de group_id
    # y aplicar UNIQUE compuesto (fleet_id, group_id). SQLite no soporta DROP UNIQUE,
    # asi que se reconstruye la tabla copiando los datos.
    if "fleet_groups" in inspector.get_table_names():
        try:
            uniques = [set(ix.get("column_names", [])) for ix in inspector.get_unique_constraints("fleet_groups")]
            if {"fleet_id", "group_id"} not in uniques:
                ac = conn.execution_options(isolation_level="AUTOCOMMIT")
                ac.execute(text("PRAGMA foreign_keys=OFF"))
                ac.execute(text("ALTER TABLE fleet_groups RENAME TO fleet_groups_legacy"))
                ac.execute(text("""
                    CREATE TABLE fleet_groups (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        fleet_id INTEGER NOT NULL,
                        group_id INTEGER NOT NULL,
                        order_index INTEGER DEFAULT 0,
                        CONSTRAINT uq_fleet_groups UNIQUE (fleet_id, group_id),
                        FOREIGN KEY(fleet_id) REFERENCES fleets (id),
                        FOREIGN KEY(group_id) REFERENCES groups (id)
                    )
                """))
                ac.execute(text("INSERT INTO fleet_groups (id, fleet_id, group_id, order_index) SELECT id, fleet_id, group_id, order_index FROM fleet_groups_legacy"))
                ac.execute(text("DROP TABLE fleet_groups_legacy"))
                ac.execute(text("PRAGMA foreign_keys=ON"))
        except Exception:
            try:
                conn.execute(text("PRAGMA foreign_keys=ON"))
            except Exception:
                pass
            pass

    # Presets: garantizar que el id sea AUTOINCREMENT (nunca se reutiliza tras borrar).
    # Si la tabla existe sin AUTOINCREMENT, se reconstruye conservando los datos.
    if "presets" in inspector.get_table_names():
        try:
            sql_row = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='presets'")).scalar()
            if sql_row and "AUTOINCREMENT" not in sql_row.upper():
                conn.commit()  # cerrar la transaccion autobegin antes de cambiar isolation_level
                ac = conn.execution_options(isolation_level="AUTOCOMMIT")
                ac.execute(text("PRAGMA foreign_keys=OFF"))
                ac.execute(text("ALTER TABLE presets RENAME TO presets_legacy"))
                ac.execute(text("""
                    CREATE TABLE presets (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(100) NOT NULL,
                        ct INTEGER DEFAULT 1,
                        max_positions INTEGER DEFAULT 6,
                        tpc FLOAT DEFAULT 1500.0,
                        slc FLOAT DEFAULT 2000.0,
                        pdpt FLOAT DEFAULT 1600.0,
                        pdll FLOAT DEFAULT 2100.0,
                        tpd FLOAT DEFAULT 0.0,
                        sld FLOAT DEFAULT 0.0,
                        tpg FLOAT DEFAULT 0.0,
                        slg FLOAT DEFAULT 0.0,
                        created_at DATETIME
                    )
                """))
                ac.execute(text("""
                    INSERT INTO presets (id, name, ct, max_positions, tpc, slc, pdpt, pdll, tpd, sld, tpg, slg, created_at)
                    SELECT id, name, ct, max_positions, tpc, slc, pdpt, pdll, tpd, sld, tpg, slg, created_at
                    FROM presets_legacy
                """))
                ac.execute(text("DROP TABLE presets_legacy"))
                ac.execute(text("PRAGMA foreign_keys=ON"))
        except Exception:
            try:
                conn.execute(text("PRAGMA foreign_keys=ON"))
            except Exception:
                pass
            pass

    conn.commit()
    conn.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations()

