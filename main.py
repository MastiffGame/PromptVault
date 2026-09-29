"""PromptVault — Desktop-App zum Verwalten von Bild-Prompts.

Einstieg: python main.py
"""

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from storage import Store, DEFAULT_CATEGORIES, now_iso
from theme import C, F, px
from widgets import ghost_btn, styled_menu, Tooltip, flat_btn
from library import LibraryMixin
from builder import BuilderMixin
from dialogs import DialogsMixin
from integrations import IntegrationsMixin

ctk.set_default_color_theme("blue")

CAT_SORTS = [("manual", "Manual (drag to sort)"), ("alpha", "A → Z"), ("count", "Most prompts")]


# ─── Kategorie-Zeile ──────────────────────────────────────────────────────────

class CategoryRow(tk.Frame):
    """Kategorie-Schaltfläche mit Klick, Rechtsklick und Drag-Sortierung."""

    def __init__(self, parent, label, count, command, selected=False, on_menu=None, on_drag=None):
        super().__init__(parent, bg=C.SURF, height=px(38), cursor="hand2")
        self.pack_propagate(False)
        self._cmd = command
        self._on_drag = on_drag
        self._selected = selected
        self._press = None
        self._dragging = False

        self._bar = tk.Frame(self, width=px(3), bg=C.ACC if selected else C.SURF)
        self._bar.pack(side="left", fill="y", padx=(4, 0), pady=6)
        self._lbl = tk.Label(self, text=f"  {label}", anchor="w",
                             bg=C.SURF3 if selected else C.SURF,
                             fg=C.ACC if selected else C.TXT, font=F(12), cursor="hand2")
        self._lbl.pack(side="left", fill="both", expand=True, pady=3, padx=4)
        self._badge = tk.Label(self, text=str(count),
                               bg=C.ACC_DIM if selected else C.SURF3,
                               fg=C.ACC if selected else C.TXT2,
                               font=F(9, bold=True), padx=6, pady=2, relief="flat", cursor="hand2")
        self._badge.pack(side="right", padx=(0, 8), pady=8)

        for w in (self, self._lbl, self._badge):
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<B1-Motion>", self._on_motion)
            w.bind("<ButtonRelease-1>", self._on_release)
            if on_menu:
                w.bind("<Button-3>", on_menu)

    def _on_press(self, e):
        self._press = e.y_root
        self._dragging = False

    def _on_motion(self, e):
        if self._press is not None and self._on_drag and abs(e.y_root - self._press) > 8:
            if not self._dragging:
                self._dragging = True
                self.configure(cursor="fleur")

    def _on_release(self, e):
        if self._dragging:
            self.configure(cursor="hand2")
            self._on_drag(self, e.y_root)
        elif self._press is not None:
            self._cmd()
        self._press = None
        self._dragging = False

    def set_selected(self, v):
        self._selected = v
        self._bar.configure(bg=C.ACC if v else C.SURF)
        self._lbl.configure(bg=C.SURF3 if v else C.SURF, fg=C.ACC if v else C.TXT)
        self._badge.configure(bg=C.ACC_DIM if v else C.SURF3, fg=C.ACC if v else C.TXT2)

    def set_hover(self, v):
        if not self._selected:
            self._lbl.configure(bg=C.SEL if v else C.SURF)

    def update_count(self, count):
        self._badge.configure(text=str(count))


# ─── Hauptanwendung ───────────────────────────────────────────────────────────

