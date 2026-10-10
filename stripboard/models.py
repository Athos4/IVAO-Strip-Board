from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class FlightStrip:
    callsign: str
    departure: str = ""
    arrival: str = ""
    aircraft: str = ""
    wake_category: str = ""
    route: str = ""
    level: str = ""
    rules: str = ""
    assigned_squawk: str = ""
    current_squawk: str = ""
    assigned_runway: str = ""
    stand: str = ""
    eobt: str = ""
    eta: str = ""
    entry_fix: str = ""
    exit_fix: str = ""
    proc_waypoint: str = ""
    atis: str = ""
    takeoff_time: str = ""
    contact_time: str = ""
    coordination: str = ""
    holding_point: str = ""
    altitude: int | None = None

    @classmethod
    def from_aurora(cls, callsign: str, fp: list[str], pos: list[str] | None) -> "FlightStrip":
        def fp_field(index: int) -> str:
            return fp[index].strip() if index < len(fp) else ""

        def pos_field(index: int) -> str:
            return pos[index].strip() if pos and index < len(pos) else ""

        altitude: int | None = None
        raw_altitude = pos_field(2)
        if raw_altitude:
            try:
                altitude = int(float(raw_altitude))
            except ValueError:
                altitude = None

        return cls(
            callsign=callsign.upper(),
            departure=fp_field(0).upper(),
            arrival=fp_field(1).upper(),
            aircraft=fp_field(4).upper(),
            wake_category=fp_field(5).upper(),
            route=fp_field(13),
            level=pos_field(9),
            rules=fp_field(6).upper(),
            current_squawk=pos_field(6),
            assigned_runway="",
            stand=pos_field(20),
            eobt=fp_field(3),
            eta="",
            entry_fix="",
            exit_fix="",
            proc_waypoint=pos_field(8),
            altitude=altitude,
        )

    def is_vfr(self) -> bool:
        return self.rules == "V"

    def is_airborne(self, field_elevation_ft: int, threshold_ft: int = 1000) -> bool:
        if self.altitude is None:
            return True
        return self.altitude >= field_elevation_ft + threshold_ft

    def phase(self, home_airport: str) -> str:
        airport = home_airport.upper()
        if self.departure == airport and self.arrival == airport:
            return "circuit"
        if self.departure == airport:
            return "departure"
        if self.arrival == airport:
            return "arrival"
        return "transit"

    def bar_colors(self, home_airport: str) -> tuple[str, ...]:
        phase = self.phase(home_airport)
        if phase == "departure":
            return ("out",)
        if phase == "arrival":
            return ("in",)
        if phase == "circuit":
            return ("out", "in")
        return ()


@dataclass(slots=True)
class Placement:
    row: int
    column: int
    span: int = 1
    under: str = ""


@dataclass(slots=True)
class Position:
    name: str
    airports: list[str] = field(default_factory=list)

    def accepts(self, strip: FlightStrip) -> bool:
        codes = {code.upper() for code in self.airports}
        return not codes or strip.departure in codes or strip.arrival in codes


@dataclass(slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 1130
    selected_position: str = "PARIS_APP"
    positions: list[Position] = field(
        default_factory=lambda: [Position("PARIS_APP", ["LFPG", "LFPO", "LFPB"])]
    )

    def current_position(self) -> Position:
        return next((p for p in self.positions if p.name == self.selected_position), self.positions[0])

    def to_dict(self) -> dict:
        return asdict(self)
