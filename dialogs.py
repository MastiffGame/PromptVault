"""Dialoge: Editoren, Einstellungen, Duplikate, Papierkorb, Backups, Import/Export."""

import os
import re
import json
import tkinter as tk
from tkinter import messagebox, filedialog

from storage import (make_prompt, normalize_prompt, normalize_tags, estimate_tokens,
                     DEFAULT_SETTINGS)
from theme import C, F, px, ACCENTS
from widgets import (flat_btn, chip, styled_menu, entry, option_menu,
                     checkbox, slider, ScrollFrame, Overlay, make_textbox, textbox_set, textbox_get,
                     load_thumb, fmt_ts, HAS_PIL, Tooltip)

SHORTCUTS = [
    ("Ctrl+N", "New prompt"),
    ("Ctrl+Shift+N", "New category"),
    ("Ctrl+F", "Search"),
    ("Esc", "Clear search / close dialog"),
    ("Ctrl+A", "Select all visible prompts"),
    ("Delete", "Delete selected prompts"),
    ("Ctrl+C", "Copy selected prompts / builder result"),
    ("Ctrl+Z", "Undo delete"),
    ("Ctrl+1 … 9", "Jump to category"),
    ("Ctrl+L / Ctrl+B", "Library / Builder"),
    ("Space", "Builder: randomize"),
    ("Ctrl+Enter", "Editor: save"),
    ("Ctrl+,", "Settings"),
    ("Ctrl+D", "Find duplicates"),
    ("Ctrl+T", "Trash"),
    ("F1", "This help"),
]


def safe_filename(name):
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_") or "category"


