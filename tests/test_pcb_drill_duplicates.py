"""Across-source duplicate exports only; physical overlaps stay errors."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from gerbonara import ExcellonFile

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.bundle import load_bundle_geometry
from antenna_lab.pcb.drills import load_drills
from antenna_lab.pcb.transform import normalize_port_orientation
from antenna_lab.pcb.gerber_quality import gerber_quality_settings
from antenna_lab.solvers.pcb_mesh import make_pcb_domain_mesh
from antenna_lab.solvers.openems_pcb import install_pcb_geometry
from test_pcb_bundle import bundle_fixture
from test_pcb_multilayer import physical_stack, solid_gerber, BAND
from test_pcb_drills import DrillCSX, drill_text


class DrillDuplicateTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.directory=bundle_fixture(self.root/'gerbers',loop=True)
        (self.directory/'B_Cu.gbr').write_text(solid_gerber())
        value=physical_stack(2);value['drills']=dict(pth_plating_um=25,pth_model='solid_pec_equivalent')
        self.config=self.root/'physical.json';self.config.write_text(json.dumps(value))
        self.main=self.directory/'Drill_PTH_Through.DRL';self.via=self.directory/'Drill_PTH_Through_Via.DRL'
        self.text=drill_text(4.826,10.24543,.305)
        self.main.write_text(self.text);self.via.write_text(self.text)

    def test_duplicate_provenance_one_geometry_anchor_and_cylinder(self):
        original={p:p.read_bytes() for p in (self.main,self.via)}
        with patch.object(ExcellonFile,'open',wraps=ExcellonFile.open) as reader:
            cfg,g,meta=load_bundle_geometry(self.directory,self.config)
        self.assertEqual({Path(c.args[0]).name for c in reader.call_args_list},{self.main.name,self.via.name})
        self.assertEqual(len(g.drills),1);self.assertEqual(g.drills[0].id,self.main.name+':1')
        sources=meta['drill_sources'];self.assertEqual([s['hole_count'] for s in sources],[1,1])
        self.assertEqual([s['modeled_hole_count'] for s in sources],[1,0])
        duplicate=sources[1]['suppressed_duplicate_holes'][0]
        self.assertEqual(duplicate,dict(source_filename=self.via.name,tool='T01',x_m=4.826*1e-3,
            y_m=10.24543*1e-3,drill_diameter_m=.000305,disposition='duplicate_pth_suppressed',
            canonical_source=str(self.main.resolve()),canonical_drill_id=self.main.name+':1'))
        self.assertTrue(all(len(s['sha256'])==64 for s in sources))
        again,_=load_drills(g,list(reversed(meta['discovered_files'])),dict(pth_plating_um=25,pth_model='solid_pec_equivalent'))
        self.assertEqual(again.as_dict(),g.as_dict())
        normalized,_=normalize_port_orientation(g);settings,_=gerber_quality_settings('preview',**BAND)
        mesh=make_pcb_domain_mesh(normalized,settings,gerber_quality='preview')
        self.assertEqual(len(mesh.drill_centres_xy_m),1)
        csx=DrillCSX();install_pcb_geometry(csx,normalized,mesh,settings,copper_config=cfg,gerber_quality='preview')
        self.assertEqual(len(csx.cylinders),1)
        # Masks consume the same single geometry record, never raw source holes.
        self.assertEqual(len(normalized.as_dict()['drills']),1)
        for p,data in original.items():self.assertEqual(p.read_bytes(),data)

    def test_conflicting_overlaps_remain_fatal(self):
        for text in (drill_text(4.826,10.24543,.4),drill_text(4.9,10.24543,.305)):
            self.via.write_text(text)
            with self.assertRaisesRegex(ConfigurationError,'Overlapping'):load_bundle_geometry(self.directory,self.config)
        self.via.unlink();(self.directory/'Drill_NPTH.drl').write_text(self.text)
        with self.assertRaisesRegex(ConfigurationError,'Overlapping'):load_bundle_geometry(self.directory,self.config)

    def test_via_only_and_lexical_fallback(self):
        self.main.unlink();_,g,meta=load_bundle_geometry(self.directory,self.config)
        self.assertEqual(len(g.drills),1);self.assertEqual(g.drills[0].id,self.via.name+':1')
        self.assertEqual(meta['drill_sources'][0]['suppressed_duplicate_holes'],[])
        self.via.rename(self.directory/'Z_PTH.drl');(self.directory/'A_PTH.drl').write_text(self.text)
        _,g,_=load_bundle_geometry(self.directory,self.config)
        self.assertEqual(g.drills[0].id,'A_PTH.drl:1')

    def test_tolerance_not_rounding_and_same_source_duplicates_not_hidden(self):
        # Decimal mm perturbations convert below the existing 1e-10 m tolerance.
        self.via.write_text(self.text.replace('X4.826000','X4.82600004').replace('C0.305000','C0.30500004'))
        _,g,_=load_bundle_geometry(self.directory,self.config)
        self.assertEqual(len(g.drills),1);self.assertEqual(g.drills[0].x_m,4.826*1e-3)
        self.via.write_text(self.text.replace('C0.305000','C0.3050002'))
        with self.assertRaisesRegex(ConfigurationError,'Overlapping'):load_bundle_geometry(self.directory,self.config)
        self.via.unlink();self.main.write_text(self.text.replace('M30','X4.826Y10.24543\nM30'))
        with self.assertRaisesRegex(ConfigurationError,'Overlapping'):load_bundle_geometry(self.directory,self.config)


if __name__=='__main__':unittest.main()
