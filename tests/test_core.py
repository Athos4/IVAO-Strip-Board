import json
import tempfile
import unittest
from pathlib import Path

from stripboard.aurora import parse_message
from stripboard.models import FlightStrip, Placement, Position, Settings
from stripboard.store import Store


class ProtocolTests(unittest.TestCase):
    def test_parses_aliases(self):
        kind, strip = parse_message(json.dumps({"callsign": "afr1", "adep": "lfpg", "ades": "lfpo", "flight_level": 120}))
        self.assertEqual(kind, "upsert")
        self.assertEqual((strip.callsign, strip.departure, strip.arrival, strip.level), ("AFR1", "LFPG", "LFPO", "120"))

    def test_delete_and_invalid_messages(self):
        self.assertEqual(parse_message('{"type":"delete","callsign":"afr1"}'), ("delete", "AFR1"))
        self.assertIsNone(parse_message("not json"))
        self.assertIsNone(parse_message("[]"))


class ModelTests(unittest.TestCase):
    def test_position_filter(self):
        position = Position("PARIS", ["LFPG", "LFPO"])
        self.assertTrue(position.accepts(FlightStrip("A", "LFPG", "EGLL")))
        self.assertTrue(position.accepts(FlightStrip("B", "EGLL", "LFPO")))
        self.assertFalse(position.accepts(FlightStrip("C", "EGLL", "EHAM")))

    def test_store_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            settings = Settings("localhost", 9999, "TEST", [Position("TEST", ["LFFF"])])
            store.save_settings(settings)
            store.save_layout({"AFR1": Placement(2, 1, 2)})
            self.assertEqual(store.load_settings(), settings)
            self.assertEqual(store.load_layout(), {"AFR1": Placement(2, 1, 2)})


if __name__ == "__main__":
    unittest.main()
