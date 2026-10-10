from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Runway:
    near_identifier: str
    far_identifier: str
    fato: bool = False
    gap_before: bool = False

    def label(self) -> str:
        return f"{self.near_identifier}/{self.far_identifier}"


@dataclass(slots=True)
class AirportProfile:
    icao: str
    runways: list[Runway] = field(default_factory=list)
    elevation_ft: int = 0
    verified: bool = True

    def runway_by_identifier(self, identifier: str) -> Runway | None:
        code = identifier.upper()
        return next((r for r in self.runways if code in (r.near_identifier, r.far_identifier)), None)


PROFILES: dict[str, AirportProfile] = {
    "LFBO": AirportProfile(
        icao="LFBO",
        runways=[
            Runway("FATO", "FATO", fato=True),
            Runway("32L", "14R"),
            Runway("32R", "14L", gap_before=True),
        ],
        elevation_ft=500,
        verified=True,
    ),
}


def profile_for(icao: str) -> AirportProfile | None:
    return PROFILES.get(icao.upper())
