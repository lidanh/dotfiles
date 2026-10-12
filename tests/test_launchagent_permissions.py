import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dots_permissions',ROOT/'scripts/dots.py')
dots=importlib.util.module_from_spec(spec);spec.loader.exec_module(dots)

class LaunchAgentPermissionsTests(unittest.TestCase):
    def prepare(self, owner, dry=False):
        with patch.object(dots.Path,'home',return_value=Path('/Users/example')), \
             patch.object(dots,'symlink_parent',return_value=None), \
             patch.object(dots.Path,'is_symlink',return_value=False), \
             patch.object(dots.Path,'stat',return_value=SimpleNamespace(st_uid=owner,st_mode=0o40755)), \
             patch.object(dots.os,'getuid',return_value=501), \
             patch.object(dots.os,'access',return_value=True),patch.object(dots,'run') as run:
            dots.prepare_launch_agents(dry=dry)
            return run

    def test_root_owned_directory_gets_nonrecursive_chown(self):
        run=self.prepare(0)
        run.assert_called_once_with(['sudo','chown','501','/Users/example/Library/LaunchAgents'],dry=False)

    def test_user_owned_directory_is_unchanged(self):
        self.prepare(501).assert_not_called()

    def test_other_users_directory_is_not_taken_over(self):
        with self.assertRaisesRegex(ValueError,'owner'):self.prepare(502)

    def test_preview_does_not_execute_chown(self):
        run=self.prepare(0,dry=True)
        self.assertTrue(run.call_args.kwargs['dry'])

    def test_symlink_is_rejected(self):
        with patch.object(dots.Path,'is_symlink',return_value=True),patch.object(dots,'run') as run:
            with self.assertRaisesRegex(ValueError,'symlink'):dots.prepare_launch_agents()
            run.assert_not_called()

    def test_missing_directory_is_left_to_mise(self):
        with patch.object(dots.Path,'is_symlink',return_value=False),patch.object(dots,'symlink_parent',return_value=None), \
             patch.object(dots.Path,'stat',side_effect=FileNotFoundError),patch.object(dots,'run') as run:
            dots.prepare_launch_agents()
            run.assert_not_called()
