from __future__ import annotations
import copy
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import tempfile

DEFAULTS = {"simulation": True, "game_boost": False, "startup": False, "favorites": [],
            "games": [], "profiles": {"Global": {"keep": [], "close": []}},
            "profile": "Global", "history": [], "power_restore": None}

def canonical(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)) if path else ""

class Store:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "UniversalGameBoosterPro"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "preferences.json"
        self.log = logging.getLogger("gamebooster." + str(self.directory))
        self.log.setLevel(logging.INFO)
        if not self.log.handlers:
            handler = RotatingFileHandler(self.directory / "operations.log", maxBytes=2_000_000, backupCount=4, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.log.addHandler(handler)
        self.data = copy.deepcopy(DEFAULTS)
        self.load_warning = ""
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError("Preferências precisam ser um objeto JSON")
                for key, value in loaded.items():
                    if key in DEFAULTS and ((value is None and key == "power_restore") or type(value) is type(DEFAULTS[key]) or key == "power_restore"):
                        self.data[key] = value
                for profile in self.data["profiles"].values():
                    if not isinstance(profile, dict) or not all(isinstance(profile.get(k), list) for k in ("keep", "close")):
                        raise ValueError("Perfil inválido")
                self.data["profiles"].setdefault("Global", {"keep": [], "close": []})
                if any(not isinstance(path, str) for path in self.data["favorites"]):
                    raise ValueError("Favoritos inválidos")
                if any(not isinstance(g, dict) or not isinstance(g.get("name"), str) or not isinstance(g.get("exe"), str) for g in self.data["games"]):
                    raise ValueError("Jogos inválidos")
                if any(not isinstance(p, str) for profile in self.data["profiles"].values() for key in ("keep", "close") for p in profile[key]):
                    raise ValueError("Caminhos de perfil inválidos")
                saved = self.data["power_restore"]
                if saved is not None:
                    import re
                    if not isinstance(saved, dict) or not all(isinstance(saved.get(k), str) and re.fullmatch(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", saved[k]) for k in ("original", "applied")):
                        raise ValueError("Recuperação de energia inválida")
                if any(not isinstance(entry, dict) or not all(isinstance(entry.get(k), dict) and all(isinstance(entry[k].get(metric), (int,float)) for metric in ("cpu", "ram_used", "available", "processes")) for k in ("before", "after")) for entry in self.data["history"]):
                    raise ValueError("Histórico inválido")
            except (ValueError, OSError, TypeError, AttributeError):
                self.load_warning = "Preferências inválidas não foram carregadas; o arquivo foi preservado."
                self.log.exception("Falha ao ler preferências")
                self.data = copy.deepcopy(DEFAULTS)
                # Preserve an invalid original before subsequent saves.
                import shutil
                shutil.copy2(self.path, self.directory / "preferences.invalid.json")

    def save(self):
        descriptor, temporary = tempfile.mkstemp(prefix="prefs-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(self.data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def close(self):
        for handler in list(self.log.handlers):
            handler.close()
            self.log.removeHandler(handler)

    def profile(self, name: str) -> dict:
        return self.data["profiles"].setdefault(name, {"keep": [], "close": []})

    def record(self, entry: dict):
        self.data["history"].append(entry)
        self.data["history"] = self.data["history"][-200:]
        self.save()
