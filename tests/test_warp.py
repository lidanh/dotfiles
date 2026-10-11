import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('warp',ROOT/'scripts/warp.py')
warp=importlib.util.module_from_spec(spec);spec.loader.exec_module(warp)

class WarpTests(unittest.TestCase):
    def test_install_uses_homebrew_and_personal_tap(self):
        with patch.object(warp,'run') as run,patch.object(warp.shutil,'which',return_value='/test/brew'):
            run.return_value=subprocess.CompletedProcess([],1,stdout='')
            warp.install()
            commands=[c.args[0] for c in run.call_args_list]
            self.assertIn(['/test/brew','tap','lidanh/dotfiles','https://github.com/lidanh/dotfiles.git'],commands)
            self.assertIn(['/test/brew','install','--cask','--adopt','lidanh/dotfiles/warp'],commands)
            self.assertFalse(any('ditto' in str(c) for c in commands))

    def test_update_uses_brew_and_skips_missing_app(self):
        with patch.object(warp,'run') as run,patch.object(warp.shutil,'which',return_value='/test/brew'):
            run.return_value=subprocess.CompletedProcess([],1,stdout='')
            warp.install(update=True)
            self.assertFalse(any('upgrade' in c.args[0] for c in run.call_args_list))

    def test_update_checks_latest_even_for_self_updating_cask(self):
        with patch.object(warp,'run') as run,patch.object(warp.shutil,'which',return_value='/test/brew'):
            run.return_value=subprocess.CompletedProcess([],0,stdout='warp\n')
            warp.install(update=True)
            self.assertIn(['/test/brew','upgrade','--cask','--greedy','lidanh/dotfiles/warp'],[c.args[0] for c in run.call_args_list])

    def test_cask_checksum_exception_is_scoped_and_signature_verified(self):
        source=(ROOT/'Casks/warp.rb').read_text()
        self.assertIn('version :latest',source)
        self.assertIn('sha256 :no_check',source)
        self.assertIn('2BBY89MBSN',source)
        self.assertIn('preflight_steps do',source)
        self.assertIn('--strict',source)
