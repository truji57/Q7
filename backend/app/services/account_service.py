"""
Q7 Backend - Account & Group Service
"""
from datetime import date
from sqlalchemy.orm import Session, joinedload
from app.models.account import Group, Account, TradeLog, Config


class AccountService:
    def __init__(self, db: Session):
        self.db = db

    # ========== GROUPS ==========

    def get_all_groups(self) -> list[Group]:
        return self.db.query(Group).options(joinedload(Group.accounts)).order_by(Group.id).all()

    def get_group(self, group_id: int) -> Group | None:
        return self.db.query(Group).options(joinedload(Group.accounts)).filter(Group.id == group_id).first()

    def create_group(self, data: dict) -> Group:
        g = Group(**data)
        self.db.add(g)
        self.db.commit()
        self.db.refresh(g)
        return g

    def update_group(self, group_id: int, data: dict) -> Group | None:
        g = self.db.query(Group).filter(Group.id == group_id).first()
        if not g: return None
        for k, v in data.items():
            if v is not None and hasattr(g, k):
                setattr(g, k, v)
        self.db.commit()
        self.db.refresh(g)
        return g

    def delete_group(self, group_id: int) -> bool:
        g = self.db.query(Group).filter(Group.id == group_id).first()
        if not g: return False
        self.db.delete(g)
        self.db.commit()
        return True

    # ========== ACCOUNTS ==========

    def get_accounts(self, group_id: int) -> list[Account]:
        return self.db.query(Account).filter(Account.group_id == group_id).order_by(Account.order_index).all()

    def create_account(self, group_id: int, data: dict) -> Account | None:
        g = self.db.query(Group).filter(Group.id == group_id).first()
        if not g: return None

        defaults = {
            "ct": g.default_ct, "max_positions": g.default_max_positions,
            "tpc": g.default_tpc, "slc": g.default_slc,
            "pdll": g.default_pdll, "pdpt": g.default_pdpt,
        }
        for k, v in defaults.items():
            if k not in data or data[k] is None:
                data[k] = v

        data["group_id"] = group_id
        a = Account(**data)
        self.db.add(a)
        self.db.commit()
        self.db.refresh(a)
        return a

    def update_account(self, account_id: int, data: dict) -> Account | None:
        a = self.db.query(Account).filter(Account.id == account_id).first()
        if not a: return None
        for k, v in data.items():
            if v is not None and hasattr(a, k):
                setattr(a, k, v)
        self.db.commit()
        self.db.refresh(a)
        return a

    def delete_account(self, account_id: int) -> bool:
        a = self.db.query(Account).filter(Account.id == account_id).first()
        if not a: return False
        self.db.delete(a)
        self.db.commit()
        return True

    def reset_daily(self):
        today = date.today()
        accounts = self.db.query(Account).filter(Account.last_reset != today).all()
        for a in accounts:
            a.status = "PENDING"
            a.daily_pnl = 0.0
            a.open_pnl = 0.0
            a.trades_today = 0
            a.symbol = "--"
            a.position = "FLAT"
            a.last_reset = today
        if accounts: self.db.commit()

    # ========== HELPERS ==========

    def to_group_dict(self, g: Group) -> dict:
        self.db.refresh(g)
        return {
            "id": g.id,
            "name": g.name,
            "active": g.active,
            "direction": g.direction,
            "mode": g.mode,
            "stop_on_reset": g.stop_on_reset,
            "include_in_fleet": g.include_in_fleet,
            "schedule_enabled": g.schedule_enabled,
            "schedule_start_h": g.schedule_start_h,
            "schedule_start_m": g.schedule_start_m,
            "schedule_end_h": g.schedule_end_h,
            "schedule_end_m": g.schedule_end_m,
            "default_ct": g.default_ct,
            "default_max_positions": g.default_max_positions,
            "default_tpc": g.default_tpc,
            "default_slc": g.default_slc,
            "default_pdll": g.default_pdll,
            "default_pdpt": g.default_pdpt,
            "accounts": [self.to_account_dict(a) for a in g.accounts],
        }

    def to_account_dict(self, a: Account) -> dict:
        return {
            "id": a.id,
            "group_id": a.group_id,
            "order_index": a.order_index,
            "name": a.name,
            "nt8_account": a.nt8_account,
            "enabled": a.enabled,
            "color": a.color,
            "ct": a.ct,
            "max_positions": a.max_positions,
            "pdll": a.pdll,
            "pdpt": a.pdpt,
            "tpc": a.tpc,
            "slc": a.slc,
            "status": a.status,
            "balance": round(a.balance, 2) if a.balance else 0,
            "daily_pnl": round(a.daily_pnl, 2) if a.daily_pnl else 0,
            "open_pnl": round(a.open_pnl, 2) if a.open_pnl else 0,
            "symbol": a.symbol or "--",
            "position": a.position or "FLAT",
            "trades_today": a.trades_today or 0,
        }

    # ========== CONFIG ==========

    def get_config(self, key: str) -> str | None:
        cfg = self.db.query(Config).filter(Config.key == key).first()
        return cfg.value if cfg else None

    def set_config(self, key: str, value: str):
        cfg = self.db.query(Config).filter(Config.key == key).first()
        if cfg:
            cfg.value = value
        else:
            self.db.add(Config(key=key, value=value))
        self.db.commit()
