"""Detached lattice arithmetic/topology. No native solver or active policy switch."""
from dataclasses import replace, FrozenInstanceError
from decimal import Decimal
import json
import math
import unittest

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.pcb.quantization import quantize_pcb_geometry, QuantizationError
from antenna_lab.pcb.model import (BoardOutline, CopperPolygon, CopperLayer, DielectricLayer,
    Substrate, PcbDrill, PcbLumpedComponent)
from test_pcb_model import fixture


def stack_fixture(thicknesses=(.000154,.001446)):
    g=fixture();layers=[];top=0.
    for i,t in enumerate(thicknesses):
        layers.append(DielectricLayer(g.outline,top-t,top,4.3+i,.018,f'd{i}'));top-=t
    sheets=tuple(CopperLayer(role,z,'conducting_sheet',35e-6,58e6,'hash') for role,z in
        [('top',0.),('inner1',layers[0].z_min_m),('bottom',top)])
    copper=list(g.copper)
    for sheet in sheets[1:]:copper.append(CopperPolygon(sheet.role,g.outline.vertices_xy_m,sheet.z_m,sheet.role))
    sub=Substrate(g.outline,layers[0].z_min_m,0.,4.3,.018)
    return replace(g,substrate=sub,dielectric_layers=tuple(layers),copper_layers=sheets,copper=copper)