class DialogsMixin:

    # ═══════════════════════════════════════════════════════════════
    # EINFACHER TEXTEDITOR
    # ═══════════════════════════════════════════════════════════════

    def _show_editor(self, title="Text", initial="", on_save=None, hint=None):
        ov = Overlay(self, 700, 440, title=title, hint=hint)
        tb = make_textbox(ov.body, height=240)
        tb.pack(fill="both", expand=True)
        textbox_set(tb, initial)
        counter = tk.Label(ov.body, text="", fg=C.TXT2, bg=C.SURF, font=F(9))
        counter.pack(anchor="e", pady=(4, 0))
        self._attach_counter(tb, counter)

        def save(_=None):
            text = textbox_get(tb).strip()
            ov.close()
            if text and on_save:
                on_save(text)
            return "break"
        ov.buttons(("Save", save, "neon"), ("Cancel", ov.close, "ghost"))
        tb.bind("<Control-Return>", save)
        tb.focus_set()

    def _attach_counter(self, tb, label):
        def upd(_=None):
            t = textbox_get(tb)
            tok = estimate_tokens(t)
            label.configure(text=f"{len(t)} chars · {len(t.split())} words · ~{tok} tokens"
                            + (f" · {(tok + 74) // 75} chunks of 75" if tok > 75 else ""),
                            fg=C.RED if tok > 150 else C.TXT2)
        tb._textbox.bind("<KeyRelease>", upd, add="+")
        upd()
        tb._count_update = upd

    # ═══════════════════════════════════════════════════════════════
    # VOLLER PROMPT-EDITOR
    # ═══════════════════════════════════════════════════════════════

    def _show_prompt_editor(self, title, cat, prompt=None, on_save=None):
        ov = Overlay(self, 860, 760, title=title, hint=cat if prompt else None)
        sf = ScrollFrame(ov.body, bg=C.SURF)
        sf.pack(fill="both", expand=True)
        b = sf.inner

        def lbl(text, **kw):
            tk.Label(b, text=text, fg=C.TXT2, bg=C.SURF, font=F(10)).pack(anchor="w", **kw)

        # Titel + Gewicht
        row = tk.Frame(b, bg=C.SURF)
        row.pack(fill="x")
        left = tk.Frame(row, bg=C.SURF)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="Title (optional)", fg=C.TXT2, bg=C.SURF, font=F(10)).pack(anchor="w")
        title_var = tk.StringVar(value=(prompt or {}).get("title", ""))
        entry(left, title_var, width=420, height=32, placeholder="short name").pack(anchor="w", fill="x", pady=(2, 0))
        right = tk.Frame(row, bg=C.SURF)
        right.pack(side="right", padx=(16, 0))
        w_var = tk.IntVar(value=(prompt or {}).get("weight", 5))
        w_lbl = tk.Label(right, text=f"Weight {w_var.get()}/10", fg=C.TXT2, bg=C.SURF, font=F(10))
        w_lbl.pack(anchor="w")
        slider(right, 1, 10, w_var, steps=9, width=180,
               command=lambda v: w_lbl.configure(text=f"Weight {int(float(v))}/10")).pack(pady=(6, 0))
        Tooltip(right, "Relative draw frequency in the Builder (5 = normal)")

        # Text
        lbl("Prompt", pady=(10, 0))
        tb = make_textbox(b, height=170)
        tb.pack(fill="x", pady=(2, 0))
        textbox_set(tb, (prompt or {}).get("text", ""))
        cnt_row = tk.Frame(b, bg=C.SURF)
        cnt_row.pack(fill="x")
        counter = tk.Label(cnt_row, text="", fg=C.TXT2, bg=C.SURF, font=F(9))
        counter.pack(side="right", pady=(3, 0))
        self._attach_counter(tb, counter)
        tk.Label(cnt_row, text="(word:1.2)  ((emphasis))  [de-emphasis]  __wildcard__  <lora:x:1>",
                 fg=C.TXT3, bg=C.SURF, font=F(9)).pack(side="left", pady=(3, 0))

        # Tags
        lbl("Tags (comma-separated)", pady=(10, 0))
        tags_var = tk.StringVar(value=", ".join((prompt or {}).get("tags", [])))
        entry(b, tags_var, width=600, height=32, placeholder="anime, nsfw, summer").pack(fill="x", pady=(2, 0))
        existing = self._all_tags(cats=self.categories)
        if existing:
            tag_row = tk.Frame(b, bg=C.SURF)
            tag_row.pack(fill="x", pady=(4, 0))

            def add_tag(t):
                cur = normalize_tags(tags_var.get())
                if t not in cur:
                    cur.append(t)
                    tags_var.set(", ".join(cur))
            for t, _n in existing[:18]:
                chip(tag_row, "+" + t, fg=C.TXT2, bg=C.SURF2, cmd=lambda tt=t: add_tag(tt)).pack(
                    side="left", padx=(0, 4), pady=1)

        # Notiz
        lbl("Note", pady=(10, 0))
        note_tb = make_textbox(b, height=60, font_size=11, highlight=False)
        note_tb.pack(fill="x", pady=(2, 0))
        textbox_set(note_tb, (prompt or {}).get("note", ""))

        # Varianten
        lbl("Variants — one per line, the Builder picks one at random", pady=(10, 0))
        var_tb = make_textbox(b, height=70, font_size=11)
        var_tb.pack(fill="x", pady=(2, 0))
        textbox_set(var_tb, "\n".join((prompt or {}).get("variants", [])))

        # Bild
        lbl("Example image", pady=(10, 0))
        img_row = tk.Frame(b, bg=C.SURF)
        img_row.pack(fill="x", pady=(2, 6))
        img_state = {"name": (prompt or {}).get("image"), "new_path": None, "remove": False}
        img_lbl = tk.Label(img_row, bg=C.SURF)
        img_lbl.pack(side="left", padx=(0, 10))
        img_txt = tk.Label(img_row, text="", fg=C.TXT2, bg=C.SURF, font=F(9))
        img_txt.pack(side="left")

        def show_img():
            path = img_state["new_path"] or (self.store.image_path(img_state["name"]) if img_state["name"] else None)
            if path and not img_state["remove"]:
                ph = load_thumb(path, 90)
                if ph:
                    img_lbl.configure(image=ph)
                    img_lbl.image = ph
                    img_txt.configure(text=os.path.basename(path))
                    return
            img_lbl.configure(image="")
            img_lbl.image = None
            img_txt.configure(text="no image" if HAS_PIL else "Pillow not installed")

        def choose():
            path = filedialog.askopenfilename(parent=self, title="Choose image",
                                              filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")])
            if path:
                img_state["new_path"] = path
                img_state["remove"] = False
                show_img()

        def remove():
            img_state["new_path"] = None
            img_state["remove"] = True
            show_img()
        flat_btn(img_row, "Choose…", choose, fg=C.ACC, bg=C.SURF, hover=C.SURF3).pack(side="right", padx=2)
        flat_btn(img_row, "Remove", remove, fg=C.RED, bg=C.SURF, hover=C.RED_DIM).pack(side="right", padx=2)
        show_img()

        def save(_=None):
            text = textbox_get(tb).strip()
            if not text:
                self._toast("Prompt text is empty")
                return "break"
            if prompt:
                p = dict(prompt)
            else:
                p = make_prompt(text)
            p["text"] = text
            p["title"] = title_var.get().strip()
            p["tags"] = normalize_tags(tags_var.get())
            p["note"] = textbox_get(note_tb).strip()
            p["weight"] = int(w_var.get())
            p["variants"] = [l.strip() for l in textbox_get(var_tb).splitlines() if l.strip() and l.strip() != text]
            if img_state["remove"] and p.get("image"):
                self.store.remove_image(p["image"])
                p["image"] = None
            if img_state["new_path"]:
                try:
                    if p.get("image"):
                        self.store.remove_image(p["image"])
                    p["image"] = self.store.store_image(img_state["new_path"], p["id"])
                except OSError as e:
                    messagebox.showerror("Image", f"Could not copy image:\n{e}", parent=self)
            ov.close()
            if on_save:
                on_save(p)
            return "break"

        ov.buttons(("Save  (Ctrl+Enter)", save, "neon"), ("Cancel", ov.close, "ghost"))
        for w in (tb, note_tb, var_tb):
            w.bind("<Control-Return>", save)
        ov.frame.bind("<Control-Return>", save)
        tb.focus_set()

    # ═══════════════════════════════════════════════════════════════
    # NAMENSDIALOG
    # ═══════════════════════════════════════════════════════════════

    def _show_name_dialog(self, title, initial="", on_save=None, taken=None, placeholder=""):
        ov = Overlay(self, 460, 190, title=title)
        name_var = tk.StringVar(value=initial)
        e = entry(ov.body, name_var, width=400, height=36, placeholder=placeholder)
        e.pack(fill="x")

        def save(_=None):
            name = name_var.get().strip()
            if not name:
                return
            existing = self.data if taken is None else taken
            if name != initial and name in existing:
                messagebox.showwarning("Exists", f'"{name}" already exists.', parent=self)
                return
            ov.close()
            if on_save:
                on_save(name)
        ov.buttons(("Save", save, "neon"), ("Cancel", ov.close, "ghost"))
        e.bind("<Return>", save)
        e.focus_set()
        if initial:
            e.select_range(0, "end")

    # ═══════════════════════════════════════════════════════════════
    # EINSTELLUNGEN
    # ═══════════════════════════════════════════════════════════════

    def _open_settings(self):
        s = self.store
        ov = Overlay(self, 820, 720, title="Settings")
        sf = ScrollFrame(ov.body, bg=C.SURF)
        sf.pack(fill="both", expand=True)
        b = sf.inner

        def section(text):
            tk.Frame(b, height=1, bg=C.BORDER).pack(fill="x", pady=(14, 6))
            tk.Label(b, text=text.upper(), fg=C.ACC, bg=C.SURF, font=F(10, bold=True)).pack(anchor="w")

        def row(label, widget_fn, hint=None):
            r = tk.Frame(b, bg=C.SURF)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=label, fg=C.TXT2, bg=C.SURF, font=F(10), width=22, anchor="w").pack(side="left")
            w = widget_fn(r)
            w.pack(side="left")
            if hint:
                tk.Label(r, text=hint, fg=C.TXT3, bg=C.SURF, font=F(9)).pack(side="left", padx=10)
            return w

        # Appearance
        tk.Label(b, text="APPEARANCE", fg=C.ACC, bg=C.SURF, font=F(10, bold=True)).pack(anchor="w")
        theme_var = tk.StringVar(value=s.get("theme", "dark"))
        row("Theme", lambda r: option_menu(r, ["dark", "light"], theme_var, width=140))
        accent_var = tk.StringVar(value=s.get("accent", "cyan"))
        row("Accent color", lambda r: option_menu(r, list(ACCENTS), accent_var, width=140))
        fs_var = tk.DoubleVar(value=float(s.get("font_scale", 1.0)))
        fs_lbl = {"w": None}

        def fs_widget(r):
            f = tk.Frame(r, bg=C.SURF)
            slider(f, 0.8, 1.4, fs_var, steps=12, width=200,
                   command=lambda v: fs_lbl["w"].configure(text=f"{float(v):.2f}×")).pack(side="left")
            fs_lbl["w"] = tk.Label(f, text=f"{fs_var.get():.2f}×", fg=C.TXT, bg=C.SURF, font=F(10), width=6)
            fs_lbl["w"].pack(side="left")
            return f
        row("Font size", fs_widget, "applies after Save (UI rebuilds)")
        thumbs_var = tk.BooleanVar(value=bool(s.get("show_thumbnails", True)))
        row("Thumbnails in list", lambda r: checkbox(r, "", thumbs_var))

        # Behaviour
        section("Behaviour")
        sep_var = tk.StringVar(value=s.get("default_sep", ", "))
        row("Default separator", lambda r: entry(r, sep_var, width=80, height=30))
        rnd_var = tk.StringVar(value=str(s.get("random_count", 10)))
        row("Random picker count", lambda r: entry(r, rnd_var, width=80, height=30))
        conf_var = tk.BooleanVar(value=bool(s.get("confirm_delete", True)))
        row("Confirm before delete", lambda r: checkbox(r, "", conf_var), "Ctrl+Z / Trash still work")
        rem_var = tk.BooleanVar(value=bool(s.get("remember_window", True)))
        row("Remember window size", lambda r: checkbox(r, "", rem_var))

        # Data
        section("Data & backups")
        dir_var = tk.StringVar(value=s.data_dir)

        def dir_widget(r):
            f = tk.Frame(r, bg=C.SURF)
            entry(f, dir_var, width=360, height=30).pack(side="left")

            def browse():
                p = filedialog.askdirectory(parent=self, title="Choose data folder", initialdir=dir_var.get())
                if p:
                    dir_var.set(p)

            def open_dir():
                try:
                    os.startfile(s.data_dir)
                except OSError:
                    pass
            flat_btn(f, "Browse…", browse, fg=C.ACC, bg=C.SURF, hover=C.SURF3).pack(side="left", padx=4)
            flat_btn(f, "Open", open_dir, fg=C.TXT2, bg=C.SURF, hover=C.SURF3).pack(side="left")
            return f
        row("Data folder", dir_widget)
        move_var = tk.BooleanVar(value=True)
        row("", lambda r: checkbox(r, "copy existing files when the folder changes", move_var),
            "e.g. a OneDrive / Dropbox folder to sync")
        keep_var = tk.StringVar(value=str(s.get("backups_keep", 15)))
        row("Backups to keep", lambda r: entry(r, keep_var, width=80, height=30))
        int_var = tk.StringVar(value=str(s.get("backup_interval_min", 10)))
        row("Backup interval (min)", lambda r: entry(r, int_var, width=80, height=30),
            "a backup is written at most this often")

        def tools(r):
            f = tk.Frame(r, bg=C.SURF)
            flat_btn(f, "Backup now", lambda: self._toast("Backup written" if s.maybe_backup(force=True) else "Nothing to back up"),
                     fg=C.ACC, bg=C.SURF, hover=C.SURF3).pack(side="left", padx=2)
            flat_btn(f, "Restore backup…", lambda: (ov.close(), self._open_backups()),
                     fg=C.TXT2, bg=C.SURF, hover=C.SURF3).pack(side="left", padx=2)
            flat_btn(f, "Trash…", lambda: (ov.close(), self._open_trash()),
                     fg=C.TXT2, bg=C.SURF, hover=C.SURF3).pack(side="left", padx=2)
            flat_btn(f, "Find duplicates…", lambda: (ov.close(), self._open_duplicates()),
                     fg=C.TXT2, bg=C.SURF, hover=C.SURF3).pack(side="left", padx=2)
            return f
        row("Tools", tools)

        # SD (lokaler Bild-Server, optional)
        section("Local image backend (Automatic1111 / ComfyUI on this PC)")
        be_var = tk.StringVar(value=s.get("sd.backend", "a1111"))
        row("Backend", lambda r: option_menu(r, ["a1111", "comfy"], be_var, width=140))
        url_var = tk.StringVar(value=s.get("sd.url", ""))
        row("URL", lambda r: entry(r, url_var, width=360, height=30), "empty = disabled")
        wf_var = tk.StringVar(value=s.get("sd.workflow", ""))

        def wf_widget(r):
            f = tk.Frame(r, bg=C.SURF)
            entry(f, wf_var, width=360, height=30).pack(side="left")
            flat_btn(f, "Browse…", lambda: wf_var.set(filedialog.askopenfilename(
                parent=self, title="ComfyUI API workflow", filetypes=[("JSON", "*.json")]) or wf_var.get()),
                fg=C.ACC, bg=C.SURF, hover=C.SURF3).pack(side="left", padx=4)
            return f
        row("ComfyUI workflow", wf_widget, "API-format JSON with %PROMPT% / %NEGATIVE%")
        steps_var = tk.StringVar(value=str(s.get("sd.steps", 25)))
        w_var = tk.StringVar(value=str(s.get("sd.width", 832)))
        h_var = tk.StringVar(value=str(s.get("sd.height", 1216)))

        def dims(r):
            f = tk.Frame(r, bg=C.SURF)
            for lab, v in (("steps", steps_var), ("W", w_var), ("H", h_var)):
                tk.Label(f, text=lab, fg=C.TXT3, bg=C.SURF, font=F(9)).pack(side="left", padx=(0, 3))
                entry(f, v, width=70, height=30).pack(side="left", padx=(0, 10))
            return f
        row("A1111 params", dims)
        out_var = tk.BooleanVar(value=bool(s.get("sd.save_output", True)))
        row("Save A1111 images", lambda r: checkbox(r, "into data folder / outputs", out_var))
        test_lbl = tk.Label(b, text="", fg=C.TXT2, bg=C.SURF, font=F(9))

        def test():
            test_lbl.configure(text="testing…", fg=C.TXT2)
            self._sd_test(be_var.get(), url_var.get().strip(),
                          lambda msg, ok: test_lbl.configure(text=msg, fg=C.GREEN if ok else C.RED))
        row("", lambda r: flat_btn(r, "Test connection", test, fg=C.ACC, bg=C.SURF, hover=C.SURF3))
        test_lbl.pack(anchor="w", padx=(4, 0))

        # Tray & hotkey
        section("Background mode")
        tray_var = tk.BooleanVar(value=bool(s.get("tray", False)))
        row("Minimize to tray on close", lambda r: checkbox(r, "", tray_var),
            "" if self._tray_available() else "pip install pystray pillow")
        hk_var = tk.StringVar(value=s.get("hotkey", "ctrl+alt+r"))
        row("Global hotkey", lambda r: entry(r, hk_var, width=200, height=30),
            "rolls the Builder and copies the result (Windows)")

        def save():
            old_theme = (s.get("theme"), s.get("accent"), float(s.get("font_scale", 1.0)))
            old_dir = s.data_dir
            old_tray, old_hk = s.get("tray"), s.get("hotkey")
            s.settings["theme"] = theme_var.get()
            s.settings["accent"] = accent_var.get()
            s.settings["font_scale"] = round(float(fs_var.get()), 2)
            s.settings["show_thumbnails"] = thumbs_var.get()
            s.settings["default_sep"] = sep_var.get() or ", "
            try:
                s.settings["random_count"] = max(1, int(rnd_var.get()))
            except ValueError:
                pass
            s.settings["confirm_delete"] = conf_var.get()
            s.settings["remember_window"] = rem_var.get()
            try:
                s.settings["backups_keep"] = max(1, int(keep_var.get()))
                s.settings["backup_interval_min"] = max(0, int(int_var.get()))
            except ValueError:
                pass
            s.settings.pop("ai", None)
            s.settings["sd"]["backend"] = be_var.get()
            s.settings["sd"]["url"] = url_var.get().strip().rstrip("/")
            s.settings["sd"]["workflow"] = wf_var.get().strip()
            for k, v in (("steps", steps_var), ("width", w_var), ("height", h_var)):
                try:
                    s.settings["sd"][k] = int(v.get())
                except ValueError:
                    pass
            s.settings["sd"]["save_output"] = out_var.get()
            s.settings["tray"] = tray_var.get()
            s.settings["hotkey"] = hk_var.get().strip()
            s.save_settings()
            ov.close()

            new_dir = dir_var.get().strip()
            if new_dir and os.path.abspath(new_dir) != os.path.abspath(old_dir):
                try:
                    s.set_data_dir(new_dir, move_files=move_var.get())
                except OSError as e:
                    messagebox.showerror("Data folder", f"Could not switch folder:\n{e}", parent=self)
                    s.set_data_dir(old_dir)
                else:
                    self._reload_all()
                    self._toast(f"Data folder: {new_dir}")

            if (theme_var.get(), accent_var.get(), s.settings["font_scale"]) != old_theme:
                self._rebuild_ui()
            else:
                self._update_result()
            if (tray_var.get(), hk_var.get()) != (old_tray, old_hk):
                self._apply_background_settings()
            self._toast("Settings saved")

        def reset():
            if messagebox.askyesno("Reset", "Reset all settings to defaults?", parent=self):
                s.settings = json.loads(json.dumps(DEFAULT_SETTINGS))
                s.save_settings()
                ov.close()
                self._rebuild_ui()
        ov.buttons(("Save", save, "neon"), ("Cancel", ov.close, "ghost"), ("Reset defaults", reset, "ghost"))

    # ═══════════════════════════════════════════════════════════════
    # DUPLIKATE
    # ═══════════════════════════════════════════════════════════════

    def _open_duplicates(self):
        groups = {}
        for cat, lst in self.data.items():
            for p in lst:
                key = re.sub(r"\s+", " ", p["text"].strip().lower())
                groups.setdefault(key, []).append((cat, p))
        dups = [g for g in groups.values() if len(g) > 1]
        total = sum(len(g) - 1 for g in dups)
        ov = Overlay(self, 880, 640, title="Duplicate Finder",
                     hint=f"{len(dups)} groups · {total} redundant" if dups else "no duplicates 🎉")
        lst = ScrollFrame(ov.body, bg=C.BG)
        lst.pack(fill="both", expand=True)

        def render():
            lst.clear()
            live = []
            for g in dups:
                g2 = [(c, p) for c, p in g if any(x["id"] == p["id"] for x in self.data.get(c, []))]
                if len(g2) > 1:
                    live.append(g2)
            dups[:] = live
            ov.title_lbl.configure(text="Duplicate Finder")
            if not live:
                tk.Label(lst.inner, text="No duplicates.", fg=C.TXT2, bg=C.BG, font=F(13)).pack(pady=50)
                return
            for g in live:
                box = tk.Frame(lst.inner, bg=C.SURF2, highlightbackground=C.BORDER, highlightthickness=1)
                box.pack(fill="x", padx=4, pady=4)
                tk.Label(box, text=g[0][1]["text"], fg=C.TXT, bg=C.SURF2, font=F(11, mono=True), wraplength=px(780),
                         justify="left", anchor="w").pack(fill="x", padx=10, pady=(6, 2))
                for cat, p in g:
                    r = tk.Frame(box, bg=C.SURF2)
                    r.pack(fill="x", padx=10, pady=1)
                    chip(r, cat).pack(side="left")
                    tk.Label(r, text="  ★" if p.get("fav") else "", fg=C.GOLD, bg=C.SURF2, font=F(10)).pack(side="left")
                    tk.Label(r, text=f"  used {p.get('uses', 0)}×  ·  {len(p.get('tags', []))} tags",
                             fg=C.TXT2, bg=C.SURF2, font=F(9)).pack(side="left")
                    flat_btn(r, "Delete", lambda i=p["id"]: (self._del_prompts([i], confirm=False), render()),
                             fg=C.RED, hover=C.RED_DIM).pack(side="right", pady=2)
                tk.Frame(box, height=4, bg=C.SURF2).pack()
                lst.bind_children_wheel(box)

        def auto_clean():
            ids = []
            for g in dups:
                # den behalten, der Favorit ist / am meisten genutzt / zuerst kommt
                keep = max(g, key=lambda cp: (bool(cp[1].get("fav")), cp[1].get("uses", 0),
                                             len(cp[1].get("tags", [])), -g.index(cp)))
                ids += [p["id"] for _, p in g if p is not keep[1]]
            if ids and messagebox.askyesno("Auto-clean", f"Delete {len(ids)} duplicates (keeps starred / most used)?",
                                           parent=self):
                self._del_prompts(ids, confirm=False)
                render()
        render()
        ov.buttons(("Close", ov.close, "ghost"), ("Auto-clean", auto_clean, "red"))

    # ═══════════════════════════════════════════════════════════════
    # PAPIERKORB
    # ═══════════════════════════════════════════════════════════════

    def _open_trash(self):
        ov = Overlay(self, 860, 620, title=f"Trash  —  {len(self._trash)} items")
        lst = ScrollFrame(ov.body, bg=C.BG)
        lst.pack(fill="both", expand=True)

        def restore(e):
            cat = e["cat"] if e["cat"] in self.data else (self.selected or (self.categories[0] if self.categories else None))
            if cat is None:
                self.data[e["cat"]] = []
                cat = e["cat"]
                self._render_cats()
            p = normalize_prompt(e["prompt"])
            if any(x["id"] == p["id"] for x in self.data[cat]):
                p["id"] = make_prompt("x")["id"]
            self.data[cat].append(p)
            self._trash.remove(e)
            self._trash = self.store.save_trash(self._trash)
            self._save()
            self._refresh()
            render()
            self._toast(f'Restored to "{cat}"')

        def render():
            lst.clear()
            ov.title_lbl.configure(text=f"Trash  —  {len(self._trash)} items")
            if not self._trash:
                tk.Label(lst.inner, text="Trash is empty.", fg=C.TXT2, bg=C.BG, font=F(13)).pack(pady=50)
            for e in self._trash:
                c = tk.Frame(lst.inner, bg=C.SURF2, highlightbackground=C.BORDER, highlightthickness=1)
                c.pack(fill="x", padx=4, pady=3)
                h = tk.Frame(c, bg=C.SURF2)
                h.pack(fill="x", padx=10, pady=(6, 2))
                chip(h, e["cat"]).pack(side="left")
                tk.Label(h, text="  " + fmt_ts(e.get("deleted")), fg=C.TXT2, bg=C.SURF2, font=F(9)).pack(side="left")
                flat_btn(h, "Restore", lambda x=e: restore(x), fg=C.ACC, hover_fg=C.ACC).pack(side="right", padx=2)
                flat_btn(h, "✕", lambda x=e: (self._trash.remove(x), self.store.save_trash(self._trash), render()),
                         fg=C.RED, hover=C.RED_DIM).pack(side="right", padx=2)
                tk.Label(c, text=e["prompt"].get("text", ""), fg=C.TXT, bg=C.SURF2, font=F(11, mono=True),
                         wraplength=px(760), justify="left", anchor="w").pack(fill="x", padx=10, pady=(2, 6))
                lst.bind_children_wheel(c)
        render()

        def empty():
            if self._trash and messagebox.askyesno("Trash", "Empty trash permanently?", parent=self):
                self._trash = []
                self.store.save_trash([])
                render()
        ov.buttons(("Close", ov.close, "ghost"), ("Empty trash", empty, "red"))

    # ═══════════════════════════════════════════════════════════════
    # BACKUPS
    # ═══════════════════════════════════════════════════════════════

    def _open_backups(self):
        backups = self.store.list_backups()
        ov = Overlay(self, 760, 560, title="Restore Backup", hint=self.store.backup_dir)
        lst = ScrollFrame(ov.body, bg=C.BG)
        lst.pack(fill="both", expand=True)
        if not backups:
            tk.Label(lst.inner, text="No backups yet.", fg=C.TXT2, bg=C.BG, font=F(13)).pack(pady=50)
        import datetime as dt
        for path, mtime in backups:
            try:
                data = self.store.read_backup(path)
            except Exception:
                data = None
            n = sum(len(v) for v in data.values()) if data else 0
            c = tk.Frame(lst.inner, bg=C.SURF2, highlightbackground=C.BORDER, highlightthickness=1)
            c.pack(fill="x", padx=4, pady=3)
            when = dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            tk.Label(c, text=when, fg=C.TXT, bg=C.SURF2, font=F(11, bold=True)).pack(side="left", padx=10, pady=8)
            tk.Label(c, text=f"{n} prompts · {len(data) if data else 0} categories · {os.path.basename(path)}"
                     if data else "unreadable", fg=C.TXT2, bg=C.SURF2, font=F(10)).pack(side="left")

            def do_restore(p=path, d=data):
                if not d:
                    return
                if not messagebox.askyesno("Restore", "Replace current prompts with this backup?\n"
                                                      "(a backup of the current state is written first)", parent=self):
                    return
                self.store.maybe_backup(force=True)
                self.data = d
                self._save()
                self._render_cats()
                self._select(self.categories[0] if self.categories else None)
                ov.close()
                self._toast("Backup restored")
            flat_btn(c, "Restore", do_restore, fg=C.ACC, hover_fg=C.ACC).pack(side="right", padx=10)
            lst.bind_children_wheel(c)
        ov.buttons(("Close", ov.close, "ghost"),
                   ("Backup now", lambda: (self.store.maybe_backup(force=True), ov.close(), self._open_backups()), "neon"))

    # ═══════════════════════════════════════════════════════════════
    # EXPORT / IMPORT
    # ═══════════════════════════════════════════════════════════════

    def _export_menu(self):
        m = styled_menu(self)
        m.add_command(label="Full backup (.json — prompts, templates, rules, history)", command=self._export_full)
        m.add_command(label="Prompts only, plain (.json — {category: [text]})", command=self._export_plain)
        m.add_command(label="CSV (category, text, tags, title, note)", command=self._export_csv)
        m.add_separator()
        m.add_command(label="Wildcards — one .txt per category…", command=self._export_wildcards)
        if self.selected:
            m.add_command(label=f'Wildcard "{self.selected}" only (.txt)', command=lambda: self._export_wildcards([self.selected]))
        m.tk_popup(*self.winfo_pointerxy())

    def _export_full(self):
        path = filedialog.asksaveasfilename(parent=self, title="Export everything", defaultextension=".json",
                                            initialfile="promptvault_backup.json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        bundle = self.store.export_bundle(self.data, self.store.load_templates(), self._rules, self._history)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showerror("Export", f"Could not write file:\n{e}", parent=self)
            return
        self._toast(f"Exported {sum(len(v) for v in self.data.values())} prompts + templates")

    def _export_plain(self):
        path = filedialog.asksaveasfilename(parent=self, title="Export prompts", defaultextension=".json",
                                            initialfile="promptvault_export.json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.store.export_plain(self.data), f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showerror("Export", f"Could not write file:\n{e}", parent=self)
            return
        self._toast("Exported")

    def _export_csv(self):
        import csv
        path = filedialog.asksaveasfilename(parent=self, title="Export CSV", defaultextension=".csv",
                                            initialfile="promptvault.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["category", "text", "tags", "title", "note", "weight", "fav", "uses"])
                for cat, lst in self.data.items():
                    for p in lst:
                        w.writerow([cat, p["text"], ", ".join(p.get("tags", [])), p.get("title", ""),
                                    p.get("note", ""), p.get("weight", 5), int(bool(p.get("fav"))), p.get("uses", 0)])
        except OSError as e:
            messagebox.showerror("Export", f"Could not write file:\n{e}", parent=self)
            return
        self._toast("CSV exported")

    def _export_wildcards(self, cats=None):
        cats = cats or self.categories
        if not cats:
            return
        if len(cats) == 1:
            path = filedialog.asksaveasfilename(parent=self, title="Export wildcard", defaultextension=".txt",
                                                initialfile=safe_filename(cats[0]) + ".txt",
                                                filetypes=[("Text", "*.txt")])
            if not path:
                return
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.store.wildcard_text(self.data[cats[0]]))
            self._toast(f"Wildcard written: {os.path.basename(path)}")
            return
        folder = filedialog.askdirectory(parent=self, title="Folder for wildcard files (e.g. …/wildcards)")
        if not folder:
            return
        n = 0
        for cat in cats:
            lst = self.data.get(cat, [])
            if not lst:
                continue
            with open(os.path.join(folder, safe_filename(cat) + ".txt"), "w", encoding="utf-8") as f:
                f.write(self.store.wildcard_text(lst))
            n += 1
        self._toast(f"{n} wildcard files written")

    def _import_data(self):
        path = filedialog.askopenfilename(
            parent=self, title="Import prompts",
            filetypes=[("Supported", "*.json *.txt *.csv"), ("JSON", "*.json"), ("Text", "*.txt"),
                       ("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                raw_text = f.read()
        except (OSError, UnicodeDecodeError):
            messagebox.showerror("Import", "Could not read this file.", parent=self)
            return

        incoming = {}
        templates = None
        rules = None
        if ext == ".json" or raw_text.lstrip().startswith(("{", "[")):
            try:
                raw = json.loads(raw_text)
            except json.JSONDecodeError:
                messagebox.showerror("Import", "Could not parse this file as JSON.", parent=self)
                return
            if isinstance(raw, list):
                cat = self.selected or self._ask_import_category()
                if not cat:
                    return
                incoming = {cat: [normalize_prompt(p) for p in raw if isinstance(p, (str, dict))]}
            elif isinstance(raw, dict) and raw.get("version") == 2 and "categories" in raw:
                incoming = {c: [normalize_prompt(p) for p in lst if isinstance(p, (str, dict))]
                            for c, lst in raw["categories"].items() if isinstance(lst, list)}
                templates = raw.get("templates") if isinstance(raw.get("templates"), dict) else None
                rules = raw.get("rules") if isinstance(raw.get("rules"), list) else None
            elif isinstance(raw, dict):
                incoming = {c: [normalize_prompt(p) for p in lst if isinstance(p, (str, dict))]
                            for c, lst in raw.items() if isinstance(c, str) and isinstance(lst, list)}
            else:
                messagebox.showerror("Import", "Invalid format.", parent=self)
                return
        else:
            cat = self.selected or self._ask_import_category()
            if not cat:
                return
            incoming = self.store.parse_import_text(raw_text, cat)

        new_cats = added = skipped = 0
        for cat, prompts in incoming.items():
            if cat not in self.data:
                self.data[cat] = []
                new_cats += 1
            for p in prompts:
                if not p["text"]:
                    continue
                if self._is_dup(cat, p["text"]):
                    skipped += 1
                    continue
                if any(x["id"] == p["id"] for lst in self.data.values() for x in lst):
                    p["id"] = make_prompt("x")["id"]
                self.data[cat].append(p)
                added += 1
        tpl_n = 0
        if templates:
            cur = self.store.load_templates()
            for name, t in templates.items():
                if name not in cur:
                    cur[name] = t
                    tpl_n += 1
            self.store.save_templates(cur)
        if rules:
            for r in rules:
                if r not in self._rules:
                    self._rules.append(r)
        self._save()
        self._render_cats()
        if self.selected is None and self.categories:
            self._select(self.categories[0])
        else:
            self._refresh()
        msg = (f"{added} prompt{'s' if added != 1 else ''} added\n"
               f"{skipped} duplicate{'s' if skipped != 1 else ''} skipped\n"
               f"{new_cats} new categor{'ies' if new_cats != 1 else 'y'}")
        if tpl_n:
            msg += f"\n{tpl_n} template{'s' if tpl_n != 1 else ''} added"
        messagebox.showinfo("Import", msg, parent=self)

    def _ask_import_category(self):
        """Blockierender Namensdialog; None bei Abbruch."""
        result = {"name": None}
        done = tk.BooleanVar(value=False)
        ov = Overlay(self, 460, 190, title="Import into category", on_close=lambda: done.set(True))
        name_var = tk.StringVar(value=self.categories[0] if self.categories else "")
        e = entry(ov.body, name_var, width=400, height=36)
        e.pack(fill="x")

        def ok(_=None):
            if name_var.get().strip():
                result["name"] = name_var.get().strip()
                ov.close()
        ov.buttons(("Import", ok, "neon"), ("Cancel", ov.close, "ghost"))
        e.bind("<Return>", ok)
        e.focus_set()
        self.wait_variable(done)
        return result["name"]

    # ═══════════════════════════════════════════════════════════════
    # HILFE
    # ═══════════════════════════════════════════════════════════════

    def _open_shortcuts(self):
        ov = Overlay(self, 520, 560, title="Keyboard Shortcuts")
        for key, desc in SHORTCUTS:
            r = tk.Frame(ov.body, bg=C.SURF)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=key, fg=C.ACC, bg=C.SURF2, font=F(10, bold=True, mono=True), width=16,
                     anchor="w", padx=8, pady=3).pack(side="left")
            tk.Label(r, text=desc, fg=C.TXT, bg=C.SURF, font=F(11)).pack(side="left", padx=12)
        ov.buttons(("Close", ov.close, "ghost"))

    def _open_stats(self):
        total = sum(len(v) for v in self.data.values())
        favs = sum(1 for v in self.data.values() for p in v if p.get("fav"))
        tags = {t for v in self.data.values() for p in v for t in p.get("tags", [])}
        used = sorted((p for v in self.data.values() for p in v if p.get("uses")),
                      key=lambda p: -p.get("uses", 0))[:10]
        ov = Overlay(self, 680, 560, title="Statistics")
        info = (f"{len(self.data)} categories · {total} prompts · {favs} favorites · {len(tags)} tags\n"
                f"{len(self._history)} history entries · {len(self._trash)} in trash · "
                f"{len(self.store.list_backups())} backups")
        tk.Label(ov.body, text=info, fg=C.TXT, bg=C.SURF, font=F(11), justify="left").pack(anchor="w")
        tk.Label(ov.body, text="MOST USED", fg=C.TXT3, bg=C.SURF, font=F(9, bold=True)).pack(anchor="w", pady=(14, 4))
        for p in used:
            r = tk.Frame(ov.body, bg=C.SURF2, highlightbackground=C.BORDER, highlightthickness=1)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=f"{p.get('uses', 0)}×", fg=C.ACC, bg=C.SURF2, font=F(10, bold=True), width=5).pack(side="left", padx=6)
            tk.Label(r, text=p["text"][:90], fg=C.TXT, bg=C.SURF2, font=F(10, mono=True), anchor="w").pack(side="left", pady=4)
        if not used:
            tk.Label(ov.body, text="Nothing copied yet.", fg=C.TXT2, bg=C.SURF, font=F(11)).pack(anchor="w")
        ov.buttons(("Close", ov.close, "ghost"))
