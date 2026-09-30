"""
Q7 Backend - Account & Group Service
"""
from datetime import date
from sqlalchemy.orm import Session, joinedload
from app.models.account import Group, Account, TradeLog, Config, Fleet, FleetGroup, Preset

# Parametros de trading que un preset define y que se aplican a las cuentas.
PARAM_FIELDS = ["ct", "max_positions", "tpc", "slc", "pdpt", "pdll", "tpd", "sld", "tpg", "slg"]


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

        params_changed = False
        for k, v in data.items():
            if v is None:
                continue
            if k == "preset_id":
                g.preset_id = v or None
                params_changed = True
                continue
            if hasattr(g, k):
                setattr(g, k, v)
                if k.startswith("default_"):
                    params_changed = True

        self.db.commit()
        self.db.refresh(g)

        if params_changed:
            self._propagate_group_params(g)
        return g

    def _group_effective_params(self, group: Group) -> dict:
        """Parametros efectivos de un grupo: los del preset asignado (si hay) o los manuales."""
        if group.preset_id:
            preset = self.db.query(Preset).filter(Preset.id == group.preset_id).first()
            if preset:
                return {f: getattr(preset, f) for f in PARAM_FIELDS}
        return {
            "ct": group.default_ct,
            "max_positions": group.default_max_positions,
            "tpc": group.default_tpc,
            "slc": group.default_slc,
            "pdpt": group.default_pdpt,
            "pdll": group.default_pdll,
            "tpd": group.default_tpd,
            "sld": group.default_sld,
            "tpg": group.default_tpg,
            "slg": group.default_slg,
        }

    def _propagate_group_params(self, group: Group):
        """Aplica los parametros efectivos del grupo a TODAS sus cuentas."""
        eff = self._group_effective_params(group)
        for a in group.accounts:
            for f, v in eff.items():
                setattr(a, f, v)
        self.db.commit()

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

        # Si el nombre llega vacio, usar el nombre de la cuenta NT8
        if not (data.get("name") or "").strip():
            data["name"] = (data.get("nt8_account") or "").strip() or "?"

        # Orden de la cola/turnos: siguiente indice del grupo
        last = (self.db.query(Account)
                .filter(Account.group_id == group_id)
                .order_by(Account.order_index.desc(), Account.id.desc()).first())
        data.setdefault("order_index", (last.order_index if last else 0) + 1)

        defaults = self._group_effective_params(g)
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

    def reorder_accounts(self, group_id: int, account_ids: list):
        accounts = self.db.query(Account).filter(Account.group_id == group_id).all()
        order = {aid: i for i, aid in enumerate(account_ids)}
        for a in accounts:
            if a.id in order:
                a.order_index = order[a.id]
        self.db.commit()

    def reset_daily(self):
        today = date.today()
        accounts = self.db.query(Account).filter(Account.last_reset != today).all()
        for a in accounts:
            # Pausa diaria (TPD/SLD): al nuevo dia el PNL DIA vuelve a 0 -> reactivar.
            # No reactiva desactivaciones manuales ni TPG/SLG (esos no tienen status TP_DIA/SL_DIA).
            if a.status in ("TP_DIA", "SL_DIA"):
                a.enabled = True
            a.status = "PENDING"
            a.daily_pnl = 0.0
            a.open_pnl = 0.0
            a.trades_today = 0
            a.symbol = "--"
            a.position = "FLAT"
            a.daily_start_realized = 0.0  # Se fijara en el primer sync
            a.daily_baseline_set = False
            a.round_start_realized = 0.0  # Reset ronda
            a.round_baseline_set = False
            a.round_pnl = 0.0
            a.round_num = 0
            a.last_reset = today
        if accounts: self.db.commit()

    # ========== HELPERS ==========

    def to_group_dict(self, g: Group) -> dict:
        self.db.refresh(g)
        eff = self._group_effective_params(g)
        preset_name = g.preset.name if g.preset else None
        return {
            "id": g.id,
            "name": g.name,
            "active": g.active,
            "direction": g.direction,
            "mode": g.mode,
            "stop_on_reset": g.stop_on_reset,
            "reset_mode": g.reset_mode or "diario",
            "include_in_fleet": g.include_in_fleet,
            "preset_id": g.preset_id,
            "preset_name": preset_name,
            "params": eff,
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
            "default_tpd": g.default_tpd or 0,
            "default_sld": g.default_sld or 0,
            "default_tpg": g.default_tpg or 0,
            "default_slg": g.default_slg or 0,
            "accounts": [self.to_account_dict(a) for a in sorted(g.accounts, key=lambda a: (a.order_index or 0, a.id))],
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
            "tpd": a.tpd or 0,
            "sld": a.sld or 0,
            "tpg": a.tpg or 0,
            "slg": a.slg or 0,
            "tpc": a.tpc,
            "slc": a.slc,
            "status": a.status,
            "balance": round(a.balance, 2) if a.balance else 0,
            "starting_balance": a.starting_balance or 0,
            "daily_pnl": round(a.daily_pnl, 2) if a.daily_pnl else 0,
            "total_pnl": round(a.total_pnl, 2) if a.total_pnl else 0,
            "round_pnl": round(a.round_pnl, 2) if a.round_pnl else 0,
            "round_num": a.round_num or 0,
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

    # ========== FLEETS ==========

    def get_all_fleets(self) -> list[Fleet]:
        return (self.db.query(Fleet)
                .options(joinedload(Fleet.members).joinedload(FleetGroup.group))
                .order_by(Fleet.id).all())

    def get_fleet(self, fleet_id: int) -> Fleet | None:
        return (self.db.query(Fleet)
                .options(joinedload(Fleet.members).joinedload(FleetGroup.group))
                .filter(Fleet.id == fleet_id).first())

    def create_fleet(self, data: dict) -> Fleet:
        f = Fleet(**data)
        self.db.add(f)
        self.db.commit()
        self.db.refresh(f)
        return f

    def update_fleet(self, fleet_id: int, data: dict) -> Fleet | None:
        f = self.db.query(Fleet).filter(Fleet.id == fleet_id).first()
        if not f: return None
        for k, v in data.items():
            if v is not None and hasattr(f, k):
                setattr(f, k, v)
        self.db.commit()
        self.db.refresh(f)
        return f

    def delete_fleet(self, fleet_id: int) -> bool:
        f = self.db.query(Fleet).filter(Fleet.id == fleet_id).first()
        if not f: return False
        self.db.delete(f)
        self.db.commit()
        return True

    def add_group_to_fleet(self, fleet_id: int, group_id: int) -> str | None:
        """Devuelve None si ok (o el grupo ya estaba en ESTA flota), o un mensaje de error.
        Un grupo puede estar en varias flotas; solo no puede repetirse dentro de la misma."""
        fleet = self.db.query(Fleet).filter(Fleet.id == fleet_id).first()
        if not fleet: return "Flota no encontrada"
        g = self.db.query(Group).filter(Group.id == group_id).first()
        if not g: return "Grupo no encontrado"
        exists = (self.db.query(FleetGroup)
                  .filter(FleetGroup.fleet_id == fleet_id, FleetGroup.group_id == group_id).first())
        if exists:
            return None  # ya estaba en esta flota
        order = self.db.query(FleetGroup).filter(FleetGroup.fleet_id == fleet_id).count()
        self.db.add(FleetGroup(fleet_id=fleet_id, group_id=group_id, order_index=order))
        self.db.commit()
        return None

    def remove_group_from_fleet(self, fleet_id: int, group_id: int) -> bool:
        fg = (self.db.query(FleetGroup)
              .filter(FleetGroup.fleet_id == fleet_id, FleetGroup.group_id == group_id).first())
        if not fg: return False
        self.db.delete(fg)
        self.db.commit()
        return True

    def reorder_fleet(self, fleet_id: int, group_ids: list):
        fgs = self.db.query(FleetGroup).filter(FleetGroup.fleet_id == fleet_id).all()
        order = {gid: i for i, gid in enumerate(group_ids)}
        for fg in fgs:
            if fg.group_id in order:
                fg.order_index = order[fg.group_id]
        self.db.commit()

    def to_fleet_dict(self, f: Fleet) -> dict:
        members = sorted(f.members, key=lambda m: m.order_index)
        return {
            "id": f.id,
            "name": f.name,
            "mode": f.mode or "paralelo",
            "active": f.active,
            "color": f.color or "#4f8cff",
            "schedule_enabled": f.schedule_enabled,
            "schedule_start_h": f.schedule_start_h,
            "schedule_start_m": f.schedule_start_m,
            "schedule_end_h": f.schedule_end_h,
            "schedule_end_m": f.schedule_end_m,
            "groups": [{**self.to_group_dict(m.group), "fleet_order": m.order_index} for m in members],
        }

    # ========== PRESETS ==========

    def get_presets(self) -> list[Preset]:
        return self.db.query(Preset).order_by(Preset.id).all()

    def get_preset(self, preset_id: int) -> Preset | None:
        return self.db.query(Preset).filter(Preset.id == preset_id).first()

    def create_preset(self, data: dict) -> Preset:
        p = Preset(**data)
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p

    def update_preset(self, preset_id: int, data: dict) -> Preset | None:
        p = self.db.query(Preset).filter(Preset.id == preset_id).first()
        if not p:
            return None
        for k, v in data.items():
            if v is not None and hasattr(p, k):
                setattr(p, k, v)
        self.db.commit()
        self.db.refresh(p)
        # Propagar a los grupos que usan este preset
        for g in self.db.query(Group).filter(Group.preset_id == p.id).all():
            self._propagate_group_params(g)
        return p

    def delete_preset(self, preset_id: int) -> bool:
        p = self.db.query(Preset).filter(Preset.id == preset_id).first()
        if not p:
            return False
        # Los grupos que lo usaban vuelven a "Sin preset" (defaults manuales)
        for g in self.db.query(Group).filter(Group.preset_id == preset_id).all():
            g.preset_id = None
            self.db.commit()
            self._propagate_group_params(g)
        self.db.delete(p)
        self.db.commit()
        return True

    def duplicate_preset(self, preset_id: int) -> Preset | None:
        p = self.db.query(Preset).filter(Preset.id == preset_id).first()
        if not p:
            return None
        copy = Preset(
            name=(p.name or "") + " (copia)",
            ct=p.ct, max_positions=p.max_positions,
            tpc=p.tpc, slc=p.slc,
            pdpt=p.pdpt, pdll=p.pdll,
            tpd=p.tpd, sld=p.sld,
            tpg=p.tpg, slg=p.slg,
        )
        self.db.add(copy)
        self.db.commit()
        self.db.refresh(copy)
        return copy

    def to_preset_dict(self, p: Preset) -> dict:
        return {
            "id": p.id,
            "name": p.name,
            "ct": p.ct,
            "max_positions": p.max_positions,
            "tpc": p.tpc,
            "slc": p.slc,
            "pdpt": p.pdpt,
            "pdll": p.pdll,
            "tpd": p.tpd,
            "sld": p.sld,
            "tpg": p.tpg,
            "slg": p.slg,
        }
