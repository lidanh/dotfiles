import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dots', ROOT / 'scripts/dots.py')
dots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dots)

class DotfilesTests(unittest.TestCase):
    def test_profile_must_be_selected_and_valid(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): dots.load_profile(pathlib.Path(d))
            p = pathlib.Path(d) / '.dots-profile'
            p.write_text('Work\n')
            with self.assertRaises(ValueError): dots.load_profile(pathlib.Path(d))
            p.write_text('Wonderful\n')
            self.assertEqual(dots.load_profile(pathlib.Path(d)), 'Wonderful')

    def test_shared_and_wonderful_packages(self):
        personal = dots.packages(ROOT, 'Personal')
        work = dots.packages(ROOT, 'Wonderful')
        self.assertNotIn('brew-cask:slack', personal)
        self.assertIn('brew-cask:slack', work)
        self.assertIn('brew-cask:adobe-creative-cloud', personal)
        self.assertIn('mas:497799835', personal)
        self.assertTrue(set(personal) <= set(work))

    def test_exact_package_beats_partial_results(self):
        catalog = ['brew:jq', 'brew:jq-lsp', 'brew-cask:google-chrome']
        self.assertEqual(dots.matches('jq', catalog), ['brew:jq'])
        self.assertEqual(dots.matches('chrome', catalog), ['brew-cask:google-chrome'])
        self.assertEqual(dots.matches('$(touch /tmp/pwn)', catalog), [])

    def test_ambiguous_match_requires_choice(self):
        with patch('builtins.input', return_value='2'):
            self.assertEqual(dots.choose(['brew:foo', 'brew-cask:foo'], 'Choose'), 'brew-cask:foo')
        with patch('builtins.input', return_value='x'):
            with self.assertRaises(ValueError): dots.choose(['a','b'], 'Choose')

    def test_conflicting_parent_symlink_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            home = pathlib.Path(d)
            external = home / 'legacy'; external.mkdir()
            (home / '.config').symlink_to(external)
            self.assertTrue(dots.symlink_parent(home / '.config/fish/config.fish', home))
            self.assertFalse(dots.symlink_parent(home / '.gitconfig', home))

    def test_read_only_report_has_no_apply_commands(self):
        for command in dots.status_commands():
            self.assertIn('status', command)
            self.assertNotIn('apply', command)

if __name__ == '__main__': unittest.main()
