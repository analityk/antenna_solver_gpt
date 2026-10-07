"""Exact Gerbonara compatibility whitelist; no source edits or native solver."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import warnings

from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.drills import read_drill_source
from gerbonara import ExcellonFile
from gerbonara.excellon import ExcellonParser

FIXTURES=Path(__file__).parent/'fixtures/pcb-drills'


class DrillWarningTests(unittest.TestCase):
    def test_post_header_g90_identical_geometry_and_detached_warning(self):
        after=FIXTURES/'post_header_g90_PTH.drl'
        before=FIXTURES/'header_g90_PTH.drl'
        original=(after.read_bytes(),before.read_bytes())
        holes,meta=read_drill_source(after,2)
        expected,clean=read_drill_source(before,2)
        self.assertEqual(holes,expected)
        self.assertEqual(meta['tool_diameters_m'],clean['tool_diameters_m'])
        self.assertEqual(meta['hole_count'],1)
        self.assertEqual(holes[0][3],'T01')
        self.assertAlmostEqual(holes[0][0],.004826,places=15)
        self.assertAlmostEqual(holes[0][1],.01024543,places=15)
        self.assertAlmostEqual(holes[0][2],.000305,places=15)
        self.assertEqual(clean['compatibility_warnings'],[])
        self.assertEqual(meta['compatibility_warnings'],[dict(
            source_filename=after.name,statement='G90',
            warning_text=f'{after}:7 "G90": G90 header statement found after end of header',
            disposition='accepted_gerbonara_compatibility_warning')])
        self.assertEqual((after.read_bytes(),before.read_bytes()),original)
        self.assertEqual(read_drill_source(after,2),(holes,meta))

    def test_other_real_warnings_and_invalid_inputs_remain_fatal(self):
        source=(FIXTURES/'post_header_g90_PTH.drl').read_text()
        with TemporaryDirectory() as tmp:
            for name,text in [
                ('other-PTH.drl',source.replace('G05\nG90','G05\nM48\nG90')),
                ('before-PTH.drl','G90\n'+source),
                ('trailing-PTH.drl',source+'X1Y2\n'),
                ('invalid-PTH.drl',source.replace('X4.826Y10.24543','NOT_EXCELLON')),
                ('ambiguous.drl',source.replace(';TYPE=PLATED\n','')),
                ('conflict-NPTH.drl',source)]:
                p=Path(tmp)/name;p.write_text(text);original=p.read_bytes()
                with self.subTest(name=name),self.assertRaises(ConfigurationError):read_drill_source(p,2)
                self.assertEqual(p.read_bytes(),original)

    def test_exact_statement_text_category_and_both_parse_passes(self):
        path=FIXTURES/'header_g90_PTH.drl'
        allowed=f'{path}:7 "G90": G90 header statement found after end of header'
        cases=[(allowed.replace('"G90"','"G91"'),SyntaxWarning),
               (allowed+' (different warning)',SyntaxWarning),
               (allowed.replace('after end','before start'),SyntaxWarning),
               ('G90 header statement found after end of header',SyntaxWarning),
               ('some other parser warning',SyntaxWarning),
               (allowed,UserWarning)]
        original_open=ExcellonFile.open
        original_parse=ExcellonParser.do_parse
        for stage in ('open','tool_parse'):
            for text,category in cases:
                count=0
                def wrapped_parse(self,*args,**kwargs):
                    nonlocal count
                    count+=1
                    if count==2:warnings.warn(text,category)
                    return original_parse(self,*args,**kwargs)
                def wrapped_open(*args,**kwargs):
                    warnings.warn(text,category)
                    return original_open(*args,**kwargs)
                target=patch.object(ExcellonFile,'open',side_effect=wrapped_open) if stage=='open' else patch.object(ExcellonParser,'do_parse',wrapped_parse)
                with self.subTest(stage=stage,text=text,category=category),target,self.assertRaises(ConfigurationError):
                    read_drill_source(path,2)


if __name__=='__main__':unittest.main()
