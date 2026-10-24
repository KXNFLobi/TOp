import ast
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch, MagicMock
from booster.fps import FrameWindow, verify_collector, collector_path, OwnedCollector, PRESENTMON_SHA256


def frame(pid=42,chain="0xA",timestamp=1,interval=16.6666667):
    return {"ProcessID":str(pid),"SwapChainAddress":chain,"TimeInSeconds":str(timestamp),"msBetweenPresents":str(interval)}

class FpsTests(unittest.TestCase):
    def test_weighted_rate_not_average_of_instantaneous_rates(self):
        window=FrameWindow(42);window.add(frame(timestamp=1,interval=10),now=10);window.add(frame(timestamp=1.02,interval=30),now=10)
        self.assertAlmostEqual(window.sample(now=11).fps,50)
    def test_other_pid_never_contributes(self):
        window=FrameWindow(42);self.assertFalse(window.add(frame(pid=43),now=1));self.assertIsNone(window.sample(now=1).fps)
    def test_swapchains_not_added_together(self):
        window=FrameWindow(42)
        for i in range(60):window.add(frame(timestamp=i/60,chain="A"),now=1)
        for i in range(30):window.add(frame(timestamp=i/30,chain="B",interval=33.3333333),now=1)
        self.assertAlmostEqual(window.sample(now=1).fps,60,places=3)
        self.assertEqual(window.sample(now=1).chain,"A")
    def test_stale_value_becomes_unavailable(self):
        window=FrameWindow(42)
        window.add(frame(timestamp=1),now=1);window.add(frame(timestamp=1.02),now=1)
        self.assertIsNone(window.sample(now=5).fps)
    def test_invalid_values_never_become_fake_fps(self):
        window=FrameWindow(42)
        for value in (0,-1,"NA","nan","inf"):
            self.assertFalse(window.add(frame(interval=value),now=1))
        self.assertIsNone(window.sample(now=1).fps)
    def test_old_intervals_expire_from_window(self):
        window=FrameWindow(42);window.add(frame(timestamp=1,interval=100),now=1)
        window.add(frame(timestamp=5,interval=10),now=5);window.add(frame(timestamp=5.01,interval=10),now=5)
        self.assertAlmostEqual(window.sample(now=5).fps,100)
    def test_out_of_order_rows_rejected(self):
        window=FrameWindow(42);window.add(frame(timestamp=2),now=1)
        self.assertFalse(window.add(frame(timestamp=1),now=1))
    def test_pinned_presentmon_integrity(self):verify_collector(collector_path())
    def test_collector_stop_touches_owned_session_only(self):
        own=MagicMock();own.poll.return_value=None;own.wait.return_value=0
        with patch('booster.fps.subprocess.Popen',return_value=own) as launch,patch('booster.fps.subprocess.run') as stop:
            capture=OwnedCollector(collector_path(),42);capture.stop()
            args=launch.call_args.args[0]
            self.assertEqual(args[args.index('--process_id')+1],'42')
            self.assertIn('--session_name',stop.call_args.args[0]);self.assertIn(capture.session,stop.call_args.args[0])
            self.assertNotIn('--process_id',stop.call_args.args[0]);own.kill.assert_not_called()
    def test_emergency_cleanup_kills_only_the_owned_popen_handle(self):
        own=MagicMock();own.poll.return_value=None;own.wait.side_effect=[subprocess.TimeoutExpired('collector',6),0]
        with patch('booster.fps.subprocess.Popen',return_value=own),patch('booster.fps.subprocess.run'):
            capture=OwnedCollector(collector_path(),42);capture.stop();own.kill.assert_called_once()

if __name__=='__main__':unittest.main()
