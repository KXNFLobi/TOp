import ast
from dataclasses import replace
import json
import logging
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from booster.safety import ProcessRow, assess, choose
from booster.state import Store, canonical
from booster.windows import PowerPlan, HIGH_PERFORMANCE
from booster.games import discover
from booster.gpu import aggregate_engines, probe_gpu
from types import SimpleNamespace

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.row=ProcessRow(123,1,"chrome.exe",str(self.root/"chrome.exe"),"alice",2,200_000_000,(100,),False,False,"Google LLC",True)
    def tearDown(self):
        logger=logging.getLogger("gamebooster."+str(self.root))
        for handler in list(logger.handlers):handler.close();logger.removeHandler(handler)
        self.temporary.cleanup()
    def decision(self,row):return assess(row,"alice",set(),str(self.root/"Windows"),True)
    def test_known_signed_window_allowed(self):self.assertTrue(self.decision(self.row).allowed)
    def test_unknown_signature_protected(self):self.assertFalse(self.decision(replace(self.row,signature_valid=False)).allowed)
    def test_wrong_publisher_protected(self):self.assertFalse(self.decision(replace(self.row,publisher="Unknown")).allowed)
    def test_game_path_always_protected(self):self.assertFalse(assess(self.row,"alice",{canonical(self.row.exe)},"",True).allowed)
    def test_critical_overrides_known_signed_app(self):self.assertFalse(self.decision(replace(self.row,critical=True)).allowed)
    def test_service_protected(self):self.assertFalse(self.decision(replace(self.row,service=True)).allowed)
    def test_other_user_protected(self):self.assertFalse(self.decision(replace(self.row,user="bob")).allowed)
    def test_no_visible_window_protected(self):self.assertFalse(self.decision(replace(self.row,windows=())).allowed)
    def test_anticheat_protected(self):self.assertFalse(self.decision(replace(self.row,name="EasyAntiCheat.exe")).allowed)
    def test_self_protected(self):self.assertFalse(self.decision(replace(self.row,own_tree=True)).allowed)
    def test_launcher_protected(self):self.assertFalse(self.decision(replace(self.row,name="Steam.exe")).allowed)
    def test_arbitrary_game_unknown_protected(self):self.assertFalse(self.decision(replace(self.row,name="NewGame.exe",exe=str(self.root/"NewGame.exe"))).allowed)
    def test_non_windows_never_closes(self):self.assertFalse(assess(self.row,"alice",set(),"",False).allowed)
    def test_windows_directory_protected(self):self.assertFalse(self.decision(replace(self.row,exe=str(self.root/"Windows"/"chrome.exe"))).allowed)
    def test_keep_overrides_selection(self):
        selected={canonical(self.row.exe)}
        self.assertEqual(choose([self.row],{123:self.decision(self.row)},selected,selected),[])
        self.assertEqual(choose([self.row],{123:self.decision(self.row)},selected,set()),[self.row])
    def test_preferences_roundtrip(self):
        store=Store(self.root);store.profile("Game")["keep"]=[self.row.exe];store.save()
        self.assertEqual(Store(self.root).profile("Game")["keep"],[self.row.exe])
    def test_corrupt_preferences_preserved(self):
        (self.root/"preferences.json").write_text("broken")
        store=Store(self.root)
        self.assertTrue(store.data["simulation"]);self.assertTrue((self.root/"preferences.invalid.json").exists())
    def test_power_recovery_validated(self):
        (self.root/"preferences.json").write_text(json.dumps({"power_restore":{"original":"bad","applied":"bad"}}))
        self.assertIsNone(Store(self.root).data["power_restore"])
    def test_no_force_termination_or_fake_memory_commands(self):
        for path in (Path(__file__).parents[1]/"booster").glob("*.py"):
            tree=ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                    self.assertNotIn(node.func.attr,{"kill","terminate","suspend"},str(path))
    def test_epic_manifest_discovers_real_executable_only(self):
        data=self.root/"data";manifests=data/"Epic/EpicGamesLauncher/Data/Manifests";manifests.mkdir(parents=True)
        install=self.root/"game";install.mkdir();(install/"Test.exe").write_bytes(b"fixture")
        (manifests/"one.item").write_text(json.dumps({"InstallLocation":str(install),"LaunchExecutable":"Test.exe","DisplayName":"Test Game"}))
        (manifests/"escape.item").write_text(json.dumps({"InstallLocation":str(install),"LaunchExecutable":"../outside.exe","DisplayName":"Escape"}))
        with patch.dict(os.environ,{"PROGRAMDATA":str(data),"LOCALAPPDATA":str(self.root/"none"),"ProgramFiles(x86)":str(self.root/"none")}):
            found=discover()
        self.assertTrue(any(g["name"]=="Test Game" for g in found));self.assertFalse(any(g["name"]=="Escape" for g in found))

