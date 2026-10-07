from __future__ import annotations

import random
import tkinter as tk
from tkinter import messagebox, ttk

from . import board
from .airport import AirportProfile, profile_for
from .aurora import AuroraClient
from .models import FlightStrip, Placement, Position, Settings
from .store import Store
from .wake_turbulence import wake_category

COLORS = {
    "bg": "#182128", "panel": "#24323b", "grid": "#43535d", "strip": "#edc282", "ink": "#000000",
    "accent": "#52b7c8", "warning": "#e08a2a", "label": "#5a4424",
    "out": "#c62828", "in": "#1e5aa8",
    "runway_header": "#8c8f93", "hazard_bg": "#15181c", "hazard_stripe": "#d7c832",
}
ZONES = ("ATTENTE", "COORDONNÉ", "ACTIF", "NON TRAITÉ")
DIVIDER_W = 14
SHIFT_MASK = 0x0001
ATIS_LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

STRIP_WIDTH_MM = 242.0
X_ID_END = 72.5
X_COLOR_END = 75.0
X_ROUTE_END = 134.0
X_LEVEL_END = 194.0
X_ARCHIVE_END = 227.4


STRIP_FONT = "Segoe UI"


def _strip_font_size(height: float, ratio: float) -> int:
    return max(9, round(height * ratio))


