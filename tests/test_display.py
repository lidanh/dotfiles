import importlib.util
from pathlib import Path
from contextlib import nullcontext
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('display',ROOT/'scripts/display.py')
display=importlib.util.module_from_spec(spec);spec.loader.exec_module(display)

def mode(w,h,pw=None,ph=None,flags=0,hz=0,gui=True):
    return dict(width=w,height=h,pixel_width=pw or w*2,pixel_height=ph or h*2,flags=flags,hz=hz,gui=gui,ref=1)

class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.current=mode(1512,982,flags=0x02000000)
        self.target=mode(1800,1169)
        self.modes=[self.current,self.target,mode(3024,1964,3024,1964)]
        self.api=Mock();self.api.displays.return_value=[1,2]
        self.api.builtin.side_effect=lambda d:d==1
        self.api.active.return_value=True;self.api.mirrored.return_value=False
        self.api.modes.return_value=nullcontext(self.modes)
        self.api.current.side_effect=[self.current,self.target]

    def test_selects_more_space_not_largest_raw_resolution(self):
        self.assertEqual(display.select_mode(self.modes,self.current),self.target)

    def test_preserves_current_refresh_choice(self):
        alternate=mode(1800,1169,hz=60)
        self.assertEqual(display.select_mode(self.modes+[alternate],self.current),self.target)

    def test_supports_13_and_16_inch_panels(self):
        for native,target in [((2560,1600),(1680,1050)),((3456,2234),(2056,1329))]:
            current=mode(native[0]//2,native[1]//2,flags=0x02000000)
            desired=mode(*target)
            self.assertEqual(display.select_mode([current,desired],current),desired)

    def test_unknown_panel_or_missing_hidpi_mode_fails_without_guessing(self):
        for modes in [[mode(1000,600,flags=0x02000000)], [self.current,mode(1800,1169,1800,1169)]]:
            with self.assertRaises(ValueError):display.select_mode(modes,self.current)

    def test_applies_only_to_builtin_and_verifies(self):
        display.configure(api=self.api)
        self.api.apply.assert_called_once_with(1,self.target)

    def test_dry_run_and_check_never_apply(self):
        for flags in [dict(dry=True),dict(check_only=True)]:
            self.api.current.side_effect=None;self.api.current.return_value=self.current
            self.api.modes.return_value=nullcontext(self.modes)
            self.assertTrue(display.configure(api=self.api,**flags))
        self.api.apply.assert_not_called()

    def test_already_configured_does_not_apply(self):
        self.api.current.side_effect=None;self.api.current.return_value=self.target
        self.assertFalse(display.configure(api=self.api))
        self.api.apply.assert_not_called()

    def test_mirrored_builtin_is_deferred(self):
        self.api.mirrored.return_value=True
        self.assertTrue(display.configure(api=self.api))
        self.api.apply.assert_not_called();self.api.modes.assert_not_called()

    def test_absent_builtin_is_reported_deferred(self):
        self.api.displays.return_value=[2]
        self.assertTrue(display.configure(api=self.api))
        self.api.apply.assert_not_called()

    def test_unsuccessful_apply_is_not_reported_as_success(self):
        self.api.current.side_effect=[self.current,self.current]
        with self.assertRaisesRegex(ValueError,'did not take effect'):display.configure(api=self.api)