class GridTests(unittest.TestCase):
    def test_all_quanta_integer_rounding_and_signed_ties(self):
        for nm in (100000,10000,1000,100):
            g=PcbGrid(nm);q=g.quantum_decimal_m
            for n in (-220,-35,-1,0,1,35,160):
                self.assertEqual(g.nearest_tick(Decimal(n)*q),n)
                self.assertEqual(g.floor_tick(Decimal(n)*q),n)
                self.assertEqual(g.ceil_tick(Decimal(n)*q),n)
                self.assertEqual(g.nearest_tick(g.to_metres(n)),n)
            for x,expected in [('15.2',15),('15.5',16),('-15.2',-15),('-15.5',-16)]:
                self.assertEqual(g.nearest_tick(Decimal(x)*q),expected)
            self.assertEqual(g.floor_tick(Decimal('-15.2')*q),-16)
            self.assertEqual(g.ceil_tick(Decimal('-15.2')*q),-15)
            self.assertEqual(g.floor_tick(Decimal('15.2')*q),15)
            self.assertEqual(g.ceil_tick(Decimal('15.2')*q),16)
            with self.assertRaises(FrozenInstanceError):g.quantum_nm=100
        for invalid in (0,10,500,True,10000.):
            with self.assertRaises(ConfigurationError):PcbGrid(invalid)
        for invalid in (float('nan'),float('inf'),True,'bad'):
            with self.assertRaises(ConfigurationError):PcbGrid().nearest_tick(invalid)
        with self.assertRaises(ConfigurationError):PcbGrid().to_metres(1.5)

    def test_decimal_examples_and_float_boundary_residue(self):
        g=PcbGrid()
        for mm,tick in [('0.152',15),('0.8640064',86),('10.24543',1025),('0.35',35),('-2.20',-220),('1.60',160)]:
            self.assertEqual(g.nearest_tick(Decimal(mm)*Decimal('.001')),tick)
        for sign in (1,-1):
            for value in (.000155,math.nextafter(.000155,0),math.nextafter(.000155,1)):
                self.assertEqual(g.nearest_tick(sign*value),sign*16)
        # Exact Decimal data outside the half is not changed by the float guard.
        self.assertEqual(g.nearest_tick(Decimal('.000154999999999999999999')),15)
        self.assertEqual(g.floor_tick(math.nextafter(.00015,0)),15)
        self.assertEqual(g.ceil_tick(math.nextafter(.00015,1)),15)

    def test_detached_integer_geometry_counts_provenance_all_quanta(self):
        source=fixture();original=source.as_dict()
        for nm in (100000,10000,1000,100):
            g,a=quantize_pcb_geometry(source,PcbGrid(nm))
            self.assertEqual(a['topology_status'],'PASS')
            self.assertEqual(a['total_spatial_values_examined'],a['already_on_grid']+a['adjusted'])
            self.assertEqual(g.provenance,original)
            for p in g.outline:self.assertTrue(all(type(v) is int for v in p))
            self.assertTrue(all(type(v) is int for d in g.dielectrics for v in (d.bottom,d.top,d.thickness)))
            snapshot=g.as_dict();snapshot['source_geometry']['port']['width_m']=100
            self.assertEqual(g.provenance,original)
            self.assertEqual(g,quantize_pcb_geometry(source,PcbGrid(nm))[0])
            json.dumps(a,allow_nan=False);json.dumps(g.as_dict(),allow_nan=False)
        self.assertEqual(source.as_dict(),original)

    def test_ring_duplicate_removal_order_and_collapse(self):
        g=fixture();points=((0.,0.),(.000001,0.),(.02,0.),(.02,.02),(0.,.02))
        outline=BoardOutline(points);g=replace(g,outline=outline,substrate=replace(g.substrate,outline=outline))
        result,a=quantize_pcb_geometry(g)
        self.assertEqual(result.outline,((0,0),(2000,0),(2000,2000),(0,2000)))
        self.assertGreater(a['adjusted'],0)
        tiny=CopperPolygon('tiny',((.001,.001),(.001002,.001),(.001002,.001002),(.001,.001002)),0.)
        with self.assertRaises(QuantizationError) as error:quantize_pcb_geometry(replace(g,copper=g.copper+[tiny]))
        self.assertTrue(any('tiny' in v for v in error.exception.audit['collapsed_features']))

    def test_collapsed_gap_and_self_intersection_rejected(self):
        g=fixture()
        left=replace(g.copper[0],vertices_xy_m=((.004,.008),(.010001,.008),(.010001,.012),(.004,.012)))
        right=replace(g.copper[1],vertices_xy_m=((.010003,.008),(.016,.008),(.016,.012),(.010003,.012)))
        g=replace(g,copper=[left,right],port=replace(g.port,negative_xy_m=(.010001,.01),positive_xy_m=(.010003,.01)))
        with self.assertRaises(QuantizationError) as error:quantize_pcb_geometry(g)
        self.assertTrue(any('gap' in v for v in error.exception.audit['collapsed_features']))
        # A valid narrow U becomes a self-touching polygon after snapping.
        g=fixture();u=((.001,.001),(.003,.001),(.003,.003),(.002004,.003),(.002004,.002),(.002001,.002),(.002001,.003),(.001,.003))
        with self.assertRaises(QuantizationError) as error:
            quantize_pcb_geometry(replace(g,copper=g.copper+[CopperPolygon('narrow_u',u,0.)]))
        self.assertTrue(any('invalid quantized' in v for v in error.exception.audit['topology_changes']))

    def test_shared_interfaces_accumulate_and_materials_unchanged(self):
        source=stack_fixture();g,a=quantize_pcb_geometry(source)
        self.assertEqual([(d.top,d.bottom,d.thickness) for d in g.dielectrics],[(0,-15,15),(-15,-160,145)])
        self.assertEqual([c.z for c in g.copper_layers],[0,-15,-160])
        self.assertEqual(g.dielectrics[0].bottom,g.dielectrics[1].top)
        self.assertEqual(g.copper_layers[0].material_thickness_m,35e-6)
        self.assertEqual(g.copper_layers[0].conductivity_s_m,58e6)
        self.assertEqual(g.dielectrics[1].epsilon_r,source.dielectric_layers[1].epsilon_r)
        self.assertAlmostEqual(a['maximum_z_displacement_m'],4e-6,delta=1e-17)
        with self.assertRaises(QuantizationError) as error:quantize_pcb_geometry(stack_fixture((.000004,.001596)))
        self.assertTrue(any('thickness' in v for v in error.exception.audit['collapsed_features']))

    def test_pth_geometry_and_via_contacts_preserved(self):
        g=stack_fixture();d=PcbDrill('via',.005002,.010003,.000305,True,'PTH','T01','abc',25e-6,.000305/2+25e-6,('top','inner1','bottom'))
        g=replace(g,drills=(d,));raw=g.as_dict();q,a=quantize_pcb_geometry(g)
        via=q.drills[0]
        self.assertEqual(via.centre,(500,1000));self.assertEqual((via.radius,via.diameter,via.outer_radius),(15,30,18))
        self.assertEqual(via.plating_thickness_m,25e-6)
        self.assertEqual(via.connected_layer_roles,('top','inner1','bottom'))
        self.assertEqual(q.provenance,raw);self.assertEqual(g.as_dict(),raw)
        # Tiny NPTH is physically legal but cannot survive this lattice.
        hole=PcbDrill('tiny_void',.001,.001,2e-6,False,'NPTH','T02','def')
        with self.assertRaises(QuantizationError) as error:quantize_pcb_geometry(replace(g,drills=(hole,)))
        self.assertTrue(any('radius' in v for v in error.exception.audit['collapsed_features']))

    def test_touching_regions_and_terminal_ownership_changes_rejected(self):
        g=fixture()
        # Remote regions, separate physically, touch on the coarse tick lattice.
        a=CopperPolygon('extra_a',((.001,.001),(.002001,.001),(.002001,.002),(.001,.002)),0.)
        b=CopperPolygon('extra_b',((.002004,.001),(.003,.001),(.003,.002),(.002004,.002)),0.)
        with self.assertRaises(QuantizationError) as error:quantize_pcb_geometry(replace(g,copper=g.copper+[a,b]))
        self.assertTrue(any('contact changed' in s for s in error.exception.audit['topology_changes']))
        # Oblique endpoint rounding moves it off its owning copper edge.
        triangle=replace(g.copper[0],vertices_xy_m=((.004,.008),(.009,.010003),(.004,.012)))
        port=replace(g.port,negative_xy_m=(.0065,.0090015),width_m=.0001)
        with self.assertRaises(QuantizationError) as error:quantize_pcb_geometry(replace(g,copper=[triangle,g.copper[1]],port=port))
        self.assertTrue(error.exception.audit['topology_changes'])

    def test_remote_quantized_bridge_cannot_short_terminal_pair(self):
        g=fixture()
        bridge=CopperPolygon('bridge',((.008,.0115),(.010999,.0115),(.010999,.0119),(.008,.0119)),0.)
        with self.assertRaises(QuantizationError) as error:
            quantize_pcb_geometry(replace(g,copper=g.copper+[bridge]))
        self.assertTrue(any('terminal connectivity changed' in v for v in error.exception.audit['topology_changes']))

    def test_component_ticks_electrical_values_and_capped_examples(self):
        g=fixture()
        c=PcbLumpedComponent('R1','R',49.9,'49.9Ω','A','B',(.005152,.010003),(.015152,.010003),
            'top','x',g.port.negative_xy_m,g.port.positive_xy_m,((.009,.0095),(.011,.0095),(.011,.0105),(.009,.0105)),'enet','probe')
        g=replace(g,components=(c,));modeled,a=quantize_pcb_geometry(g)
        self.assertEqual(modeled.components[0].pin1,(515,1000))
        self.assertEqual(modeled.components[0].value_si,49.9)
        self.assertEqual(modeled.components[0].source_sha256,'enet')
        self.assertEqual(modeled.provenance['components'][0]['pin1_xy_m'],list(c.pin1_xy_m))
        self.assertLessEqual(len(a['examples']),20)
        # More than 20 adjusted occurrences: example list remains capped.
        from antenna_lab.pcb.transform import _map_xy
        moved=_map_xy(g,lambda p:(p[0]+.000002,p[1]+.000003))
        _,audit=quantize_pcb_geometry(moved)
        self.assertGreater(audit['adjusted'],20);self.assertEqual(len(audit['examples']),20)

    def test_holes_and_changed_via_contacts_fail_closed(self):
        g=fixture()
        hole=((.0045,.0085),(.0055,.0085),(.0055,.0095),(.0045,.0095))
        g=replace(g,copper=[replace(g.copper[0],holes_xy_m=(hole,)),g.copper[1]])
        modeled,a=quantize_pcb_geometry(g)
        self.assertEqual(modeled.copper[0].holes,(((450,850),(550,850),(550,950),(450,950)),))
        self.assertEqual(a['layers']['top']['modeled']['holes'],1)
        # The raw via just misses an inner pad, but lattice projection contacts it.
        g=stack_fixture()
        inner=next(c for c in g.copper if c.layer_role=='inner1')
        inner=replace(inner,vertices_xy_m=((.0051776,.008),(.008,.008),(.008,.012),(.0051776,.012)))
        g=replace(g,copper=[inner if c.id==inner.id else c for c in g.copper])
        d=PcbDrill('via',.005,.010,.000305,True,'PTH','T01','hash',25e-6,.000305/2+25e-6,('top','bottom'))
        with self.assertRaises(QuantizationError) as error:quantize_pcb_geometry(replace(g,drills=(d,)))
        self.assertTrue(any('via copper/layer contacts changed' in v for v in error.exception.audit['topology_changes']))

    def test_active_mesh_untouched_after_detached_projection(self):
        from antenna_lab.pcb.transform import normalize_port_orientation
        from antenna_lab.pcb.control import make_control_settings
        from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
        g,_=normalize_port_orientation(fixture());s=make_control_settings()
        before=make_pcb_domain_mesh(g,s);snapshot=g.as_dict()
        quantize_pcb_geometry(g)
        self.assertEqual(snapshot,g.as_dict());self.assertEqual(before,make_pcb_domain_mesh(g,s))


if __name__=='__main__':unittest.main()
