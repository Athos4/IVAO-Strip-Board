from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class FlightStrip:
    callsign: str
    departure: str = ""
    arrival: str = ""
    aircraft: str = ""
    route: str = ""
    level: str = ""

    @classmethod
    def from_message(cls, message: dict) -> "FlightStrip":
        def value(*keys: str) -> str:
            return str(next((message[k] for k in keys if message.get(k) is not None), "")).upper()

        return cls(
            callsign=value("callsign", "call_sign", "cs"),
            departure=value("departure", "dep", "adep"),
            arrival=value("arrival", "destination", "dest", "ades"),
            aircraft=value("aircraft", "aircraft_type", "type_aircraft"),
            route=str(message.get("route", "")),
            level=value("level", "flight_level", "assigned_level"),
        )


@dataclass(slots=True)
class Placement:
    row: int
    column: int
    span: int = 1


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
    port: int = 11300
    selected_position: str = "PARIS_APP"
    positions: list[Position] = field(
        default_factory=lambda: [Position("PARIS_APP", ["LFPG", "LFPO", "LFPB"])]
    )

    def current_position(self) -> Position:
        return next((p for p in self.positions if p.name == self.selected_position), self.positions[0])

    def to_dict(self) -> dict:
        return asdict(self)
