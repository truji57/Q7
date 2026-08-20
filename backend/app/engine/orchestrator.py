"""
Q7 Backend - Orchestrator (v2: Group-based, sequential)
"""
import glob
import json
import logging
import os
import re
import threading
from datetime import date, datetime, time

from app.database import SessionLocal
from app.models.account import Account, Group, Config, ActivityLog, SymbolMap
from app.services.account_service import AccountService
from app.services.stats_service import StatsService

log = logging.getLogger("Q7Backend.Orchestrator")


class OrchestratorEngine:
    def __init__(self):
        docs = os.path.join(os.path.expanduser("~"), "Documents", "NinjaTrader 8", "Q7")
        self.signals_path = os.path.join(docs, "signals")
        self.commands_path = os.path.join(docs, "commands")
        self.status_path = os.path.join(docs, "status")

        # MT5 signals path - configurable via Settings
        self._mt5_terminal_id = self._get_config("mt5_terminal_id") or "D0E8209F77C8CF37AD8BF550E51FF075"
        self._update_mt5_path()

        for p in [self.signals_path, self.commands_path, self.status_path, self.mt5_signals_path]:
            os.makedirs(p, exist_ok=True)
        os.makedirs(os.path.join(self.signals_path, "processed"), exist_ok=True)

        self.group_state: dict[int, dict] = {}
        self.last_signal_time: str = ""
        self.signal_log: list[str] = []
        self.mt5_connected: bool = False
        self.last_mt5_hb: float = 0
        self._last_close_time: dict[str, float] = {}
        self._cycle_start_realized: dict[str, float] = {}
        self._cycle_start_ts: dict[str, datetime] = {}
        self._cycle_adds: dict[str, int] = {}
        self._last_snapshot_ts: dict[str, float] = {}
        self._stats_interval = self._get_stats_interval()
        self._lock = threading.Lock()
        self.ws_broadcast = None

    def set_ws_broadcast(self, fn):
        self.ws_broadcast = fn

    def _get_config(self, key: str) -> str | None:
        db = SessionLocal()
        try:
            cfg = db.query(Config).filter(Config.key == key).first()
            return cfg.value if cfg else None
        finally:
            db.close()

    def _update_mt5_path(self):
        mt5 = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "MetaQuotes",
                           "Terminal", self._mt5_terminal_id, "MQL5", "Files", "Q7", "signals")
        self.mt5_signals_path = mt5

    def reload_mt5_config(self):
        """Recarga la ruta de MT5 cuando el usuario cambia el terminal ID"""
        new_id = self._get_config("mt5_terminal_id") or "D0E8209F77C8CF37AD8BF550E51FF075"
        if new_id != self._mt5_terminal_id:
            self._mt5_terminal_id = new_id
            self._update_mt5_path()
            os.makedirs(self.mt5_signals_path, exist_ok=True)
            log.info(f"MT5 terminal changed to: {new_id}")

    # ===== Stats / Metrica =====

    def _get_stats_interval(self) -> float:
        try:
            return float(self._get_config("stats_interval_s") or 10)
        except:
            return 10.0

    def reload_stats_config(self):
        self._stats_interval = self._get_stats_interval()

    def _record_close(self, db, account: Account, pnl: float, reason: str):
        """Registra un cierre de ciclo (unit de 'trade') + snapshot del preset."""
        try:
            StatsService(db).record_close(
                account, pnl, reason, ts_open=self._cycle_start_ts.get(account.nt8_account)
            )
        except Exception as e:
            log.error(f"Stats record_close error: {e}")

    def _snapshot_equity(self, db, account: Account):
        """Muestrea equity de la cuenta con throttle configurable (stats_interval_s)."""
        try:
            now = datetime.now().timestamp()
            if now - self._last_snapshot_ts.get(account.nt8_account, 0) < self._stats_interval:
                return
            self._last_snapshot_ts[account.nt8_account] = now
            StatsService(db).snapshot(account)
        except Exception as e:
            log.error(f"Stats snapshot error: {e}")

    def reset_group_state(self, group_id: int):
        with self._lock:
            self.group_state.pop(group_id, None)
            log.info(f"Group {group_id} reset")

    def activate_group(self, group_id: int):
        with self._lock:
            db = SessionLocal()
            try:
                svc = AccountService(db)
                svc.reset_daily()
                accounts = svc.get_accounts(group_id)
                enabled = [a for a in accounts if a.enabled]
                if not enabled:
                    log.warning(f"Group {group_id}: no enabled accounts")
                    return

                # Mark first account as TRADING
                enabled[0].status = "TRADING"
                db.commit()

                self.group_state[group_id] = {
                    "active_account_id": enabled[0].id,
                    "processed": [],
                }
                log.info(f"Group {group_id} activated -> account {enabled[0].name} (ACTIVE)")
            finally:
                db.close()
        self._broadcast()

    def send_test_trade(self, action: str = "ENTER_LONG") -> dict:
        """Envia un trade a la primera cuenta PENDING disponible"""
        db = SessionLocal()
        try:
            accounts = db.query(Account).filter(
                Account.enabled == True,
                Account.status == "PENDING"
            ).order_by(Account.order_index).all()

            if not accounts:
                return {"error": "No PENDING accounts. All done or TP/SL reached."}

            account = accounts[0]
            self._write_trade(account.nt8_account, action, "MNQ 09-26", account.ct, 75, 90)

            # Update group state to track this account
            state = self.group_state.get(account.group_id)
            if state:
                state["active_account_id"] = account.id

            return {
                "account": account.nt8_account,
                "group_id": account.group_id,
                "action": "LONG" if "LONG" in action else "SHORT",
                "contracts": account.ct,
                "instrument": "MNQ 09-26"
            }
        finally:
            db.close()

    def poll_signals(self):
        """Lee senales pendientes de signals/ y las procesa"""
        processed_dir = os.path.join(self.signals_path, "processed")
        os.makedirs(processed_dir, exist_ok=True)

        try:
            files = sorted(glob.glob(os.path.join(self.signals_path, "signal_*.json")) +
                           glob.glob(os.path.join(self.signals_path, "manual_*.json")) +
                           glob.glob(os.path.join(self.signals_path, "cyclescale_??????????????_*.json")) +
                           glob.glob(os.path.join(self.mt5_signals_path, "cyclescale_[0-9]*.json")) +
                           glob.glob(os.path.join(self.mt5_signals_path, "cyclescale_catcher_*.json")))
        except:
            return

        for filepath in files:
            try:
                # Small delay to let MT5 finish writing the file
                try:
                    fsize = os.path.getsize(filepath)
                    if fsize < 10:  # Too small, still being written
                        time.sleep(0.3)
                except:
                    pass
                # Try reading with different encodings
                signal = None
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        signal = json.load(f)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    try:
                        with open(filepath, "r", encoding="utf-16") as f:
                            signal = json.load(f)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue

                if signal is None:
                    continue

                # Move FIRST — prevent re-processing if something fails
                dest = os.path.join(processed_dir, os.path.basename(filepath))
                os.replace(filepath, dest)

                sig_type = signal.get("type", "").upper()

                if sig_type in ("OPEN_LONG", "OPEN_SHORT"):
                    signal["direction"] = 1 if sig_type == "OPEN_LONG" else -1
                    instrument = signal.get("instrument", "?")
                    self._handle_entry(signal)
                    self._add_log(f"{sig_type} | {instrument} | vol={signal.get('volume', '?')}",
                                  category="SIGNAL")
                elif sig_type in ("CYCLE_START", "ADD_POSITION"):
                    # Back-compat: la direccion sale SIEMPRE de la senal
                    direction_val = signal.get("direction", 1)
                    direction_str = "LONG" if (direction_val or 1) > 0 else "SHORT"
                    instrument = signal.get("instrument", "?")
                    self._handle_entry(signal)
                    self._add_log(f"{sig_type} {direction_str} | {instrument} | vol={signal.get('volume', '?')}",
                                  category="SIGNAL")
                elif sig_type == "CYCLE_END":
                    # Obsoleto: el cierre lo gestionan SOLO los limites de riesgo (TPC/SLC/PDLL/PDPT/TPG/SLG)
                    self._add_log(f"CYCLE_END ignorado (cierre por limites) | {signal.get('instrument','?')}",
                                  category="SIGNAL")
                elif sig_type == "HEARTBEAT":
                    self.mt5_connected = True
                    self.last_mt5_hb = datetime.now().timestamp()
                else:
                    self.on_signal(signal)
                    self._add_log(f"SIGNAL {signal.get('action','?')}", category="SIGNAL")

                self.last_signal_time = datetime.now().isoformat()
            except Exception as e:
                log.error(f"Signal error: {e}")

    def _group_has_open_positions(self, db, group_id: int) -> bool:
        """True si alguna cuenta del grupo tiene posicion abierta segun el status LIVE del AddOn"""
        try:
            files = sorted(glob.glob(os.path.join(self.status_path, "status_*.json")), reverse=True)
            if not files:
                return False
            with open(files[0], "r", encoding="utf-8") as f:
                status = json.load(f)
            names = {nt8 for (nt8,) in db.query(Account.nt8_account).filter(Account.group_id == group_id).all()}
            for nt8 in status.get("accounts", []):
                if nt8.get("name", "") in names and nt8.get("positions"):
                    return True
            return False
        except:
            return False

    def _account_open_units(self, nt8_account: str, ct: int) -> int:
        """Numero de posiciones abiertas (en unidades de CT) segun el status LIVE del AddOn.
        Suma la cantidad total y la divide entre CT -> robusto ante el merge de posiciones de NT8."""
        try:
            files = sorted(glob.glob(os.path.join(self.status_path, "status_*.json")), reverse=True)
            if not files:
                return 0
            with open(files[0], "r", encoding="utf-8") as f:
                status = json.load(f)
            for nt8 in status.get("accounts", []):
                if nt8.get("name", "") == nt8_account:
                    total_qty = 0.0
                    for p in (nt8.get("positions") or []):
                        try:
                            total_qty += float(p.get("quantity") or 0)
                        except:
                            pass
                    return int(round(total_qty / max(1, ct or 1)))
            return 0
        except:
            return 0

    def _handle_entry(self, signal: dict):
        """OPEN_LONG / OPEN_SHORT (back-compat: CYCLE_START / ADD_POSITION).

        Abre o SUMA posicion en la cuenta activa del grupo. La direccion sale
        SIEMPRE de la senal (nunca de estado interno). Repetir la misma
        direccion con posicion abierta = anadir contratos en esa misma cuenta.
        """
        sig_type = (signal.get("type") or "").upper()
        direction = 1 if (signal.get("direction", 1) or 1) > 0 else -1
        if sig_type == "OPEN_SHORT":
            direction = -1
        elif sig_type == "OPEN_LONG":
            direction = 1
        direction_str = "LONG" if direction > 0 else "SHORT"
        signal_instrument = signal.get("instrument") or "?"

        with self._lock:
            db = SessionLocal()
            try:
                svc = AccountService(db)
                svc.reset_daily()

                groups = svc.get_all_groups()
                active_groups = [g for g in groups if g.active]
                if not active_groups:
                    log.warning(f"{direction_str}: no active group")
                    return

                for active_group in active_groups:
                    if not self._in_schedule(active_group):
                        continue

                    enabled = [a for a in svc.get_accounts(active_group.id) if a.enabled]
                    if not enabled:
                        continue

                    state = self.group_state.get(active_group.id, {"processed": []})
                    active_id = state.get("active_account_id")

                    # 1) Cuenta activa (por estado, o la unica TRADING de facto tras reinicio)
                    target = next((a for a in enabled if a.id == active_id and a.status == "TRADING"), None)
                    if target is None:
                        target = next((a for a in enabled if a.status == "TRADING"), None)

                    if target:
                        # MISMA cuenta activa: permitido SUMA aunque tenga posicion abierta
                        if state.get("active_account_id") != target.id:
                            state["active_account_id"] = target.id
                        self.group_state[active_group.id] = state
                        self._send_entry(target, signal)
                        return

                    # 2) Sin cuenta activa -> NUNCA activar otra mientras haya posiciones abiertas
                    if self._group_has_open_positions(db, active_group.id):
                        log.info(f"Group {active_group.id}: {direction_str} ignorado, posiciones aun abiertas")
                        continue

                    # 3) Reset continuo: todas en TP/SL y sin posiciones -> nueva ronda + abrir trade
                    if active_group.reset_mode == "continuo":
                        target = self._reset_continuo(db, active_group, enabled, state)
                        if target:
                            self._send_entry(target, signal)
                            return

                    # 4) Rotacion: siguiente PENDING no procesado
                    processed = state.get("processed", [])
                    target = next((a for a in enabled if a.id not in processed and a.status == "PENDING"), None)
                    if not target:
                        continue

                    # Safety: solo UN TRADING por grupo
                    for a in enabled:
                        if a.status == "TRADING" and a.id != target.id:
                            a.status = "PENDING"
                    if active_id and active_id not in processed:
                        processed.append(active_id)
                    target.status = "TRADING"
                    state["active_account_id"] = target.id
                    state["processed"] = processed
                    self.group_state[active_group.id] = state
                    db.commit()
                    log.info(f"Group {active_group.id}: -> {target.name}")
                    self._send_entry(target, signal)
                    return

                log.warning(f"{direction_str}: no group in schedule with available accounts")
            finally:
                db.close()

    def _reset_continuo(self, db, group, enabled, state) -> Account | None:
        """Reinicia todas las cuentas del grupo a PENDING (nueva ronda) y devuelve la primera como TRADING.
        Solo cuando todas estan en TP/SL y el llamador ya verifico que no hay posiciones abiertas."""
        tp_statuses = ("TP_RONDA", "SL_RONDA", "TP_GLOBAL", "SL_GLOBAL")
        all_done = all(a.status in tp_statuses for a in enabled)
        if not all_done:
            return None
        new_round = max((a.round_num or 0) for a in enabled) + 1
        for a in enabled:
            a.status = "PENDING"
            a.open_pnl = 0.0
            a.symbol = "--"
            a.position = "FLAT"
            a.trades_today = 0
            a.daily_start_realized = a.last_realized
            a.round_baseline_set = False
            a.round_pnl = 0.0
            a.round_num = new_round
        first = enabled[0]
        first.status = "TRADING"
        state["processed"] = []
        db.commit()
        log.info(f"Group {group.id}: continuo reset ronda {new_round}")
        self._add_log(f"Group {group.id}: nueva ronda {new_round}", category="RESET")
        return first

    def _send_entry(self, account, signal: dict):
        """Envia ENTER_LONG/ENTER_SHORT a la cuenta. Contratos = CT de la cuenta;
        instrumento = symbols map. NO resetea el baseline de ciclo (los adds no lo rompen)."""
        sig_type = (signal.get("type") or "").upper()
        direction = 1 if (signal.get("direction", 1) or 1) > 0 else -1
        if sig_type == "OPEN_SHORT":
            direction = -1
        elif sig_type == "OPEN_LONG":
            direction = 1
        direction_str = "LONG" if direction > 0 else "SHORT"
        signal_instrument = signal.get("instrument") or "?"

        db2 = SessionLocal()
        try:
            acc = db2.query(Account).filter(Account.id == account.id).first()
            if acc and acc.status != "TRADING":
                acc.status = "TRADING"
                db2.commit()
        finally:
            db2.close()

        instrument = self._resolve_instrument(signal_instrument)
        ct = max(1, account.ct)

        # Limite de posiciones por ciclo (MXP): no sumar si ya se alcanzo.
        mxp = max(1, account.max_positions or 1)
        open_units = max(
            self._cycle_adds.get(account.nt8_account, 0),
            self._account_open_units(account.nt8_account, ct),
        )
        if open_units >= mxp:
            log.info(f"{direction_str} ignorado: {account.nt8_account} ya tiene {open_units} posiciones (MXP={mxp})")
            self._add_log(f"{account.nt8_account}: MXP alcanzado ({open_units}/{mxp}), suma ignorada",
                          category="CYCLE", account=account.nt8_account)
            return

        self._write_trade(account.nt8_account, "ENTER_" + direction_str, instrument, ct, 0, 0)
        self._cycle_adds[account.nt8_account] = self._cycle_adds.get(account.nt8_account, 0) + 1

        log.info(f"{direction_str}: {ct}x {instrument} -> [{account.nt8_account}]")
        self._add_log(f"TRADE {direction_str} {ct}x {instrument} -> {account.nt8_account}",
                      category="TRADE", account=account.nt8_account)

    def _resolve_instrument(self, signal_instrument: str) -> str:
        """Traduce el simbolo del EA (USTEC, NAS100, ...) al futuro de NT8 usando el symbols map.
        Si no hay mapeo -> instrumento por defecto configurable."""
        db = SessionLocal()
        try:
            if signal_instrument and signal_instrument != "?":
                m = db.query(SymbolMap).filter(SymbolMap.mt5_symbol == signal_instrument.upper()).first()
                if m:
                    return m.nt8_instrument
                log.info(f"Symbol '{signal_instrument}' sin mapeo en symbols map -> default")
            return self._get_config("default_instrument") or "MNQ 09-26"
        finally:
            db.close()

    def on_signal(self, signal: dict):
        action = signal.get("action", "").upper()
        instrument = self._resolve_instrument(signal.get("instrument", "?"))
        order_data = signal.get("order", {})
        sl_ticks = order_data.get("sl_ticks", 75)
        tp_ticks = order_data.get("tp_ticks", 90)

        with self._lock:
            db = SessionLocal()
            try:
                svc = AccountService(db)
                svc.reset_daily()

                for group_id, state in list(self.group_state.items()):
                    group = db.query(Group).filter(Group.id == group_id).first()
                    if not group or not group.active:
                        continue

                    if not self._in_schedule(group):
                        continue

                    if group.direction != "BOTH":
                        if (group.direction == "LONG" and "SHORT" in action) or \
                           (group.direction == "SHORT" and "LONG" in action):
                            continue

                    active_id = state.get("active_account_id")
                    if not active_id:
                        continue

                    account = db.query(Account).filter(Account.id == active_id).first()
                    if not account or not account.enabled:
                        self._next_account(group_id, state, db)
                        continue

                    ct = account.ct
                    self._write_trade(account.nt8_account, action, instrument, ct, sl_ticks, tp_ticks)
                    log.info(f"[G{group_id}] {account.name}: {action} {ct}x {instrument}")

            finally:
                db.close()

    def on_trade_closed(self, nt8_account: str, pnl: float, instrument: str, direction: str):
        with self._lock:
            db = SessionLocal()
            try:
                account = db.query(Account).filter(Account.nt8_account == nt8_account).first()
                if not account:
                    return

                account.daily_pnl += pnl
                account.open_pnl = 0.0
                account.position = "FLAT"
                account.trades_today += 1
                db.commit()

                state = self.group_state.get(account.group_id)
                if not state:
                    return

                if pnl >= account.tpc:
                    account.status = "TP_TOUCHED"
                    db.commit()
                    self._next_account(account.group_id, state, db)

                elif abs(pnl) >= account.slc and pnl < 0:
                    account.status = "SL_TOUCHED"
                    db.commit()
                    self._next_account(account.group_id, state, db)

                log.info(f"Trade closed: {account.name} PnL={pnl:.0f} Status={account.status}")

            finally:
                db.close()
        self._broadcast()

    # ===== internals =====

    def _next_account(self, group_id: int, state: dict, db):
        active_id = state.get("active_account_id")
        state["processed"] = state.get("processed", []) + [active_id]

        accounts = db.query(Account).filter(
            Account.group_id == group_id, Account.enabled == True
        ).order_by(Account.order_index).all()

        next_acc = next(
            (a for a in accounts if a.id not in state["processed"] and a.status == "PENDING"),
            None
        )

        # NUNCA rotar ni resetear mientras alguna cuenta tenga posicion abierta:
        # esperar a que la cuenta activa se cierre de verdad antes de activar la siguiente.
        if self._group_has_open_positions(db, group_id):
            log.info(f"Group {group_id}: rotacion aplazada, posiciones aun abiertas")
            state["processed"] = state["processed"][:-1]
            db.commit()
            return

        if next_acc:
            # Reset all TRADING accounts in this group (safety)
            for a in accounts:
                if a.status == "TRADING" and a.id != next_acc.id:
                    a.status = "PENDING"

            next_acc.status = "TRADING"
            db.commit()

            state["active_account_id"] = next_acc.id
            log.info(f"Group {group_id}: -> {next_acc.name}")
            # DO NOT auto-start cycles. Only MT5 initiates them.
        else:
            state.pop("active_account_id", None)
            log.info(f"Group {group_id}: all accounts done")
            group = db.query(Group).filter(Group.id == group_id).first()
            if group:
                mode = group.reset_mode or "diario"
                if mode == "manual":
                    group.active = False
                    db.commit()
                    log.info(f"Group {group_id}: stopped (reset_mode=manual)")
                elif mode == "continuo":
                    # Reiniciar las cuentas HABILITADAS a PENDING y volver a la primera.
                    # Las deshabilitadas (TPG/SLG/TPD/SLD/manual) se quedan como estan;
                    # las pausadas diarias (TPD/SLD) las reactiva reset_daily() al dia siguiente.
                    svc = AccountService(db)
                    new_round = max((a.round_num or 0) for a in svc.get_accounts(group_id)) + 1
                    for a in svc.get_accounts(group_id):
                        if not a.enabled:
                            continue
                        a.status = "PENDING"
                        a.daily_pnl = 0.0
                        a.open_pnl = 0.0
                        a.symbol = "--"
                        a.position = "FLAT"
                        a.trades_today = 0
                        a.daily_start_realized = a.last_realized  # Baseline diario
                        a.round_baseline_set = False  # Permitir que se recalcule
                        a.round_pnl = 0.0
                        a.round_num = new_round
                    first = next((a for a in svc.get_accounts(group_id) if a.enabled), None)
                    if first:
                        first.status = "TRADING"
                        state["active_account_id"] = first.id
                        state["processed"] = []  # Limpiar para nueva ronda
                        log.info(f"Group {group_id}: continuo -> {first.name}")
                    db.commit()
                # mode == "diario": no hacer nada, reset_daily() se encarga a las 00:00

    def _in_schedule(self, group: Group) -> bool:
        if not group.schedule_enabled:
            return True
        now = datetime.now()
        start = time(group.schedule_start_h, group.schedule_start_m)
        end = time(group.schedule_end_h, group.schedule_end_m)
        current = now.time()
        if start <= end:
            return start <= current <= end
        else:
            return current >= start or current <= end

    def _write_trade(self, nt8_account: str, action: str, instrument: str,
                     contracts: int, sl_ticks: int, tp_ticks: int, close_all: bool = False):
        if close_all:
            # Prevent duplicate close within 3 seconds
            now = datetime.now().timestamp()
            last = self._last_close_time.get(nt8_account, 0)
            if now - last < 10:  # 10 seg para que el AddOn actualice el status
                return
            self._last_close_time[nt8_account] = now
            cmd = {
                "command": "CLOSE_ALL",
                "account": nt8_account
            }
        else:
            cmd = {
                "command": "TRADE",
                "account": nt8_account,
                "action": action,
                "instrument": instrument,
                "contracts": contracts,
                "sl_ticks": sl_ticks,
                "tp_ticks": tp_ticks
            }
        filename = f"cmd_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        with open(os.path.join(self.commands_path, filename), "w", encoding="utf-8") as f:
            json.dump(cmd, f)

    def get_dashboard_state(self) -> dict:
        db = SessionLocal()
        try:
            svc = AccountService(db)
            svc.reset_daily()
            self._sync_balances(db)
            return {
                "groups": [svc.to_group_dict(g) for g in svc.get_all_groups()],
                "version": self._get_version(),
                "timestamp": datetime.now().isoformat(),
                "nt8_connected": self._is_nt8_connected(),
                "engine_active": self._is_engine_active(),
                "mt5_connected": self._is_mt5_connected(),
                "last_signal_time": self.last_signal_time,
                "signal_log": self.signal_log[-50:],  # last 50 entries
                "activity_log": self._get_activity_log(50),
                "nt8_accounts": self._get_nt8_accounts()
            }
        finally:
            db.close()

    def _get_activity_log(self, limit: int = 50) -> list:
        """Ultimas entradas del ActivityLog persistente (para el WebSocket)"""
        try:
            db = SessionLocal()
            try:
                entries = db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(limit).all()
                return [{
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else "",
                    "category": e.category or "INFO",
                    "message": e.message or "",
                    "account": e.account or "",
                    "group_id": e.group_id,
                } for e in entries]
            finally:
                db.close()
        except:
            return []

    def _is_nt8_connected(self) -> bool:
        try:
            files = sorted(glob.glob(os.path.join(self.status_path, "status_*.json")), reverse=True)
            if not files:
                return False
            mtime = os.path.getmtime(files[0])
            return (datetime.now().timestamp() - mtime) < 15
        except:
            return False

    def _get_version(self) -> str:
        try:
            cl_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "changelog.json")
            if os.path.exists(cl_path):
                with open(cl_path, "r") as f:
                    entries = json.load(f)
                    if entries:
                        return entries[0].get("version", "")
        except:
            pass
        return ""

    def _add_log(self, msg: str, category: str = "INFO", account: str = None, group_id: int = None):
        entry = f"{datetime.now().strftime('%H:%M:%S')} {msg}"
        self.signal_log.append(entry)
        if len(self.signal_log) > 200:
            self.signal_log = self.signal_log[-100:]
        # Persistir en BD
        try:
            db = SessionLocal()
            db.add(ActivityLog(timestamp=datetime.now(), category=category,
                               message=msg, account=account, group_id=group_id))
            db.commit()
            db.close()
        except:
            pass

    def _is_engine_active(self) -> bool:
        try:
            if self.last_signal_time:
                ts = datetime.fromisoformat(self.last_signal_time)
                if (datetime.now() - ts).total_seconds() < 300:
                    return True
            # NT8 heartbeat
            hb_file = os.path.join(self.signals_path, "heartbeat.json")
            if os.path.exists(hb_file):
                mtime = os.path.getmtime(hb_file)
                if (datetime.now().timestamp() - mtime) < 120:
                    return True
            # MT5 heartbeat (catcher or EA)
            for p in [self.mt5_signals_path]:
                for hb in ["heartbeat_catcher.json", "cyclescale_*.json"]:
                    files = sorted(glob.glob(os.path.join(p, hb)), reverse=True)
                    if files:
                        mtime = os.path.getmtime(files[0])
                        if (datetime.now().timestamp() - mtime) < 120:
                            return True
            return False
        except:
            return False

    def _is_mt5_connected(self) -> bool:
        # Check for catcher heartbeat
        hb = os.path.join(self.mt5_signals_path, "heartbeat_catcher.json")
        if os.path.exists(hb):
            mtime = os.path.getmtime(hb)
            return (datetime.now().timestamp() - mtime) < 60

        # Fallback: check for recent signals
        if self.last_mt5_hb > 0:
            return (datetime.now().timestamp() - self.last_mt5_hb) < 60

        return False
        try:
            # Check NT8 heartbeat
            hb_file = os.path.join(self.signals_path, "heartbeat.json")
            if os.path.exists(hb_file):
                mtime = os.path.getmtime(hb_file)
                if (datetime.now().timestamp() - mtime) < 120:
                    return True

            # Check MT5 signals
            for p in [self.mt5_signals_path, self.signals_path]:
                files = sorted(glob.glob(os.path.join(p, "cyclescale_*.json")), reverse=True)
                if files:
                    mtime = os.path.getmtime(files[0])
                    if (datetime.now().timestamp() - mtime) < 300:  # 5 min
                        return True

            return False
        except:
            return False

    def _get_nt8_accounts(self) -> list:
        try:
            files = sorted(glob.glob(os.path.join(self.status_path, "status_*.json")), reverse=True)
            if not files:
                return []
            with open(files[0], "r", encoding="utf-8") as f:
                status = json.load(f)
            accounts = status.get("accounts", [])
            return [{"name": a.get("name", ""), "balance": a.get("balance", 0)} for a in accounts]
        except:
            return []

    def _sync_balances(self, db):
        """Lee el status del AddOn y actualiza balances/posiciones en DB. Tambien cierra si TP/SL tocado"""
        files = sorted(glob.glob(os.path.join(self.status_path, "status_*.json")), reverse=True)
        if not files:
            return
        try:
            with open(files[0], "r", encoding="utf-8") as f:
                status = json.load(f)
        except:
            return

        nt8_accounts = status.get("accounts", [])

        # Guard: si el ultimo status NO es de hoy (NT8 apagado / finde),
        # no re-derivar baselines, PNL ni estados desde datos rancios. Eso
        # deshace el reset diario y deja PNL RONDA negativo. Solo se sincronizan balances.
        m = re.search(r"status_(\d{8})", os.path.basename(files[0]))
        is_today = bool(m and m.group(1) == datetime.now().strftime("%Y%m%d"))

        # Check cycles: TPC/SLC (per-cycle) using raw status data directly
        if is_today:
            for nt8 in nt8_accounts:
                acc_name = nt8.get("name", "")
                pos_list = nt8.get("positions", [])
                if not pos_list:
                    # No positions → ciclo cerrado: resetear contador de adds
                    self._cycle_adds.pop(acc_name, None)
                    # reset cycle tracking (registra cierre externo si lo habia)
                    if acc_name in self._cycle_start_realized:
                        if datetime.now().timestamp() - self._last_close_time.get(acc_name, 0) >= 10:
                            acc = db.query(Account).filter(Account.nt8_account == acc_name).first()
                            if acc and acc.status in ("PENDING", "TRADING"):
                                base = self._cycle_start_realized.get(acc_name) or 0
                                ext_pnl = nt8.get("realized_pnl", 0) - base
                                self._record_close(db, acc, ext_pnl, "EXTERNAL")
                                log.info(f"External close {acc_name}: pnl={ext_pnl:.0f}")
                        self._cycle_start_realized.pop(acc_name, None)
                        self._cycle_start_ts.pop(acc_name, None)
                    continue

                acc = db.query(Account).filter(Account.nt8_account == acc_name).first()
                if not acc or acc.status not in ("PENDING", "TRADING"):
                    continue

                db.refresh(acc)  # Live edits from dashboard

                realized = nt8.get("realized_pnl", 0)
                unrealized = nt8.get("unrealized_pnl", 0)

                # Track cycle start baseline
                if acc_name not in self._cycle_start_realized or self._cycle_start_realized[acc_name] is None:
                    self._cycle_start_realized[acc_name] = realized
                    self._cycle_start_ts[acc_name] = datetime.now()
                    log.info(f"Cycle baseline for {acc_name}: realized={realized:.0f}")

        if not nt8_accounts:
            db.commit()
            return

        for nt8 in nt8_accounts:
            name = nt8.get("name", "")
            if not name:
                continue
            acc = db.query(Account).filter(Account.nt8_account == name).first()
            if not acc:
                continue

            db.refresh(acc)  # Live edits from dashboard

            acc.balance = nt8.get("balance", acc.balance)

            # Status rancio (no de hoy): solo balance, nada mas.
            if not is_today:
                continue

            unrealized = nt8.get("unrealized_pnl", 0)
            realized = nt8.get("realized_pnl", 0)
            acc.open_pnl = unrealized
            acc.last_realized = realized  # Guardar para baseline de ronda

            # PNL DIA: usar el valor diario de NT8 si esta disponible
            daily_realized = nt8.get("daily_realized", None)
            if daily_realized is not None:
                acc.daily_pnl = round(daily_realized + unrealized, 2)
            else:
                # Fallback: baseline calculado
                if not acc.daily_baseline_set:
                    acc.daily_start_realized = realized
                    acc.daily_baseline_set = True
                daily_baseline = acc.daily_start_realized or 0
                acc.daily_pnl = round((realized - daily_baseline) + unrealized, 2)

            acc.total_pnl = round((acc.balance + unrealized) - (acc.starting_balance or 0), 2)

            # Calcular PNL Ronda
            if not acc.round_baseline_set:
                acc.round_start_realized = realized
                acc.round_baseline_set = True
            round_baseline = acc.round_start_realized or 0
            acc.round_pnl = round((realized - round_baseline) + unrealized, 2)

            # Muestrear equity (throttle stats_interval_s)
            self._snapshot_equity(db, acc)

            pos_list = nt8.get("positions", [])
            if pos_list:
                p = pos_list[0]
                acc.symbol = p.get("instrument", acc.symbol)
                acc.position = p.get("direction", acc.position)
            else:
                acc.position = "FLAT"
                acc.symbol = "--"

            # Skip if close was recently sent (status may be stale)
            if datetime.now().timestamp() - self._last_close_time.get(name, 0) < 10:
                continue

            # Cycle PnL para TPC/SLC (prioridad minima)
            cycle_pnl = None
            if pos_list:
                base = self._cycle_start_realized.get(name)
                if base is not None:
                    cycle_pnl = (realized - base) + unrealized

            # Prioridad: TPG/SLG -> TPD/SLD -> TPR/SLR -> TPC/SLC
            if acc.tpg and acc.tpg > 0 and acc.total_pnl >= acc.tpg and acc.status in ("PENDING", "TRADING", "TP_RONDA", "SL_RONDA"):
                acc.status = "TP_GLOBAL"
                acc.enabled = False
                if pos_list:
                    self._write_trade(name, "", "", 0, 0, 0, close_all=True)
                    self._last_close_time[name] = datetime.now().timestamp()
                    if cycle_pnl is not None:
                        self._record_close(db, acc, cycle_pnl, "TPG")
                        self._cycle_start_realized.pop(name, None)
                        self._cycle_start_ts.pop(name, None)
                self._add_log(f"{name}: GLOBAL TP +${acc.total_pnl:.0f} ≥ +${acc.tpg:.0f} → disabled", category="GLOBAL", account=name)
                log.info(f"TPG {name}: total={acc.total_pnl:.0f} >= {acc.tpg}")

            elif acc.slg and acc.slg > 0 and acc.total_pnl <= -acc.slg and acc.status in ("PENDING", "TRADING", "TP_RONDA", "SL_RONDA"):
                acc.status = "SL_GLOBAL"
                acc.enabled = False
                if pos_list:
                    self._write_trade(name, "", "", 0, 0, 0, close_all=True)
                    self._last_close_time[name] = datetime.now().timestamp()
                    if cycle_pnl is not None:
                        self._record_close(db, acc, cycle_pnl, "SLG")
                        self._cycle_start_realized.pop(name, None)
                        self._cycle_start_ts.pop(name, None)
                self._add_log(f"{name}: GLOBAL SL -${abs(acc.total_pnl):.0f} ≥ -${acc.slg:.0f} → disabled", category="GLOBAL", account=name)
                log.info(f"SLG {name}: total={acc.total_pnl:.0f} <= -{acc.slg}")

            elif acc.tpd and acc.tpd > 0 and acc.daily_pnl >= acc.tpd and acc.status in ("PENDING", "TRADING"):
                acc.status = "TP_DIA"
                acc.enabled = False
                if pos_list:
                    self._write_trade(name, "", "", 0, 0, 0, close_all=True)
                    self._last_close_time[name] = datetime.now().timestamp()
                    if cycle_pnl is not None:
                        self._record_close(db, acc, cycle_pnl, "DAILY_TP")
                        self._cycle_start_realized.pop(name, None)
                        self._cycle_start_ts.pop(name, None)
                self._add_log(f"{name}: DAILY TP +${acc.daily_pnl:.0f} ≥ +${acc.tpd:.0f} → pausada hoy", category="ROTATION", account=name)
                log.info(f"TPD {name}: daily={acc.daily_pnl:.0f} >= {acc.tpd}")

            elif acc.sld and acc.sld > 0 and acc.daily_pnl <= -acc.sld and acc.status in ("PENDING", "TRADING"):
                acc.status = "SL_DIA"
                acc.enabled = False
                if pos_list:
                    self._write_trade(name, "", "", 0, 0, 0, close_all=True)
                    self._last_close_time[name] = datetime.now().timestamp()
                    if cycle_pnl is not None:
                        self._record_close(db, acc, cycle_pnl, "DAILY_SL")
                        self._cycle_start_realized.pop(name, None)
                        self._cycle_start_ts.pop(name, None)
                self._add_log(f"{name}: DAILY SL -${abs(acc.daily_pnl):.0f} ≥ -${acc.sld:.0f} → pausada hoy", category="ROTATION", account=name)
                log.info(f"SLD {name}: daily={acc.daily_pnl:.0f} <= -{acc.sld}")

            elif acc.pdpt and acc.pdpt > 0 and acc.round_pnl >= acc.pdpt and acc.status in ("PENDING", "TRADING"):
                acc.status = "TP_RONDA"
                self._write_trade(name, "", "", 0, 0, 0, close_all=True)
                self._last_close_time[name] = datetime.now().timestamp()
                if cycle_pnl is not None:
                    self._record_close(db, acc, cycle_pnl, "ROUND_TP")
                    self._cycle_start_realized.pop(name, None)
                    self._cycle_start_ts.pop(name, None)
                self._add_log(f"{name}: ROUND TP +${acc.round_pnl:.0f} ≥ +${acc.pdpt:.0f} → rotating", category="ROTATION", account=name)
                log.info(f"TPR {name}: round={acc.round_pnl:.0f} >= {acc.pdpt}")

            elif acc.pdll and acc.pdll > 0 and acc.round_pnl <= -acc.pdll and acc.status in ("PENDING", "TRADING"):
                acc.status = "SL_RONDA"
                self._write_trade(name, "", "", 0, 0, 0, close_all=True)
                self._last_close_time[name] = datetime.now().timestamp()
                if cycle_pnl is not None:
                    self._record_close(db, acc, cycle_pnl, "ROUND_SL")
                    self._cycle_start_realized.pop(name, None)
                    self._cycle_start_ts.pop(name, None)
                self._add_log(f"{name}: ROUND SL -${abs(acc.round_pnl):.0f} ≥ -${acc.pdll:.0f} → rotating", category="ROTATION", account=name)
                log.info(f"SLR {name}: round={acc.round_pnl:.0f} <= -{acc.pdll}")

            elif cycle_pnl is not None and cycle_pnl >= acc.tpc:
                self._write_trade(name, "", "", 0, 0, 0, close_all=True)
                self._last_close_time[name] = datetime.now().timestamp()
                self._record_close(db, acc, cycle_pnl, "TPC")
                self._cycle_start_realized.pop(name, None)
                self._cycle_start_ts.pop(name, None)
                self._add_log(f"{name}: CYCLE TP +${cycle_pnl:.0f} ≥ +${acc.tpc:.0f} → closed", category="CYCLE", account=name)

            elif cycle_pnl is not None and cycle_pnl <= -acc.slc:
                self._write_trade(name, "", "", 0, 0, 0, close_all=True)
                self._last_close_time[name] = datetime.now().timestamp()
                self._record_close(db, acc, cycle_pnl, "SLC")
                self._cycle_start_realized.pop(name, None)
                self._cycle_start_ts.pop(name, None)
                self._add_log(f"{name}: CYCLE SL -${abs(cycle_pnl):.0f} ≥ -${acc.slc:.0f} → closed", category="CYCLE", account=name)

            # If account was TP/SL and position is now closed, rotate
            if not pos_list and acc.status in ("TP_RONDA", "SL_RONDA", "TP_DIA", "SL_DIA", "TP_GLOBAL", "SL_GLOBAL", "TP_TOUCHED", "SL_TOUCHED"):
                # Migrar status antiguo al nuevo
                if acc.status == "TP_TOUCHED": acc.status = "TP_RONDA"
                if acc.status == "SL_TOUCHED": acc.status = "SL_RONDA"
                state = self.group_state.get(acc.group_id)
                if not state:
                    # Reconstruir state tras reinicio del backend
                    # Buscar TRADING o, si no hay, la ultima cuenta que acabo de tocar
                    active = next((a for a in db.query(Account).filter(
                        Account.group_id == acc.group_id, Account.status.in_(["TRADING", "TP_RONDA", "SL_RONDA", "TP_DIA", "SL_DIA", "TP_GLOBAL", "SL_GLOBAL"])
                    ).order_by(Account.order_index).all()), None)
                    if active:
                        state = {"active_account_id": active.id, "processed": []}
                        self.group_state[acc.group_id] = state
                if state and state.get("active_account_id") == acc.id:
                    self._next_account(acc.group_id, state, db)

        db.commit()

    def test_account(self, nt8_account: str) -> dict:
        if not os.path.isdir(self.status_path):
            return {"ok": False, "error": "No Q7 status folder."}
        files = sorted(glob.glob(os.path.join(self.status_path, "status_*.json")), reverse=True)
        if not files:
            return {"ok": False, "error": "No status files. Restart NT8 / F5."}
        try:
            with open(files[0], "r", encoding="utf-8") as f:
                status = json.load(f)
        except:
            return {"ok": False, "error": "Cannot read status file"}
        accounts = status.get("accounts", [])
        target = next((a for a in accounts if a.get("name", "").lower() == nt8_account.lower()), None)
        if target:
            return {"ok": True, "balance": target.get("balance", 0), "pnl": target.get("realized_pnl", 0)}
        names = [a.get("name", "") for a in accounts]
        return {"ok": False, "error": f"Not found. NT8 sees: {', '.join(names) or 'none'}"}

    def _broadcast(self):
        if self.ws_broadcast:
            try:
                self.ws_broadcast(self.get_dashboard_state())
            except:
                pass
