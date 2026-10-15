import io
from pathlib import Path
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from update_progress import follow_log

class ProgressTests(unittest.TestCase):
    def test_streams_before_completion_and_drains_final_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'update.log'
            path.write_text('previous run\n')
            output=io.StringIO()
            with redirect_stdout(output), path.open('a') as log:
                with follow_log(log, 'test package', interval=0.01, heartbeat=10):
                    log.write('downloading 25%\r');log.flush()
                    deadline=time.monotonic()+2
                    while '25%' not in output.getvalue() and time.monotonic()<deadline:time.sleep(0.01)
                    self.assertIn('25%',output.getvalue())
                    log.write('finished\n');log.flush()
            self.assertIn('finished',output.getvalue())
            self.assertNotIn('previous run',output.getvalue())

    def test_silent_command_gets_heartbeat_and_exception_cleans_up(self):
        with tempfile.TemporaryDirectory() as directory:
            output=io.StringIO()
            with redirect_stdout(output), (Path(directory)/'log').open('a') as log:
                with self.assertRaises(ValueError):
                    with follow_log(log,'brew:example',interval=0.01,heartbeat=0.02):
                        deadline=time.monotonic()+2
                        while 'Still running' not in output.getvalue() and time.monotonic()<deadline:time.sleep(0.01)
                        raise ValueError('failed')
            self.assertIn('brew:example',output.getvalue())

class TerminalTests(unittest.TestCase):
    def test_redirected_output_has_no_ansi(self):
        import terminal_ui as ui
        output=io.StringIO()
        with redirect_stdout(output):
            ui.heading('setup','Wonderful')
            with ui.stage('Configure Mac'):pass
        self.assertNotIn('\033',output.getvalue())
        self.assertIn('✓ Configure Mac',output.getvalue())

    def test_failed_stage_never_reports_success(self):
        import terminal_ui as ui
        from contextlib import redirect_stderr
        output=io.StringIO()
        with redirect_stdout(output),redirect_stderr(output),self.assertRaises(ValueError):
            with ui.stage('Install'):raise ValueError('failure')
        self.assertNotIn('✓',output.getvalue())
        self.assertIn('✗ Install stopped',output.getvalue())

    def test_color_obeys_no_color(self):
        import terminal_ui as ui
        from unittest.mock import patch
        output=io.StringIO();output.isatty=lambda:True
        with patch.dict('os.environ',{'NO_COLOR':'1'}):ui.line('hello',stream=output)
        self.assertEqual(output.getvalue(),'hello\n')

    def test_unverified_stage_does_not_claim_success(self):
        import terminal_ui as ui
        output=io.StringIO()
        with redirect_stdout(output):
            with ui.stage('Configure display',verify=True):
                print('DEFERRED: open the lid')
        self.assertNotIn('✓',output.getvalue())
        self.assertIn('dots check',output.getvalue())
