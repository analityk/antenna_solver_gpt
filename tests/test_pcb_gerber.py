"""Real Gerbonara/Shapely imports, authored fixtures; native FDTD is always fake."""
from dataclasses import replace
import contextlib
import io
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from shapely.geometry import Polygon, Point
from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.config import load_pcb_config
from antenna_lab.pcb.gerber import load_pcb_geometry, CURVE_ERROR_M
from antenna_lab.pcb import gerber_control as runner
from antenna_lab.pcb.control import make_control_settings, make_synthetic_control_case
from antenna_lab.pcb.transform import normalize_port_orientation, inverse_transform_geometry
from antenna_lab.pcb.validation import validate_pcb_geometry
from antenna_lab.pcb.port import resolve_pcb_lumped_port
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from test_pcb_edge_convergence import RunEngine
from test_openems_pcb import CSX

FIXTURE = Path(__file__).parent/'fixtures/pcb-gerber'
COORD_TOLERANCE_M = 1e-12


class GerberTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.top = self.root/'top.gtl'
        self.outline = self.root/'outline.gko'
        self.top.write_text((FIXTURE/'top.gtl').read_text())
        self.outline.write_text((FIXTURE/'outline.gko').read_text())
        self.config_path = self.root/'pcb.json'
        self.value = dict(schema_version=1, model='pcb',
            files=dict(copper_top='top.gtl', board_outline='outline.gko'),
            copper=dict(thickness_um=35,conductivity_s_m=58000000,model='pec'),
            substrate=dict(thickness_mm=1.6,epsilon_r=4.3,loss_tangent=.018),
            port=dict(negative_mm=[12.22288,12.573],positive_mm=[12.92312,12.573],width_mm=.86401))
        self.config_path.write_text(json.dumps(self.value))
        self.config = load_pcb_config(self.config_path)

    def append_graphics(self, content):
        self.top.write_text(self.top.read_text().replace('M02*',content+'\nM02*'))

    def test_regions_flashes_union_two_conductors_source_si_and_feed_gap(self):
        g = load_pcb_geometry(self.config)
        self.assertEqual(g,load_pcb_geometry(self.config))
        self.assertEqual(g.outline.vertices_xy_m,((0.,0.),(0.,.025),(.025,.025),(.025,0.)))
        self.assertEqual(len(g.copper),2)
        left,right = [Polygon(p.vertices_xy_m) for p in g.copper]
        self.assertTrue(left.covers(Point(.002,.006)))  # region retained
        self.assertTrue(left.covers(Point(.0122,.012573)))  # flash extends region
        self.assertTrue(right.covers(Point(.01294,.012573)))
        self.assertAlmostEqual(left.bounds[2],.01222288,delta=COORD_TOLERANCE_M)
        self.assertAlmostEqual(right.bounds[0],.01292312,delta=COORD_TOLERANCE_M)
        self.assertAlmostEqual(left.distance(right),.00070024,delta=COORD_TOLERANCE_M)
        self.assertEqual(validate_pcb_geometry(g)['copper_count'],2)
        for i, endpoint in enumerate((g.port.negative_xy_m,g.port.positive_xy_m)):
            self.assertLess([left,right][i].distance(Point(endpoint)),COORD_TOLERANCE_M)
            self.assertGreater([left,right][1-i].distance(Point(endpoint)),.0007)
        self.assertEqual(g.substrate.z_min_m,-.0016)
        self.assertEqual(g.substrate.epsilon_r,4.3)
        self.assertEqual(g.substrate.loss_tangent,.018)
        self.assertTrue(all(c.z_m==0. for c in g.copper))
        self.assertEqual(g.port.width_m,.00086401)
        self.assertIn('top copper: PEC, zero thickness in solver',g.assumptions)

    def test_normalize_once_preserves_shapes_and_inverse(self):
        g=load_pcb_geometry(self.config); before=g.as_dict()
        n,t=normalize_port_orientation(g)
        self.assertEqual(g.as_dict(),before)
        self.assertAlmostEqual(n.port.negative_xy_m[0],-.00035012,delta=COORD_TOLERANCE_M)
        self.assertAlmostEqual(n.port.positive_xy_m[0],.00035012,delta=COORD_TOLERANCE_M)
        restored=inverse_transform_geometry(n,t)
        for a,b in zip(g.copper,restored.copper):
            self.assertAlmostEqual(Polygon(a.vertices_xy_m).area,Polygon(b.vertices_xy_m).area,delta=1e-18)
            for p,q in zip(a.vertices_xy_m,b.vertices_xy_m):
                self.assertLess(math.dist(p,q),COORD_TOLERANCE_M)
        s=make_control_settings();m=make_pcb_domain_mesh(n,s)
        self.assertGreater(resolve_pcb_lumped_port(n,m,s).active_ex_edge_count,0)

    def test_stroked_lines_arcs_and_circle_flashes_are_not_dropped(self):
        self.append_graphics('''%ADD11C,0.2*%
%ADD12C,1*%
D11*
G01X200000Y800000D02*
X100000Y800000D01*
G75*
G01X200000Y1000000D02*
G02X100000Y1100000I0J100000D01*
G01*
D12*
X200000Y1600000D03*''')
        g=load_pcb_geometry(self.config)
        self.assertEqual(len(g.copper),2)
        left=Polygon(g.copper[0].vertices_xy_m)
        for point in ((.001,.008),(.001,.011),(.0016,.016)):
            self.assertTrue(left.covers(Point(point)),point)
        self.assertLess(left.bounds[0],.001)
        self.assertLess(abs(left.bounds[0]-.0009),2*CURVE_ERROR_M)

    def test_real_board_stroke_contact_conflict_not_silently_repaired(self):
        # Same width and inner edge as the user's GTL, not their production file.
        self.append_graphics('''%ADD11C,0.2032*%
D11*
G01X1296860Y600000D02*
X1296860Y1900000D01*''')
        g=load_pcb_geometry(self.config)
        n,_=normalize_port_orientation(g);s=make_control_settings()
        with self.assertRaisesRegex(ConfigurationError,'szczeliny'):
            resolve_pcb_lumped_port(n,make_pcb_domain_mesh(n,s),s)
        corrected=replace(self.config,port_positive_xy_m=(.012867,.012573))
        g=load_pcb_geometry(corrected)
        left,right=[Polygon(c.vertices_xy_m) for c in g.copper]
        self.assertAlmostEqual(left.distance(right),.00064412,delta=COORD_TOLERANCE_M)
        n,_=normalize_port_orientation(g)
        resolve_pcb_lumped_port(n,make_pcb_domain_mesh(n,s),s)
        self.assertEqual(self.config.port_positive_xy_m,tuple(v*1e-3 for v in self.value['port']['positive_mm']))

    def test_edge_touching_pad_unions_into_existing_conductor(self):
        self.append_graphics('%ADD12R,1X1*%\nD12*\nX150000Y650000D03*')
        g=load_pcb_geometry(self.config)
        self.assertEqual(len(g.copper),2)
        self.assertTrue(Polygon(g.copper[0].vertices_xy_m).covers(Point(.0015,.0065)))

    def test_inch_units_are_converted_by_importer(self):
        self.top.write_text('''%FSLAX26Y26*%
%MOIN*%
G01*
G36*
X100000Y100000D02*
X400000Y100000D01*
X400000Y900000D01*
X100000Y900000D01*
X100000Y100000D01*
G37*
G36*
X600000Y100000D02*
X900000Y100000D01*
X900000Y900000D01*
X600000Y900000D01*
X600000Y100000D01*
G37*
M02*''')
        config=replace(self.config,port_negative_xy_m=(.01016,.0127),port_positive_xy_m=(.01524,.0127))
        g=load_pcb_geometry(config)
        self.assertAlmostEqual(Polygon(g.copper[0].vertices_xy_m).bounds[0],.00254,delta=COORD_TOLERANCE_M)
        self.assertAlmostEqual(Polygon(g.copper[1].vertices_xy_m).bounds[2],.02286,delta=COORD_TOLERANCE_M)

    def test_outline_rejects_open_disconnected_or_branched_contours(self):
        original=self.outline.read_text()
        bad=(original.replace('X0Y0D01*',''),
             original.replace('M02*','X100000Y100000D02*\nX200000Y100000D01*\nM02*'),
             original.replace('M02*','X100000Y100000D02*\nX200000Y100000D01*\nX200000Y200000D01*\nX100000Y100000D01*\nM02*'))
        for text in bad:
            self.outline.write_text(text)
            with self.assertRaisesRegex(ConfigurationError,'GKO'):
                load_pcb_geometry(self.config)

    def test_clear_holes_point_contacts_and_bad_inputs_fail_explicitly(self):
        original=self.top.read_text()
        cases=['%LPC*%\nD10*\nX500000Y1000000D03*',
               # A positive ring away from both conductors cannot be a simple polygon.
               '%ADD12C,0.1*%\nD12*\nG75*\nG01X100000Y100000D02*\nG02X100000Y100000I50000J0D01*',
               # Point-only contact at the upper-left region corner.
               '%ADD12R,1X1*%\nD12*\nX150000Y1950000D03*']
        for content in cases:
            self.top.write_text(original)
            self.append_graphics(content)
            with self.assertRaises(ConfigurationError):load_pcb_geometry(self.config)
        for text in (original.replace('M02*',''),original.replace('M02*','UNKNOWN*\nM02*'),''):
            self.top.write_text(text)
            with self.assertRaises(ConfigurationError):load_pcb_geometry(self.config)
        with self.assertRaises(ConfigurationError):load_pcb_geometry(replace(self.config,copper_top_path=self.root/'missing.gtl'))
        with self.assertRaisesRegex(ConfigurationError,'expected top copper'):
            load_pcb_geometry(replace(self.config,copper_top_path=self.root/'paste.gtp'))

    @contextlib.contextmanager
    def native_fakes(self):
        self.engine=RunEngine()
        with patch('antenna_lab.solvers.openems.native_modules',return_value=(
                SimpleNamespace(openEMS=lambda **kw:self.engine),SimpleNamespace(ContinuousStructure=CSX))),\
                contextlib.redirect_stdout(io.StringIO()):
            yield

    def test_single_run_pipeline_native_fakes_normal_policy_and_output(self):
        out=self.root/'result'
        with self.native_fakes(),patch.object(runner,'normalize_port_orientation',wraps=normalize_port_orientation) as norm:
            result=runner.run_gerber_control(self.config_path,out)
        norm.assert_called_once()
        self.assertEqual(result['validation_status'],'unverified')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['simulation_settings']['cells_per_wavelength'],20)
        self.assertEqual(result['simulation_settings']['min_substrate_cells_z'],4)
        self.assertEqual(result['simulation_settings']['min_port_gap_cells'],2)
        self.assertEqual(make_control_settings(),make_synthetic_control_case()[1])
        calls=[c for c in self.engine.calls if c[0]=='Run']
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][2],dict(cleanup=False,numThreads=0))
        for file in ('summary.json','impedance.csv','geometry.json','geometry.source.json','import.json','native/model.xml'):
            self.assertTrue((out/file).is_file(),file)
        self.assertEqual(result,json.loads((out/'summary.json').read_text()))
        for item in ('soldermask: omitted','silkscreen: omitted','paste: omitted','no bottom copper','no vias'):
            self.assertIn(item,result['import']['assumptions'])
        self.assertEqual(result['import']['dependencies']['gerbonara'],'1.6.3')
        with self.native_fakes(),self.assertRaises(ConfigurationError):runner.run_gerber_control(self.config_path,out)
        self.assertFalse(any(c[0]=='Run' for c in self.engine.calls))

    def test_prepare_only_has_xml_without_any_run_or_calcport(self):
        out=self.root/'prepare'
        with self.native_fakes():
            result=runner.run_gerber_control(self.config_path,out,prepare_only=True,
                excitation_center_hz=2.45e9,excitation_cutoff_hz=.4e9,result_frequency_hz=(2.2e9,2.45e9,2.7e9))
        self.assertEqual(result['status'],'prepared')
        self.assertFalse(any(c[0]=='Run' for c in self.engine.calls))
        self.assertEqual(self.engine.port.calls,[])
        self.assertFalse((out/'impedance.csv').exists())
        self.assertEqual(result['simulation_settings']['excitation_center_hz'],2.45e9)

    def test_cli_and_preflight_failure_before_native(self):
        with patch.object(runner,'run_gerber_control',return_value={'status':'prepared'}) as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main([str(self.config_path),'--output',str(self.root/'cli'),'--prepare-only']),0)
            self.assertTrue(run.call_args.kwargs['prepare_only'])
        self.append_graphics('%ADD11C,0.2032*%\nD11*\nG01X1296860Y600000D02*\nX1296860Y1900000D01*')
        with patch('antenna_lab.solvers.openems.native_modules') as native:
            with self.assertRaises(ConfigurationError):runner.run_gerber_control(self.config_path,self.root/'bad')
            native.assert_not_called()


if __name__=='__main__': unittest.main()
