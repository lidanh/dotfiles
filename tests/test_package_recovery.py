import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dots_recovery', ROOT/'scripts/dots.py')
dots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dots)

class RecoveryTests(unittest.TestCase):
    def test_setup_records_packages_without_implicit_removal(self):
        with patch.object(dots,'Manager') as manager:
            dots.install_packages('Wonderful')
            manager.return_value.reconcile.assert_called_once_with(dry=False,remove=False)

    def test_preview_forwards_dry_run(self):
        with patch.object(dots,'Manager') as manager:
            dots.install_packages('Personal',dry=True)
            manager.return_value.reconcile.assert_called_once_with(dry=True,remove=False)

    def test_refresh_preserves_downloads_and_other_caches(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); cache=root/'cache'; cache.mkdir()
            api=cache/'system-brew/api';api.mkdir(parents=True)
            (api/'cask.json').write_text('old')
            (cache/'keep').write_text('keep')
            binary=root/'mise';binary.write_text('#!/bin/sh\nprintf "%s\\n" "$TEST_CACHE"\n');binary.chmod(0o755)
            brew=root/'brew';brew.write_text('#!/bin/sh\nexit 0\n');brew.chmod(0o755)
            import os
            env=dict(os.environ,PATH=f'{root}:/usr/bin:/bin',TEST_CACHE=str(cache))
            subprocess.run(['/bin/bash',str(ROOT/'scripts/refresh-packages.sh')],env=env,check=True)
            self.assertFalse((api/'cask.json').exists())
            self.assertTrue((cache/'keep').exists())

    def test_failed_refresh_records_failure_without_installing(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory)
            with patch.object(dots.Path,'home',return_value=home),patch.object(dots.subprocess,'run') as run:
                run.return_value=subprocess.CompletedProcess([],1)
                self.assertEqual(dots.update_packages('Personal'),1)
                self.assertEqual(run.call_count,1)
                report=json.loads((home/'.local/state/lidan-dotfiles/update.json').read_text())
                self.assertFalse(report['ok'])
                self.assertIn('refresh-packages.sh',report['failures'][0])


    def test_foreground_update_has_live_output_and_package_counter(self):
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as directory:
            output=io.StringIO()
            def execute(command,**kwargs):
                kwargs['stdout'].write('installer progress\n');kwargs['stdout'].flush()
                return subprocess.CompletedProcess(command,0)
            with patch.object(dots.Path,'home',return_value=Path(directory)),patch.object(dots,'Manager') as manager,patch.object(dots.subprocess,'run',side_effect=execute),redirect_stdout(output):
                manager.return_value.desired.return_value={'brew:jq','mas:123'}
                self.assertEqual(dots.update_packages('Personal'),0)
            self.assertIn('[1/1] Checking/updating brew:jq',output.getvalue())
            self.assertIn('installer progress',output.getvalue())
            self.assertIn('Update finished',output.getvalue())

    def test_background_update_keeps_child_output_in_log(self):
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as directory:
            output=io.StringIO()
            def execute(command,**kwargs):
                self.assertIs(kwargs['stdin'],subprocess.DEVNULL)
                kwargs['stdout'].write('background detail\n');kwargs['stdout'].flush()
                return subprocess.CompletedProcess(command,0)
            with patch.object(dots.Path,'home',return_value=Path(directory)),patch.object(dots,'Manager') as manager,patch.object(dots.subprocess,'run',side_effect=execute),redirect_stdout(output):
                manager.return_value.desired.return_value={'brew:jq'}
                self.assertEqual(dots.update_packages('Personal',background=True),0)
            self.assertNotIn('background detail',output.getvalue())
            self.assertNotIn('[1/1]',output.getvalue())
            self.assertIn('background detail',(Path(directory)/'Library/Logs/lidan-dotfiles/update.log').read_text())

if __name__ == '__main__': unittest.main()
