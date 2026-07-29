"""
Q7 Orchestrator
Backend central que gestiona la rotacion de cuentas, control de riesgo,
y puente de comunicacion entre NinjaTrader y el Dashboard web.

Flujo:
  1. Lee señales del Signal Engine (archivos JSON en signals/)
  2. Decide si ejecutar en la cuenta activa segun limites diarios
  3. Envia comandos al AddOn de Ninja (archivos JSON en commands/)
  4. Lee estado del AddOn (archivos JSON en status/)
  5. Sirve Dashboard web con Flask + SocketIO en tiempo real
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from threading import Lock, Thread
from typing import Optional, Dict, List, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('q7_orchestrator.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger('Q7Orchestrator')


class Account:
    """Representa una cuenta individual de Ninja/prop firm"""

    def __init__(self, cfg: dict):
        self.id: int = cfg['id']
        self.name: str = cfg['name']
        self.daily_profit_target: float = cfg.get('daily_profit_target', 1500)
        self.daily_loss_limit: float = cfg.get('daily_loss_limit', 1500)
        self.account_max_loss: float = cfg.get('account_max_loss', 10000)
        self.base_contracts: int = cfg.get('base_contracts', 1)

        self.daily_pnl: float = 0.0
        self.total_pnl: float = 0.0
        self.status: str = 'PENDING'
        self.trades_today: int = 0
        self.last_reset: date = date.today()

        self.martingale_multiplier: float = 1.0
        self.consecutive_losses: int = 0

    def reset_daily(self):
        """Reinicia contadores diarios"""
        self.daily_pnl = 0.0
        self.status = 'PENDING'
        self.trades_today = 0
        self.last_reset = date.today()
        self.martingale_multiplier = 1.0
        self.consecutive_losses = 0

    def is_target_reached(self) -> bool:
        return self.daily_pnl >= self.daily_profit_target

    def is_loss_limit_reached(self) -> bool:
        return abs(self.daily_pnl) >= self.daily_loss_limit and self.daily_pnl < 0

    def is_blown(self) -> bool:
        return self.total_pnl <= -self.account_max_loss

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'daily_pnl': round(self.daily_pnl, 2),
            'total_pnl': round(self.total_pnl, 2),
            'daily_target': self.daily_profit_target,
            'daily_limit': self.daily_loss_limit,
            'daily_target_pct': round(self.daily_pnl / self.daily_profit_target * 100, 1) if self.daily_profit_target else 0,
            'trades_today': self.trades_today,
            'consecutive_losses': self.consecutive_losses,
            'martingale': round(self.martingale_multiplier, 2),
            'contracts': int(self.base_contracts * self.martingale_multiplier)
        }


class Orchestrator:
    """Motor central de Q7"""

    def __init__(self, config_path: str = 'config.json'):
        self.cfg = self._load_config(config_path)
        self._expand_paths()

        self.accounts: List[Account] = []
        self.active_index: int = 0
        self.paused: bool = False
        self.lock: Lock = Lock()

        self.martingale_multiplier: float = self.cfg.get('risk', {}).get('martingale_multiplier', 1.6)
        self.max_consecutive_losses: int = self.cfg.get('risk', {}).get('max_consecutive_losses', 5)

        self._load_accounts()
        self._ensure_directories()

        self.watcher_running: bool = True
        self.dashboard = None

        log.info(f"Orchestrator initialized with {len(self.accounts)} accounts")
        log.info(f"Active account: #{self.active_account.id} - {self.active_account.name}")

    def _load_config(self, path: str) -> dict:
        if not os.path.exists(path):
            log.warning(f"Config file not found: {path}, using defaults")
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _expand_paths(self):
        username = os.environ.get('USER', os.environ.get('USERNAME', 'danit'))
        paths = self.cfg.get('q7', {}).get('paths', {})
        self.signals_path = os.path.expandvars(
            paths.get('signals_in', f'C:/Users/{username}/Documents/NinjaTrader 8/Q7/signals')
        ).replace('%USER%', username).replace('%USERNAME%', username)
        self.commands_path = os.path.expandvars(
            paths.get('commands_out', f'C:/Users/{username}/Documents/NinjaTrader 8/Q7/commands')
        ).replace('%USER%', username).replace('%USERNAME%', username)
        self.status_path = os.path.expandvars(
            paths.get('status_in', f'C:/Users/{username}/Documents/NinjaTrader 8/Q7/status')
        ).replace('%USER%', username).replace('%USERNAME%', username)

    def _load_accounts(self):
        accounts_cfg = self.cfg.get('q7', {}).get('accounts', [])
        self.accounts = [Account(cfg) for cfg in accounts_cfg]
        if not self.accounts:
            self.accounts = [Account({'id': 1, 'name': 'Default Sim'})]

    def _ensure_directories(self):
        for p in [self.signals_path, self.commands_path, self.status_path]:
            Path(p).mkdir(parents=True, exist_ok=True)
        Path(self.signals_path, 'processed').mkdir(parents=True, exist_ok=True)

    @property
    def active_account(self) -> Account:
        return self.accounts[self.active_index]

    def rotate_account(self):
        """Rota a la siguiente cuenta disponible"""
        with self.lock:
            current = self.active_account
            if current.status != 'BLOWN':
                current.status = 'TARGET_REACHED' if current.is_target_reached() else 'LOSS_LIMIT'

            self.active_index = (self.active_index + 1) % len(self.accounts)

            pending = [a for a in self.accounts if a.status == 'PENDING']
            if not pending:
                log.info("All accounts have reached target/loss limit today")
                self.active_account.status = 'WAITING_RESET'
            else:
                self.active_account.status = 'TRADING'

            log.info(f"Rotated to account #{self.active_account.id}: {self.active_account.name}")

    def process_signal(self, signal: dict) -> Optional[dict]:
        """Procesa una senal del Signal Engine"""
        with self.lock:
            if self.paused:
                return None

            self._check_daily_reset()

            account = self.active_account

            if account.is_target_reached() or account.is_loss_limit_reached():
                self.rotate_account()
                account = self.active_account

            if account.is_blown():
                account.status = 'BLOWN'
                self.rotate_account()
                account = self.active_account

            action = signal.get('action', '')
            order = signal.get('order', {})

            contracts = int(account.base_contracts * account.martingale_multiplier)

            command = {
                'type': 'TRADE_COMMAND',
                'timestamp': datetime.now().isoformat(),
                'target_account': account.name,
                'action': action,
                'order': {
                    'instrument': order.get('instrument', 'YM 09-26'),
                    'entry_price': order.get('entry_price', 0),
                    'sl_ticks': order.get('sl_ticks', 75),
                    'tp_ticks': order.get('tp_ticks', 90),
                    'contracts': contracts
                }
            }

            return command

    def report_trade_result(self, pnl: float):
        """Registra resultado de una operacion"""
        with self.lock:
            account = self.active_account
            account.daily_pnl += pnl
            account.total_pnl += pnl
            account.trades_today += 1

            if pnl < 0:
                account.consecutive_losses += 1
                account.martingale_multiplier *= self.martingale_multiplier
                if account.consecutive_losses >= self.max_consecutive_losses:
                    account.status = 'CONSECUTIVE_LIMIT'
                    self.rotate_account()
            else:
                account.consecutive_losses = 0
                account.martingale_multiplier = 1.0

            if account.is_target_reached():
                account.status = 'TARGET_REACHED'
                log.info(f"Account #{account.id} TARGET REACHED: ${account.daily_pnl:.0f}")

            if account.is_loss_limit_reached():
                account.status = 'LOSS_LIMIT'
                log.warning(f"Account #{account.id} LOSS LIMIT: ${account.daily_pnl:.0f}")

    def send_command(self, command: dict):
        """Envia comando al AddOn de Ninja (escribe archivo JSON)"""
        filename = f"cmd_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        filepath = os.path.join(self.commands_path, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(command, f, indent=2)
            log.debug(f"Command sent: {filepath}")
        except Exception as e:
            log.error(f"Error sending command: {e}")

    def read_status(self) -> Optional[dict]:
        """Lee el ultimo estado del AddOn de Ninja"""
        if not os.path.exists(self.status_path):
            return None
        files = sorted(
            [f for f in os.listdir(self.status_path) if f.endswith('.json')],
            reverse=True
        )
        if not files:
            return None
        filepath = os.path.join(self.status_path, files[0])
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None

    def _check_daily_reset(self):
        """Reinicia cuentas al cambiar de dia"""
        today = date.today()
        for account in self.accounts:
            if account.last_reset != today:
                account.reset_daily()

    def get_dashboard_state(self) -> dict:
        """Devuelve estado completo para el dashboard"""
        with self.lock:
            return {
                'active_account_index': self.active_index,
                'paused': self.paused,
                'timestamp': datetime.now().isoformat(),
                'accounts': [a.to_dict() for a in self.accounts],
                'ninja_status': self.read_status()
            }

    def start(self):
        """Inicia el orchestrator"""
        self.watcher_running = True

    def stop(self):
        """Detiene el orchestrator"""
        self.paused = True

    def pause(self):
        """Pausa/Reanuda trading"""
        self.paused = not self.paused
        return self.paused

    def skip_account(self):
        """Salta la cuenta activa manualmente"""
        with self.lock:
            self.rotate_account()
        return self.active_account.id
