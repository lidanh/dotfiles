import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('check_report',ROOT/'scripts/check_report.py')
report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)

class CheckReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'update.json'
        self.data=[{'files':[{'target':'~/.gitconfig','state':'applied'}],'edits':[], 'history':{'noisy':'not needed'}},
                   {'macos_defaults':{'available':True,'entries':[{'domain':'com.apple.dock','key':'tilesize','value':54,'current':'54','state':'set'}]}},
                   {'launchd':{'available':True,'agents':[{'name':'updates','state':'loaded'}]}},
                   {'login_shell':{'available':True,'state':'set','shell':'/opt/homebrew/bin/fish'}}]
        self.native=Mock(side_effect=lambda command:subprocess.CompletedProcess(command,0,stdout=json.dumps(self.data.pop(0)),stderr=''))
        self.manager=Mock();self.manager.desired.return_value={'brew:jq'};self.manager.status.return_value={'brew:jq':'installed'};self.manager.load.return_value={'brew:jq'}
        self.system=Mock(return_value=False)

    def run_check(self,**kwargs):
        output=io.StringIO()
        with redirect_stdout(output):code=report.check('Wonderful',native=self.native,preflight=Mock(),system=self.system,manager=self.manager,report_path=self.path,**kwargs)
        return code,output.getvalue()

    def test_healthy_report_is_short_without_tables_commands_or_json(self):
        code,text=self.run_check()
        self.assertEqual(code,0);self.assertIn('All checked settings match',text)
        self.assertLess(len(text.splitlines()),12)
        self.assertNotIn('noisy',text);self.assertNotIn('bootstrap',text)
        for call in self.native.call_args_list:
            self.assertIn('status',call.args[0]);self.assertNotIn('apply',call.args[0])

    def test_groups_observed_trackpad_types_dock_and_failed_dropbox_update(self):
        entries=self.data[1]['macos_defaults']['entries']
        for domain in ['com.apple.AppleMultitouchTrackpad','com.apple.driver.AppleBluetoothMultitouch.trackpad']:
            for key in ['Dragging','TrackpadPinch','TrackpadRotate','TrackpadTwoFingerDoubleTapGesture']:
                value=key!='Dragging'
                entries.append(dict(domain=domain,key=key,value=value,current=f'{int(value)} (integer; expected boolean)',state='differs'))
        entries.append(dict(domain='com.apple.dock',key='persistent-apps',value=['/Applications/X.app']*17,current='array (23 items)',state='differs'))
        self.path.write_text(json.dumps(dict(time='2026-10-15T11:02:09+03:00',ok=False,failures=['/bin/mise bootstrap packages upgrade --yes brew-cask:dropbox'],log='/tmp/update.log')))
        code,text=self.run_check()
        self.assertEqual(code,1);self.assertNotIn('Trackpad: 8',text);self.assertIn('Dock:',text);self.assertIn('23',text);self.assertIn('17',text)
        self.assertIn('dropbox',text);self.assertIn('dots apply',text);self.assertIn('dots update',text)
        self.assertNotIn('/bin/mise',text);self.assertNotIn('TrackpadPinch',text)
        self.assertLess(len(text.splitlines()),20)

    def test_verbose_retains_diagnostics(self):
        _,text=self.run_check(verbose=True)
        self.assertIn('noisy',text);self.assertIn('com.apple.dock',text)

    def test_broken_status_is_unknown_not_healthy_and_other_checks_continue(self):
        self.native.side_effect=[subprocess.CompletedProcess([],1,stdout='',stderr='failed to read files'),*[subprocess.CompletedProcess([],0,stdout=json.dumps(x),stderr='') for x in self.data[1:]]]
        code,text=self.run_check()
        self.assertEqual(code,1);self.assertIn('Could not check',text);self.assertNotIn('All checked settings match',text)
        self.manager.status.assert_called_once();self.system.assert_called_once()

    def test_unknown_json_shape_fails_closed(self):
        self.data[1]={}
        code,text=self.run_check()
        self.assertEqual(code,1);self.assertIn('Could not check',text)

    def test_unavailable_native_category_is_reported(self):
        self.data[2]={'launchd':{'available':False,'reason':'no graphical session'}}
        code,text=self.run_check()
        self.assertEqual(code,1);self.assertIn('no graphical session',text)

    def test_system_messages_are_focused_and_deferred_is_not_ok(self):
        def system():print('DEFERRED: no online built-in display; run dots apply with the lid open.');return True
        self.system=system
        code,text=self.run_check()
        self.assertEqual(code,1);self.assertIn('lid open',text)

    def test_package_failure_and_pending_removal_have_distinct_actions(self):
        self.manager.status.return_value={'brew:jq':'missing'};self.manager.load.return_value={'brew:jq','brew:fd'}
        code,text=self.run_check()
        self.assertEqual(code,1);self.assertIn('jq',text);self.assertIn('fd',text)
        self.assertIn('dots setup',text);self.assertIn('dots sync',text)

    def test_corrupt_update_report_does_not_hide_healthy_categories(self):
        self.path.write_text('[]')
        code,text=self.run_check()
        self.assertEqual(code,1);self.assertIn('Could not check',text);self.assertIn('Packages',text)

    def test_verbose_display_diagnostics_are_not_reported_as_issues(self):
        def system():
            print('Built-in display available modes:')
            print('DIAGNOSTIC MODE DATA')
            print('DIFF: built-in display → More Space 2056x1329 HiDPI')
            return True
        self.system=system
        code,text=self.run_check(verbose=True)
        self.assertEqual(code,1)
        summary,diagnostics=text.split('Diagnostics:')
        self.assertNotIn('DIAGNOSTIC MODE DATA',summary)
        self.assertIn('DIAGNOSTIC MODE DATA',diagnostics)
        self.assertIn('More Space',summary)

    def test_verbose_preserves_native_package_error_streams(self):
        self.manager.status.side_effect=subprocess.CalledProcessError(1,['mise','bootstrap','packages','status'],output='native stdout',stderr='specific native failure')
        code,text=self.run_check(verbose=True)
        self.assertEqual(code,1)
        self.assertIn('specific native failure',text);self.assertIn('native stdout',text)

    def test_equivalent_trackpad_storage_is_healthy(self):
        self.data[1]['macos_defaults']['entries']=[dict(domain='com.apple.AppleMultitouchTrackpad',key='Dragging',value=False,current='0 (integer; expected boolean)',state='differs')]
        code,text=self.run_check()
        self.assertEqual(code,0)
        self.assertIn('Mac preferences (1)',text)

    def test_different_trackpad_value_is_still_reported(self):
        self.data[1]['macos_defaults']['entries']=[dict(domain='com.apple.AppleMultitouchTrackpad',key='Dragging',value=False,current='1 (integer; expected boolean)',state='differs')]
        code,text=self.run_check()
        self.assertEqual(code,1)
        self.assertIn('Dragging',text)
