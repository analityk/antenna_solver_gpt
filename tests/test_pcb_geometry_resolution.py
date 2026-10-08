"""Detached normalized geometry -> existing EM mesher; never native FDTD."""
from dataclasses import replace, asdict
from hashlib import sha256
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb import geometry_resolution as candidate
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.pcb.quantization import quantize_pcb_geometry, QuantizationError
from antenna_lab.pcb.model import BoardOutline, PcbDrill, QuantizedPcbDrill
from antenna_lab.pcb.validation import validate_pcb_geometry
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from antenna_lab.pcb.gerber_quality import gerber_quality_settings
from test_pcb_model import fixture
from test_pcb_grid import stack_fixture
from test_pcb_simulation import settings


class GeometryResolutionTests(unittest.TestCase):
    def test_order_and_only_modeled_geometry_reaches_existing_mesher(self):
        raw=fixture();before=raw.as_dict();s=settings();events=[]
        def record(name,real):
            def call(*args,**kwargs):
                events.append(name)
                return real(*args,**kwargs)
            return call
        with patch.object(candidate,'normalize_port_orientation',wraps=record('normalize',normalize_port_orientation)) as norm,patch.object(
                candidate,'quantize_pcb_geometry',wraps=record('quantize',quantize_pcb_geometry)) as quant,patch.object(
                candidate,'materialize_quantized_geometry',wraps=record('materialize',candidate.materialize_quantized_geometry)),patch.object(
                candidate,'make_pcb_domain_mesh',wraps=make_pcb_domain_mesh) as mesh,patch(
                'antenna_lab.solvers.openems.native_modules',side_effect=AssertionError('native invoked')):
            result=candidate.prepare_geometry_resolution_candidate(raw,s)
        self.assertEqual(events,['normalize','quantize','materialize'])
        norm.assert_called_once_with(raw)
        self.assertIsNot(quant.call_args.args[0],raw)
        self.assertIs(mesh.call_args.args[0],result.modeled_geometry)
        self.assertIsNot(result.modeled_geometry,raw)
        self.assertEqual(result.diagnostics['source_geometry'],before)
        self.assertEqual(raw.as_dict(),before)
        self.assertEqual(result.diagnostics['geometry_resolution_um'],10)
        self.assertEqual(result.mesh,make_pcb_domain_mesh(result.modeled_geometry,s,gerber_quality='preview'))
        json.dumps(result.diagnostics,allow_nan=False)

    def test_materialization_all_quanta_and_preservation(self):
        raw=stack_fixture();normalized,_=normalize_port_orientation(raw)
        before=normalized.as_dict()
        for nm in (100000,10000,1000,100):
            grid=PcbGrid(nm);q,a=quantize_pcb_geometry(normalized,grid)
            materialized=candidate.materialize_quantized_geometry(q)
            self.assertEqual(materialized.as_dict(),candidate.materialize_quantized_geometry(q).as_dict())
            self.assertEqual(q.provenance,before)
            for source,modeled in zip(q.copper,materialized.copper):
                self.assertEqual(modeled.vertices_xy_m,tuple(tuple(grid.to_metres(v) for v in p) for p in source.outer))
                self.assertEqual(modeled.holes_xy_m,tuple(tuple(tuple(grid.to_metres(v) for v in p) for p in h) for h in source.holes))
                self.assertEqual(modeled.z_m,grid.to_metres(source.z))
                self.assertEqual((modeled.id,modeled.layer_role),(source.id,source.layer_role))
            for source,modeled in zip(normalized.dielectrics,materialized.dielectrics):
                self.assertEqual((modeled.epsilon_r,modeled.loss_tangent),(source.epsilon_r,source.loss_tangent))
            for source,modeled in zip(normalized.copper_layers,materialized.copper_layers):
                self.assertEqual((modeled.thickness_m,modeled.conductivity_s_m,modeled.source_sha256),
                                 (source.thickness_m,source.conductivity_s_m,source.source_sha256))
            for a,b in zip(materialized.dielectrics,materialized.dielectrics[1:]):
                self.assertEqual(a.z_min_m,b.z_max_m)
            self.assertEqual(materialized.dielectrics[0].z_max_m,0.)
        self.assertEqual(normalized.as_dict(),before)

    def test_drill_projection_keeps_plating_and_checks_provenance_not_relaxed_tolerance(self):
        raw=stack_fixture()
        drill=PcbDrill('via',.005002,.010003,.000305,True,'PTH','T01','sha',25e-6,
                       .000305/2+25e-6,('top','inner1','bottom'))
        raw=replace(raw,drills=(drill,));normalized,_=normalize_port_orientation(raw)
        q,_=quantize_pcb_geometry(normalized,PcbGrid())
        modeled=candidate.materialize_quantized_geometry(q);d=modeled.drills[0]
        self.assertIsInstance(d,QuantizedPcbDrill)
        self.assertEqual(d.drill_diameter_m,.0003)
        self.assertEqual(d.equivalent_outer_radius_m,.00018)
        self.assertEqual(d.plating_thickness_m,25e-6)
        self.assertEqual(d.source_drill_diameter_m,.000305)
        self.assertEqual(d.source_file_sha256,drill.source_file_sha256)
        self.assertEqual(d.connected_layer_roles,drill.connected_layer_roles)
        validate_pcb_geometry(modeled)
        for altered in (replace(d,drill_diameter_m=.000305),replace(d,equivalent_outer_radius_m=.00019),
                        replace(d,source_drill_diameter_m=float('nan')),replace(d,geometry_resolution_nm=500),
                        replace(d,connected_layer_roles=('top',))):
            with self.assertRaises(ConfigurationError):validate_pcb_geometry(replace(modeled,drills=(altered,)))
        # No new fields or new radius semantics in legacy serialized geometry.
        self.assertNotIn('geometry_resolution_nm',raw.as_dict()['drills'][0])
        self.assertNotIn('source_drill_diameter_m',asdict(drill))
        with self.assertRaisesRegex(ConfigurationError,'inconsistent PTH equivalent radius'):
            validate_pcb_geometry(replace(raw,drills=(replace(drill,equivalent_outer_radius_m=.00018),)))

    def test_npth_and_copper_holes_materialize_without_restoring_source_dimensions(self):
        raw=stack_fixture()
        hole=((.013001,.014001),(.014001,.014001),(.014001,.015001),(.013001,.015001))
        copper=list(raw.copper)
        copper[-1]=replace(copper[-1],holes_xy_m=(hole,))
        npth=PcbDrill('npth',.002002,.002003,.000305,False,'NPTH','T2','hash')
        raw=replace(raw,copper=copper,drills=(npth,))
        q,_=quantize_pcb_geometry(raw,PcbGrid())
        m=candidate.materialize_quantized_geometry(q)
        self.assertEqual(m.drills[0].drill_diameter_m,.0003)
        self.assertIsNone(m.drills[0].equivalent_outer_radius_m)
        self.assertEqual(m.copper[-1].holes_xy_m,(((.013,.014),(.014,.014),(.014,.015),(.013,.015)),))
        self.assertEqual(m.drills[0].source_file_sha256,'hash')

    def test_duplicate_vertices_disappear_and_source_remains_detached(self):
        raw=fixture();outline=BoardOutline(((0.,0.),(.000001,0.),(.02,0.),(.02,.02),(0.,.02)))
        raw=replace(raw,outline=outline,substrate=replace(raw.substrate,outline=outline));before=raw.as_dict()
        result=candidate.prepare_geometry_resolution_candidate(raw,settings())
        self.assertEqual(len(result.modeled_geometry.outline.vertices_xy_m),4)
        self.assertEqual(raw.as_dict(),before)
        result.diagnostics['source_geometry']['port']['width_m']=999
        result.modeled_geometry.assumptions.append('local edit')
        self.assertEqual(raw.as_dict(),before)

    def test_geometry_failure_stops_before_materialization_or_meshing(self):
        raw=fixture()
        left=replace(raw.copper[0],vertices_xy_m=((.004,.008),(.009998,.008),(.009998,.012),(.004,.012)))
        right=replace(raw.copper[1],vertices_xy_m=((.010002,.008),(.016,.008),(.016,.012),(.010002,.012)))
        raw=replace(raw,copper=[left,right],port=replace(raw.port,negative_xy_m=(.009998,.01),positive_xy_m=(.010002,.01)))
        before=raw.as_dict()
        with patch.object(candidate,'materialize_quantized_geometry') as materialize,patch.object(candidate,'make_pcb_domain_mesh') as mesh:
            with self.assertRaises(QuantizationError) as error:candidate.prepare_geometry_resolution_candidate(raw,settings())
        materialize.assert_not_called();mesh.assert_not_called()
        self.assertEqual(error.exception.audit['topology_status'],'FAIL')
        self.assertTrue(error.exception.audit['collapsed_features'])
        self.assertEqual(raw.as_dict(),before)

    def test_float_mesh_and_sub_resolution_cells_are_legal(self):
        grid=PcbGrid(100000)
        s=replace(settings(),min_port_width_cells=24)
        result=candidate.prepare_geometry_resolution_candidate(fixture(),s,grid=grid)
        axes=(result.mesh.x_lines_m,result.mesh.y_lines_m,result.mesh.z_lines_m)
        self.assertLess(result.mesh.min_step_m,grid.quantum_m)
        self.assertTrue(any(abs(x/grid.quantum_m-round(x/grid.quantum_m))>1e-5 for axis in axes for x in axis))
        info=result.diagnostics['geometry_and_mesh']
        self.assertGreaterEqual(info['y']['minimum_geometry_anchor_separation_m'],grid.quantum_m)
        self.assertLess(info['y']['minimum_mesh_step_m'],grid.quantum_m)
        for axis in 'xyz':
            self.assertTrue(info[axis]['closest_geometry_anchor_pair'])
            self.assertTrue(all(v['owners'] for v in info[axis]['closest_geometry_anchor_pair']))

    def test_legacy_mesh_and_cli_remain_unchanged(self):
        from antenna_lab.pcb.gerber_control import main
        raw=fixture();s=settings();g,_=normalize_port_orientation(raw)
        before=make_pcb_domain_mesh(g,s,gerber_quality='preview')
        candidate.prepare_geometry_resolution_candidate(raw,s)
        self.assertEqual(make_pcb_domain_mesh(g,s,gerber_quality='preview'),before)
        for option in ('--grid-quantum-um',):
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
                main(['unused',option,'10'])
            self.assertEqual(error.exception.code,2)

    def test_modeled_geometry_display_precision_only(self):
        for nm,text in ((100000,'0.9 mm'),(10000,'0.86 mm'),(1000,'0.864 mm'),(100,'0.8640 mm')):
            self.assertEqual(candidate.format_modeled_mm(.000864,PcbGrid(nm)),text)


ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless((ROOT/'gerbs/emtest3').is_dir() and (ROOT/'gerbs/emtest4').is_dir(),
                     'Production Gerber bundles not present; synthetic contracts still run.')
