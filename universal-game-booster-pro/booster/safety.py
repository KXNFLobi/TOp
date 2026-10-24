from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
from .state import canonical

# These are desktop applications, not a general list of processes that may be killed.
SAFE_PUBLISHERS = {
    "chrome.exe": ("Google LLC", "Google Inc"),
    "msedge.exe": ("Microsoft Corporation",),
    "firefox.exe": ("Mozilla Corporation",),
    "brave.exe": ("Brave Software, Inc.", "Brave Software Inc."),
    "spotify.exe": ("Spotify AB",),
    "discord.exe": ("Discord Inc.", "Discord Inc"),
    "telegram.exe": ("Telegram FZ-LLC", "Telegram Messenger Inc."),
    "whatsapp.exe": ("WhatsApp LLC", "WhatsApp Inc."),
}
PROTECTED_WORDS = ("anticheat", "anti-cheat", "battleye", "beservice", "easyanticheat", "vgc", "vgtray", "vanguard",
                   "defender", "msmpeng", "securityhealth", "antivirus", "avast", "kaspersky", "malwarebytes",
                   "nvidia", "nvcontainer", "amd", "radeon", "intel", "audiodg", "audio", "realtek", "razer", "logitech",
                   "steam", "epicgames", "eadesktop", "origin", "ubisoft", "rockstar", "riotclient", "battle.net", "battlenet",
                   "fivem", "gta5", "cs2.exe", "fortnite", "valorant", "cod.exe", "minecraft", "javaw.exe", "roblox", "rdr2")

@dataclass(frozen=True)
class ProcessRow:
    pid: int
    created: float
    name: str
    exe: str
    user: str
    cpu: float
    rss: int
    windows: tuple[int, ...] = ()
    service: bool = False
    own_tree: bool = False
    publisher: str = ""
    signature_valid: bool = False
    critical: bool = False

@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str

def assess(row: ProcessRow, current_user: str, game_paths: set[str], windows_dir: str, native_windows: bool = True) -> Decision:
    if not native_windows:
        return Decision(False, "Monitoramento: fechamento disponível somente no Windows")
    if row.pid <= 4 or row.service or row.own_tree or row.critical:
        return Decision(False, "Sistema, serviço ou processo do próprio gerenciador")
    if not row.exe or not row.user or row.user.casefold() != current_user.casefold():
        return Decision(False, "Identidade inacessível ou pertencente a outro usuário")
    path = canonical(row.exe)
    if path in game_paths:
        return Decision(False, "Jogo cadastrado — protegido")
    # Protect launchers, security, drivers and unknown processes before considering the allowlist.
    if any(word in (row.name + " " + path).casefold() for word in PROTECTED_WORDS):
        return Decision(False, "Jogo, launcher, segurança, driver ou periférico protegido")
    if windows_dir and (path == canonical(windows_dir) or path.startswith(canonical(windows_dir).rstrip(os.sep) + os.sep)):
        return Decision(False, "Componente do Windows")
    if not row.windows:
        return Decision(False, "Sem janela visível: não será encerrado à força")
    publishers = SAFE_PUBLISHERS.get(Path(row.exe).name.casefold(), ())
    if not row.signature_valid or row.publisher.casefold() not in {p.casefold() for p in publishers}:
        return Decision(False, "Desconhecido ou assinatura/editor não reconhecidos — protegido")
    return Decision(True, "Aplicativo conhecido, assinado e com janela; permite solicitar fechamento normal")

def choose(rows: list[ProcessRow], decisions: dict[int, Decision], selected: set[str], keep: set[str]) -> list[ProcessRow]:
    return [r for r in rows if decisions.get(r.pid, Decision(False, "")).allowed
            and canonical(r.exe) in selected and canonical(r.exe) not in keep]
