from dataclasses import replace
import unittest

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import BoardOutline
from antenna_lab.pcb.validation import TOLERANCE_M, validate_pcb_geometry
from test_pcb_model import fixture


class PcbValidationTests(unittest.TestCase):
    def assert_invalid(self, geometry, message):
        with self.assertRaisesRegex(ConfigurationError, message):
            validate_pcb_geometry(geometry)

    def test_fixture_boundary_membership_and_no_mutation(self):
        geometry = fixture()
        before = geometry.as_dict()
        result = validate_pcb_geometry(geometry)
        self.assertEqual(result, {"geometry_status": "passed",
                                 "electromagnetic_status": "unverified", "copper_count": 2})
        self.assertEqual(geometry.as_dict(), before)

    def test_interior_and_vertex_membership(self):
        for negative, positive in (((.008, .010), (.012, .010)),
                                   ((.009, .008), (.011, .008))):
            geometry = fixture()
            geometry.port = replace(geometry.port, negative_xy_m=negative, positive_xy_m=positive)
            validate_pcb_geometry(geometry)

    def test_empty_copper(self):
        geometry = fixture()
        geometry.copper = []
        self.assert_invalid(geometry, "copper")

    def test_bad_substrate(self):
        for changes in ({"z_min_m": 0}, {"z_min_m": .001},
                        {"epsilon_r": .99}, {"loss_tangent": -.01}, {"z_max_m": .001}):
            with self.subTest(changes=changes):
                geometry = fixture()
                geometry.substrate = replace(geometry.substrate, **changes)
                self.assert_invalid(geometry, "substrate")

    def test_bad_width(self):
        for width in (0, -.001):
            geometry = fixture()
            geometry.port = replace(geometry.port, width_m=width)
            self.assert_invalid(geometry, "port.width_m")

    def test_coincident_port(self):
        geometry = fixture()
        geometry.port = replace(geometry.port, positive_xy_m=geometry.port.negative_xy_m)
        self.assert_invalid(geometry, "końce muszą być różne")

    def test_off_copper(self):
        geometry = fixture()
        geometry.port = replace(geometry.port, negative_xy_m=(.010, .010))
        self.assert_invalid(geometry, "port.negative")

    def test_same_conductor_loop_with_clear_local_gap(self):
        geometry = fixture()
        # One U-shaped copper polygon joins the terminals away from the feed.
        geometry.copper = [replace(geometry.copper[0], vertices_xy_m=(
            (.004,.008),(.009,.008),(.009,.012),(.011,.012),
            (.011,.008),(.016,.008),(.016,.014),(.004,.014)))]
        self.assertEqual(validate_pcb_geometry(geometry)['copper_count'], 1)

    def test_ambiguous_membership(self):
        geometry = fixture()
        geometry.copper.append(replace(geometry.copper[0], id="overlap"))
        self.assert_invalid(geometry, "dokładnie jednej")

    def test_endpoint_outside_board_even_on_copper(self):
        geometry = fixture()
        geometry.copper[0] = replace(geometry.copper[0], vertices_xy_m=
                                    ((-.004, .008), (.009, .008), (.009, .012), (-.004, .012)))
        geometry.port = replace(geometry.port, negative_xy_m=(-.001, .010))
        self.assert_invalid(geometry, "poza obrysem")

    def test_degenerate_and_non_simple_polygons(self):
        invalid = [(), ((0., 0.),) * 3, ((0., 0.), (.001, 0.), (.002, 0.)),
                   ((0., 0.), (.003, .003), (0., .003), (.002, 0.)),
                   ((0., 0.), (.003, 0.), (.001, 0.), (.003, .003), (0., .003)),
                   ((0., 0.), (.003, 0.), (.003, 0.), (0., .003))]
        for vertices in invalid:
            with self.subTest(vertices=vertices):
                geometry = fixture()
                geometry.copper[0] = replace(geometry.copper[0], vertices_xy_m=vertices)
                self.assert_invalid(geometry, "copper")
        # BoardOutline permits these at construction; validation must reject.
        for vertices in invalid[2:]:
            geometry = fixture()
            geometry.outline = BoardOutline(vertices)
            self.assert_invalid(geometry, "outline")

    def test_nonadjacent_near_contact_keeps_distance_tolerance(self):
        from antenna_lab.pcb.validation import _polygon
        # A narrow open notch is GEOS-valid but unresolved at the old tolerance.
        for gap, valid in ((TOLERANCE_M / 2, False), (TOLERANCE_M * 4, True)):
            ring = ((0.,0.),(.01,0.),(.01,.01),(.005+gap,.01),
                    (.005+gap,.002),(.005,.002),(.005,.01),(0.,.01))
            if valid:
                _polygon(ring, "notch")
            else:
                with self.assertRaises(ConfigurationError):
                    _polygon(ring, "notch")

    def test_polygon_validation_does_not_scan_distant_edge_pairs(self):
        from math import cos, sin, pi
        from unittest.mock import patch
        from antenna_lab.pcb import validation
        ring = tuple((.01*cos(2*pi*i/256), .01*sin(2*pi*i/256)) for i in range(256))
        with patch.object(validation, "_intersect", wraps=validation._intersect) as intersect:
            validation._polygon(ring, "ring")
        self.assertEqual(intersect.call_count, 0)

    def test_nonfinite_values(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            for field in ("z_min_m", "z_max_m", "epsilon_r", "loss_tangent"):
                with self.subTest(value=value, field=field):
                    geometry = fixture()
                    geometry.substrate = replace(geometry.substrate, **{field: value})
                    self.assert_invalid(geometry, "substrate")
            for changes in ({"width_m": value}, {"negative_xy_m": (value, .010)},
                            {"positive_xy_m": (.011, value)}):
                geometry = fixture()
                geometry.port = replace(geometry.port, **changes)
                self.assert_invalid(geometry, "port")
            for changes in ({"z_m": value}, {"vertices_xy_m": ((value, 0), (.01, 0), (0, .01))}):
                geometry = fixture()
                geometry.copper[0] = replace(geometry.copper[0], **changes)
                self.assert_invalid(geometry, "copper")

    def test_empty_ids_and_wrong_model(self):
        for id_value in ("", "  ", None):
            geometry = fixture()
            geometry.copper[0] = replace(geometry.copper[0], id=id_value)
            self.assert_invalid(geometry, "id")
            geometry = fixture()
            geometry.port = replace(geometry.port, id=id_value)
            self.assert_invalid(geometry, "id")
        geometry = fixture()
        geometry.model = "biquad"
        self.assert_invalid(geometry, "model")

    def test_top_plane_tolerance_without_snapping(self):
        geometry = fixture()
        geometry.copper[0] = replace(geometry.copper[0], z_m=TOLERANCE_M / 2)
        before = geometry.as_dict()
        validate_pcb_geometry(geometry)
        self.assertEqual(geometry.as_dict(), before)
        geometry.copper[0] = replace(geometry.copper[0], z_m=TOLERANCE_M * 2)
        self.assert_invalid(geometry, "z_m")

    def test_membership_tolerance(self):
        geometry = fixture()
        geometry.port = replace(geometry.port, negative_xy_m=(.009 + TOLERANCE_M / 2, .010))
        validate_pcb_geometry(geometry)
        geometry.port = replace(geometry.port, negative_xy_m=(.009 + TOLERANCE_M * 2, .010))
        self.assert_invalid(geometry, "port.negative")

    def test_equivalent_outline_order_and_closure(self):
        geometry = fixture()
        points = list(reversed(geometry.outline.vertices_xy_m))
        points = points[1:] + points[:1]
        geometry.substrate = replace(geometry.substrate, outline=BoardOutline(tuple(points + points[:1])))
        validate_pcb_geometry(geometry)

    def test_mismatched_substrate_outline(self):
        geometry = fixture()
        geometry.substrate = replace(geometry.substrate, outline=BoardOutline(
            ((0., 0.), (.021, 0.), (.020, .020), (0., .020))))
        self.assert_invalid(geometry, "obrys nie zgadza")

    def test_concave_outline(self):
        geometry = fixture()
        outline = BoardOutline(((0., 0.), (.020, 0.), (.020, .020),
                                (.010, .015), (0., .020)))
        geometry.outline = outline
        geometry.substrate = replace(geometry.substrate, outline=outline)
        validate_pcb_geometry(geometry)


if __name__ == "__main__":
    unittest.main()