class RealGeometryResolutionTests(unittest.TestCase):
    def test_real_emtest3_and_emtest4_detached_acceptance(self):
        from antenna_lab.pcb.bundle import load_bundle_geometry
        s,_=gerber_quality_settings('preview',excitation_center_hz=2e9,excitation_cutoff_hz=1e9,
            result_frequency_hz=tuple(f*1e6 for f in range(1500,2501,10)))
        for name,expected_raw in (('emtest3',99750),('emtest4',270480)):
            directory=ROOT/'gerbs'/name
            hashes={p:sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}
            _,raw,import_info=load_bundle_geometry(directory,ROOT/'parameters/pcb_fr4_2layer_pth.json')
            before=raw.as_dict();normalized,_=normalize_port_orientation(raw)
            legacy=make_pcb_domain_mesh(normalized,s,gerber_quality='preview')
            self.assertEqual(legacy.cell_count,expected_raw)
            result=candidate.prepare_geometry_resolution_candidate(raw,s,grid=PcbGrid())
            d=result.diagnostics;m=result.modeled_geometry
            self.assertEqual(d['quantization']['topology_status'],'PASS')
            self.assertLessEqual(result.mesh.cell_count,expected_raw*1.05)
            self.assertEqual(result.mesh.z_lines_m,legacy.z_lines_m)
            self.assertEqual(len(m.drills),1)
            self.assertEqual(m.drills[0].connected_layer_roles,raw.drills[0].connected_layer_roles)
            self.assertEqual(set(m.drills[0].connected_layer_roles),{'top','bottom'})
            self.assertTrue(d['normalization']['exact_orthogonal'])
            self.assertEqual(m.port.negative_xy_m,(-.00035,0.))
            self.assertEqual(m.port.positive_xy_m,(.00035,0.))
            self.assertEqual(m.port.width_m,.00086)
            for axis in 'xy':self.assertGreaterEqual(d['geometry_and_mesh'][axis]['minimum_geometry_anchor_separation_m'],1e-5)
            if name=='emtest4':
                self.assertEqual(m.source_port.source_refdes,'CSRC')
                self.assertEqual(m.source_port.source_pin_nets,raw.source_port.source_pin_nets)
                self.assertEqual({c.id:c.kind for c in m.components},{'C1':'C','L1':'L','R1':'R'})
                for c,old in zip(m.components,raw.components):
                    self.assertEqual((c.value_si,c.pin1_net,c.pin2_net,c.source_sha256,c.flying_probe_sha256),
                                     (old.value_si,old.pin1_net,old.pin2_net,old.source_sha256,old.flying_probe_sha256))
                    for p in (c.pin1_xy_m,c.pin2_xy_m,c.gap_start_xy_m,c.gap_stop_xy_m,*c.contact_window_xy_m):
                        for v in p:self.assertEqual(v,PcbGrid().to_metres(PcbGrid().nearest_tick(v)))
                values={c.id:c.value_si for c in m.components}
                self.assertAlmostEqual(values['C1'],100e-12,delta=1e-24)
                self.assertAlmostEqual(values['L1'],18e-9,delta=1e-22)
                self.assertEqual(values['R1'],49.9)
                self.assertEqual(len(d['ideal_components']),3)
                self.assertEqual(d['port']['port_nr'],1)
                with patch.object(candidate,'make_pcb_domain_mesh') as mesh:
                    with self.assertRaises(QuantizationError) as error:
                        candidate.prepare_geometry_resolution_candidate(raw,s,grid=PcbGrid(100000))
                mesh.assert_not_called()
                self.assertEqual(error.exception.audit['topology_changes'],[
                    'port.negative: full-width contact disconnected','port.positive: full-width contact disconnected'])
            self.assertEqual(raw.as_dict(),before)
            self.assertEqual({p:sha256(p.read_bytes()).hexdigest() for p in hashes},hashes)


if __name__=='__main__':unittest.main()
