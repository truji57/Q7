"""
Q7 Backend - NT8 Bridge Connector (TCP)
"""
import json
import socket
import logging
from threading import Lock

log = logging.getLogger("Q7Backend.Bridge")


class BridgeConnector:
    """Cliente TCP para comunicarse con Q7Bridge AddOn en NinjaTrader"""

    def __init__(self, host: str = "127.0.0.1", port: int = 5556):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._lock = Lock()
        self._connected = False

    def connect(self) -> bool:
        with self._lock:
            try:
                if self._sock:
                    self._sock.close()
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(5)
                self._sock.connect((self.host, self.port))
                self._connected = True
                log.info(f"Connected to NT8 bridge at {self.host}:{self.port}")
                return True
            except Exception as e:
                self._connected = False
                log.warning(f"Bridge not available: {e}")
                return False

    def disconnect(self):
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except:
                    pass
                self._sock = None
                self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def send(self, command: dict) -> dict:
        with self._lock:
            try:
                if not self._sock or not self._connected:
                    self.connect()
                    if not self._connected:
                        return {"success": False, "error": "Bridge not connected"}

                payload = json.dumps(command) + "\n"
                self._sock.sendall(payload.encode())

                response = ""
                self._sock.settimeout(5)
                while True:
                    chunk = self._sock.recv(4096).decode()
                    response += chunk
                    if "\n" in response or not chunk:
                        break

                return json.loads(response.strip())

            except socket.timeout:
                self._connected = False
                return {"success": False, "error": "Timeout"}
            except Exception as e:
                self._connected = False
                log.error(f"Bridge error: {e}")
                return {"success": False, "error": str(e)}

    def ping(self) -> bool:
        r = self.send({"action": "PING"})
        return r.get("success", False) and r.get("data", {}).get("data") == "pong"

    def get_status(self) -> dict:
        return self.send({"action": "STATUS"})

    def open_position(self, account: str, instrument: str, direction: str,
                      contracts: int, sl_ticks: int, tp_ticks: int) -> dict:
        return self.send({
            "action": "OPEN",
            "account": account,
            "instrument": instrument,
            "direction": direction.upper(),
            "contracts": contracts,
            "sl_ticks": sl_ticks,
            "tp_ticks": tp_ticks
        })

    def close_position(self, account: str, instrument: str = None) -> dict:
        return self.send({
            "action": "CLOSE",
            "account": account,
            "instrument": instrument
        })

    def close_all(self, account: str) -> dict:
        return self.send({
            "action": "CLOSE_ALL",
            "account": account
        })
