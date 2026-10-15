"""Real Git repositories; package manager boundaries stay mocked."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pm_git',ROOT/'scripts/package_manager.py')
pm=importlib.util.module_from_spec(spec);spec.loader.exec_module(pm)

class PackageGitTests(unittest.TestCase):
    def git(self,*args,repo=None):
        return subprocess.run(['git','-C',str(repo or self.repo),*args],check=True,text=True,capture_output=True).stdout.strip()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.repo=root/'repo';self.repo.mkdir();self.remote=root/'remote.git'
        self.git('init','--bare',str(self.remote));self.git('init','-b','main')
        self.git('config','user.name','Test');self.git('config','user.email','test@example.invalid')
        # Isolate from user global hooks and commit signing preferences.
        self.git('config','core.hooksPath',str(root/'no-hooks'));self.git('config','commit.gpgsign','false')
        (self.repo/'mise.toml').write_text('[bootstrap.packages]\n"brew-cask:slack"="latest"\n')
        (self.repo/'mise.Wonderful.toml').write_text('[bootstrap.packages]\n"brew-cask:slack"="latest"\n')
        (self.repo/'note.txt').write_text('original')
        self.git('add','.');self.git('commit','-m','Initial');self.git('remote','add','origin',str(self.remote));self.git('push','-u','origin','main')
        self.manager=pm.Manager(self.repo,'Wonderful',state_dir=root/'state')

    def test_remove_pushes_only_its_changes_preserving_other_staged_files(self):
        (self.repo/'note.txt').write_text('unrelated');self.git('add','note.txt')
        with patch.object(self.manager,'uninstall'):
            self.manager.remove('brew-cask:slack')
        self.assertEqual(self.git('diff','--cached','--name-only'),'note.txt')
        self.assertEqual(set(self.git('show','--pretty=format:','--name-only','HEAD').splitlines()),{'mise.toml','mise.Wonderful.toml'})
        self.assertEqual(self.git('show','HEAD:note.txt'),'original')
        self.assertEqual(self.git('rev-parse','HEAD'),self.git('rev-parse','main',repo=self.remote))

    def test_add_installs_then_declares_commits_and_pushes(self):
        with patch.object(self.manager,'install') as install:self.manager.add('brew:jq','shared')
        install.assert_called_once_with('brew:jq',dry=False)
        self.assertIn('brew:jq',self.git('show','HEAD:mise.toml'))
        self.assertEqual(self.git('rev-parse','HEAD'),self.git('rev-parse','main',repo=self.remote))

    def test_dirty_target_blocks_before_uninstall(self):
        p=self.repo/'mise.toml';p.write_text(p.read_text()+'# user change\n')
        with patch.object(self.manager,'uninstall') as uninstall:
            with self.assertRaisesRegex(ValueError,'existing edits'):self.manager.remove('brew-cask:slack')
            uninstall.assert_not_called()

    def test_push_failure_preserves_local_commit_and_reports_partial_success(self):
        hook=self.remote/'hooks/pre-receive';hook.write_text('#!/bin/sh\nexit 1\n');hook.chmod(0o755)
        self.git('config','core.hooksPath',str(self.remote/'hooks'),repo=self.remote)
        old=self.git('rev-parse','HEAD')
        with patch.object(self.manager,'uninstall'):
            with self.assertRaisesRegex(ValueError,'local commit succeeded, but push failed'):self.manager.remove('brew-cask:slack')
        self.assertNotEqual(old,self.git('rev-parse','HEAD'))
        self.assertNotIn('slack',(self.repo/'mise.toml').read_text())

    def test_failed_install_does_not_edit_or_commit(self):
        old=self.git('rev-parse','HEAD')
        with patch.object(self.manager,'install',side_effect=ValueError('install failed')):
            with self.assertRaisesRegex(ValueError,'install failed'):self.manager.add('brew:jq','shared')
        self.assertEqual(old,self.git('rev-parse','HEAD'))
        self.assertNotIn('jq',(self.repo/'mise.toml').read_text())

    def test_dry_run_does_not_commit_push_or_modify_config(self):
        old=self.git('rev-parse','HEAD')
        with patch.object(self.manager,'uninstall') as uninstall:self.manager.remove('brew-cask:slack',dry=True)
        self.assertTrue(uninstall.call_args.kwargs['dry'])
        self.assertEqual(old,self.git('rev-parse','HEAD'))
        self.assertEqual(self.git('status','--porcelain'),'')

    def test_unpublished_commits_block_before_package_changes(self):
        (self.repo/'note.txt').write_text('unpublished')
        self.git('add','note.txt');self.git('commit','-m','Unpublished')
        with patch.object(self.manager,'uninstall') as uninstall:
            with self.assertRaisesRegex(ValueError,'Local branch differs'):self.manager.remove('brew-cask:slack')
            uninstall.assert_not_called()
