from dataclasses import asdict, replace, FrozenInstanceError
import unittest
from unittest.mock import patch
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.validation import _contains

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.model import CopperPolygon
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from antenna_lab.pcb.validation import validate_pcb_geometry
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
import test_pcb_mesh as fixtures
from test_pcb_simulation import settings


class PcbPortTests(unittest.TestCase):
    def geometry(self, **kwargs):
        geometry = fixtures.PcbMeshTests().geometry(**kwargs).normalized_geometry
        # Explicit fixture preparation: enforce the requested exact X-zero frame.
        return normalize_port_orientation(geometry)[0]

    def test_exact_contract_counts_ids_frozen_no_mutation(self):
        for gap,width in ((2.,1.),(.5,4.),(.1,.3)):
            with self.subTest(gap=gap,width=width):
                geometry = self.geometry(gap=gap,width=width)
                experiment = replace(settings(),reference_impedance_ohm=75)
                mesh = make_pcb_domain_mesh(geometry,experiment)
                before = (geometry.as_dict(),asdict(mesh),asdict(experiment))
                spec = resolve_pcb_lumped_port(geometry,mesh,experiment)
                n,p = geometry.port.negative_xy_m,geometry.port.positive_xy_m
                self.assertEqual(spec.start_m,(n[0],-width*.001/2,0.))
                self.assertEqual(spec.stop_m,(p[0],width*.001/2,0.))
                self.assertEqual((spec.port_nr,spec.port_id,spec.exc_dir,spec.excite,spec.priority),
                                 (1,geometry.port.id,'x',1.,5))
                self.assertEqual(spec.reference_impedance_ohm,75)
                # Fixture order is not assumed: identify which side each pad spans.
                neg=next(c.id for c in geometry.copper if max(x for x,y in c.vertices_xy_m)==n[0])
                pos=next(c.id for c in geometry.copper if min(x for x,y in c.vertices_xy_m)==p[0])
                self.assertEqual((spec.negative_copper_id,spec.positive_copper_id),(neg,pos))
                nx=mesh.x_lines_m.index(p[0])-mesh.x_lines_m.index(n[0])
                ny=mesh.y_lines_m.index(spec.stop_m[1])-mesh.y_lines_m.index(spec.start_m[1])
                self.assertEqual((spec.x_cell_count,spec.y_cell_count,spec.active_ex_edge_count),(nx,ny,nx*(ny+1)))
                self.assertEqual(spec,resolve_pcb_lumped_port(geometry,mesh,experiment))
                self.assertEqual(before,(geometry.as_dict(),asdict(mesh),asdict(experiment)))
                with self.assertRaises(FrozenInstanceError): spec.priority=10

    def test_missing_critical_lines(self):
        g,s=self.geometry(),settings();m=make_pcb_domain_mesh(g,s)
        for axis,values in (('x',(g.port.negative_xy_m[0],0.,g.port.positive_xy_m[0])),
                            ('y',(-g.port.width_m/2,0.,g.port.width_m/2)),('z',(0.,))):
            for value in values:
                with self.subTest(axis=axis,value=value):
                    field=axis+'_lines_m'
                    bad=replace(m,**{field:tuple(v for v in getattr(m,field) if v!=value)})
                    with self.assertRaisesRegex(ConfigurationError,'brak dokładnej linii'):
                        resolve_pcb_lumped_port(g,bad,s)

    def test_insufficient_cells_and_mismatch(self):
        g,s=self.geometry(),settings();m=make_pcb_domain_mesh(g,s)
        spec=resolve_pcb_lumped_port(g,m,s)
        for field,count,message in (('min_port_gap_cells',spec.x_cell_count,'szczelina'),
                                    ('min_port_width_cells',spec.y_cell_count,'szerokość')):
            with self.assertRaisesRegex(ConfigurationError,message):
                resolve_pcb_lumped_port(g,m,replace(s,**{field:count+1}))
        with self.assertRaisesRegex(ConfigurationError,'pml_cells'):
            resolve_pcb_lumped_port(g,replace(m,pml_cells=12),s)

    def test_incomplete_contact_both_sides(self):
        for side in (0,1):
            g,s=self.geometry(),settings()
            c=g.copper[side]
            g.copper[side]=replace(c,vertices_xy_m=tuple((x,y/4) for x,y in c.vertices_xy_m))
            validate_pcb_geometry(g)  # Endpoint alone still passes.
            m=make_pcb_domain_mesh(g,s)
            before=g.as_dict()
            with self.assertRaisesRegex(ConfigurationError,'negative|positive'):
                resolve_pcb_lumped_port(g,m,s)
            self.assertEqual(before,g.as_dict())

    def test_gap_intrusion_and_ambiguous_contact(self):
        for kind in ('gap','contact'):
            g,s=self.geometry(),settings()
            x=0. if kind=='gap' else g.port.negative_xy_m[0]
            y=g.port.width_m/2
            g.copper.append(CopperPolygon('intruder',((x-.0001,y-.0001),(x+.0001,y-.0001),
                (x+.0001,y+.0001),(x-.0001,y+.0001)),0.))
            validate_pcb_geometry(g)
            m=make_pcb_domain_mesh(g,s)
            with self.assertRaisesRegex(ConfigurationError,'szczeliny' if kind=='gap' else 'niejednoznaczny kontakt'):
                resolve_pcb_lumped_port(g,m,s)

    def test_cell_centre_gap_audit(self):
        g,s=self.geometry(),settings();m=make_pcb_domain_mesh(g,s)
        ix=m.x_lines_m.index(g.port.negative_xy_m[0])
        iy=m.y_lines_m.index(-g.port.width_m/2)
        centre=(m.x_lines_m[ix]+(m.x_lines_m[ix+1]-m.x_lines_m[ix])/2,
                m.y_lines_m[iy]+(m.y_lines_m[iy+1]-m.y_lines_m[iy])/2)
        self.assertNotIn(centre[1],m.y_lines_m)
        # A membership oracle isolates cell-centre sampling from Ex-row sampling.
        # Real polygon semantics are covered by the intrusion/contact tests.
        def membership(point,polygon):
            return point==centre or _contains(point,polygon)
        with patch('antenna_lab.pcb.port._contains',side_effect=membership):
            with self.assertRaisesRegex(ConfigurationError,'szczeliny'):
                resolve_pcb_lumped_port(g,m,s)

    def test_existing_near_zero_midpoint_is_not_silently_snapped(self):
        g=fixtures.PcbMeshTests().geometry(gap=.5,width=4.).normalized_geometry
        s=settings();m=make_pcb_domain_mesh(g,s)
        self.assertNotIn(0.,m.x_lines_m)
        before=(g.as_dict(),asdict(m))
        with self.assertRaisesRegex(ConfigurationError,'x=0.0'):
            resolve_pcb_lumped_port(g,m,s)
        self.assertEqual(before,(g.as_dict(),asdict(m)))

    def test_reordered_closed_polygons(self):
        g,s=self.geometry(),settings();m=make_pcb_domain_mesh(g,s)
        expected=resolve_pcb_lumped_port(g,m,s)
        g.copper.reverse()
        g.copper=[replace(c,vertices_xy_m=c.vertices_xy_m+(c.vertices_xy_m[0],)) for c in g.copper]
        self.assertEqual(expected,resolve_pcb_lumped_port(g,m,s))


if __name__=='__main__': unittest.main()
