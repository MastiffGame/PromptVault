"""Lokale Anbindungen: Automatic1111 / ComfyUI (eigener Rechner, per URL),
System-Tray und globaler Hotkey. Alles optional und fehlertolerant.

Es gibt bewusst keine Verbindung zu KI-/LLM-Diensten."""

import base64
import ctypes
import datetime as _dt
import json
import os
import queue
import random
import sys
import threading

if sys.platform == "win32":
    import ctypes.wintypes  # noqa: F401  (stellt MSG bereit)
import urllib.error
import urllib.request
import uuid

from tkinter import messagebox

from theme import C

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:          # pragma: no cover
    pystray = None
    HAS_TRAY = False


class IntegrationsMixin:

    # ═══════════════════════════════════════════════════════════════
    # THREAD → TK
    # ═══════════════════════════════════════════════════════════════

    def _init_queue(self):
        self._q = queue.Queue()
        self._poll_queue()

    def _post(self, fn, *args):
        """Funktion aus einem Hintergrund-Thread im Tk-Thread ausführen."""
        self._q.put((fn, args))

    def _poll_queue(self):
        try:
            while True:
                fn, args = self._q.get_nowait()
                try:
                    fn(*args)
                except Exception as e:      # UI darf nicht sterben
                    print("queued callback failed:", e, file=sys.stderr)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(150, self._poll_queue)

    # ═══════════════════════════════════════════════════════════════
    # AUTOMATIC1111 / COMFYUI  (lokaler Bild-Server, nur wenn URL gesetzt)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _http_json(method, url, payload=None, timeout=600):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8")
        return json.loads(body) if body else {}

    def _sd_test(self, backend, url, cb):
        url = (url or "").rstrip("/")
        if not url:
            cb("no URL", False)
            return

        def work():
            try:
                if backend == "comfy":
                    r = self._http_json("GET", url + "/system_stats", timeout=8)
                    ver = r.get("system", {}).get("comfyui_version", "")
                    self._post(cb, f"ComfyUI reachable {ver}".strip(), True)
                else:
                    r = self._http_json("GET", url + "/sdapi/v1/options", timeout=8)
                    ck = r.get("sd_model_checkpoint", "")
                    self._post(cb, f"A1111 reachable · model: {ck or '?'}", True)
            except urllib.error.HTTPError as e:
                self._post(cb, f"HTTP {e.code} — is the API enabled (--api)?", False)
            except Exception as e:      # noqa: BLE001
                self._post(cb, f"not reachable: {e}"[:140], False)
        threading.Thread(target=work, daemon=True).start()

    def _sd_ready(self, quiet=False):
        """Prüft Einstellungen; gibt (backend, url, workflow_text) zurück oder None."""
        url = (self.store.get("sd.url") or "").rstrip("/")
        backend = self.store.get("sd.backend", "a1111")
        if not url:
            if not quiet:
                self._toast("Set the image backend URL in Settings")
            return None
        wf_text = None
        if backend == "comfy":
            wf_path = self.store.get("sd.workflow", "")
            if not wf_path or not os.path.exists(wf_path):
                if not quiet:
                    messagebox.showwarning("ComfyUI", "Choose an API-format workflow JSON in Settings.\n"
                                                      "Use %PROMPT%, %NEGATIVE% and %SEED% as placeholders.", parent=self)
                return None
            try:
                with open(wf_path, "r", encoding="utf-8") as f:
                    wf_text = f.read()
            except OSError as e:
                if not quiet:
                    self._toast(f"Workflow unreadable: {e}")
                return None
            if "%PROMPT%" not in wf_text and not quiet:
                self._toast("Workflow has no %PROMPT% placeholder")
        return backend, url, wf_text

    @staticmethod
    def comfy_workflow(wf_text, prompt, negative, seed=None):
        """Setzt Platzhalter ein und liefert das Workflow-Dict.

        %PROMPT% / %NEGATIVE% werden JSON-sicher als Text eingesetzt, %SEED% als Zahl
        (funktioniert sowohl als "seed": "%SEED%" als auch als "seed": %SEED%).
        """
        if seed is None:
            seed = random.randint(0, 2 ** 32 - 1)
        t = wf_text.replace("%PROMPT%", json.dumps(prompt)[1:-1])
        t = t.replace("%NEGATIVE%", json.dumps(negative or "")[1:-1])
        t = t.replace('"%SEED%"', str(seed)).replace("%SEED%", str(seed))
        return json.loads(t)

    def _sd_send(self, prompt, negative=""):
        self._sd_send_many([(prompt, negative)])

    def _sd_send_many(self, items):
        """Schickt mehrere (prompt, negative)-Paare nacheinander an das lokale Backend.

        ComfyUI: jeder Auftrag landet in der Warteschlange, die Bilder schreibt ComfyUI selbst.
        A1111:   Aufträge laufen nacheinander, jedes Bild wird in outputs/ gespeichert.
        """
        items = [(p, n or "") for p, n in items if p]
        if not items:
            return
        ready = self._sd_ready()
        if not ready:
            return
        backend, url, wf_text = ready
        n = len(items)
        if backend == "comfy":
            try:
                self.comfy_workflow(wf_text, items[0][0], items[0][1])
            except json.JSONDecodeError as e:
                self._toast(f"Workflow JSON invalid: {e}")
                return
        self._toast(f"Queuing {n} in ComfyUI…" if backend == "comfy" else
                    (f"Generating {n} in A1111…" if n > 1 else "Generating in A1111…"))

        def work():
            ok, errors, saved = 0, [], []
            for i, (prompt, negative) in enumerate(items, 1):
                try:
                    if backend == "comfy":
                        payload = {"prompt": self.comfy_workflow(wf_text, prompt, negative),
                                   "client_id": uuid.uuid4().hex}
                        self._http_json("POST", url + "/prompt", payload, timeout=30)
                    else:
                        payload = {
                            "prompt": prompt, "negative_prompt": negative,
                            "steps": int(self.store.get("sd.steps", 25)),
                            "width": int(self.store.get("sd.width", 832)),
                            "height": int(self.store.get("sd.height", 1216)),
                        }
                        r = self._http_json("POST", url + "/sdapi/v1/txt2img", payload, timeout=900)
                        imgs = r.get("images") or []
                        if imgs and self.store.get("sd.save_output", True):
                            os.makedirs(self.store.output_dir, exist_ok=True)
                            stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                            path = os.path.join(self.store.output_dir, f"a1111_{stamp}.png")
                            with open(path, "wb") as f:
                                f.write(base64.b64decode(imgs[0].split(",", 1)[-1]))
                            saved.append(path)
                        if n > 1:
                            self._post(self._toast, f"A1111  {i} / {n} done")
                    ok += 1
                except urllib.error.HTTPError as e:
                    errors.append(f"HTTP {e.code}")
                except Exception as e:      # noqa: BLE001
                    errors.append(str(e)[:80])
                    if backend == "comfy" and "refused" in str(e).lower():
                        break   # Server weg, nicht weiter hämmern

            def done():
                name = "ComfyUI" if backend == "comfy" else "A1111"
                if errors and not ok:
                    self._toast(f"{name} error: {errors[0]}"[:120])
                    return
                if backend == "comfy":
                    msg = f"{ok} queued in ComfyUI" if n > 1 else "ComfyUI accepted"
                elif saved:
                    msg = (f"{len(saved)} images saved to outputs/" if n > 1
                           else f"Image saved: {os.path.basename(saved[0])}")
                else:
                    msg = f"A1111 finished {ok} / {n}"
                if errors:
                    msg += f"  ·  {len(errors)} failed"
                self._toast(msg)
                if backend != "comfy" and len(saved) == 1 and n == 1:
                    try:
                        os.startfile(saved[0])
                    except OSError:
                        pass
            self._post(done)
        threading.Thread(target=work, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════
    # TRAY
    # ═══════════════════════════════════════════════════════════════

    def _tray_available(self):
        return HAS_TRAY

    def _tray_image(self):
        img = Image.new("RGBA", (64, 64), (6, 6, 15, 255))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=14, outline=C.ACC, width=4)
        d.rectangle((18, 18, 30, 46), fill=C.ACC)
        d.rectangle((34, 18, 46, 30), fill=C.PURP)
        d.rectangle((34, 36, 46, 46), fill=C.PURP)
        return img

    def _apply_background_settings(self):
        self._stop_hotkey()
        if self.store.get("hotkey"):
            self._start_hotkey(self.store.get("hotkey"))
        if not self.store.get("tray") and self._tray:
            self._stop_tray()

    def _start_tray(self):
        if not HAS_TRAY or self._tray:
            return False
        menu = pystray.Menu(
            pystray.MenuItem("Show PromptVault", lambda: self._post(self._show_from_tray), default=True),
            pystray.MenuItem("Roll builder & copy", lambda: self._post(self._hotkey_action)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self._post(self._quit)),
        )
        self._tray = pystray.Icon("PromptVault", self._tray_image(), "PromptVault", menu)
        threading.Thread(target=self._tray.run, daemon=True).start()
        return True

    def _stop_tray(self):
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass
            self._tray = None

    def _show_from_tray(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _hide_to_tray(self):
        if self._start_tray() or self._tray:
            self.withdraw()
            return True
        return False

    # ═══════════════════════════════════════════════════════════════
    # GLOBALER HOTKEY (Windows, RegisterHotKey)
    # ═══════════════════════════════════════════════════════════════

    _MODS = {"ctrl": 0x0002, "control": 0x0002, "alt": 0x0001, "shift": 0x0004, "win": 0x0008}

    @classmethod
    def _parse_hotkey(cls, spec):
        mods, vk = 0, None
        for part in (spec or "").lower().replace(" ", "").split("+"):
            if part in cls._MODS:
                mods |= cls._MODS[part]
            elif len(part) == 1 and part.isalnum():
                vk = ord(part.upper())
            elif part.startswith("f") and part[1:].isdigit():
                vk = 0x70 + int(part[1:]) - 1
            elif part == "space":
                vk = 0x20
        mods |= 0x4000  # MOD_NOREPEAT
        return mods, vk

    def _start_hotkey(self, spec):
        if sys.platform != "win32":
            return
        mods, vk = self._parse_hotkey(spec)
        if vk is None:
            return
        self._hotkey_stop = threading.Event()
        user32 = ctypes.windll.user32
        stop = self._hotkey_stop
        result = {"ok": None}

        def loop():
            tid = ctypes.windll.kernel32.GetCurrentThreadId()
            self._hotkey_tid = tid
            if not user32.RegisterHotKey(None, 1, mods, vk):
                result["ok"] = False
                self._post(self._toast, f"Hotkey {spec} is already taken")
                return
            result["ok"] = True
            msg = ctypes.wintypes.MSG()
            try:
                while not stop.is_set():
                    r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                    if r <= 0:
                        break
                    if msg.message == 0x0312:      # WM_HOTKEY
                        self._post(self._hotkey_action)
            finally:
                user32.UnregisterHotKey(None, 1)
        threading.Thread(target=loop, daemon=True).start()

    def _stop_hotkey(self):
        if sys.platform != "win32":
            return
        if getattr(self, "_hotkey_stop", None):
            self._hotkey_stop.set()
            tid = getattr(self, "_hotkey_tid", None)
            if tid:
                try:
                    ctypes.windll.user32.PostThreadMessageW(tid, 0x0012, 0, 0)   # WM_QUIT
                except Exception:
                    pass
            self._hotkey_stop = None
            self._hotkey_tid = None

    def _hotkey_action(self):
        """Builder würfeln und Ergebnis in die Zwischenablage legen."""
        if not self._slots:
            self._toast("Builder has no slots")
            return
        for slot in self._slots:
            if not slot["locked"]:
                self._roll_slot(slot)
        self._apply_rules()
        self._render_slots()
        self._record_history()
        text = self._result_text(wildcard=False)
        if text:
            self._copy(text)
            self._mark_slot_usage()
            self._toast("Rolled & copied")
