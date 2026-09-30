"""Datenhaltung für PromptVault.

Alles, was auf die Platte geht, läuft hier durch: Prompts, Einstellungen,
Templates, Builder-Zustand, History, Papierkorb, Backups und Bilder.

Datenformat (prompts.json, Version 2)::

    {
      "version": 2,
      "categories": {
        "Clothing": [ {prompt}, {prompt}, ... ],
        ...
      }
    }

Ein Prompt-Objekt::

    {
      "id": "8f3a...",          # eindeutig, bleibt bei Edit/Move erhalten
      "text": "red dress",
      "title": "",              # optionaler Kurzname
      "tags": ["nsfw", "anime"],
      "note": "",
      "weight": 5,              # 1..10, relative Zieh-Häufigkeit im Builder
      "fav": false,
      "uses": 0,
      "last_used": null,        # ISO-Zeitstempel
      "created": "2026-01-01T12:00:00",
      "variants": [],           # alternative Formulierungen
      "image": null             # Dateiname im images/-Ordner
    }

Das alte Format (Version 1: {Kategorie: [str, ...]} + favorites.json) wird
beim ersten Start automatisch migriert.
"""

import csv
import datetime as _dt
import glob
import io
import json
import os
import re
import shutil
import sys
import uuid

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")

DEFAULT_CATEGORIES = ["Clothing", "Hairstyle", "Environment", "Appearance", "Position", "Character"]

DEFAULT_SETTINGS = {
    "data_dir": None,             # None = neben der EXE / main.py
    "theme": "dark",              # dark | light
    "accent": "cyan",             # cyan | green | pink | orange | blue | gold
    "font_scale": 1.0,
    "default_sep": ", ",
    "random_count": 10,
    "confirm_delete": True,
    "remember_window": True,
    "geometry": "",
    "zoomed": False,
    "cat_sort": "manual",         # manual | alpha | count
    "prompt_sort": "manual",      # manual | alpha | used | recent | newest | longest
    "backups_keep": 15,
    "backup_interval_min": 10,
    "history_keep": 100,
    "trash_keep": 200,
    "show_thumbnails": True,
    "sd": {                       # lokaler Bild-Server; leer = Funktion aus
        "backend": "a1111",       # a1111 | comfy
        "url": "",                # z. B. http://127.0.0.1:7860
        "workflow": "",           # Pfad zu ComfyUI-API-Workflow (JSON) mit %PROMPT% / %NEGATIVE%
        "steps": 25,
        "width": 832,
        "height": 1216,
        "save_output": True,
    },
    "tray": False,
    "hotkey": "",                 # z. B. "ctrl+alt+r" — leer = aus
}


def now_iso():
    return _dt.datetime.now().replace(microsecond=0).isoformat()


def uid():
    return uuid.uuid4().hex[:12]


def _deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def atomic_write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_read_json(path, default=None):
    try:
        return read_json(path, default)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return default


# ─── Prompt-Objekte ───────────────────────────────────────────────────────────

def make_prompt(text, **kw):
    p = {
        "id": uid(),
        "text": text.strip(),
        "title": "",
        "tags": [],
        "note": "",
        "weight": 5,
        "fav": False,
        "uses": 0,
        "last_used": None,
        "created": now_iso(),
        "variants": [],
        "image": None,
    }
    p.update({k: v for k, v in kw.items() if k in p})
    p["tags"] = normalize_tags(p.get("tags") or [])
    return p


def normalize_prompt(p):
    """Fehlende Felder auffüllen (z. B. nach Import älterer Exporte)."""
    if isinstance(p, str):
        return make_prompt(p)
    base = make_prompt(str(p.get("text", "")))
    for k in base:
        if k in p and p[k] is not None:
            base[k] = p[k]
    if not base["id"]:
        base["id"] = uid()
    base["tags"] = normalize_tags(base.get("tags") or [])
    base["variants"] = [v for v in (base.get("variants") or []) if isinstance(v, str) and v.strip()]
    try:
        base["weight"] = max(1, min(10, int(base.get("weight", 5))))
    except (TypeError, ValueError):
        base["weight"] = 5
    return base