class StripBoard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("IVAO Strip Board")
        self.geometry("1680x980")
        self.minsize(1200, 700)
        self.configure(bg=COLORS["bg"])
        self.store = Store()
        self.settings = self.store.load_settings()
        self.layout = self.store.load_layout()
        self.strips: dict[str, FlightStrip] = {}
        self.manual_fields: dict[str, dict[str, str]] = {}
        self.dragged: str | None = None
        self._field_boxes: dict[tuple[str, str], tuple[float, float, float, float]] = {}
        self._active_entry: tuple[tk.Entry, object] | None = None
        self.status = tk.StringVar(value="Hors ligne")
        self.position = tk.StringVar(value=self.settings.selected_position)
        self.view = tk.StringVar(value="grid")
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
        self.view_button = tk.Button(header, text="Tableau de strip", command=self.toggle_view, relief="flat", padx=12)
        self.view_button.pack(side="left", padx=4)
        tk.Label(header, textvariable=self.status, bg=COLORS["panel"], fg="#c4d1d7", font=("Segoe UI", 10)).pack(side="right", padx=22)

        self.labels = tk.Frame(self, bg=COLORS["bg"])
        self.labels.pack(fill="x", padx=20, pady=(16, 4))
        self._build_labels()
        self.canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.canvas.bind("<Configure>", lambda _e: self.draw())
        self.canvas.bind("<ButtonPress-1>", self.begin_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Double-Button-1>", self.toggle_span)
        self.canvas.bind("<ButtonPress-3>", self.archive_strip)

    def _home_profile(self) -> AirportProfile | None:
        for code in self.settings.current_position().airports:
            profile = profile_for(code)
            if profile:
                return profile
        return None

    def _column_count(self) -> int:
        if self.view.get() == "board":
            return 2
        return len(ZONES)

    def _build_labels(self) -> None:
        for widget in self.labels.winfo_children():
            widget.destroy()
        if self.view.get() == "board":
            return
        for title in ZONES:
            tk.Label(self.labels, text=title, bg=COLORS["bg"], fg="#aab8be", font=("Segoe UI", 10, "bold")).pack(side="left", expand=True)

    def toggle_view(self) -> None:
        self.view.set("grid" if self.view.get() == "board" else "board")
        if self.view.get() == "board" and self._home_profile() is None:
            messagebox.showinfo("Tableau de strip", "Aucun profil de pistes pour l'aéroport de cette position.")
            self.view.set("grid")
        self.view_button.config(text="Vue grille" if self.view.get() == "board" else "Tableau de strip")
        self._build_labels()
        self.draw()

    def draw(self) -> None:
        self._close_active_entry()
        self.canvas.delete("all")
        self._field_boxes = {}
        if self.view.get() == "board" and self._home_profile() is not None:
            self._draw_board()
        else:
            self._draw_grid()

    def _draw_grid(self) -> None:
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        columns = self._column_count()
        cw, rh = width / columns, height / 8
        for col in range(columns):
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
            self.canvas.create_text(x1+10, y1+9, anchor="nw", text=callsign, fill=COLORS["ink"], font=(STRIP_FONT, 14, "bold"), tags=(tag, "strip"))
            detail = f"{strip.departure}  →  {strip.arrival}     {strip.aircraft}     {strip.level}\n{strip.route}".strip()
            self.canvas.create_text(x1+10, y1+34, anchor="nw", width=max(80, x2-x1-18), text=detail, fill=COLORS["ink"], font=(STRIP_FONT, 10), tags=(tag, "strip"))
            if placement.span == 2:
                self.canvas.create_text(x2-12, y1+9, anchor="ne", text="↔ 2", fill="#735f27", tags=(tag, "strip"))

    def _draw_gradient_row(self, x1: float, y1: float, x2: float, y2: float) -> None:
        top, bottom = (205, 203, 193), (166, 164, 154)
        steps = 8
        for i in range(steps):
            t0, t1 = i / steps, (i + 1) / steps
            shade = tuple(int(top[k] + (bottom[k] - top[k]) * t0) for k in range(3))
            yk0, yk1 = y1 + (y2 - y1) * t0, y1 + (y2 - y1) * t1
            self.canvas.create_rectangle(x1, yk0, x2, yk1, fill=f"#{shade[0]:02x}{shade[1]:02x}{shade[2]:02x}", width=0)

    def _draw_hazard_stripe(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=COLORS["hazard_bg"], width=0)
        step = 18
        y = y1 - step
        while y < y2 + step:
            self.canvas.create_polygon(x1, y + step, x2, y, x2, y + 7, x1, y + step + 7, fill=COLORS["hazard_stripe"], width=0)
            y += step * 2

    def _draw_board_column(self, rows: list, x0: float, col_w: float, row_h: float, column_index: int, conflicts: set) -> None:
        for i, row_def in enumerate(rows):
            y0, y1 = i * row_h, (i + 1) * row_h
            if row_def.kind in ("spacer", "category"):
                self._draw_gradient_row(x0 + 2, y0 + 1, x0 + col_w - 2, y1 - 1)
            elif row_def.kind == "runway":
                conflict = (column_index, i) in conflicts
                fill = COLORS["warning"] if conflict else COLORS["runway_header"]
                self.canvas.create_rectangle(x0 + 2, y0 + 2, x0 + col_w - 2, y1 - 2, fill=fill, outline="#000000", width=1)
                runway = row_def.runway
                label = "FATO" if runway.fato else "RUNWAY"
                self.canvas.create_text(x0 + col_w / 2, y0 + row_h / 2, text=" ".join(label), fill="#111111", font=("Segoe UI", 13, "italic bold"))
                if not runway.fato:
                    self.canvas.create_text(x0 + 16, y0 + row_h / 2, anchor="w", text=runway.near_identifier, fill="#111111", font=("Segoe UI", 12, "italic bold"))
                    self.canvas.create_text(x0 + col_w - 16, y0 + row_h / 2, anchor="e", text=runway.far_identifier, fill="#111111", font=("Segoe UI", 12, "italic bold"))

    def _draw_board_strip(self, strip: FlightStrip, x0: float, y0: float, col_w: float, row_h: float, home_icao: str) -> None:
        tag = f"strip:{strip.callsign}"
        pad = 2
        x1, y1 = x0 + pad, y0 + pad
        w, h = col_w - 2 * pad, row_h - 2 * pad
        x2, y2 = x1 + w, y1 + h
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=COLORS["strip"], outline="#000000", width=1, tags=(tag, "strip"))

        def mm(value: float) -> float:
            return x1 + w * (value / STRIP_WIDTH_MM)

        x_id_end, x_color_end = mm(X_ID_END), mm(X_COLOR_END)
        x_route_end, x_level_end, x_archive_end = mm(X_ROUTE_END), mm(X_LEVEL_END), mm(X_ARCHIVE_END)

        def fsize(ratio: float) -> int:
            return _strip_font_size(h, ratio)

        def text(x: float, y: float, value: str, ratio: float, *, bold: bool = False, anchor: str = "w", fill: str = COLORS["ink"]) -> None:
            if value:
                self.canvas.create_text(x, y, anchor=anchor, text=value, fill=fill, font=(STRIP_FONT, fsize(ratio), "bold" if bold else "normal"), tags=(tag, "strip"))

        phase = strip.phase(home_icao)
        movement = phase if phase in ("departure", "arrival", "circuit") else "transit"

        colors = strip.bar_colors(home_icao)
        if len(colors) == 1:
            self.canvas.create_rectangle(x_id_end, y1, x_color_end, y2, fill=COLORS[colors[0]], width=0, tags=(tag, "strip"))
        elif len(colors) == 2:
            mid_y = (y1 + y2) / 2
            self.canvas.create_rectangle(x_id_end, y1, x_color_end, mid_y, fill=COLORS[colors[0]], width=0, tags=(tag, "strip"))
            self.canvas.create_rectangle(x_id_end, mid_y, x_color_end, y2, fill=COLORS[colors[1]], width=0, tags=(tag, "strip"))

        text(x1 + w * 0.012, y1 + h * 0.17, strip.callsign, 0.165, bold=True, anchor="w")
        squawk = strip.assigned_squawk if movement in ("departure", "circuit") else strip.current_squawk
        text(x_id_end - w * 0.012, y1 + h * 0.17, squawk, 0.13, bold=True, anchor="e")
        aircraft_text = f"{strip.aircraft} {strip.wake_category}".strip()
        text(x1 + w * 0.012, y1 + h * 0.55, aircraft_text, 0.115, anchor="w")
        dep_arr = f"{strip.departure} {strip.arrival}".strip()
        text(x1 + w * 0.012, y1 + h * 0.92, dep_arr, 0.115, anchor="sw")
        text(x_id_end - w * 0.012, y1 + h * 0.92, strip.rules, 0.13, bold=True, anchor="se")

        route_split = y1 + h * 0.57
        waiting_split = x_color_end + (x_route_end - x_color_end) * 0.76
        self.canvas.create_line(x_color_end, route_split, x_route_end, route_split, fill="#000000", width=1, tags=(tag, "strip"))
        self.canvas.create_line(waiting_split, route_split, waiting_split, y2, fill="#000000", width=1, tags=(tag, "strip"))
        text(x_color_end + (x_route_end - x_color_end) * 0.05, y1 + h * 0.36, strip.proc_waypoint, 0.115, anchor="w")
        self._register_field(strip.callsign, "coordination", x_color_end, route_split, waiting_split, y2, tag)
        text(x_color_end + (waiting_split - x_color_end) * 0.5, route_split + (y2 - route_split) * 0.5, strip.coordination, 0.115, anchor="center")
        self._register_field(strip.callsign, "holding", waiting_split, route_split, x_route_end, y2, tag)
        text(waiting_split + (x_route_end - waiting_split) * 0.5, route_split + (y2 - route_split) * 0.5, strip.holding_point, 0.1, anchor="center")

        level_box = x_route_end, x_level_end
        level_split = y1 + h * 0.62
        text(level_box[0] + (level_box[1] - level_box[0]) * 0.08, y1 + h * 0.43, strip.level, 0.135, bold=True, anchor="w")
        text(level_box[1] - (level_box[1] - level_box[0]) * 0.08, y1 + h * 0.86, strip.stand, 0.115, bold=True, anchor="e")
        self._register_field(strip.callsign, "atis", level_box[0] + (level_box[1] - level_box[0]) * 0.55, y1, level_box[1], level_split, tag)
        text(level_box[1] - (level_box[1] - level_box[0]) * 0.08, y1 + h * 0.2, strip.atis, 0.12, bold=True, anchor="ne")

        archive_mid_x = x_level_end + (x_archive_end - x_level_end) * 0.5
        archive_mid_y = (y1 + y2) / 2
        self.canvas.create_line(archive_mid_x, y1, archive_mid_x, y2, fill="#000000", width=1, tags=(tag, "strip"))
        self.canvas.create_line(x_level_end, archive_mid_y, x_archive_end, archive_mid_y, fill="#000000", width=1, tags=(tag, "strip"))
        eobt_eta = strip.eobt if movement in ("departure", "circuit") else strip.eta
        text(x_level_end + (archive_mid_x - x_level_end) * 0.5, y1 + (archive_mid_y - y1) * 0.5, eobt_eta, 0.105, anchor="center")
        self._register_field(strip.callsign, "runway", archive_mid_x, y1, x_archive_end, archive_mid_y, tag)
        text(archive_mid_x + (x_archive_end - archive_mid_x) * 0.5, y1 + (archive_mid_y - y1) * 0.5, strip.assigned_runway, 0.105, anchor="center")
        self._register_field(strip.callsign, "takeoff", x_level_end, archive_mid_y, archive_mid_x, y2, tag)
        text(x_level_end + (archive_mid_x - x_level_end) * 0.5, archive_mid_y + (y2 - archive_mid_y) * 0.5, strip.takeoff_time, 0.105, anchor="center")
        self._register_field(strip.callsign, "contact", archive_mid_x, archive_mid_y, x_archive_end, y2, tag)
        text(archive_mid_x + (x_archive_end - archive_mid_x) * 0.5, archive_mid_y + (y2 - archive_mid_y) * 0.5, strip.contact_time, 0.105, anchor="center")

        text((x_archive_end + x2) / 2, y1 + h * 0.30, home_icao, 0.115, bold=True, anchor="center")
        text((x_archive_end + x2) / 2, y1 + h * 0.75, strip.rules, 0.085, anchor="center")

        for bx in (x_id_end, x_color_end, x_route_end, x_level_end, x_archive_end):
            self.canvas.create_line(bx, y1, bx, y2, fill="#000000", width=1, tags=(tag, "strip"))

    def _register_field(self, callsign: str, name: str, x1: float, y1: float, x2: float, y2: float, tag: str) -> None:
        self._field_boxes[(callsign, name)] = (x1, y1, x2, y2)
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="", outline="", tags=(tag, "strip", f"field:{callsign}:{name}"))

    def _draw_stacked_pair(self, top: FlightStrip, under: FlightStrip, x0: float, y0: float, col_w: float, row_h: float, home_icao: str) -> None:
        sliver_w = col_w * (X_COLOR_END / STRIP_WIDTH_MM) * 1.08
        self._draw_board_strip(under, x0, y0, col_w, row_h, home_icao)
        self._draw_board_strip(top, x0 + sliver_w, y0, col_w - sliver_w, row_h, home_icao)

    def _draw_board(self) -> None:
        profile = self._home_profile()
        left_rows, right_rows = board.left_column(profile), board.right_column(profile)
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        col_w = (width - DIVIDER_W) / 2
        row_h = height / board.TOTAL_ROWS
        placements: dict[str, Placement] = {}
        occupied: set[tuple[int, int]] = set()
        for callsign in self.strips:
            if not self.settings.current_position().accepts(self.strips[callsign]):
                continue
            placement = self._valid_placement(callsign, occupied)
            if placement.under and placement.under not in self.strips:
                placement.under = ""
                self.store.save_layout(self.layout)
            if not placement.under:
                occupied.add((placement.row, placement.column))
            placements[callsign] = placement
        counts: dict[tuple[int, int], int] = {}
        for placement in placements.values():
            if placement.under:
                continue
            key = (placement.column, placement.row)
            counts[key] = counts.get(key, 0) + 1
        rows_by_column = {0: left_rows, 1: right_rows}
        conflicts = {key for key, count in counts.items() if count > 1 and rows_by_column[key[0]][key[1]].kind == "runway"}
        self._draw_board_column(left_rows, 0, col_w, row_h, 0, conflicts)
        self._draw_board_column(right_rows, col_w + DIVIDER_W, col_w, row_h, 1, conflicts)
        self._draw_hazard_stripe(col_w, 0, col_w + DIVIDER_W, height)
        stacked_under = {placement.under: callsign for callsign, placement in placements.items() if placement.under}
        for callsign, placement in placements.items():
            if placement.under:
                continue
            x0 = (col_w + DIVIDER_W) if placement.column == 1 else 0
            y0 = placement.row * row_h
            under_callsign = stacked_under.get(callsign)
            if under_callsign and under_callsign in self.strips:
                self._draw_stacked_pair(self.strips[callsign], self.strips[under_callsign], x0, y0, col_w, row_h, profile.icao)
            else:
                self._draw_board_strip(self.strips[callsign], x0, y0, col_w, row_h, profile.icao)

    def _layout_key(self, callsign: str) -> str:
        return f"{self.view.get()}:{callsign}"

    def _forget_layout(self, callsign: str) -> None:
        self.layout.pop(f"board:{callsign}", None)
        self.layout.pop(f"grid:{callsign}", None)

    def _valid_placement(self, callsign: str, occupied: set[tuple[int, int]]) -> Placement:
        columns = self._column_count()
        is_board = self.view.get() == "board"
        rows = board.TOTAL_ROWS if is_board else 8
        key = self._layout_key(callsign)
        placement = self.layout.get(key)
        if placement and 0 <= placement.row < rows and 0 <= placement.column < columns and placement.column + placement.span <= columns:
            if placement.under:
                return placement
            cells = {(placement.row, c) for c in range(placement.column, placement.column + placement.span)}
            if not cells & occupied:
                return placement
        default_col = 0 if is_board else columns - 1
        for row in range(rows):
            if (row, default_col) not in occupied:
                placement = Placement(row, default_col)
                self.layout[key] = placement
                return placement
        return Placement(rows - 1, default_col)

    def _occupied_cells(self, exclude: str) -> set[tuple[int, int]]:
        occupied: set[tuple[int, int]] = set()
        for callsign, strip in self.strips.items():
            if callsign == exclude:
                continue
            if not self.settings.current_position().accepts(strip):
                continue
            placement = self._valid_placement(callsign, occupied)
            if not placement.under:
                occupied.update((placement.row, c) for c in range(placement.column, placement.column + placement.span))
        return occupied

    def _primary_callsign_in_cell(self, row: int, col: int) -> str | None:
        for callsign, strip in self.strips.items():
            if not self.settings.current_position().accepts(strip):
                continue
            placement = self.layout.get(self._layout_key(callsign))
            if placement and not placement.under and placement.row == row and placement.column == col:
                return callsign
        return None

    def _is_linked(self, target: str) -> bool:
        return any(p.under == target for p in self.layout.values())

    def _is_conditional(self, callsign: str) -> bool:
        placement = self.layout.get(self._layout_key(callsign))
        if placement and placement.under:
            return True
        return self._is_linked(callsign)

    def _unlink_dependents(self, callsign: str) -> None:
        changed = False
        for placement in self.layout.values():
            if placement.under == callsign:
                placement.under = ""
                changed = True
        if changed:
            self.store.save_layout(self.layout)

    def _is_runway_row(self, col: int, row: int) -> bool:
        profile = self._home_profile()
        if profile is None:
            return False
        rows = board.right_column(profile) if col == 1 else board.left_column(profile)
        return 0 <= row < len(rows) and rows[row].kind == "runway"

    def _callsign_at(self, event) -> str | None:
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        for item in reversed(items):
            for tag in self.canvas.gettags(item):
                if tag.startswith("strip:"):
                    return tag.split(":", 1)[1]
        return None

    def begin_drag(self, event) -> None:
        field = self._field_at(event)
        if field:
            self.dragged = None
            callsign, name = field
            if self._is_conditional(callsign):
                self.status.set(f"{callsign} : édition bloquée (alignement conditionnel)")
                return
            self._edit_field(callsign, name, event)
            return
        self._close_active_entry()
        self.dragged = self._callsign_at(event)

    def end_drag(self, event) -> None:
        if not self.dragged:
            return
        columns = self._column_count()
        is_board = self.view.get() == "board"
        rows = board.TOTAL_ROWS if is_board else 8
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        rh = height / rows
        if is_board:
            col_w = (width - DIVIDER_W) / 2
            col = 0 if event.x < col_w + DIVIDER_W / 2 else 1
        else:
            cw = width / columns
            col = max(0, min(columns - 1, int(event.x / cw)))
        row = max(0, min(rows - 1, int(event.y / rh)))
        key = self._layout_key(self.dragged)
        old = self.layout.get(key, Placement(row, col))
        span = 1 if is_board else min(old.span, columns-col)
        candidate = {(row, c) for c in range(col, col+span)}
        used = self._occupied_cells(self.dragged)
        if candidate & used:
            target = self._primary_callsign_in_cell(row, col) if is_board else None
            can_link = (
                is_board and span == 1 and target and target != self.dragged
                and not self._is_linked(target) and bool(event.state & SHIFT_MASK)
                and self._is_runway_row(col, row)
            )
            if can_link:
                self.layout[key] = Placement(row, col, 1, under=target)
                self._unlink_dependents(self.dragged)
                self.store.save_layout(self.layout)
                self.status.set(f"{self.dragged} aligné sous {target} (dégagement piste conditionné)")
            else:
                self.status.set("Case déjà occupée")
        else:
            self.layout[key] = Placement(row, col, span)
            self._unlink_dependents(self.dragged)
            self.store.save_layout(self.layout)
        self.dragged = None
        self.draw()

    def toggle_span(self, event) -> None:
        if self.view.get() == "board":
            return
        callsign = self._callsign_at(event)
        if not callsign:
            return
        placement = self.layout[self._layout_key(callsign)]
        wanted = 1 if placement.span == 2 else 2
        if placement.column + wanted <= self._column_count():
            used = self._occupied_cells(callsign)
            cells = {(placement.row, c) for c in range(placement.column, placement.column+wanted)}
            if not cells & used:
                placement.span = wanted
                self.store.save_layout(self.layout)
                self.draw()

    def _field_at(self, event) -> tuple[str, str] | None:
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        for item in reversed(items):
            for tag in self.canvas.gettags(item):
                if tag.startswith("field:"):
                    _, callsign, name = tag.split(":", 2)
                    return callsign, name
        return None

    def _edit_field(self, callsign: str, name: str, event) -> None:
        if name == "runway":
            profile = self._home_profile()
            options, seen = [], set()
            for runway in (profile.runways if profile else []):
                for ident in (runway.near_identifier, runway.far_identifier):
                    if ident and ident != "FATO" and ident not in seen:
                        seen.add(ident)
                        options.append(ident)
            self._open_dropdown(event, options, lambda value: self._apply_field(callsign, "assigned_runway", value))
        elif name == "atis":
            self._open_dropdown(event, ATIS_LETTERS, lambda value: self._apply_field(callsign, "atis", value))
        elif name == "takeoff":
            self._open_text_entry(callsign, name, "takeoff_time")
        elif name == "contact":
            self._open_text_entry(callsign, name, "contact_time")
        elif name == "holding":
            self._open_text_entry(callsign, name, "holding_point")
        elif name == "coordination":
            self._open_text_entry(callsign, name, "coordination")

    def _open_dropdown(self, event, options: list[str], on_select) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="(vide)", command=lambda: on_select(""))
        for option in options:
            menu.add_command(label=option, command=lambda v=option: on_select(v))
        menu.tk_popup(event.x_root, event.y_root)

    def _open_text_entry(self, callsign: str, field_name: str, attr: str) -> None:
        self._close_active_entry()
        box = self._field_boxes.get((callsign, field_name))
        strip = self.strips.get(callsign)
        if box is None or strip is None:
            return
        x1, y1, x2, y2 = box
        var = tk.StringVar(value=getattr(strip, attr))
        entry = tk.Entry(self.canvas, textvariable=var, justify="center", font=(STRIP_FONT, 10), relief="solid", bd=1)
        self.canvas.create_window((x1 + x2) / 2, (y1 + y2) / 2, window=entry, width=max(24, x2 - x1 - 4), height=max(16, y2 - y1 - 4))
        entry.focus_set()
        entry.selection_range(0, "end")

        def commit() -> None:
            value = var.get().strip()
            if entry.winfo_exists():
                entry.destroy()
            self._apply_field(callsign, attr, value)

        def on_commit(_event=None) -> None:
            self._active_entry = None
            commit()

        def on_cancel(_event=None) -> None:
            self._active_entry = None
            if entry.winfo_exists():
                entry.destroy()
            self.draw()

        entry.bind("<Return>", on_commit)
        entry.bind("<FocusOut>", on_commit)
        entry.bind("<Escape>", on_cancel)
        self._active_entry = (entry, commit)

    def _close_active_entry(self) -> None:
        active = self._active_entry
        if active is None:
            return
        self._active_entry = None
        entry, commit_fn = active
        if entry.winfo_exists():
            commit_fn()

    def _apply_field(self, callsign: str, attr: str, value: str) -> None:
        strip = self.strips.get(callsign)
        if strip is None:
            return
        setattr(strip, attr, value)
        self.manual_fields.setdefault(callsign, {})[attr] = value
        self.draw()

    def _network_message(self, message) -> None:
        self.after(0, self.apply_message, message)

    def _network_status(self, text: str, _connected: bool) -> None:
        self.after(0, self.status.set, text)

    def apply_message(self, message) -> None:
        kind, value = message
        if kind == "delete":
            strip = self.strips.get(value)
            if strip is not None and not self._is_airborne(strip):
                self.strips.pop(value, None)
                self.manual_fields.pop(value, None)
                self._forget_layout(value)
        else:
            for attr, override in self.manual_fields.get(value.callsign, {}).items():
                setattr(value, attr, override)
            self.strips[value.callsign] = value
        self.draw()

    def _is_airborne(self, strip: FlightStrip) -> bool:
        profile = next((p for p in (profile_for(strip.departure), profile_for(strip.arrival)) if p is not None), None)
        if profile is None:
            return True
        return strip.is_airborne(profile.elevation_ft)

    def archive_strip(self, event) -> None:
        callsign = self._callsign_at(event)
        if not callsign:
            return
        self.strips.pop(callsign, None)
        self.manual_fields.pop(callsign, None)
        self._forget_layout(callsign)
        self._unlink_dependents(callsign)
        self.store.save_layout(self.layout)
        self.status.set(f"{callsign} archivé")
        self.draw()

    def connect(self) -> None:
        self.client.connect(self.settings.host, self.settings.port)

    def change_position(self) -> None:
        if not self.settings.positions:
            return
        self.settings.selected_position = self.position.get()
        self.store.save_settings(self.settings)
        if self.view.get() == "board" and self._home_profile() is None:
            self.view.set("grid")
            self.view_button.config(text="Tableau de strip")
        self._build_labels()
        self.draw()

    def simulate(self) -> None:
        home = self.settings.current_position().airports or ["LFPG"]
        others = [a for a in ("LFPG", "LFPO", "LEMH", "LFSB", "EHAM", "EGLL", "LFBD", "LFMN") if a not in home]
        home_airport, other_airport = random.choice(home), random.choice(others)
        departure, arrival = (home_airport, other_airport) if random.random() < 0.5 else (other_airport, home_airport)
        callsign = random.choice(("AFR", "EZY", "RYR", "TVF")) + str(random.randint(100, 999))
        aircraft = random.choice(("A320", "B738", "E190"))
        strip = FlightStrip(callsign, departure, arrival, aircraft, wake_category(aircraft), "DCT OKIPA", random.choice(("FL080", "FL120", "FL180")))
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
                self._build_labels()
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