class GpuTests(unittest.TestCase):
    def test_aggregate_processes_on_same_engine_but_not_different_engines(self):
        counters=[{"Name":"pid_1_luid_0x0_0x1_phys_0_eng_0_engtype_3D","UtilizationPercentage":30},
                  {"Name":"pid_2_luid_0x0_0x1_phys_0_eng_0_engtype_3D","UtilizationPercentage":20},
                  {"Name":"pid_2_luid_0x0_0x1_phys_0_eng_1_engtype_Copy","UtilizationPercentage":40}]
        self.assertEqual(aggregate_engines(counters),50)
    def test_unavailable_temperature_does_not_discard_real_utilization(self):
        with patch("booster.gpu.shutil.which",return_value="nvidia-smi"),patch("booster.gpu.subprocess.run",return_value=SimpleNamespace(returncode=0,stdout=b"42, N/A\n")):
            utilization,temperature,source=probe_gpu()
        self.assertEqual(utilization,42);self.assertIsNone(temperature)
    def test_missing_counter_value_does_not_discard_valid_engines(self):
        self.assertEqual(aggregate_engines([{"Name":"pid_1_luid_0_1_phys_0_eng_0_engtype_3D","UtilizationPercentage":None},{"Name":"pid_2_luid_0_1_phys_0_eng_0_engtype_3D","UtilizationPercentage":20}]),20)
    def test_missing_source_has_no_fake_zero(self):self.assertIsNone(aggregate_engines([]))
    def test_overlapping_counter_roundoff_capped(self):
        self.assertEqual(aggregate_engines([{"Name":"pid_1_luid_0_1_phys_0_eng_0_engtype_3D","UtilizationPercentage":70},{"Name":"pid_2_luid_0_1_phys_0_eng_0_engtype_3D","UtilizationPercentage":40}]),100)

class FakePower(PowerPlan):
    def __init__(self,store):super().__init__(store);self.active="11111111-1111-1111-1111-111111111111";self.available=True;self.fail=False
    def run(self,*args):
        if args[0]=="/getactivescheme":return self.active
        if args[0]=="/list":return HIGH_PERFORMANCE if self.available else ""
        if args[0]=="/setactive":
            # Recovery MUST have been durably stored before any change.
            if args[1]==HIGH_PERFORMANCE:
                assert json.loads(self.store.path.read_text())["power_restore"]["original"]==self.active
            if self.fail:raise RuntimeError("denied")
            self.active=args[1];return ""
        raise AssertionError(args)

class PowerTests(unittest.TestCase):
    def setUp(self):self.temporary=tempfile.TemporaryDirectory();self.store=Store(Path(self.temporary.name));self.power=FakePower(self.store)
    def tearDown(self):self.store.close();self.temporary.cleanup()
    def test_apply_and_restore(self):
        original=self.power.active;self.power.apply();self.assertEqual(self.power.active,HIGH_PERFORMANCE)
        self.power.apply();self.assertEqual(self.store.data["power_restore"]["original"],original)
        self.power.restore();self.assertEqual(self.power.active,original);self.assertIsNone(self.store.data["power_restore"])
    def test_missing_plan_not_created(self):
        self.power.available=False
        with self.assertRaises(RuntimeError):self.power.apply()
        self.assertIsNone(self.store.data["power_restore"])
    def test_failed_apply_keeps_recovery(self):
        self.power.fail=True
        with self.assertRaises(RuntimeError):self.power.apply()
        self.assertIsNotNone(Store(self.store.directory).data["power_restore"])
    def test_external_plan_change_not_overwritten(self):
        self.power.apply();self.power.active="22222222-2222-2222-2222-222222222222"
        with self.assertRaises(RuntimeError):self.power.restore()
        self.assertEqual(self.power.active,"22222222-2222-2222-2222-222222222222")
        self.power.restore(force=True);self.assertIsNone(self.store.data["power_restore"])

if __name__=="__main__":unittest.main()
