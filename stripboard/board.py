from __future__ import annotations

from dataclasses import dataclass

from .airport import AirportProfile, Runway

TOTAL_ROWS = 15


@dataclass(slots=True)
class BoardRow:
    kind: str
    label_fr: str = ""
    label_en: str = ""
    runway: Runway | None = None


def _padded(rows: list[BoardRow]) -> list[BoardRow]:
    while len(rows) < TOTAL_ROWS:
        rows.append(BoardRow("spacer"))
    return rows[:TOTAL_ROWS]


def right_column(profile: AirportProfile) -> list[BoardRow]:
    rows = [
        BoardRow("category", "Aéronef en transit", "Overflight aircraft"),
        BoardRow("category", "Aéronef en vol hors du circuit (VFR + IFR)", "Inflight aircraft out of pattern (VFR + IFR)"),
        BoardRow("spacer"),
        BoardRow("spacer"),
        BoardRow("category", "Aéronef dans le circuit (VFR + IFR) non autorisé à l'atterrissage", "Aircraft in pattern (VFR + IFR) not cleared to land"),
    ]
    for runway in profile.runways:
        if runway.gap_before:
            rows.append(BoardRow("category", "Aéronef ou véhicule sur le taxiway", "Aircraft or vehicle on taxiway"))
        rows.append(BoardRow("runway", runway=runway))
    rows.append(BoardRow("category", "Aéronef ou véhicule au point d'attente", "Aircraft or vehicle at holding point"))
    return _padded(rows)


def left_column(profile: AirportProfile) -> list[BoardRow]:
    rows = [
        BoardRow("spacer"),
        BoardRow("category", "Arrivées IFR non identifiées", "IFR arrivals not identified"),
        BoardRow("category", "VFR sous plan de vol (arrivée, transit, départ hélicoptère)", "VFR with flight plan (arrival, transit, helicopter departure)"),
        BoardRow("spacer"),
        BoardRow("spacer"),
        BoardRow("spacer"),
        BoardRow("category", "Hélicoptère ayant mis en route avant translation", "Helicopter with start up clearance before taxiing"),
    ]
    return _padded(rows)
