from __future__ import annotations

import random
import tkinter as tk
from tkinter import messagebox, ttk

from .aurora import AuroraClient
from .models import FlightStrip, Placement, Position, Settings
from .store import Store

COLORS = {"bg": "#182128", "panel": "#24323b", "grid": "#43535d", "strip": "#f4d77b", "ink": "#172027", "accent": "#52b7c8"}


class StripBoard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("IVAO Strip Board")
        self.geometry("1180x760")
        self.minsize(900, 600)
        self.configure(bg=COLORS["bg"])
        self.store = Store()
        self.settings = self.store.load_settings()
        self.layout = self.store.load_layout()
        self.strips: dict[str, FlightStrip] = {}
        self.dragged: str | None = None
        self.status = tk.StringVar(value="Hors ligne")
        self.position = tk.StringVar(value=self.settings.selected_position)
        self.client = AuroraClient(self._network_message, self._network_status)
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self) -> None:
        header = tk.Frame(self, bg=COLORS["panel"], height=66)
        header.pack(fill="x")
        tk.Label(header, text="IVAO  STRIP BOARD", bg=COLORS["panel"], fg="white", font=("Segoe UI", 17, "bold")).pack(side="left", padx=22)
        ttk.Combobox(header, textvariable=self.position, values=[p.name for p in self.settings.positions], state="readonly", width=18).pack(side="left", padx=12)
        self.position.trace_add("write", lambda *_: self.change_position())
        tk.Button(header, text="Connecter", command=self.connect, bg=COLORS["accent"], relief="flat", padx=15).pack(side="left", padx=4)
        tk.Button(header, text="Configuration", command=self.configure_dialog, relief="flat", padx=12).pack(side="left", padx=4)
        tk.Button(header, text="+ Simuler un vol", command=self.simulate, relief="flat", padx=12).pack(side="left", padx=4)
        tk.Label(header, textvariable=self.status, bg=COLORS["panel"], fg="#c4d1d7", font=("Segoe UI", 10)).pack(side="right", padx=22)

        labels = tk.Frame(self, bg=COLORS["bg"])
        labels.pack(fill="x", padx=20, pady=(16, 4))
        for title in ("ATTENTE", "COORDONNÉ", "ACTIF", "NON TRAITÉ"):
            tk.Label(labels, text=title, bg=COLORS["bg"], fg="#aab8be", font=("Segoe UI", 10, "bold")).pack(side="left", expand=True)
        self.canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.canvas.bind("<Configure>", lambda _e: self.draw())
        self.canvas.bind("<ButtonPress-1>", self.begin_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Double-Button-1>", self.toggle_span)

    def draw(self) -> None:
        self.canvas.delete("all")
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        cw, rh = width / 4, height / 8
        for col in range(4):
            for row in range(8):
                self.canvas.create_rectangle(col*cw+3, row*rh+3, (col+1)*cw-3, (row+1)*rh-3, outline=COLORS["grid"], width=1)
        occupied: set[tuple[int, int]] = set()
        for callsign, strip in self.strips.items():
            if not self.settings.current_position().accepts(strip):
                continue
            placement = self._valid_placement(callsign, occupied)
            occupied.update((placement.row, c) for c in range(placement.column, placement.column + placement.span))
            x1, y1 = placement.column*cw+7, placement.row*rh+7
            x2, y2 = (placement.column+placement.span)*cw-7, (placement.row+1)*rh-7
            tag = f"strip:{callsign}"
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=COLORS["strip"], outline="#b89d49", width=2, tags=(tag, "strip"))
            self.canvas.create_text(x1+10, y1+9, anchor="nw", text=callsign, fill=COLORS["ink"], font=("Consolas", 13, "bold"), tags=(tag, "strip"))
            detail = f"{strip.departure}  →  {strip.arrival}     {strip.aircraft}     {strip.level}\n{strip.route}".strip()
            self.canvas.create_text(x1+10, y1+34, anchor="nw", width=max(80, x2-x1-18), text=detail, fill=COLORS["ink"], font=("Segoe UI", 9), tags=(tag, "strip"))
            if placement.span == 2:
                self.canvas.create_text(x2-12, y1+9, anchor="ne", text="↔ 2", fill="#735f27", tags=(tag, "strip"))

    def _valid_placement(self, callsign: str, occupied: set[tuple[int, int]]) -> Placement:
        placement = self.layout.get(callsign)
        if placement and 0 <= placement.row < 8 and 0 <= placement.column < 4 and placement.column + placement.span <= 4:
            cells = {(placement.row, c) for c in range(placement.column, placement.column + placement.span)}
            if not cells & occupied:
                return placement
        for row in range(8):
            if (row, 3) not in occupied:
                placement = Placement(row, 3)
                self.layout[callsign] = placement
                return placement
        return Placement(7, 3)

    def _callsign_at(self, event) -> str | None:
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        for item in reversed(items):
            for tag in self.canvas.gettags(item):
                if tag.startswith("strip:"):
                    return tag.split(":", 1)[1]
        return None

    def begin_drag(self, event) -> None:
        self.dragged = self._callsign_at(event)

    def end_drag(self, event) -> None:
        if not self.dragged:
            return
        cw, rh = self.canvas.winfo_width()/4, self.canvas.winfo_height()/8
        col, row = max(0, min(3, int(event.x/cw))), max(0, min(7, int(event.y/rh)))
        old = self.layout.get(self.dragged, Placement(row, col))
        span = min(old.span, 4-col)
        candidate = {(row, c) for c in range(col, col+span)}
        used = {(p.row, c) for key, p in self.layout.items() if key != self.dragged for c in range(p.column, p.column+p.span)}
        if candidate & used:
            self.status.set("Case déjà occupée")
        else:
            self.layout[self.dragged] = Placement(row, col, span)
            self.store.save_layout(self.layout)
        self.dragged = None
        self.draw()

    def toggle_span(self, event) -> None:
        callsign = self._callsign_at(event)
        if not callsign:
            return
        placement = self.layout[callsign]
        wanted = 1 if placement.span == 2 else 2
        if placement.column + wanted <= 4:
            used = {(p.row, c) for key, p in self.layout.items() if key != callsign for c in range(p.column, p.column+p.span)}
            cells = {(placement.row, c) for c in range(placement.column, placement.column+wanted)}
            if not cells & used:
                placement.span = wanted
                self.store.save_layout(self.layout)
                self.draw()

    def _network_message(self, message) -> None:
        self.after(0, self.apply_message, message)

    def _network_status(self, text: str, _connected: bool) -> None:
        self.after(0, self.status.set, text)

    def apply_message(self, message) -> None:
        kind, value = message
        if kind == "delete":
            self.strips.pop(value, None)
            self.layout.pop(value, None)
        else:
            self.strips[value.callsign] = value
        self.draw()

    def connect(self) -> None:
        self.client.connect(self.settings.host, self.settings.port)

    def change_position(self) -> None:
        if not self.settings.positions:
            return
        self.settings.selected_position = self.position.get()
        self.store.save_settings(self.settings)
        self.draw()

    def simulate(self) -> None:
        airports = self.settings.current_position().airports or ["LFPG", "LFPO"]
        callsign = random.choice(("AFR", "EZY", "RYR", "TVF")) + str(random.randint(100, 999))
        strip = FlightStrip(callsign, random.choice(airports), random.choice(airports), random.choice(("A320", "B738", "E190")), "DCT OKIPA", random.choice(("FL080", "FL120", "FL180")))
        self.apply_message(("upsert", strip))

    def configure_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Configuration")
        dialog.geometry("520x390")
        dialog.transient(self)
        dialog.grab_set()
        fields = tk.Frame(dialog, padx=20, pady=18)
        fields.pack(fill="both", expand=True)
        host, port = tk.StringVar(value=self.settings.host), tk.StringVar(value=str(self.settings.port))
        tk.Label(fields, text="Adresse Aurora").grid(row=0, column=0, sticky="w", pady=5)
        tk.Entry(fields, textvariable=host, width=28).grid(row=0, column=1, sticky="ew")
        tk.Label(fields, text="Port TCP").grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(fields, textvariable=port).grid(row=1, column=1, sticky="ew")
        tk.Label(fields, text="Positions (une par ligne : NOM = LFPG, LFPO)").grid(row=2, column=0, columnspan=2, sticky="w", pady=(18, 5))
        editor = tk.Text(fields, height=10, font=("Consolas", 10))
        editor.grid(row=3, column=0, columnspan=2, sticky="nsew")
        editor.insert("1.0", "\n".join(f"{p.name} = {', '.join(p.airports)}" for p in self.settings.positions))
        fields.columnconfigure(1, weight=1)
        fields.rowconfigure(3, weight=1)

        def save() -> None:
            try:
                parsed = []
                for line in editor.get("1.0", "end").splitlines():
                    if not line.strip():
                        continue
                    name, separator, codes = line.partition("=")
                    if not separator or not name.strip():
                        raise ValueError("Format de position invalide")
                    parsed.append(Position(name.strip().upper(), [c.strip().upper() for c in codes.split(",") if c.strip()]))
                if not parsed:
                    raise ValueError("Ajoutez au moins une position")
                self.settings = Settings(host.get().strip(), int(port.get()), parsed[0].name, parsed)
                self.position.set(parsed[0].name)
                self.store.save_settings(self.settings)
                dialog.destroy()
                self._build_position_values()
                self.draw()
            except ValueError as exc:
                messagebox.showerror("Configuration", str(exc), parent=dialog)

        tk.Button(dialog, text="Enregistrer", command=save, bg=COLORS["accent"], relief="flat", padx=18, pady=7).pack(pady=12)

    def _build_position_values(self) -> None:
        for widget in self.winfo_children()[0].winfo_children():
            if isinstance(widget, ttk.Combobox):
                widget.configure(values=[p.name for p in self.settings.positions])

    def close(self) -> None:
        self.client.disconnect()
        self.store.save_layout(self.layout)
        self.destroy()


def main() -> None:
    StripBoard().mainloop()
