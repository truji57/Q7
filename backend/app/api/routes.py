"""
Q7 Backend - API Routes (v2: Group-based)
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.account_service import AccountService
from app.services.stats_service import StatsService
from app.models.account import ActivityLog, SymbolMap
from app.schemas.account import (
    GroupCreate, GroupUpdate, GroupSchema,
    AccountCreate, AccountUpdate, AccountSchema,
    DashboardState
)

router = APIRouter(prefix="/api", tags=["api"])


def get_orch():
    from app.main import orchestrator
    return orchestrator


# ========== GROUPS ==========

@router.get("/groups", response_model=list[GroupSchema])
def list_groups(db: Session = Depends(get_db)):
    svc = AccountService(db)
    svc.reset_daily()
    return [svc.to_group_dict(g) for g in svc.get_all_groups()]


@router.post("/groups", response_model=GroupSchema)
def create_group(data: GroupCreate, db: Session = Depends(get_db)):
    svc = AccountService(db)
    g = svc.create_group(data.model_dump())
    return svc.to_group_dict(g)


@router.put("/groups/{group_id}", response_model=GroupSchema)
def update_group(group_id: int, data: GroupUpdate, db: Session = Depends(get_db)):
    svc = AccountService(db)
    g = svc.update_group(group_id, data.model_dump(exclude_none=True))
    if not g:
        raise HTTPException(404, "Group not found")
    return svc.to_group_dict(g)


@router.delete("/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    svc = AccountService(db)
    if not svc.delete_group(group_id):
        raise HTTPException(404, "Group not found")
    return {"ok": True}


@router.post("/groups/{group_id}/activate")
def activate_group(group_id: int, db: Session = Depends(get_db)):
    svc = AccountService(db)
    g = svc.update_group(group_id, {"active": True})
    if not g:
        raise HTTPException(404, "Group not found")
    orch = get_orch()
    if orch:
        orch.activate_group(group_id)
    return {"ok": True}


@router.post("/groups/{group_id}/deactivate")
def deactivate_group(group_id: int, db: Session = Depends(get_db)):
    svc = AccountService(db)
    svc.update_group(group_id, {"active": False})
    return {"ok": True}


@router.post("/groups/{group_id}/reset")
def reset_group(group_id: int, db: Session = Depends(get_db)):
    svc = AccountService(db)
    svc.reset_daily()
    accounts = svc.get_accounts(group_id)
    for a in accounts:
        # NO tocar: balance, starting_balance, total_pnl, daily_pnl, CT, MXP, TPC, SLC, TPxR, SLxR, TPG, SLG
        
        # Re-habilitar todas las cuentas primero
        a.enabled = True

        # Evaluar TPG/SLG y deshabilitar cuenta si corresponde
        total = a.total_pnl or 0
        if a.tpg and a.tpg > 0 and total >= a.tpg:
            a.enabled = False
        if a.slg and a.slg > 0 and total <= -a.slg:
            a.enabled = False

        # Resetear estado de ronda y trading
        a.status = "PENDING"
        a.open_pnl = 0.0
        a.symbol = "--"
        a.position = "FLAT"
        a.trades_today = 0
        a.round_start_realized = a.last_realized  # Baseline de ronda desde PnL actual
        a.round_baseline_set = False
        a.round_pnl = 0.0
        a.round_num = 0
    db.commit()

    # Marcar primera cuenta habilitada como TRADING
    enabled = [a for a in accounts if a.enabled]
    if enabled:
        enabled[0].status = "TRADING"
    db.commit()

    orch = get_orch()
    if orch:
        orch.reset_group_state(group_id)
    return {"ok": True}


# ========== ACCOUNTS ==========

@router.get("/groups/{group_id}/accounts", response_model=list[AccountSchema])
def list_accounts(group_id: int, db: Session = Depends(get_db)):
    svc = AccountService(db)
    return [svc.to_account_dict(a) for a in svc.get_accounts(group_id)]


@router.post("/groups/{group_id}/accounts", response_model=AccountSchema)
def create_account(group_id: int, data: AccountCreate, db: Session = Depends(get_db)):
    svc = AccountService(db)
    a = svc.create_account(group_id, data.model_dump())
    if not a:
        raise HTTPException(404, "Group not found")
    return svc.to_account_dict(a)


@router.put("/accounts/{account_id}", response_model=AccountSchema)
def update_account(account_id: int, data: AccountUpdate, db: Session = Depends(get_db)):
    svc = AccountService(db)
    a = svc.update_account(account_id, data.model_dump(exclude_none=True))
    if not a:
        raise HTTPException(404, "Account not found")
    return svc.to_account_dict(a)


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    svc = AccountService(db)
    if not svc.delete_account(account_id):
        raise HTTPException(404, "Account not found")
    return {"ok": True}


@router.post("/accounts/{account_id}/test")
def test_account(account_id: int, db: Session = Depends(get_db)):
    from app.models.account import Account
    a = db.query(Account).filter(Account.id == account_id).first()
    if not a:
        raise HTTPException(404, "Account not found")
    orch = get_orch()
    if orch:
        return orch.test_account(a.nt8_account)
    return {"ok": False, "error": "Orchestrator not running"}


# ========== DASHBOARD ==========

@router.get("/dashboard", response_model=DashboardState)
def dashboard(db: Session = Depends(get_db)):
    svc = AccountService(db)
    svc.reset_daily()
    return {
        "groups": [svc.to_group_dict(g) for g in svc.get_all_groups()],
    }


# ========== SIGNALS ==========

@router.post("/signal")
async def post_signal(request: Request):
    orch = get_orch()
    if not orch:
        return {"ok": False, "error": "Orchestrator not running"}

    try:
        data = await request.json()
    except:
        return {"ok": False, "error": "Invalid JSON"}

    sig_type = data.get("type", "").upper()

    if sig_type == "HEARTBEAT":
        orch.mt5_connected = True
        orch.last_mt5_hb = __import__("datetime").datetime.now().timestamp()
        return {"ok": True, "heartbeat": True}
    elif sig_type in ("OPEN_LONG", "OPEN_SHORT", "CYCLE_START", "ADD_POSITION"):
        orch._handle_entry(data)
        orch._add_log(f"{sig_type} | {data.get('instrument', '?')}")
    elif sig_type == "CYCLE_END":
        orch._add_log(f"CYCLE_END ignorado (cierre por limites) | {data.get('instrument','?')}")
    else:
        action = data.get("action", "ENTER_LONG")
        result = orch.send_test_trade(action)

    return {"ok": True}


# ========== CONFIG ==========

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    svc = AccountService(db)
    return {
        "bridge_port": svc.get_config("bridge_port") or "5556",
        "debug_mode": svc.get_config("debug_mode") or "false",
        "mt5_terminal_id": svc.get_config("mt5_terminal_id") or "D0E8209F77C8CF37AD8BF550E51FF075",
        "default_instrument": svc.get_config("default_instrument") or "MNQ 09-26",
        "stats_interval_s": svc.get_config("stats_interval_s") or "10",
    }


@router.put("/config")
def update_config(data: dict, db: Session = Depends(get_db)):
    svc = AccountService(db)
    for k, v in data.items():
        svc.set_config(k, str(v))
    # Reload MT5 terminal ID if changed
    if "mt5_terminal_id" in data:
        orch = get_orch()
        if orch:
            orch.reload_mt5_config()
    if "stats_interval_s" in data:
        orch = get_orch()
        if orch:
            orch.reload_stats_config()
    return {"ok": True}


# ========== SYMBOLS MAP ==========

@router.get("/symbols")
def get_symbols(db: Session = Depends(get_db)):
    svc = AccountService(db)
    maps = db.query(SymbolMap).order_by(SymbolMap.id).all()
    return {
        "symbols": [{"id": m.id, "mt5_symbol": m.mt5_symbol, "nt8_instrument": m.nt8_instrument} for m in maps],
        "default_instrument": svc.get_config("default_instrument") or "MNQ 09-26",
    }


@router.put("/symbols")
def update_symbols(data: dict, db: Session = Depends(get_db)):
    svc = AccountService(db)
    symbols = data.get("symbols", [])
    default_instrument = data.get("default_instrument")

    db.query(SymbolMap).delete()
    for s in symbols:
        mt5 = (s.get("mt5_symbol") or "").strip().upper()
        nt8 = (s.get("nt8_instrument") or "").strip()
        if mt5 and nt8:
            db.add(SymbolMap(mt5_symbol=mt5, nt8_instrument=nt8))
    if default_instrument:
        svc.set_config("default_instrument", default_instrument.strip())
    db.commit()
    return {"ok": True}


# ========== VERSION ==========

@router.get("/version")
def get_version():
    import os as _os, json as _json
    cl_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))), "changelog.json")
    if _os.path.exists(cl_path):
        try:
            with open(cl_path, "r") as f:
                entries = _json.load(f)
                if entries:
                    return {"version": entries[0]["version"], "date": entries[0].get("date", "")}
        except:
            pass
    return {"version": "v0.0", "date": ""}


@router.get("/changelog")
def get_changelog():
    import os as _os, json as _json
    cl_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))), "changelog.json")
    if _os.path.exists(cl_path):
        try:
            with open(cl_path, "r") as f:
                return _json.load(f)
        except:
            pass
    return []


# ========== INSTALL ==========

@router.post("/config/install-addon")
def install_addon():
    """Copia Q7AccountManagerAddOn.cs a la carpeta de NT8"""
    import os as _os, shutil as _shutil

    base = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))))
    src = _os.path.join(base, "src", "Q7NinjaTrader", "AddOns", "Q7AccountManagerAddOn.cs")

    if not _os.path.exists(src):
        return {"ok": False, "error": "Source file not found"}

    nt8_addons = _os.path.join(_os.path.expanduser("~"), "Documents", "NinjaTrader 8", "bin", "Custom", "AddOns")
    _os.makedirs(nt8_addons, exist_ok=True)
    dst = _os.path.join(nt8_addons, "Q7AccountManagerAddOn.cs")

    try:
        _shutil.copy2(src, dst)
        return {"ok": True, "message": "Copied to NT8 AddOns folder. Compile with F5."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ========== UPDATE CHECK ==========

@router.get("/check-update")
def check_update():
    import os as _os, json as _json, urllib.request as _req

    # Get local version
    local = "v0.0"
    cl_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))), "changelog.json")
    if _os.path.exists(cl_path):
        try:
            with open(cl_path, "r") as f:
                entries = _json.load(f)
                if entries:
                    local = entries[0].get("version", "v0.0")
        except:
            pass

    # Get latest tag from GitHub
    remote = ""
    try:
        url = "https://api.github.com/repos/truji57/Q7/tags?per_page=1"
        req = _req.Request(url, headers={"User-Agent": "Q7/1.0"})
        with _req.urlopen(req, timeout=5) as r:
            tags = _json.loads(r.read())
            if tags:
                remote = tags[0].get("name", "")
    except:
        pass

    has_update = remote and remote != local
    return {"local": local, "remote": remote, "has_update": has_update}


# ========== STATS ==========

@router.get("/stats/accounts")
def stats_accounts(from_dt: datetime | None = Query(None, alias="from"),
                   to_dt: datetime | None = Query(None, alias="to"),
                   db: Session = Depends(get_db)):
    svc = AccountService(db)
    st = StatsService(db)
    rows = []
    for g in svc.get_all_groups():
        for a in g.accounts:
            m = st.account_summary(a.id, from_dt, to_dt)
            m.update({
                "account_id": a.id,
                "name": a.name,
                "nt8_account": a.nt8_account,
                "group_id": a.group_id,
                "group_name": g.name,
                "color": a.color,
                "balance": round(a.balance or 0, 2),
                "total_pnl": round(a.total_pnl or 0, 2),
                "status": a.status,
                "enabled": a.enabled,
            })
            rows.append(m)
    return rows


@router.get("/stats/accounts/{account_id}")
def stats_account_detail(account_id: int,
                         from_dt: datetime | None = Query(None, alias="from"),
                         to_dt: datetime | None = Query(None, alias="to"),
                         db: Session = Depends(get_db)):
    from app.models.account import Account
    a = db.query(Account).filter(Account.id == account_id).first()
    if not a:
        raise HTTPException(404, "Account not found")
    st = StatsService(db)
    m = st.account_summary(a.id, from_dt, to_dt)
    m.update({
        "account_id": a.id,
        "name": a.name,
        "nt8_account": a.nt8_account,
        "group_id": a.group_id,
        "color": a.color,
        "status": a.status,
        "balance": round(a.balance or 0, 2),
        "total_pnl": round(a.total_pnl or 0, 2),
        "equity": st.account_equity(a.id, from_dt, to_dt, bucket=300),
        "breakdowns": st.account_breakdowns(a.id, from_dt, to_dt),
        "trades": st.account_trades(a.id, from_dt, to_dt, limit=200),
    })
    return m


@router.get("/stats/accounts/{account_id}/equity")
def stats_account_equity(account_id: int,
                         bucket: int = 300,
                         from_dt: datetime | None = Query(None, alias="from"),
                         to_dt: datetime | None = Query(None, alias="to"),
                         db: Session = Depends(get_db)):
    st = StatsService(db)
    return {"points": st.account_equity(account_id, from_dt, to_dt, bucket=bucket)}


@router.get("/stats/groups/{group_id}")
def stats_group(group_id: int,
                from_dt: datetime | None = Query(None, alias="from"),
                to_dt: datetime | None = Query(None, alias="to"),
                db: Session = Depends(get_db)):
    from app.models.account import Group, Account, TradeClose
    g = db.query(Group).filter(Group.id == group_id).first()
    if not g:
        raise HTTPException(404, "Group not found")
    st = StatsService(db)
    accounts = db.query(Account).filter(Account.group_id == group_id).all()
    rows = []
    team_net, team_trades = 0.0, 0
    for a in accounts:
        m = st.account_summary(a.id, from_dt, to_dt)
        m.update({"account_id": a.id, "name": a.name, "color": a.color,
                  "balance": round(a.balance or 0, 2), "total_pnl": round(a.total_pnl or 0, 2),
                  "status": a.status, "enabled": a.enabled})
        rows.append(m)
        team_net += m["net_pnl"]
        team_trades += m["n"]
    rows.sort(key=lambda r: -abs(r["net_pnl"]))
    # Max DD de equipo: curva de pnl acumulado combinando los CIERRES de todas
    # las cuentas (ordenados por hora). Refleja la perdida realizada real.
    closes = db.query(TradeClose).filter(TradeClose.group_id == group_id)
    if from_dt: closes = closes.filter(TradeClose.ts_close >= from_dt)
    if to_dt: closes = closes.filter(TradeClose.ts_close <= to_dt)
    closes = closes.order_by(TradeClose.ts_close).all()
    peak, team_max_dd = 0.0, 0.0
    cum = 0.0
    for c in closes:
        cum += c.pnl or 0
        if cum > peak:
            peak = cum
        team_max_dd = max(team_max_dd, peak - cum)
    return {
        "group_id": g.id,
        "group_name": g.name,
        "accounts": rows,
        "team_net_pnl": round(team_net, 2),
        "team_trades": team_trades,
        "team_max_dd": round(team_max_dd, 2),
    }


@router.get("/stats/presets")
def stats_presets(from_dt: datetime | None = Query(None, alias="from"),
                  to_dt: datetime | None = Query(None, alias="to"),
                  db: Session = Depends(get_db)):
    st = StatsService(db)
    return st.preset_summary(from_dt, to_dt)


# ========== ACTIVITY LOG ==========

@router.get("/activity")
def get_activity(limit: int = 100, db: Session = Depends(get_db)):
    entries = db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(limit).all()
    return [{"id": e.id, "timestamp": e.timestamp.isoformat() if e.timestamp else "",
             "category": e.category or "INFO", "message": e.message or "",
             "account": e.account or "", "group_id": e.group_id} for e in entries]
