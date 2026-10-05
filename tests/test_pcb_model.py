import json
import unittest
from dataclasses import FrozenInstanceError

from antenna_lab.pcb.model import (
    BoardOutline, CopperPolygon, PcbGeometry, PcbPort, PcbTransform, Substrate,
)


def fixture():
    outline = BoardOutline(((0.0, 0.0), (.020, 0.0), (.020, .020), (0.0, .020)))
    return PcbGeometry(
        model="pcb", outline=outline,
        copper=[
            CopperPolygon("A", ((.004, .008), (.009, .008), (.009, .012), (.004, .012)), 0.0),
            CopperPolygon("B", ((.011, .008), (.016, .008), (.016, .012), (.011, .012)), 0.0),
        ],
        substrate=Substrate(outline, -.0016, 0.0, 4.3, .018),
        port=PcbPort("1", (.009, .010), (.011, .010), .001),
    )


class PcbModelTests(unittest.TestCase):
    def test_fixture_bounds_in_metres(self):
        self.assertEqual(fixture().bounds, ((0.0, 0.0, -.0016), (.020, .020, 0.0)))

    def test_bounds_include_copper_and_independent_substrate_outline(self):
        geometry = fixture()
        geometry.copper.append(CopperPolygon("outside", ((-.002, 0), (0, 0), (0, .001)), .003))
        geometry.substrate = Substrate(
            BoardOutline(((0, 0), (.030, 0), (0, .040))), -.002, 0, 4.3, .018)
        self.assertEqual(geometry.bounds, ((-.002, 0, -.002), (.030, .040, .003)))

    def test_json_snapshot_is_deterministic_and_detached(self):
        geometry = fixture()
        data = geometry.as_dict()
        encoded = json.dumps(data, allow_nan=False)
        self.assertEqual(encoded, json.dumps(fixture().as_dict(), allow_nan=False))
        self.assertEqual(json.loads(encoded), data)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["units"], "m")
        self.assertEqual(data["model"], "pcb")
        self.assertEqual(data["port"]["positive_xy_m"], [.011, .010])
        self.assertEqual(data["substrate"]["epsilon_r"], 4.3)
        data["copper"][0]["vertices_xy_m"][0][0] = 999
        data["assumptions"].append("changed")
        self.assertEqual(geometry.copper[0].vertices_xy_m[0][0], .004)
        self.assertEqual(geometry.assumptions, [])

    def test_assumptions_not_shared(self):
        first, second = fixture(), fixture()
        first.assumptions.append("PEC top copper")
        self.assertEqual(second.assumptions, [])

    def test_outline_closure_and_invalid_coordinates(self):
        points = ((0., 0.), (1., 0.), (0., 1.))
        self.assertEqual(BoardOutline(points + (points[0],)).vertices_xy_m[-1], points[0])
        for bad in ((), ((0., 0.),) * 3, ((0., 0.), (1., 0.), (float("nan"), 1.)),
                    ((0., 0.), (1., 0.), (0., float("inf")))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                BoardOutline(bad)

    def test_leaf_records_are_frozen(self):
        geometry = fixture()
        transform = PcbTransform((.001, -.002), .5)
        for record, attribute in ((geometry.outline, "vertices_xy_m"),
                                  (geometry.copper[0], "z_m"),
                                  (geometry.substrate, "epsilon_r"),
                                  (geometry.port, "width_m"),
                                  (transform, "rotation_rad")):
            with self.subTest(record=type(record).__name__), self.assertRaises(FrozenInstanceError):
                setattr(record, attribute, None)


if __name__ == "__main__":
    unittest.main()
