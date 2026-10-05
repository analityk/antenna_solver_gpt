from dataclasses import replace
from itertools import combinations
from math import cos, sin, radians, hypot
import unittest

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import BoardOutline
from antenna_lab.pcb.transform import normalize_port_orientation, inverse_transform_geometry
from antenna_lab.pcb.validation import validate_pcb_geometry
from test_pcb_model import fixture

# Double-precision comparisons for a 20 mm PCB, including offsets of metres.
# These are stricter than PCB-002's geometric membership tolerance (1e-10 m).
COORDINATE_TOL_M = 1e-14
AREA_TOL_M2 = 1e-16
ANGLE_TOL_RAD = 1e-12


def placed_fixture(degrees=0, offset=(0., 0.)):
    """Independent test placement: center fixture, rotate, then translate."""
    geometry = fixture()
    c, s = cos(radians(degrees)), sin(radians(degrees))

    def point(p):
        x, y = p[0] - .010, p[1] - .010
        return (c * x - s * y + offset[0], s * x + c * y + offset[1])

    geometry.outline = BoardOutline(tuple(point(p) for p in geometry.outline.vertices_xy_m))
    geometry.substrate = replace(geometry.substrate, outline=geometry.outline)
    geometry.copper = [replace(v, vertices_xy_m=tuple(point(p) for p in v.vertices_xy_m))
                       for v in geometry.copper]
    geometry.port = replace(geometry.port, negative_xy_m=point((.009, .010)),
                            positive_xy_m=point((.011, .010)))
    return geometry


def points(geometry):
    return (list(geometry.outline.vertices_xy_m) + list(geometry.substrate.outline.vertices_xy_m)
            + [p for copper in geometry.copper for p in copper.vertices_xy_m]
            + [geometry.port.negative_xy_m, geometry.port.positive_xy_m])


def area(vertices):
    ox, oy = vertices[0]
    shifted = [(x - ox, y - oy) for x, y in vertices]
    return abs(sum(a[0] * b[1] - b[0] * a[1]
                   for a, b in zip(shifted, shifted[1:] + shifted[:1]))) / 2


