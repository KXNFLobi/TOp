"""PresentMon ETW capture: no injection, target-process termination or memory hooks."""
from __future__ import annotations
from collections import defaultdict, deque
import csv
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import psutil
from PySide6.QtCore import QThread, Signal
from .state import canonical
from .windows import IS_WINDOWS, NO_WINDOW

PRESENTMON_SHA256 = "690533cf5c2591ef571a3037aa4c205c8e75860ef3f56927bf3a98acf7198485"
REQUIRED_COLUMNS = {"ProcessID", "SwapChainAddress", "TimeInSeconds", "msBetweenPresents"}
GAME_NAME = re.compile(r"^(GTA5(?:_Enhanced)?(?:_BE)?|FiveM(?:_.*GTAProcess)?|cs2|FortniteClient-Win64-Shipping|VALORANT-Win64-Shipping|RobloxPlayerBeta|Minecraft\.Windows|javaw|RDR2|cod)\.exe$", re.I)

@dataclass(frozen=True)
class FpsSample:
    fps: float | None
    frame_ms: float | None
    frames: int
    chain: str
    message: str

class FrameWindow:
    """Weighted FPS over observed presentation intervals of one dominant swapchain."""
    def __init__(self, pid: int, window=2.0, stale=3.0):
        self.pid=pid; self.window=window; self.stale=stale
        self.chains=defaultdict(deque); self.last_event=0.0; self.last_arrival=None
        self.lock=threading.Lock()

    def add(self, row: dict, now=None) -> bool:
        try:
            if int(row["ProcessID"]) != self.pid:return False
            timestamp=float(row["TimeInSeconds"]); interval=float(row["msBetweenPresents"])
            chain=row["SwapChainAddress"].strip()
            if not chain or not math.isfinite(timestamp) or not math.isfinite(interval) or timestamp<0 or interval<=0:return False
        except (ValueError,TypeError,KeyError):return False
        with self.lock:
            # Reject out-of-order trace rows and avoid merging different swapchains.
            frames=self.chains[chain]
            if frames and timestamp<frames[-1][0]:return False
            frames.append((timestamp,interval));self.last_event=max(self.last_event,timestamp)
            self.last_arrival=time.monotonic() if now is None else now
            cutoff=self.last_event-self.window
            for name in list(self.chains):
                items=self.chains[name]
                while items and items[0][0]<cutoff:items.popleft()
                if not items:self.chains.pop(name,None)
            if sum(len(items) for items in self.chains.values())>20000:
                self.chains.clear();raise RuntimeError("Volume de quadros acima do limite; leitura descartada")
        return True

    def sample(self, now=None) -> FpsSample:
        now=time.monotonic() if now is None else now
        with self.lock:
            if self.last_arrival is None:return FpsSample(None,None,0,"","Aguardando quadros do processo escolhido")
            if now-self.last_arrival>self.stale:return FpsSample(None,None,0,"","Sem quadros recentes; jogo minimizado, pausado ou fonte indisponível")
            if not self.chains:return FpsSample(None,None,0,"","Aguardando amostra válida")
            chain,items=max(self.chains.items(),key=lambda pair:len(pair[1]))
            if len(items)<2:return FpsSample(None,None,len(items),chain,"Aquecendo a leitura de FPS")
            duration=sum(interval for _,interval in items)
            return FpsSample(1000*len(items)/duration,duration/len(items),len(items),chain,"FPS de apresentação • média móvel de 2 segundos")


def collector_path() -> Path:
    root=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parents[1]))
    return root/"vendor"/"PresentMon"/"PresentMon.exe"


def verify_collector(path: Path) -> None:
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=PRESENTMON_SHA256:
        raise RuntimeError("PresentMon ausente ou com integridade inválida. Reinstale pelo instalador oficial deste projeto.")


def trace_allowed() -> bool:
    if not IS_WINDOWS:return False
    if ctypes.windll.shell32.IsUserAnAdmin():return True
    advapi=ctypes.WinDLL("advapi32",use_last_error=True);kernel=ctypes.WinDLL("kernel32")
    advapi.ConvertStringSidToSidW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_void_p)]
    advapi.CheckTokenMembership.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.POINTER(wintypes.BOOL)]
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    sid=ctypes.c_void_p()
    if not advapi.ConvertStringSidToSidW("S-1-5-32-559",ctypes.byref(sid)):return False
    try:
        member=wintypes.BOOL()
        return bool(advapi.CheckTokenMembership(None,sid,ctypes.byref(member)) and member.value)
    finally:kernel.LocalFree(sid)


