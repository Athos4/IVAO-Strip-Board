import tempfile
import unittest
from pathlib import Path

from stripboard.aurora import parse_line
from stripboard.models import FlightStrip, Placement, Position, Settings
from stripboard.store import Store


class ProtocolTests(unittest.TestCase):
    def test_parses_traffic_list(self):
        self.assertEqual(parse_line("#TR;AFR1;BAW2;"), ("#TR", ["AFR1", "BAW2", ""]))

    def test_parses_error_and_invalid_lines(self):
        self.assertEqual(parse_line("$ERR;unknown command"), ("$ERR", ["unknown command"]))
        self.assertIsNone(parse_line("not aurora"))
        self.assertIsNone(parse_line(""))

    def test_builds_strip_from_flight_plan_and_position(self):
        fp = ["LFPG", "LFPO", "", "", "A320"] + [""] * 4 + ["120"] + [""] * 4
        pos = ["090", "090", "3500"] + [""] * 6 + ["F120"]
        strip = FlightStrip.from_aurora("afr1", fp, pos)
        self.assertEqual((strip.callsign, strip.departure, strip.arrival, strip.aircraft, strip.level, strip.altitude),
                          ("AFR1", "LFPG", "LFPO", "A320", "F120", 3500))


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
