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
    stop_on_reset = Column(Boolean, default=True)    # Parar hasta reinicio
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
    tpc = Column(Float, default=1500.0)   # TP por ciclo
    slc = Column(Float, default=2000.0)   # SL por ciclo

    # Estado actual
    status = Column(String(20), default="PENDING")
    balance = Column(Float, default=0.0)
    daily_pnl = Column(Float, default=0.0)
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
