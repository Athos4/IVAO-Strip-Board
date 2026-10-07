from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable

from .models import FlightStrip

LINE_END = b"\r\n"
POLL_INTERVAL_S = 15


def parse_line(text: str) -> tuple[str, list[str]] | None:
    if not text or text[0] not in "#$":
        return None
    parts = text.split(";")
    return parts[0], parts[1:]


class AuroraClient:
    def __init__(self, on_message: Callable, on_status: Callable[[str, bool], None]) -> None:
        self.on_message = on_message
        self.on_status = on_status
        self._stop = threading.Event()
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._poll_thread: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self._known: dict[str, dict] = {}

    def connect(self, host: str, port: int) -> None:
        self.disconnect()
        self._stop.clear()
        self._known = {}
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

    def _send(self, command: str) -> None:
        if not self._socket:
            return
        with self._send_lock:
            try:
                self._socket.sendall(command.encode("ascii", errors="replace") + LINE_END)
            except OSError:
                pass

    def _run(self, host: str, port: int) -> None:
        self.on_status("Connexion…", False)
        try:
            with socket.create_connection((host, port), timeout=8) as connection:
                self._socket = connection
                connection.settimeout(1)
                self.on_status("Aurora connecté", True)
                self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
                self._poll_thread.start()
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
                        text = line.decode("ascii", errors="replace").strip("\r\n").strip()
                        if text:
                            self._handle_line(text)
        except OSError as exc:
            if not self._stop.is_set():
                self.on_status(f"Hors ligne — {exc}", False)
        finally:
            self._socket = None
            if not self._stop.is_set():
                self.on_status("Aurora déconnecté", False)

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            self._send("#TR")
            self._stop.wait(POLL_INTERVAL_S)

    def _handle_line(self, text: str) -> None:
        parsed = parse_line(text)
        if parsed is None:
            return
        command, args = parsed
        if command.startswith("$"):
            return
        if command == "#TR":
            self._handle_traffic_list(args)
        elif command == "#FP":
            self._handle_flight_plan(args)
        elif command == "#TRPOS":
            self._handle_position(args)

    def _handle_traffic_list(self, args: list[str]) -> None:
        current = {callsign for callsign in args if callsign}
        previous = set(self._known)
        for callsign in current - previous:
            self._known[callsign] = {}
            self._send(f"#FP;{callsign}")
            self._send(f"#TRPOS;{callsign}")
        for callsign in previous - current:
            self._known.pop(callsign, None)
            self.on_message(("delete", callsign))
        for callsign in current & previous:
            self._send(f"#TRPOS;{callsign}")

    def _handle_flight_plan(self, args: list[str]) -> None:
        if not args:
            return
        callsign, *fp_fields = args
        entry = self._known.setdefault(callsign, {})
        entry["fp"] = fp_fields
        self._emit(callsign)

    def _handle_position(self, args: list[str]) -> None:
        if not args:
            return
        callsign, *pos_fields = args
        entry = self._known.setdefault(callsign, {})
        entry["pos"] = pos_fields
        self._emit(callsign)

    def _emit(self, callsign: str) -> None:
        entry = self._known.get(callsign)
        if not entry or "fp" not in entry:
            return
        strip = FlightStrip.from_aurora(callsign, entry["fp"], entry.get("pos"))
        self.on_message(("upsert", strip))
