"""Targeted offline GUI command tests; no Tk display and no FDTD."""
import unittest

from antenna_lab.pcb.gui_commands import command_for, is_matching_preparation, cmd_display


BASE = {
    'project': r'C:\dev\antenna_solver_gpt\gerbs\dif4001\dif4001.epro',
    'quality': 'design', 'geometry_um': '10',
    'center_mhz': '1500', 'cutoff_mhz': '1400',
    'start_mhz': '1000', 'stop_mhz': '2000', 'step_mhz': '100',
    'fields_enabled': True, 'fields_mhz': '1000 2000',
    'overrides': '', 'source_config': '', 'pth_plating_um': '',
    'pcb_id': '',
    'run_dir': r'C:\dev\antenna_solver_gpt\outcomes\pcb_easyeda\dif4001_003',
    'field_view': 'active+geometry', 'threshold_db': '-40', 'margin_mm': '1',
    'phase_step': '15',
}


class GuiCommandTests(unittest.TestCase):
    def cmd(self, stage, **updates):
        return command_for(stage, dict(BASE, **updates), interpreter=r'C:\dev\.venv\Scripts\python.exe')

    def test_inspect_uses_source_inspector_without_reduced_solve(self):
        args = self.cmd('inspect')
        self.assertIn('antenna_lab.pcb.reduced_control', args)
        self.assertIn('--inspect-source', args)
        self.assertNotIn('--source-config', args)
        self.assertNotIn('--yes', args)

    def test_prepare_and_run_same_experiment_exactly_one_flag(self):
        prepare = self.cmd('prepare')
        run = self.cmd('run')
        self.assertIn('--prepare-only', prepare)
        self.assertNotIn('--yes', prepare)
        self.assertIn('--yes', run)
        self.assertNotIn('--prepare-only', run)
        self.assertTrue(is_matching_preparation(prepare, run))
        self.assertIn('--fields-mhz', run)
        self.assertEqual(run[run.index('--fields-mhz') + 1:run.index('--yes')],
                         ['1000.0','2000.0'])
        self.assertNotIn('--source-config', run)
        self.assertFalse(is_matching_preparation(prepare, self.cmd('run', step_mhz='50')))
        self.assertFalse(is_matching_preparation(None, run))

    def test_optional_explicit_inputs_override_automatic_contract(self):
        args = self.cmd('run', pth_plating_um='25')
        self.assertEqual(args[args.index('--pth-plating-um')+1],'25.0')
        manual = self.cmd('run', source_config=r'C:\tmp\my config.json')
        self.assertIn('--source-config', manual)
        with self.assertRaisesRegex(ValueError, 'source-config'):
            self.cmd('prepare', pth_plating_um='25', source_config=r'C:\tmp\x.json')

    def test_no_fields_and_solver_overrides(self):
        args = self.cmd('prepare', fields_enabled=False, fields_mhz='',
                        overrides='air_padding_wavelengths=0.1\n# comment\nmax_timesteps=50000')
        self.assertIn('--no-fields', args)
        self.assertNotIn('--fields-mhz', args)
        self.assertEqual(args.count('--openems-set'),2)
        self.assertIn('max_timesteps=50000',args)
        with self.assertRaisesRegex(ValueError,'KEY=VALUE'):
            self.cmd('prepare', overrides='bad-key')

    def test_input_validation_prevents_expensive_accidents(self):
        cases = [
            ({'project':'dif4001.zip'}, 'epro'),
            ({'step_mhz':'0'}, 'dodatnia'),
            ({'step_mhz':'90'}, 'dzielić'),
            ({'center_mhz':'2000','cutoff_mhz':'200'}, 'pasmem'),
            ({'fields_mhz':'1500 2500'}, 'zakresie'),
            ({'fields_mhz':'1000 1000'}, 'Powtórzone'),
            ({'quality':'bad'}, 'Profil'),
        ]
        for updates, fragment in cases:
            with self.subTest(updates=updates), self.assertRaisesRegex(ValueError, fragment):
                self.cmd('run', **updates)

    def test_report_offline_crop_animation_with_open(self):
        args = self.cmd('report')
        self.assertEqual(args[2:5],['-m','antenna_lab','report'])
        self.assertEqual(args[args.index('--phase-step')+1],'15')
        self.assertEqual(args[args.index('--field-view')+1],'active+geometry')
        self.assertIn('--open',args)
        self.assertNotIn('--yes',args)
        self.assertIn('dif4001_003',cmd_display(args))
        with self.assertRaisesRegex(ValueError, 'Krok fazy'):
            self.cmd('report',phase_step='10')

    def test_desktop_pythonw_launches_console_python_for_child_solver(self):
        args = command_for('prepare', BASE,
                           interpreter=r'C:\\dev\\.venv\\Scripts\\pythonw.exe')
        self.assertTrue(args[0].lower().endswith('python.exe'))
        self.assertNotIn('pythonw.exe', args[0].lower())

    def test_inspect_can_select_pcb_and_frequency_split_variants(self):
        inspect=self.cmd('inspect',pcb_id='board-1')
        self.assertEqual(inspect[-2:],['--source-pcb-id','board-1'])
        args=self.cmd('prepare', fields_mhz='1000, 2000')
        self.assertIn('2000.0',args)


if __name__ == '__main__':
    unittest.main()
