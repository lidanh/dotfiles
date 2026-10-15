import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('package_manager',ROOT/'scripts/package_manager.py')
pm=importlib.util.module_from_spec(spec);spec.loader.exec_module(pm)

class PackageManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.state=self.root/'state'
        (self.root/'mise.toml').write_text('[bootstrap.packages]\n"brew:jq" = "latest"\n"brew-cask:slack" = "latest"\n')
        (self.root/'mise.Wonderful.toml').write_text('[bootstrap.packages]\n"brew-cask:slack" = { version = "latest" }\n')
        self.manager=pm.Manager(self.root,'Wonderful',state_dir=self.state)

    def test_remove_edits_every_config_and_preserves_other_content(self):
        (self.root/'mise.Personal.toml').write_text('# keep\n[bootstrap.packages."brew-cask:slack"]\nversion = "latest"\n[vars]\nhello="world"\n')
        changes=self.manager.removal_edits('brew-cask:slack')
        self.assertEqual(len(changes),3)
        self.assertIn('"brew:jq"',changes[self.root/'mise.toml'])
        self.assertIn('[vars]',changes[self.root/'mise.Personal.toml'])
        self.assertNotIn('brew-cask:slack',''.join(changes.values()))

    def test_multiline_value_removed_without_damaging_next_entry(self):
        p=self.root/'mise.toml';p.write_text('[bootstrap.packages]\n"brew-cask:slack" = {\nversion="latest",\n}\n"brew:jq"="latest"\n')
        # TOML 1.0 rejects multiline inline tables; refuse invalid files without mutation.
        with self.assertRaises(ValueError):self.manager.removal_edits('brew-cask:slack')
        self.assertIn('slack',p.read_text())

    def test_initial_sync_has_no_removal_candidates(self):
        add,remove=self.manager.plan()
        self.assertEqual(remove,[])
        self.assertIn('brew:jq',add)

    def test_sync_only_removes_recorded_packages(self):
        self.manager.save({'brew:fd','brew:jq'})
        _,remove=self.manager.plan()
        self.assertEqual(remove,['brew:fd'])

    def test_failed_removal_preserves_config_and_ledger(self):
        self.manager.save({'brew-cask:slack'})
        with patch.object(self.manager,'git_preflight'),patch.object(self.manager,'uninstall',side_effect=ValueError('failed')):
            with self.assertRaises(ValueError):self.manager.remove('brew-cask:slack')
        self.assertIn('brew-cask:slack',(self.root/'mise.toml').read_text())
        self.assertIn('brew-cask:slack',self.manager.load())

    def test_protected_dependency_cannot_be_removed(self):
        with self.assertRaisesRegex(ValueError,'required'):self.manager.remove('brew:uv')

    def test_dry_remove_changes_neither_files_nor_ledger(self):
        before=(self.root/'mise.toml').read_text()
        with patch.object(self.manager,'uninstall') as uninstall,patch.object(self.manager,'git_preflight'):
            self.manager.remove('brew-cask:slack',dry=True)
        self.assertEqual(before,(self.root/'mise.toml').read_text())
        self.assertFalse(self.state.exists())
        self.assertTrue(uninstall.call_args.kwargs['dry'])

    def test_failed_sync_removal_remains_pending(self):
        self.manager.save({'brew:fd'})
        with patch.object(self.manager,'install'),patch.object(self.manager,'uninstall',side_effect=ValueError('blocked')):
            with self.assertRaisesRegex(ValueError,'fd'):self.manager.reconcile()
        self.assertIn('brew:fd',self.manager.load())

    def test_removed_formula_dependency_is_not_forced(self):
        with patch.object(self.manager,'present',side_effect=[True,False]),patch.object(self.manager,'command') as command:
            self.manager.uninstall('brew:jq')
        args=command.call_args.args[0]
        self.assertEqual(args,['brew','uninstall','--formula','jq'])
        self.assertNotIn('--ignore-dependencies',args)

    def test_invalid_tokens_rejected(self):
        for token in ['brew:--force','brew:../foo','brew-cask:x;rm','other:app']:
            with self.assertRaises(ValueError):pm.split_package(token)

    def test_protected_aliases_cannot_be_removed(self):
        for package in ['brew:homebrew/core/uv','brew:custom/tap/git']:
            with self.assertRaisesRegex(ValueError,'required'):self.manager.remove(package)

    def test_corrupt_ledger_blocks_before_install_or_uninstall(self):
        self.state.mkdir();self.manager.ledger.write_text('broken')
        with patch.object(self.manager,'install') as install,patch.object(self.manager,'uninstall') as uninstall:
            with self.assertRaises(ValueError):self.manager.add('brew:fd','shared')
            with self.assertRaises(ValueError):self.manager.remove('brew-cask:slack')
            install.assert_not_called();uninstall.assert_not_called()

    def test_native_removal_keeps_artifact_evidence_across_retries(self):
        artifact=self.root/'Old.app';artifact.mkdir()
        with patch.object(self.manager,'present',return_value=False),patch.object(self.manager,'command'),patch.object(self.manager,'native_receipts',return_value=[{'apps':[str(artifact)]}]):
            with self.assertRaisesRegex(ValueError,'remains'):self.manager.uninstall('brew-cask:slack')
        with patch.object(self.manager,'present',return_value=False),patch.object(self.manager,'command'),patch.object(self.manager,'native_receipts',return_value=[]):
            with self.assertRaisesRegex(ValueError,'remains'):self.manager.uninstall('brew-cask:slack')
            artifact.rmdir();self.manager.uninstall('brew-cask:slack')
        self.assertEqual(list((self.state/'pending-removals').iterdir()),[])

    def test_failed_installs_prevent_all_sync_removals(self):
        self.manager.save({'brew:fd'})
        with patch.object(self.manager,'install',side_effect=ValueError('failed')),patch.object(self.manager,'uninstall') as uninstall:
            with self.assertRaises(ValueError):self.manager.reconcile()
            uninstall.assert_not_called()
        self.assertEqual(self.manager.load(),{'brew:fd'})

if __name__=='__main__':unittest.main()

