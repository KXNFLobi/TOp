from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import os
import shutil
import subprocess
import time
import psutil
from PySide6.QtCore import QThread, Signal
from .safety import ProcessRow, SAFE_PUBLISHERS
from .windows import IS_WINDOWS, NO_WINDOW, Signatures, visible_windows, process_is_critical
from .gpu import probe_gpu

@dataclass(frozen=True)
class Metrics:
    timestamp: float
    cpu: float
    ram_percent: float
    ram_used: int
    available: int
    processes: int
    disk_mbps: float | None
    gpu: float | None
    gpu_temp: float | None
    cpu_temp: float | None
    gpu_source: str = "Indisponível"

def metrics(previous_disk=None, previous_time=None, gpu_sample=None) -> tuple[Metrics, object, float]:
    now = time.monotonic()
    memory = psutil.virtual_memory()
    disk = psutil.disk_io_counters()
    rate = None
    if disk and previous_disk and previous_time is not None and now > previous_time:
        rate = max(0, disk.read_bytes + disk.write_bytes - previous_disk.read_bytes - previous_disk.write_bytes) / (now-previous_time) / 1024**2
    gpu, gpu_temp, gpu_source = gpu_sample or (None,None,"Indisponível")
    cpu_temp = None
    try:
        sensors = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        cpu_values = [v.current for key, values in sensors.items() if key in ("coretemp", "k10temp", "cpu_thermal") for v in values]
        cpu_temp = max(cpu_values) if cpu_values else None
    except (OSError, psutil.Error):
        pass
    return Metrics(time.time(), psutil.cpu_percent(interval=None), memory.percent, memory.total-memory.available,
                   memory.available, len(psutil.pids()), rate, gpu, gpu_temp, cpu_temp, gpu_source), disk, now

class Monitor(QThread):
    sample = Signal(object, object)
    failed = Signal(str)
    def __init__(self, log):
        super().__init__()
        self.log = log
        self.signatures = Signatures()
        self._processes = {}
        self._checks = {}
        self._trust = {}
        self._gpu_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpu")
        self._gpu_future = None; self._gpu_data = (None,None,"Indisponível"); self._gpu_started = 0; self._gpu_updated = 0
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="signature")

    def run(self):
        disk = last = None
        psutil.cpu_percent(None)
        try:
            while not self.isInterruptionRequested():
                try:
                    now=time.monotonic()
                    if self._gpu_future and self._gpu_future.done():
                        self._gpu_data=self._gpu_future.result();self._gpu_updated=now;self._gpu_future=None
                    if self._gpu_future is None and now-self._gpu_started>=5:
                        self._gpu_started=now;self._gpu_future=self._gpu_executor.submit(probe_gpu)
                    snapshot, disk, last = metrics(disk, last, self._gpu_data if now-self._gpu_updated<20 else None)
                    rows = self.processes()
                    self.sample.emit(snapshot, rows)
                except Exception as exc:
                    self.log.exception("Falha de monitoramento")
                    self.failed.emit(str(exc))
                for _ in range(10):
                    if self.isInterruptionRequested():
                        break
                    self.msleep(100)
        finally:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._gpu_executor.shutdown(wait=False, cancel_futures=True)

    def processes(self) -> list[ProcessRow]:
        windows = visible_windows()
        services = set()
        if IS_WINDOWS:
            # Failure to enumerate services protects every process in this sample.
            try:
                services = {s.as_dict().get("pid") for s in psutil.win_service_iter()}
            except (psutil.Error, OSError):
                services = set(psutil.pids())
        own = {os.getpid()}
        try:
            own.update(p.pid for p in psutil.Process().parents())
            own.update(p.pid for p in psutil.Process().children(recursive=True))
        except psutil.Error:
            pass
        rows = []
        active = set()
        for process in psutil.process_iter():
            try:
                pid = process.pid
                active.add(pid)
                cached = self._processes.get(pid)
                if not cached or cached.create_time() != process.create_time():
                    cached = process
                    cached.cpu_percent(None)
                    self._processes[pid] = cached
                with cached.oneshot():
                    name, exe, user = cached.name(), cached.exe(), cached.username()
                    critical=False
                    # Only known UI application executables merit a trust query.
                    if os.path.basename(exe).casefold() in SAFE_PUBLISHERS and pid in windows:
                        critical=process_is_critical(pid)
                        future = self._checks.get(exe)
                        if future and future.done():
                            self._trust[exe] = (*future.result(), time.monotonic())
                            self._checks.pop(exe, None)
                        trust = self._trust.get(exe, (False, "", 0))
                        if exe not in self._checks and time.monotonic()-trust[2] > 60:
                            self._checks[exe] = self._executor.submit(self.signatures.check, exe)
                        valid, publisher = trust[:2]
                    else:
                        valid, publisher = False, ""
                    rows.append(ProcessRow(pid, cached.create_time(), name, exe, user,
                                           cached.cpu_percent(None)/max(1, psutil.cpu_count() or 1), cached.memory_info().rss,
                                           windows.get(pid, ()), pid in services, pid in own, publisher, valid, critical))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
                # Preserve inaccessible processes in the inventory as protected rows.
                rows.append(ProcessRow(process.pid, 0, "Processo inacessível", "", "", 0, 0))
        for pid in set(self._processes)-active:
            self._processes.pop(pid, None)
        return rows
