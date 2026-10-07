from __future__ import annotations

WAKE_CATEGORIES: dict[str, str] = {
    "A388": "J", "A124": "J", "AN225": "J",
    "A332": "H", "A333": "H", "A338": "H", "A339": "H", "A342": "H", "A343": "H",
    "A345": "H", "A346": "H", "A359": "H", "A35K": "H",
    "B741": "H", "B742": "H", "B743": "H", "B744": "H", "B748": "H",
    "B762": "H", "B763": "H", "B764": "H", "B772": "H", "B773": "H",
    "B778": "H", "B779": "H", "B77L": "H", "B77W": "H", "B788": "H",
    "B789": "H", "B78X": "H", "MD11": "H", "IL96": "H", "A400": "H",
    "C17": "H", "C5": "H", "KC135": "H",
    "A319": "M", "A320": "M", "A321": "M", "A20N": "M", "A21N": "M",
    "B736": "M", "B737": "M", "B738": "M", "B739": "M", "B37M": "M", "B38M": "M", "B39M": "M",
    "B752": "M", "B753": "M", "E170": "M", "E175": "M", "E190": "M", "E195": "M",
    "E290": "M", "E295": "M", "CRJ1": "M", "CRJ2": "M", "CRJ7": "M", "CRJ9": "M", "CRJX": "M",
    "AT43": "M", "AT72": "M", "DH8D": "M", "F100": "M", "F70": "M", "MD80": "M", "MD83": "M",
    "C130": "M", "A748": "M",
    "C172": "L", "C152": "L", "C182": "L", "DA40": "L", "DA42": "L", "SR22": "L",
    "PA28": "L", "PA34": "L", "BE20": "L", "BE36": "L", "TBM9": "L", "P28A": "L",
}


def wake_category(aircraft_icao: str) -> str:
    return WAKE_CATEGORIES.get(aircraft_icao.strip().upper(), "")
