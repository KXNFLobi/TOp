import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QDialog
from booster.ui import MainWindow, STYLE
from booster.state import Store, canonical
from booster.safety import ProcessRow, Decision
from booster.monitor import metrics

class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle("Fusion");cls.app.setStyleSheet(STYLE)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.window=MainWindow(Store(Path(self.temp.name)),start_monitor=False)
        self.row=ProcessRow(123,1,"chrome.exe",str(Path(self.temp.name)/"chrome.exe"),"user",2,200_000_000,(1,))
        self.metric,_,_=metrics();self.window.on_sample(self.metric,[self.row])
    def tearDown(self):
        self.window.store.data["power_restore"]=None;self.window.close();self.app.processEvents();self.temp.cleanup()
    def test_real_metrics_and_unknown_protection(self):
        self.assertIn("CPU",self.window.cards["CPU"].text());self.assertFalse(self.window.decisions[123].allowed)
        self.assertEqual(self.window.apps.rowCount(),1);self.assertTrue(self.window.simulation.isChecked())
    def test_keep_and_favorite_persist(self):
        keep=self.window.apps.item(0,1);keep.setCheckState(Qt.CheckState.Checked);self.app.processEvents()
        self.assertIn(canonical(self.row.exe),self.window.store.profile("Global")["keep"])
        self.window.apps.item(0,2).setCheckState(Qt.CheckState.Checked);self.app.processEvents()
        self.assertIn(canonical(self.row.exe),Store(self.window.store.directory).data["favorites"])
    def test_search_filters(self):
        self.window.search.setText("does-not-exist");self.assertEqual(self.window.apps.rowCount(),0)
        self.window.search.clear();self.assertEqual(self.window.apps.rowCount(),1)
    def test_game_selection_survives_refresh(self):
        self.window.store.data["games"]=[{"name":"Any Game","exe":self.row.exe}];self.window.render_games();self.window.games.setCurrentCell(0,1)
        self.window.render_games();self.assertEqual(self.window.selected_game()["name"],"Any Game")
    def test_simulation_never_requests_close_or_power(self):
        self.window.decisions={123:Decision(True,"fixture only")};self.window.store.profile("Global")["close"]=[canonical(self.row.exe)]
        with patch("booster.ui.Preview.exec",return_value=QDialog.DialogCode.Accepted),patch("booster.ui.request_close") as close,patch.object(self.window.power,"apply") as power:
            self.window.optimize(selected_only=True)
            loop=QEventLoop();timer=QTimer();timer.timeout.connect(lambda:loop.quit() if not self.window.busy and not self.window.jobs else None);timer.start(25)
            QTimer.singleShot(10000,loop.quit);loop.exec();timer.stop()
            self.assertFalse(self.window.busy);self.assertTrue(self.window.store.data["history"][-1]["simulation"])
            close.assert_not_called();power.assert_not_called()
            self.assertIn("SIMULAÇÃO",self.window.history_note.text())

if __name__=="__main__":unittest.main()
