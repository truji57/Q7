"""
Q7 Backend - Pydantic Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AccountSchema(BaseModel):
    id: int
    group_id: int
    order_index: int
    name: str
    nt8_account: str
    enabled: bool
    color: str
    ct: int
    max_positions: int = 6
    pdll: float
    pdpt: float
    tpd: float = 0.0
    sld: float = 0.0
    tpg: float = 0.0
    slg: float = 0.0
    tpc: float
    slc: float
    status: str
    balance: float
    starting_balance: float = 0.0
    daily_pnl: float
    total_pnl: float = 0.0
    round_pnl: float = 0.0
    round_num: int = 0
    open_pnl: float
    symbol: str
    position: str
    trades_today: int

    class Config:
        from_attributes = True


class AccountCreate(BaseModel):
    name: str
    nt8_account: str
    ct: Optional[int] = None
    max_positions: Optional[int] = None
    pdll: Optional[float] = None
    pdpt: Optional[float] = None
    tpd: Optional[float] = None
    sld: Optional[float] = None
    tpg: Optional[float] = None
    slg: Optional[float] = None
    tpc: Optional[float] = None
    slc: Optional[float] = None
    enabled: bool = True
    color: str = "#4f8cff"


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    nt8_account: Optional[str] = None
    ct: Optional[int] = None
    max_positions: Optional[int] = None
    pdll: Optional[float] = None
    pdpt: Optional[float] = None
    tpd: Optional[float] = None
    sld: Optional[float] = None
    tpg: Optional[float] = None
    slg: Optional[float] = None
    tpc: Optional[float] = None
    slc: Optional[float] = None
    enabled: Optional[bool] = None
    color: Optional[str] = None
    order_index: Optional[int] = None
    starting_balance: Optional[float] = None


class GroupSchema(BaseModel):
    id: int
    name: str
    active: bool
    direction: str
    mode: str
    stop_on_reset: bool
    reset_mode: str = "diario"
    include_in_fleet: bool
    schedule_enabled: bool
    schedule_start_h: int
    schedule_start_m: int
    schedule_end_h: int
    schedule_end_m: int
    default_ct: int
    default_max_positions: int = 6
    default_tpc: float
    default_slc: float
    default_pdll: float
    default_pdpt: float
    default_tpd: float = 0.0
    default_sld: float = 0.0
    default_tpg: float = 0.0
    default_slg: float = 0.0
    accounts: List[AccountSchema] = []

    class Config:
        from_attributes = True


class GroupCreate(BaseModel):
    name: str
    direction: str = "BOTH"
    mode: str = "SEQUENTIAL"
    stop_on_reset: bool = True
    reset_mode: str = "diario"


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    direction: Optional[str] = None
    mode: Optional[str] = None
    stop_on_reset: Optional[bool] = None
    reset_mode: Optional[str] = None
    include_in_fleet: Optional[bool] = None
    schedule_enabled: Optional[bool] = None
    schedule_start_h: Optional[int] = None
    schedule_start_m: Optional[int] = None
    schedule_end_h: Optional[int] = None
    schedule_end_m: Optional[int] = None
    default_ct: Optional[int] = None
    default_max_positions: Optional[int] = None
    default_tpc: Optional[float] = None
    default_slc: Optional[float] = None
    default_pdll: Optional[float] = None
    default_pdpt: Optional[float] = None
    default_tpd: Optional[float] = None
    default_sld: Optional[float] = None
    default_tpg: Optional[float] = None
    default_slg: Optional[float] = None


class FleetSchema(BaseModel):
    id: int
    name: str
    mode: str = "paralelo"
    active: bool
    color: str
    schedule_enabled: bool
    schedule_start_h: int
    schedule_start_m: int
    schedule_end_h: int
    schedule_end_m: int
    groups: List[GroupSchema] = []

    class Config:
        from_attributes = True


class FleetCreate(BaseModel):
    name: str
    mode: str = "paralelo"
    color: str = "#4f8cff"


class FleetUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[str] = None
    active: Optional[bool] = None
    color: Optional[str] = None
    schedule_enabled: Optional[bool] = None
    schedule_start_h: Optional[int] = None
    schedule_start_m: Optional[int] = None
    schedule_end_h: Optional[int] = None
    schedule_end_m: Optional[int] = None


class DashboardState(BaseModel):
    groups: List[GroupSchema]
    fleets: List[FleetSchema] = []
    timestamp: str
    nt8_connected: bool = False
    engine_active: bool = False
    mt5_connected: bool = False
    last_signal_time: str = ""
    signal_log: List[str] = []
    nt8_accounts: List[dict] = []


class SymbolMapSchema(BaseModel):
    id: int
    mt5_symbol: str
    nt8_instrument: str

    class Config:
        from_attributes = True


class SymbolMapUpdate(BaseModel):
    symbols: List[dict] = []
    default_instrument: Optional[str] = None
