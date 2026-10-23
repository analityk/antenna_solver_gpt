"""Offline tests of directory-scoped GUI settings; no Tk, native solver or FDTD."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from antenna_lab.pcb.gui_project_settings import (
    SETTINGS_FILE, project_parameters_dir, read_project_settings,
    write_project_settings,
)

DEFAULTS = {
    'project': '', 'csxcad_path': r'C:\dev\openems\openEMS',
    'quality': 'design', 'center_mhz': '1500', 'step_mhz': '100',
    'overrides': '', 'fields_enabled': True, 'fields_mhz': '1000 2000',
    'source_config': '', 'pth_plating_um': '', 'run_dir': '',
}


class ProjectGuiParametersTests(unittest.TestCase):
    def test_same_gerbs_directory_multiple_epro_share_settings(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            parent = root / 'gerbs' / 'projekt'
            parent.mkdir(parents=True)
            project1 = parent / 'projekt1.epro'
            project2 = parent / 'projekt2.epro'
            project1.touch()
            project2.touch()
            first = project_parameters_dir(project1, root)
            second = project_parameters_dir(project2, root)
            self.assertEqual(first, root / 'parameters' / 'projekt')
            self.assertEqual(first, second)
            values = dict(DEFAULTS, quality='verify', center_mhz='650',
                          fields_mhz='200 500 800',
                          overrides='air_padding_wavelengths=0.12',
                          source_config=r'C:\\CAD\\only-project1.json',
                          run_dir=r'C:\\outcomes\\project1_run',
                          csxcad_path='should-not-be-project-local')
            sidecar = write_project_settings(first, project1.parent, values, DEFAULTS)
            self.assertEqual(sidecar, first / SETTINGS_FILE)
            restored = read_project_settings(second, project2.parent, DEFAULTS)
            self.assertEqual(restored['quality'], 'verify')
            self.assertEqual(restored['center_mhz'], '650')
            self.assertEqual(restored['overrides'], 'air_padding_wavelengths=0.12')
            self.assertNotIn('csxcad_path', restored)
            self.assertNotIn('project', restored)
            self.assertNotIn('source_config', restored)
            self.assertNotIn('run_dir', restored)

    def test_distinct_gerbs_folders_are_isolated_including_nested(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            one = root / 'gerbs' / 'dif400' / 'pcb.epro'
            two = root / 'gerbs' / 'dif4001' / 'pcb.epro'
            nested = root / 'gerbs' / 'dif400' / 'revision' / 'pcb.epro'
            self.assertNotEqual(project_parameters_dir(one, root),
                                project_parameters_dir(two, root))
            self.assertEqual(project_parameters_dir(nested, root),
                             root / 'parameters' / 'dif400' / 'revision')
            self.assertEqual(project_parameters_dir(one, root),
                             root / 'parameters' / 'dif400')

    def test_only_epro_in_gerbs_root_uses_stem(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            self.assertEqual(project_parameters_dir(root/'gerbs'/'antenna.epro',root),
                             root/'parameters'/'antenna')

    def test_external_projects_stay_separate_but_siblings_share(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            first=root/'external1'/'same'/'a.epro'
            sibling=root/'external1'/'same'/'b.epro'
            other=root/'external2'/'same'/'c.epro'
            a=project_parameters_dir(first,root)
            self.assertEqual(a, project_parameters_dir(sibling,root))
            self.assertNotEqual(a, project_parameters_dir(other,root))
            self.assertEqual(a.parent, root/'parameters')

    def test_atomic_persistence_preserves_other_files(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            proj = root/'gerbs'/'projekt'/'pcb.epro'
            target = project_parameters_dir(proj, root)
            target.mkdir(parents=True)
            marker = target/'not-ours.txt'
            marker.write_text('intact', encoding='utf-8')
            values = dict(DEFAULTS)
            values['quality']='preview'
            write_project_settings(target, proj.parent, values, DEFAULTS)
            values['quality']='design'
            write_project_settings(target, proj.parent, values, DEFAULTS)
            self.assertEqual(marker.read_text(encoding='utf-8'), 'intact')
            self.assertEqual(read_project_settings(target, proj.parent, DEFAULTS)['quality'], 'design')
            self.assertFalse(list(target.glob('.gui-settings-*.tmp')))

    def test_missing_and_invalid_file_fail_safely(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            proj=root/'gerbs'/'proj'/'x.epro'
            target=project_parameters_dir(proj, root)
            self.assertIsNone(read_project_settings(target, proj.parent, DEFAULTS))
            target.mkdir(parents=True)
            (target/SETTINGS_FILE).write_text('{broken',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'odczytać'):
                read_project_settings(target, proj.parent, DEFAULTS)
            (target/SETTINGS_FILE).write_text(json.dumps(dict(
                schema_version=1, project_folder='another',
                settings=dict(quality='verify'))),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'inny folder'):
                read_project_settings(target, proj.parent, DEFAULTS)

    def test_strict_extension(self):
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'epro'):
                project_parameters_dir(Path(temp)/'gerbs'/'pcb.zip', temp)


if __name__ == '__main__':
    unittest.main()
