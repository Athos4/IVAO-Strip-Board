from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable

from .models import FlightStrip


def parse_message(line: str) -> tuple[str, FlightStrip | str] | None:
    """Translate one newline-delimited Aurora adapter message."""
    try:
        message = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(message, dict):
        return None
    kind = str(message.get("type", "strip")).lower()
    callsign = str(message.get("callsign", message.get("call_sign", ""))).upper()
    if kind in {"delete", "remove", "flight_deleted"}:
        return ("delete", callsign) if callsign else None
    strip = FlightStrip.from_message(message)
    return ("upsert", strip) if strip.callsign else None


class AuroraClient:
    def __init__(self, on_message: Callable, on_status: Callable[[str, bool], None]) -> None:
        self.on_message = on_message
        self.on_status = on_status
        self._stop = threading.Event()
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def connect(self, host: str, port: int) -> None:
        self.disconnect()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(host, port), daemon=True)
        self._thread.start()

    def disconnect(self) -> None:
        self._stop.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        self._socket = None

    def _run(self, host: str, port: int) -> None:
        self.on_status("Connexion…", False)
        try:
            with socket.create_connection((host, port), timeout=8) as connection:
                self._socket = connection
                connection.settimeout(1)
                self.on_status("Aurora connecté", True)
                buffer = b""
                while not self._stop.is_set():
                    try:
                        chunk = connection.recv(8192)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        parsed = parse_message(line.decode("utf-8", errors="replace").strip())
                        if parsed:
                            self.on_message(parsed)
        except OSError as exc:
            if not self._stop.is_set():
                self.on_status(f"Hors ligne — {exc}", False)
        finally:
            self._socket = None
            if not self._stop.is_set():
                self.on_status("Aurora déconnecté", False)