class PromptVaultApp(LibraryMixin, BuilderMixin, DialogsMixin, IntegrationsMixin, ctk.CTk):

    def __init__(self):
        self.store = Store()
        C.apply(self.store.get("theme", "dark"), self.store.get("accent", "cyan"),
                self.store.get("font_scale", 1.0))
        super().__init__()
        try:
            C.dpi = float(ctk.ScalingTracker.get_widget_scaling(self))
        except Exception:
            C.dpi = 1.0
        self.title("PromptVault")
        self.minsize(960, 580)
        geo = self.store.get("geometry") if self.store.get("remember_window", True) else ""
        self.geometry(geo or "1260x740")
        if geo and self.store.get("zoomed"):
            try:
                self.state("zoomed")
            except tk.TclError:
                pass
        self.configure(fg_color=C.BG)

        # ── Zustand ──────────────────────────────────────────────
        self._overlay = None
        self._tray = None
        self._hotkey_stop = None
        self._hotkey_tid = None
        self._init_queue()

        self.data = self._load_data_safely()
        self.selected = None
        self._cat_rows = {}
        self._search_job = None
        self._render_job = None
        self._state_job = None
        self._render_queue = []
        self._visible_cache = []
        self._selection = set()
        self._tag_filter = set()
        self._fav_filter = False
        self._active_view = "library"
        self._tab_btns = {}
        self._undo_stack = []
        self._trash = self.store.load_trash()
        self._history = self.store.load_history()
        self._slots, self._rules, self._active_template = [], [], None
        self._toast_lbl = None
        self._toast_job = None
        self._pending_state = self._restore_builder_state()

        self._build_ui()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._apply_background_settings()
        if self.store.load_error:
            self.after(300, self._offer_recovery)

    # ═══════════════════════════════════════════════════════════════
    # LADEN / AUFBAU
    # ═══════════════════════════════════════════════════════════════

    def _load_data_safely(self):
        data = self.store.load_data()
        if data is None:
            return {cat: [] for cat in DEFAULT_CATEGORIES}
        return data

    def _offer_recovery(self):
        backups = self.store.list_backups()
        msg = (f"prompts.json could not be read:\n{self.store.load_error}\n\n"
               "The broken file was kept as prompts.json.corrupt.*")
        if backups:
            if messagebox.askyesno("Data error", msg + "\n\nRestore the latest backup now?", parent=self):
                self._open_backups()
                return
        else:
            messagebox.showwarning("Data error", msg + "\n\nStarting with empty categories.", parent=self)
        self._save()

    def _build_ui(self):
        self._build_sidebar()
        self._main = tk.Frame(self, bg=C.BG)
        self._main.pack(side="left", fill="both", expand=True)
        self._build_content()
        self._build_builder()
        if self._pending_state:
            st = self._pending_state
            if st.get("sep"):
                self._sep_var.set(st["sep"])
            self._wild_var.set(bool(st.get("wildcard")))
            self._pending_state = None
            self._render_slots()
        if self.selected in self.data:
            self._select(self.selected)
        elif self.categories:
            self._select(self.categories[0])
        if self._active_view == "builder":
            self._active_view = "library"
            self._switch_view("builder")

    def _rebuild_ui(self):
        """Nach Theme-/Schriftwechsel alles neu aufbauen."""
        C.apply(self.store.get("theme", "dark"), self.store.get("accent", "cyan"),
                self.store.get("font_scale", 1.0))
        self._overlay = None
        self._toast_lbl = None
        for w in self.winfo_children():
            w.destroy()
        self.configure(fg_color=C.BG)
        self._cat_rows = {}
        self._tab_btns = {}
        self._pending_state = {"sep": self._sep_var.get(), "wildcard": self._wild_var.get()}
        self._build_ui()

    def _reload_all(self):
        """Nach Wechsel des Datenordners alles neu laden."""
        self.data = self._load_data_safely()
        self._trash = self.store.load_trash()
        self._history = self.store.load_history()
        self._restore_builder_state()
        self.selected = None
        self._render_cats()
        self._render_slots()
        self._select(self.categories[0] if self.categories else None)

    @property
    def categories(self):
        return list(self.data.keys())

    def _sorted_categories(self):
        mode = self.store.get("cat_sort", "manual")
        cats = self.categories
        if mode == "alpha":
            return sorted(cats, key=str.lower)
        if mode == "count":
            return sorted(cats, key=lambda c: -len(self.data.get(c, [])))
        return cats

    # ═══════════════════════════════════════════════════════════════
    # SIDEBAR
    # ═══════════════════════════════════════════════════════════════

    def _build_sidebar(self):
        sb = tk.Frame(self, bg=C.SURF, width=px(240))
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        self._sb = sb
        tk.Frame(sb, width=1, bg=C.BORDER).place(relx=1, rely=0, relheight=1, anchor="ne")

        logo = tk.Frame(sb, bg=C.SURF, height=px(80))
        logo.pack(side="top", fill="x")
        logo.pack_propagate(False)
        word = tk.Frame(logo, bg=C.SURF)
        word.place(x=px(16), y=px(16))
        tk.Label(word, text="PROMPT", fg=C.ACC, bg=C.SURF, font=F(18, bold=True)).pack(side="left")
        tk.Label(word, text="VAULT", fg=C.PURP, bg=C.SURF, font=F(18, bold=True)).pack(side="left")
        tk.Label(logo, text="Image Generation", fg=C.TXT2, bg=C.SURF, font=F(9)).place(x=px(18), y=px(50))
        icons = tk.Frame(logo, bg=C.SURF)
        icons.place(relx=1, y=px(12), x=-px(12), anchor="ne")
        gear = tk.Label(icons, text="⚙", fg=C.TXT2, bg=C.SURF, font=F(14), cursor="hand2")
        gear.pack(side="top")
        gear.bind("<Button-1>", lambda _: self._open_settings())
        Tooltip(gear, "Settings  (Ctrl+,)")
        help_l = tk.Label(icons, text="?", fg=C.TXT2, bg=C.SURF, font=F(12, bold=True), cursor="hand2")
        help_l.pack(side="top")
        help_l.bind("<Button-1>", lambda _: self._open_shortcuts())
        Tooltip(help_l, "Shortcuts  (F1)")
        tk.Frame(logo, height=1, bg=C.BORDER).place(x=px(14), rely=1, relwidth=1, width=-px(28), anchor="sw")

        tabs = tk.Frame(sb, bg=C.SURF)
        tabs.pack(side="top", fill="x", padx=12, pady=(10, 2))
        for name, label in (("library", "Library"), ("builder", "Builder")):
            active = name == self._active_view
            btn = tk.Label(tabs, text=label, cursor="hand2",
                           fg=C.ACC if active else C.TXT2, bg=C.SURF3 if active else C.SURF,
                           font=F(11, bold=True), pady=6,
                           highlightbackground=C.BORD_H, highlightthickness=1)
            btn.pack(side="left", fill="x", expand=True, padx=2)
            btn.bind("<Button-1>", lambda _, n=name: self._switch_view(n))
            self._tab_btns[name] = btn

        head = tk.Frame(sb, bg=C.SURF)
        head.pack(side="top", fill="x", padx=18, pady=(10, 4))
        tk.Label(head, text="CATEGORIES", fg=C.TXT3, bg=C.SURF, font=F(9, bold=True)).pack(side="left")
        sort_l = tk.Label(head, text="⇅", fg=C.TXT2, bg=C.SURF, font=F(11), cursor="hand2")
        sort_l.pack(side="right")
        sort_l.bind("<Button-1>", self._cat_sort_menu)
        Tooltip(sort_l, "Sort categories")
        stats_l = tk.Label(head, text="Σ", fg=C.TXT2, bg=C.SURF, font=F(10), cursor="hand2")
        stats_l.pack(side="right", padx=(0, 8))
        stats_l.bind("<Button-1>", lambda _: self._open_stats())
        Tooltip(stats_l, "Statistics")

        ghost_btn(sb, "+ New Category", self._add_category, color=C.ACC, width=200, height=32,
                  font_size=12).pack(side="bottom", fill="x", padx=12, pady=(6, 12))
        io = tk.Frame(sb, bg=C.SURF)
        io.pack(side="bottom", fill="x", padx=12)
        ghost_btn(io, "Import", self._import_data, width=100, height=28, font_size=11).pack(
            side="left", fill="x", expand=True, padx=(0, 3))
        ghost_btn(io, "Export", self._export_menu, width=100, height=28, font_size=11).pack(
            side="left", fill="x", expand=True, padx=(3, 0))
        tools = tk.Frame(sb, bg=C.SURF)
        tools.pack(side="bottom", fill="x", padx=12, pady=(0, 4))
        for label, cmd, tip in (("🗑", self._open_trash, "Trash (Ctrl+T)"),
                                ("⧉", self._open_duplicates, "Find duplicates (Ctrl+D)"),
                                ("⟲", self._open_backups, "Backups")):
            b = flat_btn(tools, label, cmd, fg=C.TXT2, bg=C.SURF, hover=C.SURF3)
            b.pack(side="left", fill="x", expand=True, padx=2)
            Tooltip(b, tip)

        self._cat_canvas = tk.Canvas(sb, bg=C.SURF, highlightthickness=0)
        self._cat_canvas.pack(side="top", fill="both", expand=True)
        self._cat_inner = tk.Frame(self._cat_canvas, bg=C.SURF)
        self._cat_win = self._cat_canvas.create_window(0, 0, window=self._cat_inner, anchor="nw")
        self._cat_inner.bind("<Configure>",
                             lambda e: self._cat_canvas.configure(scrollregion=self._cat_canvas.bbox("all")))
        self._cat_canvas.bind("<Configure>", lambda e: self._cat_canvas.itemconfig(self._cat_win, width=e.width))

        def _sb_scroll(e):
            if self._cat_inner.winfo_height() > self._cat_canvas.winfo_height():
                self._cat_canvas.yview_scroll(int(-1 * e.delta / 120), "units")
        sb.bind("<Enter>", lambda _: self._cat_canvas.bind_all("<MouseWheel>", _sb_scroll))
        sb.bind("<Leave>", lambda _: self._cat_canvas.unbind_all("<MouseWheel>"))
        self._render_cats()

    def _render_cats(self):
        for w in self._cat_inner.winfo_children():
            w.destroy()
        self._cat_rows.clear()
        manual = self.store.get("cat_sort", "manual") == "manual"
        for cat in self._sorted_categories():
            row = CategoryRow(self._cat_inner, cat, len(self.data.get(cat, [])),
                              command=lambda c=cat: (self._switch_view("library"), self._select(c)),
                              selected=cat == self.selected,
                              on_menu=lambda e, c=cat: self._cat_menu(e, c),
                              on_drag=self._on_cat_drag if manual else None)
            row.pack(fill="x", padx=6, pady=2)
            self._cat_rows[cat] = row

    def _on_cat_drag(self, row, y_root):
        src = next((c for c, r in self._cat_rows.items() if r is row), None)
        dst = None
        for c, r in self._cat_rows.items():
            top = r.winfo_rooty()
            if top <= y_root <= top + r.winfo_height():
                dst = c
                break
        if src is None or dst is None or src == dst:
            return
        cats = self.categories
        cats.remove(src)
        cats.insert(cats.index(dst) if cats.index(dst) >= 0 else 0, src)
        # dst-Index nach Entfernen von src bestimmen
        self.data = {c: self.data[c] for c in cats}
        self._save()
        self._render_cats()

    def _cat_sort_menu(self, event=None):
        m = styled_menu(self)
        cur = self.store.get("cat_sort", "manual")
        for key, label in CAT_SORTS:
            m.add_command(label=("●  " if key == cur else "    ") + label,
                          command=lambda k=key: (self.store.set("cat_sort", k), self._render_cats()))
        m.tk_popup(*self.winfo_pointerxy())

    def _cat_menu(self, event, cat):
        menu = styled_menu(self)
        menu.add_command(label=f"Rename \"{cat}\"", command=lambda: self._rename_category(cat))
        menu.add_command(label="Move up", command=lambda: self._move_category(cat, -1))
        menu.add_command(label="Move down", command=lambda: self._move_category(cat, 1))
        menu.add_separator()
        menu.add_command(label="Add to Builder as slot", command=lambda: (self._builder_add_slot(cat), self._switch_view("builder")))
        menu.add_command(label="Export as wildcard .txt", command=lambda: self._export_wildcards([cat]))
        menu.add_separator()
        menu.add_command(label=f"Delete \"{cat}\"", command=lambda: self._del_category(cat))
        menu.tk_popup(event.x_root, event.y_root)

    def _move_category(self, cat, delta):
        cats = self.categories
        i = cats.index(cat)
        j = i + delta
        if not (0 <= j < len(cats)):
            return
        cats[i], cats[j] = cats[j], cats[i]
        self.data = {c: self.data[c] for c in cats}
        self.store.set("cat_sort", "manual")
        self._save()
        self._render_cats()

    # ═══════════════════════════════════════════════════════════════
    # ANSICHTEN
    # ═══════════════════════════════════════════════════════════════

    def _switch_view(self, name):
        if name == self._active_view:
            return
        self._active_view = name
        for n, btn in self._tab_btns.items():
            act = n == name
            btn.configure(fg=C.ACC if act else C.TXT2, bg=C.SURF3 if act else C.SURF)
        if name == "library":
            self._builder_view.pack_forget()
            self._lib_view.pack(fill="both", expand=True)
        else:
            self._lib_view.pack_forget()
            self._builder_view.pack(fill="both", expand=True)
            self._render_slots()

    # ═══════════════════════════════════════════════════════════════
    # KATEGORIE CRUD
    # ═══════════════════════════════════════════════════════════════

    def _add_category(self):
        def on_save(name):
            self.data[name] = []
            self._save()
            self._render_cats()
            self._switch_view("library")
            self._select(name)
        self._show_name_dialog("New Category", on_save=on_save)

    def _rename_category(self, cat):
        def on_save(name):
            if name == cat:
                return
            self.data = {name if k == cat else k: v for k, v in self.data.items()}
            for s in self._slots:
                if s.get("cat") == cat:
                    s["cat"] = name
            for r in self._rules:
                for k in ("if_cat", "then_cat"):
                    if r.get(k) == cat:
                        r[k] = name
            self._save()
            if self.selected == cat:
                self.selected = name
            self._render_cats()
            self._select(self.selected)
        self._show_name_dialog(f'Rename "{cat}"', initial=cat, on_save=on_save)

    def _del_category(self, cat):
        n = len(self.data.get(cat, []))
        if not messagebox.askyesno("Delete Category?",
                                   f'Delete "{cat}" with {n} prompt{"s" if n != 1 else ""}?', parent=self):
            return
        pos = self.categories.index(cat)
        prompts = self.data[cat]
        self._push_undo(("category", cat, prompts, pos))
        for p in prompts:
            self._trash.insert(0, {"cat": cat, "prompt": p, "deleted": now_iso()})
        self._trash = self.store.save_trash(self._trash)
        del self.data[cat]
        self._save()
        if self.selected == cat:
            self.selected = None
        self._render_cats()
        self._select(self.selected if self.selected else (self.categories[0] if self.categories else None))
        self._toast("Deleted  —  Ctrl+Z to undo")

    # ═══════════════════════════════════════════════════════════════
    # SPEICHERN / UNDO / TOAST
    # ═══════════════════════════════════════════════════════════════

    def _save(self):
        try:
            self.store.save_data(self.data)
        except OSError as e:
            messagebox.showerror("Save failed", f"Could not write prompts.json:\n{e}", parent=self)

    def _refresh(self):
        self._select(self.selected)
        for cat, row in self._cat_rows.items():
            if cat in self.data:
                row.update_count(len(self.data[cat]))
        if set(self._cat_rows) != set(self.data):
            self._render_cats()

    def _push_undo(self, entry):
        self._undo_stack.append(entry)
        del self._undo_stack[:-30]

    def _undo(self, _=None):
        if not self._undo_stack:
            self._toast("Nothing to undo")
            return
        kind, *rest = self._undo_stack.pop()
        if kind == "prompts":
            entries = rest[0]
            for cat, index, p in sorted(entries, key=lambda e: e[1]):
                lst = self.data.setdefault(cat, [])
                if not any(x["id"] == p["id"] for x in lst):
                    lst.insert(min(index, len(lst)), p)
                self._trash = [t for t in self._trash if t["prompt"].get("id") != p["id"]]
            self.store.save_trash(self._trash)
            self._save()
            self._render_cats()
            self._refresh()
            self._toast(f"Restored {len(entries)} prompt{'s' if len(entries) != 1 else ''}")
        elif kind == "category":
            name, prompts, pos = rest
            if name in self.data:
                self.data[name].extend(prompts)
            else:
                items = list(self.data.items())
                items.insert(min(pos, len(items)), (name, prompts))
                self.data = dict(items)
            ids = {p["id"] for p in prompts}
            self._trash = [t for t in self._trash if t["prompt"].get("id") not in ids]
            self.store.save_trash(self._trash)
            self._save()
            self._render_cats()
            self._select(name)
            self._toast(f'Restored category "{name}"')

    def _toast(self, msg):
        if self._toast_lbl:
            try:
                self._toast_lbl.destroy()
            except tk.TclError:
                pass
            self._toast_lbl = None
        if self._toast_job:
            self.after_cancel(self._toast_job)
        lbl = tk.Label(self, text=f"  {msg}  ", fg=C.ACC, bg=C.SURF3, font=F(10, bold=True),
                       padx=10, pady=6, highlightbackground=C.ACC, highlightthickness=1)
        lbl.place(relx=0.99, rely=0.97, anchor="se")
        lbl.lift()
        self._toast_lbl = lbl

        def hide():
            self._toast_job = None
            if self._toast_lbl:
                try:
                    self._toast_lbl.destroy()
                except tk.TclError:
                    pass
                self._toast_lbl = None
        self._toast_job = self.after(2500, hide)

    # ═══════════════════════════════════════════════════════════════
    # TASTENKÜRZEL
    # ═══════════════════════════════════════════════════════════════

    def _bind_shortcuts(self):
        b = self.bind
        b("<Control-z>", self._shortcut_undo)
        b("<Control-f>", self._shortcut_search)
        b("<Control-c>", self._shortcut_copy)
        b("<Control-n>", lambda e: self._guard(lambda: (self._switch_view("library"), self._add_prompt())))
        b("<Control-N>", lambda e: self._guard(self._add_category))
        b("<Control-a>", lambda e: self._guard(self._select_all_visible, "library"))
        b("<Delete>", lambda e: self._guard(lambda: self._del_prompts(list(self._selection)) if self._selection else None, "library"))
        b("<Control-l>", lambda e: self._guard(lambda: self._switch_view("library")))
        b("<Control-b>", lambda e: self._guard(lambda: self._switch_view("builder")))
        b("<Control-comma>", lambda e: self._guard(self._open_settings))
        b("<Control-d>", lambda e: self._guard(self._open_duplicates))
        b("<Control-t>", lambda e: self._guard(self._open_trash))
        b("<F1>", lambda e: self._open_shortcuts() if not self._overlay else None)
        b("<space>", self._shortcut_space)
        b("<Escape>", self._shortcut_escape)
        for i in range(1, 10):
            b(f"<Control-Key-{i}>", lambda e, k=i: self._guard(lambda: self._jump_cat(k)))

    def _typing(self):
        w = self.focus_get()
        return isinstance(w, (tk.Entry, tk.Text, tk.Listbox, ctk.CTkEntry, ctk.CTkTextbox))

    def _guard(self, fn, view=None):
        if self._typing() or self._overlay:
            return None
        if view and self._active_view != view:
            return None
        fn()
        return "break"

    def _jump_cat(self, k):
        cats = self._sorted_categories()
        if k <= len(cats):
            self._switch_view("library")
            self._select(cats[k - 1])

    def _shortcut_undo(self, _):
        if not self._typing():
            self._undo()

    def _shortcut_search(self, _):
        if self._overlay:
            return None
        self._switch_view("library")
        self._search_entry.focus_set()
        return "break"

    def _shortcut_copy(self, _):
        if self._typing():
            return None
        if self._active_view == "builder":
            self._builder_copy_result()
        elif self._selection:
            self._copy_prompts(list(self._selection))
        return "break"

    def _shortcut_space(self, _):
        if self._typing() or self._overlay or self._active_view != "builder":
            return None
        self._builder_randomize()
        return "break"

    def _shortcut_escape(self, _):
        if self._overlay:
            self._overlay.close()
        elif self._search_var.get():
            self._search_var.set("")
        elif self._selection:
            self._clear_selection()
        self.focus_set()

    # ═══════════════════════════════════════════════════════════════
    # BEENDEN
    # ═══════════════════════════════════════════════════════════════

    def _persist_window(self):
        if not self.store.get("remember_window", True):
            return
        try:
            zoomed = self.state() == "zoomed"
            if zoomed:
                self.state("normal")
                self.update_idletasks()
            self.store.settings["geometry"] = self.geometry()
            self.store.settings["zoomed"] = zoomed
            self.store.save_settings()
        except tk.TclError:
            pass

    def _on_close(self):
        self._save_builder_state_now()
        if self.store.get("tray") and self._hide_to_tray():
            return
        self._quit()

    def _quit(self):
        self._persist_window()
        self._save_builder_state_now()
        self._stop_hotkey()
        self._stop_tray()
        self.destroy()


if __name__ == "__main__":
    app = PromptVaultApp()
    app.mainloop()
