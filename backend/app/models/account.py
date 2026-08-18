"""
Q7 Backend - Models: Group + Account
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)

    active = Column(Boolean, default=False)
    direction = Column(String(10), default="BOTH")   # BOTH, LONG, SHORT
    mode = Column(String(20), default="SEQUENTIAL")  # SEQUENTIAL, PARALLEL
    stop_on_reset = Column(Boolean, default=True)    # DEPRECATED -> reset_mode
    reset_mode = Column(String(20), default="diario")  # manual, diario, continuo
    include_in_fleet = Column(Boolean, default=False)

    schedule_enabled = Column(Boolean, default=False)
    schedule_start_h = Column(Integer, default=0)
    schedule_start_m = Column(Integer, default=0)
    schedule_end_h = Column(Integer, default=23)
    schedule_end_m = Column(Integer, default=59)

    # Defaults para cuentas nuevas en este grupo
    default_ct = Column(Integer, default=1)
    default_max_positions = Column(Integer, default=6)
    default_tpc = Column(Float, default=1500.0)
    default_slc = Column(Float, default=2000.0)
    default_pdll = Column(Float, default=2100.0)
    default_pdpt = Column(Float, default=1600.0)
    default_tpg = Column(Float, default=0.0)
    default_slg = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    accounts = relationship("Account", back_populates="group", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    order_index = Column(Integer, default=0)  # Orden dentro del grupo

    name = Column(String(100), nullable=False)
    nt8_account = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True)
    color = Column(String(7), default="#4f8cff")

    ct = Column(Integer, default=1)
    max_positions = Column(Integer, default=6)  # Max posiciones por ciclo
    pdll = Column(Float, default=2100.0)  # Perdida Diaria Limite → rotar cuenta
    pdpt = Column(Float, default=1600.0)  # Profit Diario Target → rotar cuenta
    tpg = Column(Float, default=0.0)  # TP Global (0=sin limite)
    slg = Column(Float, default=0.0)  # SL Global (0=sin limite)
    tpc = Column(Float, default=1500.0)   # TP por ciclo
    slc = Column(Float, default=2000.0)   # SL por ciclo

    round_start_realized = Column(Float, default=0.0)  # Baseline $ para PNL Ronda
    round_baseline_set = Column(Boolean, default=False)  # Si ya se fijo baseline de ronda
    daily_start_realized = Column(Float, default=0.0)  # Baseline $ para PNL Dia
    daily_baseline_set = Column(Boolean, default=False)  # Si ya se fijo baseline diario
    last_realized = Column(Float, default=0.0)  # Ultimo realized de NT8
    round_pnl = Column(Float, default=0.0)  # PNL Ronda calculado
    round_num = Column(Integer, default=0)  # Numero de ronda actual
    starting_balance = Column(Float, default=0.0)  # Balance inicial de la cuenta

    # Estado actual
    status = Column(String(20), default="PENDING")
    balance = Column(Float, default=0.0)
    daily_pnl = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)  # PNL Total acumulado (no se resetea)
    open_pnl = Column(Float, default=0.0)
    symbol = Column(String(20), default="--")
    position = Column(String(20), default="FLAT")
    trades_today = Column(Integer, default=0)

    last_reset = Column(Date, default=date.today)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship("Group", back_populates="accounts")


class TradeLog(Base):
    __tablename__ = "trade_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer)
    account_id = Column(Integer)
    instrument = Column(String(50))
    direction = Column(String(10))
    contracts = Column(Integer)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, default=0.0)
    status = Column(String(20), default="OPEN")
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(500), nullable=False)


class SymbolMap(Base):
    __tablename__ = "symbol_maps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mt5_symbol = Column(String(50), unique=True, nullable=False)      # Simbolo que envia el EA (USTEC, NAS100, ...)
    nt8_instrument = Column(String(100), nullable=False)             # Futuro en NT8 (MNQ 09-26, MES 09-26, ...)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    category = Column(String(20))    # SIGNAL, TRADE, ROTATION, RESET, GLOBAL, CYCLE
    message = Column(String(500))
    account = Column(String(100), nullable=True)
    group_id = Column(Integer, nullable=True)


class EquitySnapshot(Base):
    """Serie temporal balance/equity por cuenta (curva + drawdown)."""
    __tablename__ = "equity_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(Integer, nullable=True, index=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    balance = Column(Float, default=0.0)
    equity = Column(Float, default=0.0)
    daily_pnl = Column(Float, default=0.0)


class TradeClose(Base):
    """Cierre de ciclo (un 'trade'). Origen: limites TPC/SLC/PDPT/PDLL/TPG/SLG o cierre externo."""
    __tablename__ = "trade_closes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(Integer, nullable=True, index=True)
    ts_open = Column(DateTime, nullable=True)
    ts_close = Column(DateTime, default=datetime.utcnow, index=True)
    direction = Column(String(10), default="?")
    instrument = Column(String(50), default="--")
    pnl = Column(Float, default=0.0)
    reason = Column(String(20), default="")   # TPC, SLC, DAILY_TP, DAILY_SL, ROUND_TP, ROUND_SL, TPG, SLG, EXTERNAL
    preset_key = Column(String(40), nullable=True, index=True)


class ConfigSnapshot(Base):
    """Captura del preset (TPC/SLC/TPR/SLR/TPG/SLG/CT/MXP) usado en cada cierre."""
    __tablename__ = "config_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(Integer, nullable=True)
    ts = Column(DateTime, default=datetime.utcnow)
    preset_key = Column(String(40), nullable=True, index=True)
    ct = Column(Integer, default=1)
    max_positions = Column(Integer, default=6)
    tpc = Column(Float, default=1500.0)
    slc = Column(Float, default=2000.0)
    pdpt = Column(Float, default=1600.0)
    pdll = Column(Float, default=2100.0)
    tpg = Column(Float, default=0.0)
    slg = Column(Float, default=0.0)
