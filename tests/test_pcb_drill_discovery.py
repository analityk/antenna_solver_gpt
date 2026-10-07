"""Actual format separates Gerber documentation from physical NC drills."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from gerbonara import ExcellonFile
from gerbonara.layers import identify_file

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.bundle import _role, load_bundle_geometry
from antenna_lab.pcb.drills import read_drill_source
from test_pcb_bundle import bundle_fixture
from test_pcb_multilayer import physical_stack, solid_gerber
from test_pcb_drills import drill_text

DRAWING=Path(__file__).parent/'fixtures/pcb-drills/Gerber_DrillDrawingLayer.GDD'


class DrillDiscoveryTests(unittest.TestCase):
    def test_format_before_filename_and_unknown_not_guessed(self):
        self.assertEqual(identify_file(DRAWING.read_text()),'gerber')
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('Gerber_DrillDrawingLayer.GDD','documentation.GDD','Gerber_DrillDrawingLayer.gbr'):
                p=root/name;p.write_bytes(DRAWING.read_bytes())
                with self.subTest(name=name):self.assertEqual(_role(p),'drill_drawing')
            for name in ('unknown_drill.txt','unknown_drill.GDD','DrillDrawingLayer.txt'):
                p=root/name;p.write_text('not a fabrication format')
                with self.subTest(name=name):self.assertEqual(_role(p),'unclassified')
            for name in ('PTH.DRL','NPTH.xln','nc_without_drill_name.txt'):
                p=root/name;p.write_text(drill_text())
                with self.subTest(name=name):self.assertEqual(_role(p),'drill')
            # A Gerber containing "drill" in its filename still follows Gerber roles.
            p=root/'drill_related.GTL';p.write_text(solid_gerber())
            self.assertEqual(_role(p),'top_copper')
            p=root/'unknown_drill.gbr';p.write_text(solid_gerber())
            self.assertEqual(_role(p),'unclassified_gerber')
            p.write_text(solid_gerber().replace('%MOMM*%','%MOMM*%\n%TF.FileFunction,Plated,1,2,PTH*%'))
            with self.assertRaisesRegex(ConfigurationError,'unsupported Gerber drill data'):_role(p)

    def test_mixed_folder_only_real_drill_reaches_excellon(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);directory=bundle_fixture(root/'gerbers',loop=True)
            top=directory/'Gerber_TopLayer.GTL'
            (directory/'F.Cu.gbr').write_text('%TF.FileFunction,Copper,L1,Top*%\n'+top.read_text());top.unlink()
            (directory/'B.Cu.gbr').write_text(solid_gerber(2,'Bot'))
            drill=directory/'Drill_PTH_Through.DRL'
            drill.write_text(drill_text(body='G90\nX5.000Y10.000\n'))
            drawing=directory/DRAWING.name;drawing.write_bytes(DRAWING.read_bytes())
            value=physical_stack(2);value['drills']=dict(pth_plating_um=25,pth_model='solid_pec_equivalent')
            config=root/'physical.json';config.write_text(json.dumps(value))
            original={p:p.read_bytes() for p in directory.iterdir()}
            with patch('antenna_lab.pcb.drills.read_drill_source',wraps=read_drill_source) as reader, \
                 patch.object(ExcellonFile,'open',wraps=ExcellonFile.open) as native_parser:
                _,geometry,meta=load_bundle_geometry(directory,config)
            for mocked in (reader,native_parser):
                self.assertTrue(mocked.called)
                self.assertEqual({Path(c.args[0]).name for c in mocked.call_args_list},{drill.name})
            records={r['name']:r for r in meta['discovered_files']}
            self.assertEqual(records[drawing.name]['role'],'drill_drawing')
            self.assertEqual(records[drawing.name]['disposition'],'omitted')
            self.assertEqual(records[drawing.name]['sha256'],sha256(drawing.read_bytes()).hexdigest())
            self.assertEqual(records[drill.name]['role'],'PTH')
            self.assertEqual(records[drill.name]['disposition'],'modeled')
            self.assertEqual(len(geometry.drills),1)
            self.assertEqual(geometry.drills[0].connected_layer_roles,('top','bottom'))
            self.assertEqual(len(meta['drill_sources']),1)
            self.assertEqual(meta['drill_sources'][0]['compatibility_warnings'][0]['statement'],'G90')
            # Omitting documentation has no physical effect.
            drawing.unlink();_,without,_=load_bundle_geometry(directory,config)
            self.assertEqual(geometry.as_dict(),without.as_dict())
            for path,data in original.items():
                if path!=drawing:self.assertEqual(path.read_bytes(),data)


if __name__=='__main__':unittest.main()