class PcbTransformTests(unittest.TestCase):
    def assert_point_close(self, a, b):
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, delta=COORDINATE_TOL_M)

    def assert_normalized(self, geometry):
        a, b = geometry.port.negative_xy_m, geometry.port.positive_xy_m
        self.assertLess(a[0], 0)
        self.assertGreater(b[0], 0)
        self.assertAlmostEqual(a[1], 0, delta=COORDINATE_TOL_M)
        self.assertAlmostEqual(b[1], 0, delta=COORDINATE_TOL_M)
        self.assertAlmostEqual(a[0] + b[0], 0, delta=COORDINATE_TOL_M)
        validate_pcb_geometry(geometry)

    def test_already_normalized(self):
        original = placed_fixture()
        # Exact requested input coordinates, not values obtained by subtraction.
        original.port = replace(original.port, negative_xy_m=(-.001, 0.), positive_xy_m=(.001, 0.))
        result, metadata = normalize_port_orientation(original)
        self.assert_normalized(result)
        self.assertEqual(metadata.translation_xy_m, (0., 0.))
        self.assertEqual(metadata.rotation_rad, 0.)
        self.assertEqual(result.as_dict(), original.as_dict())

    def test_negative_x_and_vertical(self):
        for degrees in (180, 90, -90):
            with self.subTest(degrees=degrees):
                result, _ = normalize_port_orientation(placed_fixture(degrees))
                self.assert_normalized(result)

    def test_arbitrary_angle_and_far_offset_validation_residue(self):
        # Endpoints lie exactly on copper edges before rotation; strict PCB-002
        # membership must survive rotation residue without tolerance changes.
        for offset in ((0., 0.), (12.345, -6.789)):
            with self.subTest(offset=offset):
                original = placed_fixture(37, offset)
                validate_pcb_geometry(original)
                result, metadata = normalize_port_orientation(original)
                self.assert_normalized(result)
                self.assert_point_close(metadata.translation_xy_m, tuple(-v for v in offset))
                self.assertAlmostEqual(metadata.rotation_rad, -radians(37), delta=ANGLE_TOL_RAD)

    def test_all_pairwise_distances_and_port_length(self):
        original = placed_fixture(37, (12.345, -6.789))
        result, _ = normalize_port_orientation(original)
        for (a, b), (c, d) in zip(combinations(points(original), 2), combinations(points(result), 2)):
            self.assertAlmostEqual(hypot(a[0] - b[0], a[1] - b[1]),
                                   hypot(c[0] - d[0], c[1] - d[1]), delta=COORDINATE_TOL_M)

    def test_polygon_areas(self):
        original = placed_fixture(37, (12.345, -6.789))
        result, _ = normalize_port_orientation(original)
        for a, b in zip([original.outline, original.substrate.outline] + original.copper,
                        [result.outline, result.substrate.outline] + result.copper):
            self.assertAlmostEqual(area(a.vertices_xy_m), area(b.vertices_xy_m), delta=AREA_TOL_M2)

    def test_metadata_reproduces_every_coordinate(self):
        original = placed_fixture(37, (2.3, -1.7))
        result, metadata = normalize_port_orientation(original)
        c, s = cos(metadata.rotation_rad), sin(metadata.rotation_rad)
        for p, actual in zip(points(original), points(result)):
            x, y = (p[i] + metadata.translation_xy_m[i] for i in range(2))
            self.assert_point_close(actual, (c * x - s * y, s * x + c * y))
        again, metadata_again = normalize_port_orientation(original)
        self.assertEqual(result.as_dict(), again.as_dict())
        self.assertEqual(metadata, metadata_again)

    def test_physical_properties_and_no_mutation(self):
        original = placed_fixture(37)
        original.assumptions.append("PEC")
        original.copper[0] = replace(original.copper[0], z_m=1e-12)
        before = original.as_dict()
        result, metadata = normalize_port_orientation(original)
        restored = inverse_transform_geometry(result, metadata)
        self.assertEqual(original.as_dict(), before)
        for value in (result, restored):
            self.assertIsNot(value, original)
            for key in ("model", "assumptions"):
                self.assertEqual(getattr(value, key), getattr(original, key))
            for key in ("z_min_m", "z_max_m", "epsilon_r", "loss_tangent"):
                self.assertEqual(getattr(value.substrate, key), getattr(original.substrate, key))
            self.assertEqual(value.port.id, original.port.id)
            self.assertEqual(value.port.width_m, original.port.width_m)
            self.assertEqual([(v.id, v.z_m) for v in value.copper],
                             [(v.id, v.z_m) for v in original.copper])
        result.assumptions.append("independent")
        result.copper.clear()
        self.assertEqual(original.as_dict(), before)

    def test_round_trip_and_inverse_does_not_mutate(self):
        original = placed_fixture(37, (12.345, -6.789))
        # Preserve distinct, equivalent substrate vertex ordering too.
        original.substrate = replace(original.substrate, outline=BoardOutline(
            tuple(reversed(original.substrate.outline.vertices_xy_m))))
        result, metadata = normalize_port_orientation(original)
        before = result.as_dict()
        restored = inverse_transform_geometry(result, metadata)
        self.assertEqual(result.as_dict(), before)
        for a, b in zip(points(original), points(restored)):
            self.assert_point_close(a, b)
        validate_pcb_geometry(restored)

    def test_invalid_geometry_propagates_validation_error(self):
        original = placed_fixture()
        original.port = replace(original.port, width_m=0)
        with self.assertRaisesRegex(ConfigurationError, "port.width_m"):
            normalize_port_orientation(original)


if __name__ == "__main__":
    unittest.main()
