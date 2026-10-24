from __future__ import annotations
import json
import os
from pathlib import Path
import re
from .state import canonical

SKIP = ("unins", "setup", "crash", "redist", "anticheat", "battleye", "launcher", "vc_redist")

def discover() -> list[dict]:
    """Read launcher manifests only; no whole-disk executable guessing or game-file changes."""
    games = {}
    def add(name, path):
        path = Path(path)
        if path.is_file() and path.suffix.casefold() == ".exe":
            games[canonical(str(path))] = {"name": name, "exe": str(path), "favorite": False}
    steam_roots = []
    if os.name == "nt":
        import winreg
        for hive, key, value in [(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")]:
            try:
                with winreg.OpenKey(hive, key) as reg:
                    steam_roots.append(Path(winreg.QueryValueEx(reg, value)[0]))
            except OSError:
                pass
    program_x86 = os.environ.get("ProgramFiles(x86)")
    if program_x86:
        steam_roots.append(Path(program_x86)/"Steam")
    libraries = set(steam_roots)
    for root in steam_roots:
        file = root/"steamapps/libraryfolders.vdf"
        if file.is_file():
            try:
                libraries.update(Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', file.read_text(encoding="utf-8")))
            except (OSError, UnicodeError):
                pass
    for library in libraries:
        try:
            for manifest in (library/"steamapps").glob("appmanifest_*.acf"):
                text = manifest.read_text(encoding="utf-8")
                name = re.search(r'"name"\s+"([^"]+)"', text)
                location = re.search(r'"installdir"\s+"([^"]+)"', text)
                if not location or Path(location[1]).name != location[1]:
                    continue
                directory = library/"steamapps/common"/location[1]
                # Executables are candidates for protection/profile association; nothing is launched.
                count = 0
                for folder, directories, files in os.walk(directory, followlinks=False):
                    directories[:] = [d for d in directories if not any(s in d.casefold() for s in SKIP)
                                      and not (Path(folder)/d).is_symlink() and not os.path.isjunction(Path(folder)/d)]
                    if len(Path(folder).relative_to(directory).parts) >= 4:
                        directories.clear()
                    for file in files:
                        count += 1
                        if count > 5000:
                            break
                        if file.casefold().endswith(".exe") and not any(s in file.casefold() for s in SKIP):
                            add(f"{name[1] if name else location[1]} · {file}", Path(folder)/file)
                    if count > 5000:
                        break
        except (OSError, UnicodeError):
            continue
    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        for manifest in (Path(program_data)/"Epic/EpicGamesLauncher/Data/Manifests").glob("*.item"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                root = Path(data["InstallLocation"]).resolve()
                executable = (root/data["LaunchExecutable"]).resolve()
                if executable.is_relative_to(root):
                    add(data.get("DisplayName", executable.stem), executable)
            except (OSError, ValueError, KeyError, TypeError):
                continue
    local = os.environ.get("LOCALAPPDATA")
    if local:
        add("FiveM", Path(local)/"FiveM/FiveM.exe")
        for file in (Path(local)/"Roblox/Versions").glob("*/RobloxPlayerBeta.exe"):
            add("Roblox", file)
    return sorted(games.values(), key=lambda game: game["name"].casefold())