def normalize_tags(tags):
    if isinstance(tags, str):
        tags = re.split(r"[,\n;]+", tags)
    out = []
    for t in tags:
        t = str(t).strip().lower().lstrip("#")
        if t and t not in out:
            out.append(t)
    return out


def prompt_all_texts(p):
    """Haupttext plus Varianten."""
    return [p["text"]] + [v for v in p.get("variants", []) if v]


# ─── Text-Helfer ──────────────────────────────────────────────────────────────

def split_batch(text):
    """Zerlegt nummerierten Text ("1: foo  2. bar  3) baz") in einzelne Prompts."""
    marker = r"(?:^|[\s,;])\s*\d{1,3}\s*[.:)]\s+"
    if re.search(marker, "\n" + text):
        parts = re.split(marker, "\n" + text)
        prompts = [p.strip().strip(",;").strip() for p in parts]
        return [p for p in prompts if p]
    return [line.strip() for line in text.splitlines() if line.strip()]


_TOKEN_RE = re.compile(r"[A-Za-z]+|\d|[^\sA-Za-z\d]")


def estimate_tokens(text):
    """Grobe Schätzung der CLIP-Token (SD-Modelle: 75 pro Chunk)."""
    n = 0
    for m in _TOKEN_RE.finditer(text):
        w = m.group(0)
        if w.isalpha():
            n += 1 + max(0, (len(w) - 7) // 4)
        else:
            n += 1
    return n


# ─── Store ────────────────────────────────────────────────────────────────────

class Store:
    """Hält Pfade, Einstellungen und alle Dateien zusammen."""

    def __init__(self):
        self.settings = self.load_settings()
        self._apply_paths()
        self._last_backup = None
        self.load_error = None

    # ── Einstellungen ────────────────────────────────────────────

    def load_settings(self):
        raw = safe_read_json(SETTINGS_FILE, {}) or {}
        raw.pop("ai", None)      # Altlast: keine KI-/LLM-Einstellungen mehr
        return _deep_merge(DEFAULT_SETTINGS, raw)

    def save_settings(self):
        atomic_write_json(SETTINGS_FILE, self.settings)

    def get(self, key, default=None):
        cur = self.settings
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, key, value, save=True):
        parts = key.split(".")
        cur = self.settings
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value
        if save:
            self.save_settings()

    # ── Pfade ────────────────────────────────────────────────────

    def _apply_paths(self):
        d = self.settings.get("data_dir") or APP_DIR
        self.data_dir = d
        self.data_file = os.path.join(d, "prompts.json")
        self.legacy_backup = os.path.join(d, "prompts_backup.json")
        self.legacy_favs = os.path.join(d, "favorites.json")
        self.template_file = os.path.join(d, "builder_templates.json")
        self.state_file = os.path.join(d, "builder_state.json")
        self.history_file = os.path.join(d, "history.json")
        self.trash_file = os.path.join(d, "trash.json")
        self.rules_file = os.path.join(d, "builder_rules.json")
        self.backup_dir = os.path.join(d, "backups")
        self.image_dir = os.path.join(d, "images")
        self.output_dir = os.path.join(d, "outputs")

    def set_data_dir(self, path, move_files=False):
        """Wechselt den Datenordner. Optional werden vorhandene Dateien mitgenommen."""
        path = os.path.abspath(path) if path else None
        old_dir = self.data_dir
        if move_files and path and os.path.abspath(old_dir) != path:
            os.makedirs(path, exist_ok=True)
            for name in ("prompts.json", "builder_templates.json", "builder_state.json",
                         "history.json", "trash.json", "builder_rules.json"):
                src = os.path.join(old_dir, name)
                dst = os.path.join(path, name)
                if os.path.exists(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
            for sub in ("backups", "images"):
                src = os.path.join(old_dir, sub)
                dst = os.path.join(path, sub)
                if os.path.isdir(src) and not os.path.isdir(dst):
                    shutil.copytree(src, dst)
        self.settings["data_dir"] = path if path and path != APP_DIR else None
        self.save_settings()
        self._apply_paths()

    # ── Prompts laden / migrieren / speichern ────────────────────

    def load_data(self):
        """Gibt {Kategorie: [Prompt-Objekte]} zurück.

        Bei einer defekten Datei wird `self.load_error` gesetzt und die Datei
        nach *.corrupt.<zeit> umbenannt; der Aufrufer kann dann ein Backup
        anbieten.
        """
        self.load_error = None
        if not os.path.exists(self.data_file):
            data = {cat: [] for cat in DEFAULT_CATEGORIES}
            self.save_data(data, backup=False)
            return data
        try:
            raw = read_json(self.data_file)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            self.load_error = str(e)
            try:
                stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy2(self.data_file, self.data_file + f".corrupt.{stamp}")
            except OSError:
                pass
            return None
        return self._coerce(raw)

    def _coerce(self, raw):
        """Bringt beliebige (auch alte) JSON-Strukturen ins v2-Format."""
        if isinstance(raw, dict) and raw.get("version") == 2 and isinstance(raw.get("categories"), dict):
            return {cat: [normalize_prompt(p) for p in (lst or []) if isinstance(p, (dict, str))]
                    for cat, lst in raw["categories"].items()}
        if isinstance(raw, dict):
            # Version 1: {Kategorie: [str]}
            favs = safe_read_json(self.legacy_favs, {}) or {}
            data = {}
            for cat, lst in raw.items():
                if not isinstance(lst, list):
                    continue
                fav_list = favs.get(cat, []) if isinstance(favs, dict) else []
                data[cat] = [make_prompt(p, fav=p in fav_list)
                             for p in lst if isinstance(p, str) and p.strip()]
            # Alte Datei als Sicherheit behalten
            try:
                shutil.copy2(self.data_file, os.path.join(self.data_dir, "prompts_v1_backup.json"))
            except OSError:
                pass
            self.save_data(data, backup=False)
            return data
        return {cat: [] for cat in DEFAULT_CATEGORIES}

    def save_data(self, data, backup=True):
        if backup:
            self.maybe_backup()
        atomic_write_json(self.data_file, {"version": 2, "categories": data})

    # ── Backups ──────────────────────────────────────────────────

    def maybe_backup(self, force=False):
        """Rotierendes Backup, höchstens alle `backup_interval_min` Minuten."""
        if not os.path.exists(self.data_file):
            return None
        interval = float(self.get("backup_interval_min", 10) or 0) * 60
        now = _dt.datetime.now()
        if not force and self._last_backup and (now - self._last_backup).total_seconds() < interval:
            return None
        os.makedirs(self.backup_dir, exist_ok=True)
        name = now.strftime("prompts_%Y%m%d_%H%M%S.json")
        dst = os.path.join(self.backup_dir, name)
        try:
            shutil.copy2(self.data_file, dst)
        except OSError:
            return None
        self._last_backup = now
        self._prune_backups()
        return dst

    def _prune_backups(self):
        keep = int(self.get("backups_keep", 15) or 15)
        files = self.list_backups()
        for path, _ in files[keep:]:
            try:
                os.remove(path)
            except OSError:
                pass

    def list_backups(self):
        """[(pfad, mtime)] neueste zuerst."""
        files = glob.glob(os.path.join(self.backup_dir, "prompts_*.json"))
        if os.path.exists(self.legacy_backup):
            files.append(self.legacy_backup)
        out = []
        for f in files:
            try:
                out.append((f, os.path.getmtime(f)))
            except OSError:
                pass
        out.sort(key=lambda x: x[1], reverse=True)
        return out

    def read_backup(self, path):
        raw = read_json(path)
        return self._coerce_no_side_effects(raw)

    def _coerce_no_side_effects(self, raw):
        if isinstance(raw, dict) and raw.get("version") == 2 and isinstance(raw.get("categories"), dict):
            return {cat: [normalize_prompt(p) for p in (lst or [])]
                    for cat, lst in raw["categories"].items()}
        if isinstance(raw, dict):
            return {cat: [make_prompt(p) for p in lst if isinstance(p, str) and p.strip()]
                    for cat, lst in raw.items() if isinstance(lst, list)}
        return None

    # ── Templates ────────────────────────────────────────────────

    def load_templates(self):
        """{name: {"slots": [...], "rules": [...]}} — alte Formate werden gewandelt."""
        raw = safe_read_json(self.template_file, {}) or {}
        out = {}
        for name, val in raw.items():
            if isinstance(val, list):
                slots = []
                for e in val:
                    if isinstance(e, str):
                        slots.append({"type": "cat", "cat": e, "weight": 100})
                    elif isinstance(e, dict):
                        slots.append(e)
                out[name] = {"slots": slots, "rules": []}
            elif isinstance(val, dict):
                out[name] = {"slots": val.get("slots", []), "rules": val.get("rules", []),
                             "wf_overrides": val.get("wf_overrides") if isinstance(val.get("wf_overrides"), dict) else {}}
        return out

    def save_templates(self, templates):
        atomic_write_json(self.template_file, templates)

    # ── Builder-Zustand / Regeln ─────────────────────────────────

    def load_state(self):
        return safe_read_json(self.state_file, {}) or {}

    def save_state(self, state):
        atomic_write_json(self.state_file, state)

    # ── History ──────────────────────────────────────────────────

    def load_history(self):
        h = safe_read_json(self.history_file, []) or []
        return [e for e in h if isinstance(e, dict) and e.get("text")]

    def save_history(self, history):
        keep = int(self.get("history_keep", 100) or 100)
        pinned = [e for e in history if e.get("pinned")]
        rest = [e for e in history if not e.get("pinned")][:keep]
        merged = sorted(pinned + rest, key=lambda e: e.get("ts", ""), reverse=True)
        atomic_write_json(self.history_file, merged)
        return merged

    # ── Papierkorb ───────────────────────────────────────────────

    def load_trash(self):
        return safe_read_json(self.trash_file, []) or []

    def save_trash(self, trash):
        keep = int(self.get("trash_keep", 200) or 200)
        trash = trash[:keep]
        atomic_write_json(self.trash_file, trash)
        return trash

    # ── Bilder ───────────────────────────────────────────────────

    def store_image(self, src_path, prompt_id):
        os.makedirs(self.image_dir, exist_ok=True)
        ext = os.path.splitext(src_path)[1].lower() or ".png"
        name = f"{prompt_id}{ext}"
        dst = os.path.join(self.image_dir, name)
        shutil.copy2(src_path, dst)
        return name

    def image_path(self, name):
        return os.path.join(self.image_dir, name) if name else None

    def remove_image(self, name):
        if not name:
            return
        try:
            os.remove(self.image_path(name))
        except OSError:
            pass

    # ── Export / Import ──────────────────────────────────────────

    def export_bundle(self, data, templates, rules, history=None):
        return {
            "version": 2,
            "app": "PromptVault",
            "exported": now_iso(),
            "categories": data,
            "templates": templates,
            "rules": rules,
            "history": history or [],
        }

    @staticmethod
    def export_plain(data):
        """Kompatibles v1-Format: {Kategorie: [Text, ...]}"""
        return {cat: [p["text"] for p in lst] for cat, lst in data.items()}

    @staticmethod
    def parse_import_text(text, fallback_cat):
        """TXT (eine Zeile = ein Prompt) oder CSV (category,text[,tags]).

        Rückgabe: {Kategorie: [Prompt-Objekte]}
        """
        lines = [l for l in text.splitlines() if l.strip()]
        if not lines:
            return {}
        first = lines[0].lower().replace(" ", "")
        looks_csv = ("," in first or ";" in first) and any(
            h in first for h in ("category", "kategorie", "text", "prompt"))
        if looks_csv:
            dialect = csv.excel
            if first.count(";") > first.count(","):
                dialect = csv.excel_tab
                dialect = type("D", (csv.excel,), {"delimiter": ";"})
            reader = csv.DictReader(io.StringIO(text), dialect=dialect)
            out = {}
            for row in reader:
                low = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
                cat = low.get("category") or low.get("kategorie") or fallback_cat
                txt = low.get("text") or low.get("prompt")
                if not txt:
                    continue
                p = make_prompt(txt, tags=low.get("tags", ""), title=low.get("title", ""),
                                note=low.get("note", ""))
                out.setdefault(cat, []).append(p)
            return out
        return {fallback_cat: [make_prompt(l.strip()) for l in lines]}

    @staticmethod
    def wildcard_text(prompts):
        return "\n".join(p["text"] for p in prompts) + "\n"
