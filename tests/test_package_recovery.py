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
    def test_failed_package_does_not_block_the_remaining_packages(self):
        with patch.object(dots,'packages',return_value={'brew-cask:cursor':'latest','brew:jq':'latest'}), patch.object(dots,'run') as run:
            run.side_effect=[subprocess.CompletedProcess([],1),subprocess.CompletedProcess([],0),subprocess.CompletedProcess([],0)]
            with self.assertRaisesRegex(ValueError,'brew-cask:cursor'):
                dots.install_packages('Wonderful')
            self.assertIn('brew:jq',run.call_args_list[1].args[0])
            self.assertIn(str(ROOT/'scripts/warp.py'),run.call_args_list[2].args[0])

    def test_preview_never_installs_a_package(self):
        with patch.object(dots,'packages',return_value={'brew:jq':'latest'}),patch.object(dots,'run') as run:
            run.return_value=subprocess.CompletedProcess([],0)
            dots.install_packages('Personal',dry=True)
            self.assertTrue(all('--dry-run' in c.args[0] for c in run.call_args_list))

    def test_interrupt_stops_remaining_packages(self):
        with patch.object(dots,'packages',return_value={'brew:jq':'latest','brew:fd':'latest'}),patch.object(dots,'run') as run:
            run.return_value=subprocess.CompletedProcess([],130)
            with self.assertRaises(KeyboardInterrupt): dots.install_packages('Personal')
            self.assertEqual(run.call_count,1)

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

if __name__ == '__main__': unittest.main()
