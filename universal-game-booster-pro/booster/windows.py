from __future__ import annotations
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import psutil
from .state import canonical
from .safety import ProcessRow, assess

IS_WINDOWS = sys.platform == "win32"
NO_WINDOW = 0x08000000 if IS_WINDOWS else 0
GUID = re.compile(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", re.I)
HIGH_PERFORMANCE = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

class Signatures:
    def __init__(self):
        self.cache = {}

    def check(self, exe: str) -> tuple[bool, str]:
        if not IS_WINDOWS or not exe:
            return False, ""
        try:
            stat = os.stat(exe)
            key = (canonical(exe), stat.st_size, stat.st_mtime_ns)
            cached = self.cache.get(key)
            if cached and time.monotonic() - cached[0] < 60:
                return cached[1:]
            # LiteralPath and encoded script avoid shell argument interpretation.
            import base64
            literal = exe.replace("'", "''")
            script = ("$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
                      f"$s=Get-AuthenticodeSignature -LiteralPath '{literal}';"
                      "[pscustomobject]@{Valid=($s.Status -eq 'Valid');Publisher=if($s.SignerCertificate){"
                      "$s.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false)}else{''}} | ConvertTo-Json -Compress")
            powershell = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe")
            result = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand",
                                     base64.b64encode(script.encode("utf-16le")).decode()], capture_output=True, timeout=15,
                                    creationflags=NO_WINDOW)
            data = json.loads(result.stdout.decode("utf-8-sig")) if result.returncode == 0 else {}
            valid, publisher = data.get("Valid") is True, str(data.get("Publisher", ""))
            if len(self.cache) > 1000:
                self.cache.clear()
            self.cache[key] = (time.monotonic(), valid, publisher)
            return valid, publisher
        except (OSError, ValueError, subprocess.SubprocessError):
            return False, ""


def visible_windows() -> dict[int, tuple[int, ...]]:
    if not IS_WINDOWS:
        return {}
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    found = {}
    @callback_type
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found.setdefault(pid.value, []).append(int(hwnd))
        return True
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    if not user32.EnumWindows(visit, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return {pid: tuple(handles) for pid, handles in found.items()}


def process_is_critical(pid: int) -> bool:
    if not IS_WINDOWS:
        return True
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.IsProcessCritical.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.BOOL)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)  # Query-limited only; no write/process-VM rights.
    if not handle:return True
    try:
        critical=wintypes.BOOL()
        return bool(critical.value) if kernel.IsProcessCritical(handle,ctypes.byref(critical)) else True
    finally:kernel.CloseHandle(handle)


def request_close(row: ProcessRow, signatures: Signatures, current_user: str, game_paths: set[str]) -> str:
    """Revalidate PID, creation time, executable, ownership, service and trust. Never terminate/kill."""
    if not IS_WINDOWS:
        raise RuntimeError("Fechamento normal implementado somente no Windows")
    process = psutil.Process(row.pid)
    if process.create_time() != row.created or canonical(process.exe()) != canonical(row.exe):
        raise RuntimeError("Identidade do processo mudou; atualize a lista")
    service_pids = {s.as_dict().get("pid") for s in psutil.win_service_iter()}
    valid, publisher = signatures.check(row.exe)
    handles = visible_windows().get(row.pid, ())
    own = {os.getpid(), *(p.pid for p in psutil.Process().parents()), *(p.pid for p in psutil.Process().children(recursive=True))}
    fresh = ProcessRow(row.pid, row.created, process.name(), process.exe(), process.username(), row.cpu, row.rss,
                       handles, row.pid in service_pids, row.pid in own, publisher, valid, process_is_critical(row.pid))
    decision = assess(fresh, current_user, game_paths, os.environ.get("SystemRoot", r"C:\Windows"))
    if not decision.allowed:
        raise RuntimeError(decision.reason)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    sent = 0
    for hwnd in handles:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != row.pid:
            continue
        identity = psutil.Process(row.pid)
        if identity.create_time() != row.created or canonical(identity.exe()) != canonical(row.exe):
            raise RuntimeError("O processo mudou antes do fechamento")
        if user32.PostMessageW(hwnd, 0x0010, 0, 0):  # WM_CLOSE
            sent += 1
    if not sent:
        raise RuntimeError("O Windows não aceitou a solicitação de fechamento")
    return f"Fechamento normal solicitado a {sent} janela(s); o aplicativo pode pedir para salvar ou continuar na bandeja"


class PowerPlan:
    def __init__(self, store):
        self.store = store

    def run(self, *args) -> str:
        if not IS_WINDOWS:
            raise RuntimeError("Planos de energia disponíveis somente no Windows")
        exe = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/powercfg.exe")
        self.store.log.info("powercfg: %s", " ".join(args))
        result = subprocess.run([exe, *args], capture_output=True, timeout=12, creationflags=NO_WINDOW)
        if result.returncode:
            raise RuntimeError("powercfg recusou a operação. O plano pode estar indisponível ou sem permissão.")
        return result.stdout.decode("utf-8", errors="replace")

    def current(self) -> str:
        match = GUID.search(self.run("/getactivescheme"))
        if not match:
            raise RuntimeError("Plano ativo não identificado")
        return match.group(0).lower()

    def apply(self) -> str:
        existing = self.store.data.get("power_restore")
        if existing:
            if self.current() == existing["applied"]:
                return "Plano temporário já ativo; ponto de restauração original preservado"
            raise RuntimeError("Há restauração de energia pendente; restaure antes de aplicar outro ajuste")
        if HIGH_PERFORMANCE not in self.run("/list").lower():
            raise RuntimeError("Alto Desempenho não está disponível neste PC; nenhum plano será criado")
        original = self.current()
        if original == HIGH_PERFORMANCE:
            return "Alto Desempenho já estava ativo; nenhuma alteração"
        self.store.data["power_restore"] = {"original": original, "applied": HIGH_PERFORMANCE}
        self.store.save()  # Durable recovery before changing the system.
        self.run("/setactive", HIGH_PERFORMANCE)
        if self.current() != HIGH_PERFORMANCE:
            raise RuntimeError("A mudança do plano não foi confirmada; recuperação preservada")
        return "Alto Desempenho temporário ativado; plano anterior salvo"

    def restore(self, force=False) -> str:
        saved = self.store.data.get("power_restore")
        if not saved:
            return "Nenhum ajuste temporário pendente"
        if not force and self.current() not in (saved["applied"], saved["original"]):
            raise RuntimeError("Outro plano foi escolhido fora do aplicativo. Restauração automática não o substituirá.")
        self.run("/setactive", saved["original"])
        if self.current() != saved["original"]:
            raise RuntimeError("Restauração não confirmada; estado de recuperação mantido")
        self.store.data["power_restore"] = None
        self.store.save()
        return "Plano de energia original restaurado"


def configure_startup(enabled: bool):
    if not IS_WINDOWS:
        raise RuntimeError("Inicialização automática disponível somente no Windows")
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        if enabled:
            if getattr(sys, "frozen", False):
                args = [sys.executable]
            else:
                pythonw = Path(sys.executable).with_name("pythonw.exe")
                args = [str(pythonw if pythonw.exists() else Path(sys.executable)), str(Path(__file__).resolve().parents[1] / "main.py")]
            winreg.SetValueEx(key, "UniversalGameBoosterPro", 0, winreg.REG_SZ, subprocess.list2cmdline(args))
        else:
            try:
                winreg.DeleteValue(key, "UniversalGameBoosterPro")
            except FileNotFoundError:
                pass
