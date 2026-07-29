"""
Signal Watcher
Monitoriza la carpeta de señales (signals/) en busca de nuevos archivos JSON
generados por el Q7 Signal Engine de NinjaTrader.
"""

import json
import os
import time
import logging
from datetime import datetime

log = logging.getLogger('Q7Orchestrator.Watcher')


class SignalWatcher:
    """Vigila signals/ y procesa cada nueva senal"""

    def __init__(self, signals_path: str, orchestrator):
        self.signals_path = signals_path
        self.orchestrator = orchestrator
        self.processed_dir = os.path.join(signals_path, 'processed')
        self.seen_files = set()
        self.poll_interval = 0.5

    def start(self):
        """Inicia bucle de vigilancia (bloqueante, usar en thread)"""
        log.info(f"SignalWatcher watching: {self.signals_path}")
        os.makedirs(self.processed_dir, exist_ok=True)

        while getattr(self.orchestrator, 'watcher_running', True):
            try:
                self._poll()
            except Exception as e:
                log.error(f"SignalWatcher error: {e}")
            time.sleep(self.poll_interval)

    def _poll(self):
        if not os.path.exists(self.signals_path):
            return

        files = sorted([
            f for f in os.listdir(self.signals_path)
            if f.startswith('signal_') and f.endswith('.json')
        ])

        for filename in files:
            filepath = os.path.join(self.signals_path, filename)

            if filename in self.seen_files:
                continue

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    signal = json.load(f)

                log.info(f"Signal received: {signal.get('action')} | {signal.get('order', {}).get('instrument')}")

                command = self.orchestrator.process_signal(signal)

                if command:
                    self.orchestrator.send_command(command)
                    log.info(
                        f"Sent to account: {command.get('target_account')} | "
                        f"Contracts: {command.get('order', {}).get('contracts')}"
                    )

            except json.JSONDecodeError:
                log.warning(f"Invalid JSON signal: {filename}")
            except Exception as e:
                log.error(f"Error processing signal {filename}: {e}")
            finally:
                self.seen_files.add(filename)
                self._archive_signal(filepath, filename)

    def _archive_signal(self, filepath: str, filename: str):
        try:
            dest = os.path.join(self.processed_dir, filename)
            os.replace(filepath, dest)
        except:
            pass
