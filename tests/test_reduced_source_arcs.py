"""Semantic ARC geometry/graph only; no native solver or coupling guesses."""
from dataclasses import replace
from hashlib import sha256
from math import hypot, pi
from pathlib import Path
import json
from tempfile import TemporaryDirectory
import unittest
from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.easyeda import parse_easyeda_source
from antenna_lab.pcb.easyeda_model import build_source_layout,source_layout_geometry
from antenna_lab.pcb.easyeda_project import load_easyeda_project,materialize_project_source
from antenna_lab.pcb.geometry_resolution import apply_geometry_resolution
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.reduced_control import run_reduced
from antenna_lab.solvers.reduced_source import source_arc_radius
from antenna_lab.solvers.reduced_pcb import build_reduced_model,solve_reduced_model,detect_coupled_sections,extract_trace_sections
from test_pcb_easyeda import records,encoded,config


def routes_fixture(reverse=False):
    items=records();items.pop(13)
    routes=[['ARC','a1',0,'A',1,100,0,200,0,180,10,0],
            ['ARC','a2',0,'A',1,200,0,300,0,-180,10,0],
            ['LINE','tail',0,'A',1,300,0,400,0,10,0]]
    if reverse:
        for r in routes:
            r[5:9]=r[7:9]+r[5:7]
            if r[0]=='ARC':r[9]*=-1
    return parse_easyeda_source(encoded(items+routes))


class SemanticArcTests(unittest.TestCase):
    def test_signed_semicircles_reversal_junctions_and_projection(self):
        lengths=[]
        for reverse in (False,True):
            raw=routes_fixture(reverse)
            geometry=source_layout_geometry(build_source_layout(raw),config())
            normalized,_=normalize_port_orientation(geometry)
            for projected in (False,True):
                g=apply_geometry_resolution(normalized,PcbGrid())[0] if projected else normalized
                before=g.as_dict();model=build_reduced_model(g)
                arcs=[s for s in model['line_sections'] if s['kind']=='ARC']
                self.assertEqual(len(arcs),2)
                self.assertEqual([s['signed_sweep_deg'] for s in arcs],[-180,180] if reverse else [180,-180])
                for s in arcs:
                    self.assertAlmostEqual(s['length_m'],50*25.4e-6*pi,places=14)
                    self.assertGreater(s['length_m'],hypot(*(b-a for a,b in zip(s['source_start_xy_m'],s['source_stop_xy_m']))))
                self.assertEqual(len({n for s in model['line_sections'] if s['owner']==arcs[0]['owner'] for n in (s['node_a'],s['node_b'])}),4)
                self.assertEqual(g.as_dict(),before)
                lengths.append(model['total_centerline_length_m'])
                with self.assertRaisesRegex(ConfigurationError,'curved coupling analysis unsupported'):
                    solve_reduced_model(model,[1.42e9])
                sections,_=extract_trace_sections(g)
                with self.assertRaisesRegex(ConfigurationError,'ARC is not a straight line'):
                    detect_coupled_sections(sections)
        self.assertTrue(all(abs(x-lengths[0])<1e-14 for x in lengths))

    def test_inconsistent_source_arc_and_stale_projection_rejected(self):
        raw=routes_fixture();r=next(r for r in raw.routes if r.kind=='ARC')
        with self.assertRaisesRegex(ConfigurationError,'inconsistent'):
            source_arc_radius(replace(r,signed_sweep_deg=90))
        g=source_layout_geometry(build_source_layout(raw),config());n,_=normalize_port_orientation(g)
        g=apply_geometry_resolution(n,PcbGrid())[0]
        g.source_routes=tuple(replace(r,signed_sweep_deg=90) if r.kind=='ARC' else r for r in g.source_routes)
        with self.assertRaisesRegex(ConfigurationError,'stale/missing'):
            build_reduced_model(g)

    def test_real_spiral_axis_and_no_impedance(self):
        path=Path(__file__).resolve().parents[1]/'gerbs/emtest4/spirala.epro'
        if not path.exists():self.skipTest('spirala.epro unavailable')
        original=path.read_bytes();source=materialize_project_source(load_easyeda_project(path))
        cfg={'port':{'mode':'source','source_index':0},
             'drills':{'pth_model':'solid_pec_equivalent','pth_plating_um':25},
             'component_values':{'R1':{'kind':'R','value':'49.9ohm'}}}
        geometry=source_layout_geometry(build_source_layout(source),cfg)
        n,_=normalize_port_orientation(geometry)
        expected=sum(hypot(r.stop_xy_m[0]-r.start_xy_m[0],r.stop_xy_m[1]-r.start_xy_m[1]) if r.kind=='LINE'
                     else hypot(r.start_xy_m[0]-r.center_xy_m[0],r.start_xy_m[1]-r.center_xy_m[1])*abs(r.signed_sweep_deg)*pi/180
                     for r in source.routes if r.net=='A')
        for g in (n,apply_geometry_resolution(n,PcbGrid())[0]):
            model=build_reduced_model(g)
            self.assertEqual(len(model['line_sections']),12)
            self.assertEqual(sum(s['kind']=='ARC' for s in model['line_sections']),7)
            self.assertAlmostEqual(model['total_centerline_length_m'],expected,places=13)
            self.assertEqual(len(model['ground_vias']),2)
            self.assertEqual(len(model['lumped_components']),1)
            self.assertEqual(model['unsupported_status'],'curved_coupling_required')
        with TemporaryDirectory() as tmp:
            root=Path(tmp);override=root/'test-assumptions.json';override.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ConfigurationError,'curved coupling analysis unsupported'):
                run_reduced(None,root/'run',easyeda_project=path,source_config=override)
            self.assertFalse((root/'run/impedance.csv').exists())
            summary=json.loads((root/'run/summary.json').read_text())
            self.assertEqual(summary['unsupported_status'],'curved_coupling_required')
            self.assertTrue((root/'run/reduced_model.json').exists())
        self.assertEqual(path.read_bytes(),original)
        print(f'Spiral SHA256 {sha256(original).hexdigest()}; net A analytic length {expected*1e3:.9f} mm; 5 LINE + 7 ARC; coupling guarded')
