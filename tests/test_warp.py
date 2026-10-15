from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class WarpTests(unittest.TestCase):
    def test_cask_checksum_exception_is_scoped_and_signature_verified(self):
        source=(ROOT/'Casks/warp.rb').read_text()
        self.assertIn('version :latest',source)
        self.assertIn('sha256 :no_check',source)
        self.assertIn('2BBY89MBSN',source)
        self.assertIn('preflight_steps do',source)
        self.assertIn('--strict',source)
