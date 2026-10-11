"""Exercise entry points with external installers replaced by recording commands.

No test may install software or change the real user's configuration.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dots_installation', ROOT / 'scripts/dots.py')
dots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dots)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home'; self.home.mkdir()
        self.repo = self.base / 'repo with spaces'
        shutil.copytree(ROOT, self.repo, ignore=shutil.ignore_patterns('.git', '__pycache__', '.dots-profile'))
        self.bin = self.home / '.local/bin'; self.bin.mkdir(parents=True)
        self.log = self.base / 'commands.jsonl'
        self.env = dict(os.environ, HOME=str(self.home), PATH=f'{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin',
                        TEST_LOG=str(self.log), PYTHONDONTWRITEBYTECODE='1')
        # These replace only process boundaries, leaving bootstrap.sh and bin/dots real.
        for name in ('mise', 'uv', 'brew'):
            command = self.bin / name
            command.write_text(f'#!{sys.executable}\n' + '''import json,os,sys
with open(os.environ['TEST_LOG'], 'a') as f: f.write(json.dumps([os.path.basename(sys.argv[0]),*sys.argv[1:]])+'\\n')
if sys.argv[1:] == ['cache','path']: print(os.path.join(os.environ['HOME'],'cache'))
if 'packages' in sys.argv and os.environ.get('FAIL_PACKAGES'): sys.exit(17)
''')
            command.chmod(0o755)

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def bootstrap(self, *args):
        return subprocess.run(['/bin/bash', str(self.repo/'bootstrap.sh'), *args],
                              env=self.env, capture_output=True, text=True, cwd='/tmp')

    def test_clean_bootstrap_both_profiles_and_order(self):
        for profile in dots.PROFILES:
            with self.subTest(profile=profile):
                (self.repo/'.dots-profile').unlink(missing_ok=True)
                self.log.unlink(missing_ok=True)
                result = self.bootstrap(profile)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.repo/'.dots-profile').read_text().strip(), profile)
                commands = self.commands()
                packages = next(i for i,c in enumerate(commands) if 'packages' in c)
                python = next(i for i,c in enumerate(commands) if c[:3] == ['uv','python','install'])
                setup = next(i for i,c in enumerate(commands) if 'machine:setup' in c)
                self.assertLess(next(i for i,c in enumerate(commands) if c==['brew','update']),packages)
                self.assertLess(packages, python)
                self.assertLess(python, setup)
                self.assertIn(str(self.repo.resolve()), commands[setup])
                self.assertIn(profile, commands[setup])

    def test_failed_prerequisite_stops_before_setup(self):
        self.env['FAIL_PACKAGES'] = '1'
        result = self.bootstrap('Personal')
        self.assertEqual(result.returncode, 17)
        self.assertFalse(any('machine:setup' in c for c in self.commands()))

    def test_preview_does_not_save_profile_or_install_prerequisites(self):
        result = self.bootstrap('Wonderful','--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.repo/'.dots-profile').exists())
        self.assertEqual(len(self.commands()), 1)
        self.assertIn('--dry-run', self.commands()[0])

    def test_legacy_config_symlink_rejected_before_mutations(self):
        (self.home/'.config').symlink_to(self.base)
        result = self.bootstrap('Personal')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.commands(), [])
        self.assertFalse((self.repo/'.dots-profile').exists())

    def test_existing_profile_cannot_silently_switch(self):
        (self.repo/'.dots-profile').write_text('Personal\n')
        result = self.bootstrap('Wonderful')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.commands(), [])

    def test_dots_forwards_arguments_without_shell_interpolation(self):
        (self.repo/'.dots-profile').write_text('Personal\n')
        arg='$(touch should-not-exist)'
        result=subprocess.run([str(self.repo/'bin/dots'),'add',arg,'--scope','shared','--dry-run'],
                              env=self.env,capture_output=True,text=True,cwd=str(self.base))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(arg,self.commands()[-1])
        self.assertFalse((self.base/'should-not-exist').exists())

    def test_github_connects_the_https_clone_to_ssh(self):
        with patch.object(dots, 'run') as run:
            run.return_value=subprocess.CompletedProcess([],0,stdout='https://github.com/lidanh/dotfiles.git\n')
            dots.github_setup()
        commands=[call.args[0] for call in run.call_args_list]
        self.assertTrue(any('set-url' in c and 'git@github.com:lidanh/dotfiles.git' in c for c in commands))

    def test_github_does_not_repoint_a_fork(self):
        with patch.object(dots, 'run') as run:
            run.return_value=subprocess.CompletedProcess([],0,stdout='https://github.com/another-user/dotfiles.git\n')
            dots.github_setup()
        self.assertFalse(any('set-url' in call.args[0] for call in run.call_args_list))

    def test_check_fails_when_last_background_update_failed(self):
        result_file=self.home/'.local/state/lidan-dotfiles/update.json'
        result_file.parent.mkdir(parents=True)
        result_file.write_text(json.dumps({'ok':False,'failures':['a failed installer']}))
        with patch.object(dots.Path,'home',return_value=self.home), patch.object(dots,'preflight_links'), \
             patch.object(dots,'system',return_value=False), patch.object(dots,'run') as run:
            run.return_value=subprocess.CompletedProcess([],0)
            self.assertEqual(dots.check_machine('Personal'),1)

if __name__ == '__main__': unittest.main()