def reopen_elevated() -> None:
    if not IS_WINDOWS:raise RuntimeError("Disponível somente no Windows")
    executable=sys.executable
    arguments=[] if getattr(sys,"frozen",False) else [str(Path(__file__).resolve().parents[1]/"main.py")]
    shell=ctypes.WinDLL("shell32",use_last_error=True)
    shell.ShellExecuteW.argtypes=[wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPCWSTR,ctypes.c_int]
    shell.ShellExecuteW.restype=ctypes.c_void_p
    result=shell.ShellExecuteW(None,"runas",executable,subprocess.list2cmdline(arguments),None,1)
    if not result or result<=32:raise RuntimeError("Reabertura não autorizada ou indisponível")


class OwnedCollector:
    """Owns only a pinned PresentMon child; the game's PID is a filter argument, never a process handle."""
    def __init__(self, binary: Path, pid: int):
        verify_collector(binary)
        if pid<=0:raise ValueError("PID inválido")
        self.binary=binary;self.session="UGBPro-"+uuid.uuid4().hex
        self.errors=tempfile.TemporaryFile()
        self.process=subprocess.Popen([str(binary),"--process_id",str(pid),"--session_name",self.session,
            "--output_stdout","--v1_metrics","--no_console_stats","--no_track_display","--no_track_gpu","--no_track_input",
            "--terminate_on_proc_exit"],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=self.errors,
            text=True,encoding="utf-8-sig",errors="replace",creationflags=NO_WINDOW)
    def stop(self):
        if self.process.poll() is None:
            try:
                subprocess.run([str(self.binary),"--session_name",self.session,"--terminate_existing_session","--no_console_stats"],
                    capture_output=True,timeout=6,creationflags=NO_WINDOW)
                self.process.wait(timeout=6)
            except (subprocess.SubprocessError,OSError):
                # Last resort for this exact child handle only, never the game or another process.
                if self.process.poll() is None:self.process.kill()
                self.process.wait(timeout=5)
        self.errors.seek(0);message=self.errors.read(4096).decode("utf-8",errors="replace").strip()
        self.errors.close()
        if self.process.stdout:self.process.stdout.close()
        return message


class FpsCapture(QThread):
    updated=Signal(object)
    failed=Signal(str)
    def __init__(self,row,log):
        super().__init__();self.target=row;self.log=log
    def target_alive(self):
        try:
            p=psutil.Process(self.target.pid)
            return p.create_time()==self.target.created and canonical(p.exe())==canonical(self.target.exe)
        except psutil.Error:return False
    def run(self):
        child=None;reader=None;errors=[];frames=FrameWindow(self.target.pid)
        try:
            if not IS_WINDOWS or not trace_allowed():raise RuntimeError("FPS requer Windows e permissão de leitura ETW; reabra como administrador")
            if not self.target_alive():raise RuntimeError("O jogo mudou de processo ou foi encerrado. Atualize a seleção.")
            child=OwnedCollector(collector_path(),self.target.pid)
            self.log.info("FPS iniciado: PID=%s sessão=%s exe=%s",self.target.pid,child.session,self.target.exe)
            def consume():
                try:
                    data=csv.DictReader(child.process.stdout)
                    if not data.fieldnames or not REQUIRED_COLUMNS.issubset(data.fieldnames):
                        raise RuntimeError("Formato de métricas do PresentMon indisponível ou incompatível")
                    for row in data:frames.add(row)
                except Exception as exc:errors.append(str(exc))
            reader=threading.Thread(target=consume,daemon=True,name="presentmon-csv");reader.start()
            while child.process.poll() is None and not self.isInterruptionRequested():
                if errors:raise RuntimeError(errors[0])
                if not self.target_alive():break
                self.updated.emit(frames.sample());self.msleep(250)
            if not self.isInterruptionRequested() and child.process.poll() not in (None,0):
                raise RuntimeError("PresentMon não conseguiu capturar. Verifique permissões, compatibilidade e o relatório.")
        except Exception as exc:
            self.log.exception("Falha de captura FPS");self.failed.emit(str(exc))
        finally:
            if child:
                try:
                    detail=child.stop()
                    if detail:self.log.info("PresentMon: %s",detail)
                except Exception as exc:self.log.exception("Falha ao parar coletor de FPS");self.failed.emit(str(exc))
            if reader:reader.join(timeout=2)
            self.updated.emit(FpsSample(None,None,0,"","Captura encerrada; nenhum FPS estimado"))
