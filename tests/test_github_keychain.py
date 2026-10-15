import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dots_keychain',ROOT/'scripts/dots.py')
dots=importlib.util.module_from_spec(spec);spec.loader.exec_module(dots)

class KeychainTests(unittest.TestCase):
    def test_loads_existing_effective_key_with_apple_ssh_add(self):
        with tempfile.TemporaryDirectory() as directory:
            key=Path(directory)/'custom key';key.touch()
            with patch.object(dots,'run') as run:
                run.return_value=subprocess.CompletedProcess([],0,stdout=f'identityfile {key}\nidentityfile /nonexistent/key\n')
                dots.github_keychain('Wonderful')
            commands=[c.args[0] for c in run.call_args_list]
            self.assertIn(['/usr/bin/ssh-add','--apple-use-keychain',str(key)],commands)
            self.assertTrue(any('dotfiles' in c and 'apply' in c for c in commands))

    def test_multiple_keys_require_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            keys=[Path(directory)/name for name in ('one','two')]
            for key in keys:key.touch()
            with patch.object(dots,'run') as run,patch.object(dots,'choose',return_value=str(keys[1])) as choose:
                run.return_value=subprocess.CompletedProcess([],0,stdout=''.join(f'identityfile {k}\n' for k in keys))
                dots.github_keychain('Personal')
                choose.assert_called_once()
            self.assertEqual(run.call_args.args[0],['/usr/bin/ssh-add','--apple-use-keychain',str(keys[1])])

    def test_preview_never_loads_keys(self):
        with patch.object(dots,'run') as run:
            dots.github_keychain('Personal',dry=True)
        self.assertTrue(all(c.kwargs.get('dry') for c in run.call_args_list))
        self.assertFalse(any('ssh-add' in str(c.args[0]) for c in run.call_args_list))

    def test_missing_local_key_has_actionable_error(self):
        with patch.object(dots,'run') as run:
            run.return_value=subprocess.CompletedProcess([],0,stdout='identityfile /nonexistent/key\n')
            with self.assertRaisesRegex(ValueError,'No local GitHub SSH key'):
                dots.github_keychain('Wonderful')
        self.assertFalse(any('ssh-add' in str(c.args[0]) for c in run.call_args_list))
