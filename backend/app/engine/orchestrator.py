"""
Q7 Backend - Orchestrator (v2: Group-based, sequential)
"""
import glob
import json
import logging
import os
import threading
from datetime import date, datetime, time

from app.database import SessionLocal
from app.models.account import Account, Group
from app.services.account_service import AccountService

log = logging.getLogger("Q7Backend.Orchestrator")


class OrchestratorEngine:
    def __init__(self):
        docs = os.path.join(os.path.expanduser("~"), "Documents", "NinjaTrader 8", "Q7")
        self.signals_path = os.path.join(docs, "signals")
        self.commands_path = os.path.join(docs, "commands")
        self.status_path = os.path.join(docs, "status")

        # MT5 signals path (MQL5 sandbox)
        mt5 = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "MetaQuotes",
                           "Terminal", "D0E8209F77C8CF37AD8BF550E51FF075", "MQL5", "Files", "Q7", "signals")
        self.mt5_signals_path = mt5

        for p in [self.signals_path, self.commands_path, self.status_path, self.mt5_signals_path]:
            os.makedirs(p, exist_ok=True)
        os.makedirs(os.path.join(self.signals_path, "processed"), exist_ok=True)

        self.group_state: dict[int, dict] = {}
        self.last_signal_time: str = ""
        self.current_trend: int = 0
        self.signal_log: list[str] = []
        self.mt5_connected: bool = False
        self.last_mt5_hb: float = 0
        self._last_close_time: dict[str, float] = {}
        self._cycle_start_realized: dict[str, float] = {}
        self._cycle_start_time: dict[str, float] = {}
        self._lock = threading.Lock()
        self.ws_broadcast = None

    def set_ws_broadcast(self, fn):
        self.ws_broadcast = fn

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

                if sig_type == "CYCLE_START":
                    self._handle_cycle_start(signal)
                    self._add_log(f"CYCLE_START {'LONG' if signal.get('direction',1)>0 else 'SHORT'} | {signal.get('instrument','?')}")
                elif sig_type == "CYCLE_END":
                    self._handle_cycle_end(signal)
                    self._add_log(f"CYCLE_END | {signal.get('instrument','?')}")
                elif sig_type == "ADD_POSITION":
                    self._handle_add_position(signal)
                    self._add_log(f"ADD_POSITION {signal.get('instrument','?')}")
                elif sig_type == "HEARTBEAT":
                    self.mt5_connected = True
                    self.last_mt5_hb = datetime.now().timestamp()
                else:
                    self.on_signal(signal)
                    self._add_log(f"SIGNAL {signal.get('action','?')}")

                self.last_signal_time = datetime.utcnow().isoformat()
            except Exception as e:
                log.error(f"Signal error: {e}")

    def _handle_cycle_start(self, signal: dict):
        """Maneja una senal CYCLE_START: envia START_CYCLE a la cuenta activa"""
        direction = signal.get("direction", 1)
        self.current_trend = direction

        with self._lock:
            db = SessionLocal()
            try:
                svc = AccountService(db)
                svc.reset_daily()

                groups = svc.get_all_groups()
                active_groups = [g for g in groups if g.active]
                if not active_groups:
                    log.warning("CYCLE_START: no active group")
                    return

                # Find first active group that is in schedule and has available accounts
                for active_group in active_groups:
                    if not self._in_schedule(active_group):
                        continue
                    accounts = svc.get_accounts(active_group.id)
                    account = next((a for a in accounts if a.enabled and a.status in ("PENDING", "TRADING")), None)
                    if not account:
                        continue
                    self._start_cycle_on_account(account, signal)
                    return

                log.warning(f"CYCLE_START: no group in schedule with available accounts ({len(active_groups)} active)")
            finally:
                db.close()

    def _start_cycle_on_account(self, account, signal: dict):
        direction = signal.get("direction", 1)
        direction_str = "LONG" if direction > 0 else "SHORT"

        # Mark as TRADING (active account)
        db2 = SessionLocal()
        try:
            acc = db2.query(Account).filter(Account.id == account.id).first()
            if acc and acc.status == "PENDING":
                acc.status = "TRADING"
                db2.commit()
        finally:
            db2.close()

        # Track cycle PnL baseline
        self._cycle_start_realized[account.nt8_account] = None
        self._cycle_start_time[account.nt8_account] = datetime.now().timestamp()

        # Send TRADE command (simple order, AddOn just executes it)
        ct = max(1, account.ct)
        self._write_trade(account.nt8_account, "ENTER_" + direction_str, "MNQ 09-26", ct, 0, 0)

        log.info(f"CYCLE_START: {direction_str} on [{account.nt8_account}] CT={ct}")

    def _handle_cycle_end(self, signal: dict):
        """CYCLE_END del MT5 → cierra posiciones en cuenta activa"""
        with self._lock:
            db = SessionLocal()
            try:
                svc = AccountService(db)
                groups = svc.get_all_groups()
                active_groups = [g for g in groups if g.active]
                for active_group in active_groups:
                    if not self._in_schedule(active_group):
                        continue
                    accounts = svc.get_accounts(active_group.id)
                    account = next((a for a in accounts if a.enabled and a.status in ("PENDING", "TRADING")), None)
                    if account:
                        self._write_trade(account.nt8_account, "", "", 0, 0, 0, close_all=True)
                        log.info(f"CYCLE_END: CLOSE_ALL on [{account.nt8_account}]")
                        break
            finally:
                db.close()

    def _handle_add_position(self, signal: dict):
        """ADD_POSITION del MT5 → añade contratos a la cuenta activa"""
        with self._lock:
            db = SessionLocal()
            try:
                svc = AccountService(db)
                groups = svc.get_all_groups()
                active_groups = [g for g in groups if g.active]
                for active_group in active_groups:
                    if not self._in_schedule(active_group):
                        continue
                    accounts = svc.get_accounts(active_group.id)
                    account = next((a for a in accounts if a.enabled and a.status in ("PENDING", "TRADING")), None)
                    if not account:
                        continue
                    direction = self.current_trend
                    direction_str = "LONG" if direction > 0 else "SHORT"
                    ct = max(1, account.ct)
                    self._write_trade(account.nt8_account, "ENTER_" + direction_str, "MNQ 09-26", ct, 0, 0)
                    log.debug(f"ADD_POSITION: {account.nt8_account}")
                    break
            finally:
                db.close()

    def on_signal(self, signal: dict):
        action = signal.get("action", "").upper()
        instrument = signal.get("instrument", "YM 09-26")
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

                if pnl >= account.tp:
                    account.status = "TP_TOUCHED"
                    db.commit()
                    self._next_account(account.group_id, state, db)

                elif abs(pnl) >= account.sl and pnl < 0:
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
                    # Reiniciar todas las cuentas a PENDING y volver a la primera
                    svc = AccountService(db)
                    for a in svc.get_accounts(group_id):
                        a.status = "PENDING"
                        a.daily_pnl = 0.0
                        a.open_pnl = 0.0
                        a.symbol = "--"
                        a.position = "FLAT"
                        a.trades_today = 0
                        a.daily_start_realized = a.last_realized  # Baseline diario
                        a.round_start_realized = a.last_realized  # Baseline para nueva ronda
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
                "timestamp": datetime.utcnow().isoformat(),
                "nt8_connected": self._is_nt8_connected(),
                "engine_active": self._is_engine_active(),
                "mt5_connected": self._is_mt5_connected(),
                "last_signal_time": self.last_signal_time,
                "signal_log": self.signal_log[-20:],  # last 20 entries
                "nt8_accounts": self._get_nt8_accounts()
            }
        finally:
            db.close()

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

    def _add_log(self, msg: str):
        self.signal_log.append(f"{datetime.now().strftime('%H:%M:%S')} {msg}")
        if len(self.signal_log) > 100:
            self.signal_log = self.signal_log[-50:]

    def _is_engine_active(self) -> bool:
        try:
            if self.last_signal_time:
                ts = datetime.fromisoformat(self.last_signal_time)
                if (datetime.utcnow() - ts).total_seconds() < 300:
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

        # Check cycles: TPC/SLC (per-cycle) using raw status data directly
        for nt8 in nt8_accounts:
            acc_name = nt8.get("name", "")
            pos_list = nt8.get("positions", [])
            if not pos_list:
                # No positions → reset cycle tracking
                self._cycle_start_realized.pop(acc_name, None)
                self._cycle_start_time.pop(acc_name, None)
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
                log.info(f"Cycle baseline for {acc_name}: realized={realized:.0f}")

            cycle_pnl = (realized - self._cycle_start_realized[acc_name]) + unrealized

            # Skip if we recently sent a close for this account (status may be stale)
            if datetime.now().timestamp() - self._last_close_time.get(acc_name, 0) < 10:
                continue

            # TPC/SLC check
            if cycle_pnl >= acc.tpc:
                self._write_trade(acc_name, "", "", 0, 0, 0, close_all=True)
                self._add_log(f"{acc_name}: CYCLE TP +${cycle_pnl:.0f} ≥ +${acc.tpc:.0f} → closed")
                self._cycle_start_realized.pop(acc_name, None)
                self._cycle_start_time.pop(acc_name, None)
                break

            elif cycle_pnl <= -acc.slc:
                self._write_trade(acc_name, "", "", 0, 0, 0, close_all=True)
                self._add_log(f"{acc_name}: CYCLE SL -${abs(cycle_pnl):.0f} ≥ -${acc.slc:.0f} → closed")
                self._cycle_start_realized.pop(acc_name, None)
                self._cycle_start_time.pop(acc_name, None)
                break

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
            unrealized = nt8.get("unrealized_pnl", 0)
            realized = nt8.get("realized_pnl", 0)
            acc.open_pnl = unrealized
            acc.last_realized = realized  # Guardar para baseline de ronda

            # Calcular PNL Dia (con baseline diario)
            if not acc.daily_baseline_set:
                acc.daily_start_realized = realized
                acc.daily_baseline_set = True
            daily_baseline = acc.daily_start_realized or 0
            acc.daily_pnl = round((realized - daily_baseline) + unrealized, 2)

            # Calcular PNL Ronda
            round_baseline = acc.round_start_realized or 0
            acc.round_pnl = round((realized - round_baseline) + unrealized, 2)

            pos_list = nt8.get("positions", [])
            if pos_list:
                p = pos_list[0]
                acc.symbol = p.get("instrument", acc.symbol)
                acc.position = p.get("direction", acc.position)
            else:
                acc.position = "FLAT"
                acc.symbol = "--"

            # Determinar que PNL usar para PDLL/PDPT segun modo del grupo
            group = db.query(Group).filter(Group.id == acc.group_id).first()
            mode = group.reset_mode if group else "diario"
            check_pnl = acc.round_pnl if mode == "continuo" else acc.daily_pnl

            # Skip daily check if close was recently sent
            if datetime.now().timestamp() - self._last_close_time.get(name, 0) < 10:
                continue

            if check_pnl >= acc.pdpt and acc.status in ("PENDING", "TRADING"):
                acc.status = "TP_TOUCHED"
                self._write_trade(name, "", "", 0, 0, 0, close_all=True)
                self._last_close_time[name] = datetime.now().timestamp()
                tag = "ROUND" if mode == "continuo" else "DAILY"
                self._add_log(f"{name}: {tag} TP +${check_pnl:.0f} ≥ +${acc.pdpt:.0f} → rotating")
                log.info(f"TP {name}: {tag} pnl={check_pnl:.0f} >= {acc.pdpt}")

            elif check_pnl <= -acc.pdll and acc.status in ("PENDING", "TRADING"):
                acc.status = "SL_TOUCHED"
                self._write_trade(name, "", "", 0, 0, 0, close_all=True)
                self._last_close_time[name] = datetime.now().timestamp()
                tag = "ROUND" if mode == "continuo" else "DAILY"
                self._add_log(f"{name}: {tag} SL -${abs(check_pnl):.0f} ≥ -${acc.pdll:.0f} → rotating")
                log.info(f"SL {name}: {tag} pnl={check_pnl:.0f} <= -{acc.pdll}")

            # If account was TP/SL and position is now closed, rotate
            if not pos_list and acc.status in ("TP_TOUCHED", "SL_TOUCHED"):
                state = self.group_state.get(acc.group_id)
                if not state:
                    # Reconstruir state tras reinicio del backend
                    # Buscar TRADING o, si no hay, la ultima cuenta que acabo de tocar
                    active = next((a for a in db.query(Account).filter(
                        Account.group_id == acc.group_id, Account.status.in_(["TRADING", "TP_TOUCHED", "SL_TOUCHED"])
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
