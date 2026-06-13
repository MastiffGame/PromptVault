import customtkinter as ctk
import tkinter as tk
import json
import os
import re
import shutil
import sys
import random
from tkinter import messagebox, filedialog

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(_APP_DIR, "prompts.json")
BACKUP_FILE = os.path.join(_APP_DIR, "prompts_backup.json")
TEMPLATE_FILE = os.path.join(_APP_DIR, "builder_templates.json")
FAVS_FILE = os.path.join(_APP_DIR, "favorites.json")
DEFAULT_CATEGORIES = ["Clothing", "Hairstyle", "Environment", "Appearance", "Position", "Character"]

# ─── Farben ───────────────────────────────────────────────────────────────────
BG      = "#06060f"
SURF    = "#0b0b1a"
SURF2   = "#0f0f22"
SURF3   = "#14142e"
BORDER  = "#1c1c38"
BORD_H  = "#2c2c55"

CYAN    = "#00d4ff"
CYAN_DIM= "#002233"
CYAN_MID= "#004d66"
PURP    = "#a78bfa"
PURP_DIM= "#1a0d40"
PURP_MID= "#3d2080"
RED     = "#f87171"
RED_DIM = "#1e0808"
RED_MID = "#4a1010"

TXT     = "#dce4f5"
TXT2    = "#4a5a78"
TXT3    = "#222840"
GOLD    = "#fbbf24"


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    data = {cat: [] for cat in DEFAULT_CATEGORIES}
    save_data(data)
    return data


def save_data(data):
    # Sicherheitskopie der letzten Version, dann atomar schreiben
    if os.path.exists(DATA_FILE):
        try:
            shutil.copy2(DATA_FILE, BACKUP_FILE)
        except OSError:
            pass
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def load_templates():
    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_templates(templates):
    tmp = TEMPLATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TEMPLATE_FILE)


def load_favs():
    if os.path.exists(FAVS_FILE):
        try:
            with open(FAVS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_favs(favs):
    favs = {c: ps for c, ps in favs.items() if ps}
    tmp = FAVS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)
    os.replace(tmp, FAVS_FILE)


def split_batch(text):
    """Zerlegt nummerierten Text ("1: foo  2. bar  3) baz") in einzelne Prompts."""
    marker = r"(?:^|[\s,;])\s*\d{1,3}\s*[.:)]\s+"
    if re.search(marker, "\n" + text):
        parts = re.split(marker, "\n" + text)
        prompts = [p.strip().strip(",;").strip() for p in parts]
        return [p for p in prompts if p]
    # Keine Nummerierung gefunden: jede nicht-leere Zeile = ein Prompt
    return [line.strip() for line in text.splitlines() if line.strip()]


# ─── Button-Helfer ────────────────────────────────────────────────────────────

# CTkFont-Objekte sind teuer — einmal erstellen und wiederverwenden
_FONT_CACHE = {}

def cfont(size, weight=None, family=None):
    key = (size, weight, family)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ctk.CTkFont(size=size, weight=weight, family=family)
    return _FONT_CACHE[key]


def ghost_btn(parent, text, cmd, *, color=TXT2, hover=SURF3,
              width=90, height=28, font_size=11, **kw):
    return ctk.CTkButton(
        parent, text=text, command=cmd,
        fg_color="transparent", hover_color=hover,
        border_width=1, border_color=BORD_H,
        text_color=color, corner_radius=8,
        font=cfont(font_size),
        width=width, height=height, **kw)


def neon_btn(parent, text, cmd, *, color=CYAN, bg=CYAN_DIM, hover=CYAN_MID,
             width=120, height=34, font_size=13, state="normal", **kw):
    return ctk.CTkButton(
        parent, text=text, command=cmd,
        fg_color=bg, hover_color=hover,
        border_width=1, border_color=color,
        text_color=color, corner_radius=10,
        font=cfont(font_size, "bold"),
        width=width, height=height, state=state, **kw)


def flat_btn(parent, text, cmd, *, fg=TXT2, bg=SURF2, hover=SURF3, hover_fg=None):
    """Leichter tk-Button für Listenkarten — viel schneller als CTkButton."""
    lbl = tk.Label(parent, text=text, fg=fg, bg=bg,
                   font=("Segoe UI", 9), padx=10, pady=2, cursor="hand2",
                   highlightbackground=BORD_H, highlightthickness=1)
    lbl.bind("<Button-1>", lambda _: cmd())
    lbl.bind("<Enter>", lambda _: lbl.configure(bg=hover, fg=hover_fg or fg))
    lbl.bind("<Leave>", lambda _: lbl.configure(bg=bg, fg=fg))
    return lbl


# ─── Kategorie-Zeile ──────────────────────────────────────────────────────────

class CategoryRow(tk.Frame):
    """Einfache Kategorie-Schaltfläche ohne customtkinter-Overhead."""
    def __init__(self, parent, label, count, command, selected=False, on_menu=None):
        super().__init__(parent, bg=SURF, height=38, cursor="hand2")
        self.pack_propagate(False)
        self._cmd = command
        self._selected = selected

        # Linker Akzentbalken
        self._bar = tk.Frame(self, width=3, bg=CYAN if selected else SURF)
        self._bar.pack(side="left", fill="y", padx=(4, 0), pady=6)

        # Label
        self._lbl = tk.Label(self, text=f"  {label}", anchor="w",
                              bg=SURF3 if selected else SURF,
                              fg=CYAN if selected else TXT,
                              font=("Segoe UI", 12),
                              cursor="hand2")
        self._lbl.pack(side="left", fill="both", expand=True, pady=3, padx=4)

        # Badge
        self._badge = tk.Label(self, text=str(count),
                                bg="#002233" if selected else SURF3,
                                fg=CYAN if selected else TXT2,
                                font=("Segoe UI", 9, "bold"),
                                padx=6, pady=2, relief="flat",
                                cursor="hand2")
        self._badge.pack(side="right", padx=(0, 8), pady=8)

        # Klick überall
        for w in (self, self._lbl, self._badge):
            w.bind("<Button-1>", lambda _: self._cmd())
            if on_menu:
                w.bind("<Button-3>", on_menu)

    def set_selected(self, v):
        self._selected = v
        self._bar.configure(bg=CYAN if v else SURF)
        self._lbl.configure(bg=SURF3 if v else SURF, fg=CYAN if v else TXT)
        self._badge.configure(bg="#002233" if v else SURF3,
                               fg=CYAN if v else TXT2)

    def update_count(self, count):
        self._badge.configure(text=str(count))


# ─── Hauptanwendung ───────────────────────────────────────────────────────────

class PromptVaultApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.configure(fg_color=BG)
        self.title("PromptVault")
        self.geometry("1260x740")
        self.minsize(960, 580)

        self.data = load_data()
        self.selected = None          # aktuell gewählte Kategorie
        self._cat_rows = {}
        self._overlay = None          # aktives Modal-Overlay
        self._search_job = None       # Debounce-Timer für Suche
        self._render_job = None       # Timer für gestaffeltes Rendern
        self._render_queue = []
        self._slots = []              # Builder-Slots (siehe _builder_add_slot)
        self._active_view = "library"
        self._tab_btns = {}
        self.favs = load_favs()       # {Kategorie: [Prompt, ...]}
        self._fav_filter = False
        self._undo_stack = []         # Wiederherstellung gelöschter Prompts/Kategorien
        self._history = []            # letzte Builder-Ergebnisse (neueste zuerst)
        self._toast_lbl = None
        self._toast_job = None

        self._build_sidebar()
        self._main = tk.Frame(self, bg=BG)
        self._main.pack(side="left", fill="both", expand=True)
        self._build_content()
        self._build_builder()
        self._bind_shortcuts()
        # Erste Kategorie automatisch auswählen
        if self.categories:
            self._select(self.categories[0])

    @property
    def categories(self):
        return list(self.data.keys())

    # ═══════════════════════════════════════════════════════════════
    # SIDEBAR
    # ═══════════════════════════════════════════════════════════════

    def _build_sidebar(self):
        sb = tk.Frame(self, bg=SURF, width=240)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        self._sb = sb

        # Trennlinie
        tk.Frame(sb, width=1, bg=BORDER).place(relx=1, rely=0, relheight=1, anchor="ne")

        # Logo
        logo = tk.Frame(sb, bg=SURF, height=80)
        logo.pack(side="top", fill="x")
        logo.pack_propagate(False)
        tk.Label(logo, text="PROMPT", fg=CYAN, bg=SURF,
                 font=("Segoe UI", 18, "bold")).place(x=18, y=18)
        tk.Label(logo, text="VAULT", fg=PURP, bg=SURF,
                 font=("Segoe UI", 18, "bold")).place(x=104, y=18)
        tk.Label(logo, text="Image Generation", fg=TXT2, bg=SURF,
                 font=("Segoe UI", 9)).place(x=18, y=46)
        tk.Frame(logo, height=1, bg=BORDER).place(x=14, rely=1, relwidth=1, width=-28, anchor="sw")

        # Tab-Leiste (Library / Builder)
        tabs = tk.Frame(sb, bg=SURF)
        tabs.pack(side="top", fill="x", padx=12, pady=(10, 2))
        for name, label in (("library", "Library"), ("builder", "Builder")):
            active = name == self._active_view
            btn = tk.Label(tabs, text=label, cursor="hand2",
                           fg=CYAN if active else TXT2,
                           bg=SURF3 if active else SURF,
                           font=("Segoe UI", 11, "bold"), pady=6,
                           highlightbackground=BORD_H, highlightthickness=1)
            btn.pack(side="left", fill="x", expand=True, padx=2)
            btn.bind("<Button-1>", lambda _, n=name: self._switch_view(n))
            self._tab_btns[name] = btn

        # Label
        tk.Label(sb, text="CATEGORIES", fg=TXT3, bg=SURF,
                 font=("Segoe UI", 9, "bold")).pack(side="top", anchor="w", padx=18, pady=(10, 4))

        # Neue-Kategorie-Button (unten)
        ghost_btn(sb, "+ New Category", self._add_category,
                  color=CYAN, width=200, height=32, font_size=12).pack(
            side="bottom", fill="x", padx=12, pady=(6, 12))

        # Export / Import (unten, über New Category)
        io = tk.Frame(sb, bg=SURF)
        io.pack(side="bottom", fill="x", padx=12)
        ghost_btn(io, "↑ Import", self._import_data,
                  width=94, height=28, font_size=11).pack(
            side="left", fill="x", expand=True, padx=(0, 3))
        ghost_btn(io, "↓ Export", self._export_data,
                  width=94, height=28, font_size=11).pack(
            side="left", fill="x", expand=True, padx=(3, 0))

        # Kategorie-Canvas (scrollbar)
        self._cat_canvas = tk.Canvas(sb, bg=SURF, highlightthickness=0)
        self._cat_canvas.pack(side="top", fill="both", expand=True, padx=0)

        self._cat_inner = tk.Frame(self._cat_canvas, bg=SURF)
        self._cat_win = self._cat_canvas.create_window(0, 0, window=self._cat_inner, anchor="nw")

        self._cat_inner.bind("<Configure>",
            lambda e: self._cat_canvas.configure(scrollregion=self._cat_canvas.bbox("all")))
        self._cat_canvas.bind("<Configure>",
            lambda e: self._cat_canvas.itemconfig(self._cat_win, width=e.width))
        # Mausrad nur scrollen, wenn die Maus über der Sidebar ist
        def _sb_scroll(e):
            self._cat_canvas.yview_scroll(int(-1 * e.delta / 120), "units")
        sb.bind("<Enter>", lambda _: self._cat_canvas.bind_all("<MouseWheel>", _sb_scroll))
        sb.bind("<Leave>", lambda _: self._cat_canvas.unbind_all("<MouseWheel>"))

        self._render_cats()

    def _render_cats(self):
        for w in self._cat_inner.winfo_children():
            w.destroy()
        self._cat_rows.clear()
        for cat in self.categories:
            count = len(self.data.get(cat, []))
            sel = cat == self.selected
            row = CategoryRow(self._cat_inner, cat, count,
                               command=lambda c=cat: (self._switch_view("library"),
                                                      self._select(c)),
                               selected=sel,
                               on_menu=lambda e, c=cat: self._cat_menu(e, c))
            row.pack(fill="x", padx=6, pady=2)
            self._cat_rows[cat] = row

    def _cat_menu(self, event, cat):
        menu = tk.Menu(self, tearoff=0, bg=SURF2, fg=TXT,
                       activebackground=SURF3, activeforeground=CYAN,
                       relief="flat", borderwidth=0)
        menu.add_command(label=f"Rename \"{cat}\"", command=lambda: self._rename_category(cat))
        menu.add_command(label=f"Delete \"{cat}\"", command=lambda: self._del_category(cat))
        menu.tk_popup(event.x_root, event.y_root)

    def _select(self, cat):
        if self.selected and self.selected in self._cat_rows:
            self._cat_rows[self.selected].set_selected(False)
        self.selected = cat
        if cat is None:
            self._title_lbl.configure(text="Select Category")
            self._count_lbl.configure(text="")
            self._add_btn.configure(state="disabled")
            self._batch_btn.configure(state="disabled")
            self._rnd_btn.configure(state="disabled")
            self._search_var.set("")
            self._render_prompts()
            return
        if cat in self._cat_rows:
            self._cat_rows[cat].set_selected(True)

        n = len(self.data.get(cat, []))
        self._title_lbl.configure(text=cat)
        self._count_lbl.configure(text=f"{n} Prompt{'s' if n != 1 else ''}")
        self._add_btn.configure(state="normal")
        self._batch_btn.configure(state="normal")
        self._rnd_btn.configure(state="normal" if n > 0 else "disabled")
        self._search_var.set("")
        self._render_prompts()

    # ═══════════════════════════════════════════════════════════════
    # CONTENT
    # ═══════════════════════════════════════════════════════════════

    def _switch_view(self, name):
        if name == self._active_view:
            return
        self._active_view = name
        for n, btn in self._tab_btns.items():
            act = n == name
            btn.configure(fg=CYAN if act else TXT2, bg=SURF3 if act else SURF)
        if name == "library":
            self._builder_view.pack_forget()
            self._lib_view.pack(fill="both", expand=True)
        else:
            self._lib_view.pack_forget()
            self._builder_view.pack(fill="both", expand=True)
            self._render_slots()   # auffrischen, falls Kategorien geändert wurden

    def _build_content(self):
        content = tk.Frame(self._main, bg=BG)
        content.pack(fill="both", expand=True)
        self._lib_view = content

        # Topbar
        top = tk.Frame(content, bg=SURF, height=66)
        top.pack(side="top", fill="x")
        top.pack_propagate(False)

        left_grp = tk.Frame(top, bg=SURF)
        left_grp.pack(side="left", fill="y", padx=22)

        self._title_lbl = tk.Label(left_grp, text="Select Category",
                                    fg=TXT, bg=SURF, font=("Segoe UI", 17, "bold"))
        self._title_lbl.pack(side="top", anchor="w", pady=(14, 0))

        self._count_lbl = tk.Label(left_grp, text="", fg=TXT2, bg=SURF,
                                    font=("Segoe UI", 10))
        self._count_lbl.pack(side="top", anchor="w")

        right_grp = tk.Frame(top, bg=SURF)
        right_grp.pack(side="right", fill="y", padx=18)

        self._rnd_btn = neon_btn(right_grp, "  Random", self._open_random,
                                  color=PURP, bg=PURP_DIM, hover=PURP_MID,
                                  width=118, height=34, font_size=12, state="disabled")
        self._rnd_btn.pack(side="right", pady=16, padx=(6, 0))

        self._batch_btn = neon_btn(right_grp, "+ Batch", self._add_batch,
                                    width=100, height=34, font_size=12, state="disabled")
        self._batch_btn.pack(side="right", pady=16, padx=(6, 0))

        self._add_btn = neon_btn(right_grp, "+ Prompt", self._add_prompt,
                                  width=108, height=34, font_size=12, state="disabled")
        self._add_btn.pack(side="right", pady=16, padx=(6, 0))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        self._search_entry = ctk.CTkEntry(right_grp, textvariable=self._search_var,
                               placeholder_text="  Search...",
                               width=165, height=34,
                               fg_color=SURF2, border_color=BORD_H, border_width=1,
                               text_color=TXT, corner_radius=10,
                               font=ctk.CTkFont(size=12))
        self._search_entry.pack(side="right", pady=16)

        # Globale Suche über alle Kategorien
        self._all_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(right_grp, text="All", variable=self._all_var,
                        command=self._render_prompts,
                        width=50, height=20, checkbox_width=18, checkbox_height=18,
                        fg_color=CYAN_MID, hover_color=CYAN_MID, border_color=BORD_H,
                        checkmark_color=CYAN, text_color=TXT2,
                        font=cfont(11)).pack(side="right", pady=16, padx=(0, 8))

        # Favoriten-Filter
        self._fav_btn = ghost_btn(right_grp, "☆", self._toggle_fav_filter,
                                  width=38, height=34, font_size=15)
        self._fav_btn.pack(side="right", pady=16, padx=(0, 6))

        # Prompt-Liste
        self._list_canvas = tk.Canvas(content, bg=BG, highlightthickness=0)
        self._list_canvas.pack(side="top", fill="both", expand=True, padx=14, pady=12)

        self._list_scroll = tk.Scrollbar(content, orient="vertical",
                                          command=self._list_canvas.yview)
        self._list_canvas.configure(yscrollcommand=self._list_scroll.set)
        self._list_scroll.place(in_=self._list_canvas, relx=1, rely=0,
                                 relheight=1, anchor="ne")

        self._list_inner = tk.Frame(self._list_canvas, bg=BG)
        self._list_win = self._list_canvas.create_window(0, 0, window=self._list_inner, anchor="nw")

        self._list_inner.bind("<Configure>",
            lambda e: self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all")))
        self._list_canvas.bind("<Configure>",
            lambda e: self._list_canvas.itemconfig(self._list_win, width=e.width))
        self._list_canvas.bind("<MouseWheel>",
            lambda e: self._list_canvas.yview_scroll(int(-1 * e.delta / 120), "units"))

        tk.Label(self._list_inner, text="← Select a category on the left",
                  fg=TXT3, bg=BG, font=("Segoe UI", 14)).pack(pady=80)

    # ═══════════════════════════════════════════════════════════════
    # PROMPTS ANZEIGEN
    # ═══════════════════════════════════════════════════════════════

    def _on_search(self):
        # Debounce: erst rendern, wenn 250 ms lang nichts mehr getippt wurde
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(250, self._render_prompts)

    def _render_prompts(self):
        if self._search_job:
            self.after_cancel(self._search_job)
            self._search_job = None
        if self._render_job:
            self.after_cancel(self._render_job)
            self._render_job = None
        self._render_queue = []

        for w in self._list_inner.winfo_children():
            w.destroy()
        self._list_canvas.yview_moveto(0)

        q = self._search_var.get().strip().lower()
        global_mode = self._all_var.get()

        if not global_mode and not self.selected:
            return

        def matches(cat, p):
            if q and q not in p.lower():
                return False
            if self._fav_filter and not self._is_fav(cat, p):
                return False
            return True

        if global_mode:
            cats = self.categories
        else:
            cats = [self.selected]
        filtered = [(cat, i, p)
                    for cat in cats
                    for i, p in enumerate(self.data.get(cat, []))
                    if matches(cat, p)]

        if not filtered:
            if q:
                msg = f'No results for "{self._search_var.get()}"'
            elif self._fav_filter:
                msg = "No favorites yet.\nClick  ☆  on a prompt to star it."
            else:
                msg = "No prompts yet.\nClick  + Prompt  to add one."
            tk.Label(self._list_inner, text=msg, fg=TXT2, bg=BG,
                      font=("Segoe UI", 13)).pack(pady=60)
            return

        # Gestaffelt rendern, damit die UI bei vielen Prompts flüssig bleibt
        self._render_queue = [(cat, i, p, global_mode) for cat, i, p in filtered]
        self._render_batch()

    def _render_batch(self):
        self._render_job = None
        chunk, self._render_queue = self._render_queue[:30], self._render_queue[30:]
        for cat, real_i, prompt, show_cat in chunk:
            self._make_card(cat, real_i, prompt, show_cat)
        if self._render_queue:
            self._render_job = self.after(10, self._render_batch)

    def _make_card(self, cat, real_i, prompt, show_cat=False):
        card = tk.Frame(self._list_inner, bg=SURF2,
                         highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", padx=4, pady=5)

        # Header
        hdr = tk.Frame(card, bg=SURF2)
        hdr.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(hdr, text=f"#{real_i + 1:02d}", fg=CYAN, bg=SURF2,
                  font=("Consolas", 10, "bold")).pack(side="left")
        if show_cat:
            tk.Label(hdr, text=cat, fg=PURP, bg=SURF3,
                      font=("Segoe UI", 9, "bold"), padx=8, pady=1).pack(side="left", padx=(8, 0))

        btn_f = tk.Frame(hdr, bg=SURF2)
        btn_f.pack(side="right")

        fav = self._is_fav(cat, prompt)
        flat_btn(btn_f, "★" if fav else "☆",
                 lambda c=cat, p=prompt: self._toggle_fav(c, p),
                 fg=GOLD if fav else TXT2, hover_fg=GOLD).pack(side="left", padx=2)
        flat_btn(btn_f, "Copy",   lambda p=prompt: self._copy(p),
                 fg=TXT2, hover_fg=CYAN).pack(side="left", padx=2)
        flat_btn(btn_f, "Move",   lambda c=cat, i=real_i: self._move_prompt_menu(c, i),
                 fg=TXT2, hover_fg=CYAN).pack(side="left", padx=2)
        flat_btn(btn_f, "Edit",   lambda c=cat, i=real_i: self._edit_prompt(c, i),
                 fg=PURP, hover=PURP_DIM).pack(side="left", padx=2)
        flat_btn(btn_f, "Delete", lambda c=cat, i=real_i: self._del_prompt(c, i),
                 fg=RED, hover=RED_DIM).pack(side="left", padx=2)

        # Trennlinie
        tk.Frame(card, height=1, bg=BORDER).pack(fill="x", padx=12, pady=2)

        # Text
        tk.Label(card, text=prompt, fg=TXT, bg=SURF2,
                  font=("Consolas", 12), wraplength=900,
                  justify="left", anchor="w").pack(fill="x", padx=12, pady=(4, 10), anchor="w")

    # ── Favoriten ─────────────────────────────────────────────────

    def _is_fav(self, cat, prompt):
        return prompt in self.favs.get(cat, [])

    def _toggle_fav(self, cat, prompt):
        lst = self.favs.setdefault(cat, [])
        if prompt in lst:
            lst.remove(prompt)
        else:
            lst.append(prompt)
        save_favs(self.favs)
        self._render_prompts()

    def _toggle_fav_filter(self):
        self._fav_filter = not self._fav_filter
        self._fav_btn.configure(text="★" if self._fav_filter else "☆",
                                text_color=GOLD if self._fav_filter else TXT2,
                                border_color=GOLD if self._fav_filter else BORD_H)
        self._render_prompts()

    # ═══════════════════════════════════════════════════════════════
    # PROMPT EDITOR (In-Window Overlay — kein Toplevel)
    # ═══════════════════════════════════════════════════════════════

    def _show_editor(self, title="Prompt hinzufügen", initial="", on_save=None, hint=None):
        """Zeigt einen modalen Editor als Frame direkt im Hauptfenster."""
        if self._overlay:
            self._overlay.destroy()

        # Dunkles Overlay über alles
        ov = tk.Frame(self, bg="#020208")
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        ov.lift()
        self._overlay = ov

        # Karte zentriert
        card = ctk.CTkFrame(ov, fg_color=SURF, corner_radius=14,
                             border_width=1, border_color=BORD_H,
                             width=680, height=440 if hint else 400)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        # Header
        hdr = tk.Frame(card, bg=SURF2, height=48)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=title, fg=CYAN, bg=SURF2,
                  font=("Segoe UI", 14, "bold")).pack(side="left", padx=18, pady=10)
        if hint:
            tk.Label(hdr, text=hint, fg=TXT2, bg=SURF2,
                      font=("Segoe UI", 10)).pack(side="left", padx=(0, 18), pady=10)

        # Textbox
        tb = ctk.CTkTextbox(card, font=ctk.CTkFont(family="Consolas", size=13),
                             wrap="word", fg_color=SURF2,
                             border_color=BORD_H, border_width=1,
                             text_color=TXT, corner_radius=10,
                             scrollbar_button_color=SURF3)
        tb.grid(row=1, column=0, padx=18, pady=(14, 8), sticky="nsew")
        if initial:
            tb.insert("1.0", initial)

        # Buttons
        bot = tk.Frame(card, bg=SURF)
        bot.grid(row=2, column=0, padx=18, pady=(4, 16), sticky="e")

        def close():
            ov.destroy()
            self._overlay = None

        def save():
            text = tb.get("1.0", "end-1c").strip()
            close()
            if text and on_save:
                on_save(text)

        ghost_btn(bot, "Cancel", close, width=108, height=34, font_size=12).pack(side="left", padx=(0, 8))
        neon_btn(bot, "Save", save, width=108, height=34, font_size=12).pack(side="left")

        ov.bind("<Escape>", lambda _: close())
        tb.focus_set()

    # ═══════════════════════════════════════════════════════════════
    # PROMPT CRUD
    # ═══════════════════════════════════════════════════════════════

    def _is_dup(self, cat, text, skip_index=None):
        low = text.lower()
        return any(p.lower() == low
                   for i, p in enumerate(self.data.get(cat, []))
                   if i != skip_index)

    def _add_prompt(self):
        def on_save(text):
            if self._is_dup(self.selected, text) and not messagebox.askyesno(
                    "Duplicate",
                    f'This prompt already exists in "{self.selected}".\nAdd anyway?',
                    parent=self):
                return
            self.data[self.selected].append(text)
            save_data(self.data)
            self._refresh()
        self._show_editor(title=f"Add Prompt  —  {self.selected}", on_save=on_save)

    def _add_batch(self):
        def on_save(text):
            prompts = split_batch(text)
            if not prompts:
                return
            added = skipped = 0
            for p in prompts:
                if self._is_dup(self.selected, p):
                    skipped += 1
                else:
                    self.data[self.selected].append(p)
                    added += 1
            save_data(self.data)
            self._refresh()
            msg = (f"{added} prompt{'s' if added != 1 else ''} "
                   f"added to \"{self.selected}\".")
            if skipped:
                msg += f"\n{skipped} duplicate{'s' if skipped != 1 else ''} skipped."
            messagebox.showinfo("Batch", msg, parent=self)
        self._show_editor(
            title=f"Add Batch  —  {self.selected}",
            hint="Paste numbered prompts:  1: ...  2. ...  3) ...",
            on_save=on_save)

    def _edit_prompt(self, cat, index):
        cur = self.data[cat][index]
        def on_save(text):
            if text == cur:
                return
            if self._is_dup(cat, text, skip_index=index) and not messagebox.askyesno(
                    "Duplicate",
                    f'This prompt already exists in "{cat}".\nSave anyway?',
                    parent=self):
                return
            self.data[cat][index] = text
            # Favoriten-Stern übernehmen
            favs = self.favs.get(cat, [])
            if cur in favs and cur not in self.data[cat]:
                favs[favs.index(cur)] = text
                save_favs(self.favs)
            save_data(self.data)
            self._refresh()
        self._show_editor(title="Edit Prompt", initial=cur, on_save=on_save)

    def _del_prompt(self, cat, index):
        p = self.data[cat][index]
        prev = (p[:70] + "...") if len(p) > 70 else p
        if not messagebox.askyesno("Delete?", f'"{prev}"', parent=self):
            return
        self.data[cat].pop(index)
        was_fav = self._is_fav(cat, p)
        if was_fav and p not in self.data[cat]:
            self.favs[cat].remove(p)
            save_favs(self.favs)
        self._push_undo(("prompt", cat, index, p, was_fav))
        save_data(self.data)
        self._refresh()
        self._toast("Deleted  —  Ctrl+Z to undo")

    def _move_prompt_menu(self, cat, index):
        others = [c for c in self.categories if c != cat]
        if not others:
            self._toast("No other category to move to")
            return
        menu = tk.Menu(self, tearoff=0, bg=SURF2, fg=TXT,
                       activebackground=SURF3, activeforeground=CYAN,
                       relief="flat", borderwidth=0)
        for target in others:
            menu.add_command(label=f"Move to \"{target}\"",
                             command=lambda t=target: self._move_prompt(cat, index, t))
        menu.tk_popup(*self.winfo_pointerxy())

    def _move_prompt(self, cat, index, target):
        p = self.data[cat][index]
        if self._is_dup(target, p) and not messagebox.askyesno(
                "Duplicate",
                f'This prompt already exists in "{target}".\nMove anyway?',
                parent=self):
            return
        self.data[cat].pop(index)
        self.data[target].append(p)
        # Stern mitnehmen
        if p in self.favs.get(cat, []) and p not in self.data[cat]:
            self.favs[cat].remove(p)
            if p not in self.favs.setdefault(target, []):
                self.favs[target].append(p)
            save_favs(self.favs)
        save_data(self.data)
        self._refresh()
        self._toast(f'Moved to "{target}"')

    def _copy(self, prompt):
        self.clipboard_clear()
        self.clipboard_append(prompt)

    # ═══════════════════════════════════════════════════════════════
    # UNDO + TOAST
    # ═══════════════════════════════════════════════════════════════

    def _push_undo(self, entry):
        self._undo_stack.append(entry)
        del self._undo_stack[:-20]

    def _undo(self, _=None):
        if not self._undo_stack:
            self._toast("Nothing to undo")
            return
        kind, *rest = self._undo_stack.pop()
        if kind == "prompt":
            cat, index, text, was_fav = rest
            lst = self.data.setdefault(cat, [])
            lst.insert(min(index, len(lst)), text)
            if was_fav and text not in self.favs.setdefault(cat, []):
                self.favs[cat].append(text)
                save_favs(self.favs)
            save_data(self.data)
            self._render_cats()
            self._refresh()
            self._toast(f'Restored prompt in "{cat}"')
        elif kind == "category":
            name, prompts, favs, pos = rest
            if name in self.data:
                self.data[name].extend(prompts)
            else:
                items = list(self.data.items())
                items.insert(min(pos, len(items)), (name, prompts))
                self.data = dict(items)
            if favs:
                self.favs[name] = favs
                save_favs(self.favs)
            save_data(self.data)
            self._render_cats()
            self._select(name)
            self._toast(f'Restored category "{name}"')

    def _toast(self, msg):
        if self._toast_lbl:
            self._toast_lbl.destroy()
            self._toast_lbl = None
        if self._toast_job:
            self.after_cancel(self._toast_job)
        lbl = tk.Label(self, text=f"  {msg}  ", fg=CYAN, bg=SURF3,
                       font=("Segoe UI", 10, "bold"), padx=10, pady=6,
                       highlightbackground=CYAN, highlightthickness=1)
        lbl.place(relx=0.99, rely=0.97, anchor="se")
        lbl.lift()
        self._toast_lbl = lbl

        def hide():
            self._toast_job = None
            if self._toast_lbl:
                self._toast_lbl.destroy()
                self._toast_lbl = None
        self._toast_job = self.after(2500, hide)

    # ═══════════════════════════════════════════════════════════════
    # KATEGORIE CRUD
    # ═══════════════════════════════════════════════════════════════

    def _show_name_dialog(self, title, initial="", on_save=None, taken=None):
        if self._overlay:
            self._overlay.destroy()

        ov = tk.Frame(self, bg="#020208")
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        ov.lift()
        self._overlay = ov

        card = ctk.CTkFrame(ov, fg_color=SURF, corner_radius=14,
                             border_width=1, border_color=BORD_H,
                             width=420, height=180)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        tk.Label(card, text=title, fg=CYAN, bg=SURF,
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(18, 8))

        name_var = tk.StringVar(value=initial)
        entry = ctk.CTkEntry(card, textvariable=name_var, width=380, height=36,
                              fg_color=SURF2, border_color=BORD_H, border_width=1,
                              text_color=TXT, corner_radius=10, font=cfont(13))
        entry.pack(padx=20)

        bot = tk.Frame(card, bg=SURF)
        bot.pack(side="bottom", anchor="e", padx=20, pady=(0, 16))

        def close():
            ov.destroy()
            self._overlay = None

        def save(_=None):
            name = name_var.get().strip()
            if not name:
                return
            existing = self.data if taken is None else taken
            if name != initial and name in existing:
                messagebox.showwarning("Exists",
                    f'Category "{name}" already exists.', parent=self)
                return
            close()
            if on_save:
                on_save(name)

        ghost_btn(bot, "Cancel", close, width=100, height=32, font_size=12).pack(side="left", padx=(0, 8))
        neon_btn(bot, "Save", save, width=100, height=32, font_size=12).pack(side="left")

        ov.bind("<Escape>", lambda _: close())
        entry.bind("<Return>", save)
        entry.focus_set()

    def _add_category(self):
        def on_save(name):
            self.data[name] = []
            save_data(self.data)
            self._render_cats()
            self._select(name)
        self._show_name_dialog("New Category", on_save=on_save)

    def _rename_category(self, cat):
        def on_save(name):
            if name == cat:
                return
            self.data = {name if k == cat else k: v for k, v in self.data.items()}
            if cat in self.favs:
                self.favs = {name if k == cat else k: v for k, v in self.favs.items()}
                save_favs(self.favs)
            save_data(self.data)
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
        self._push_undo(("category", cat, self.data[cat],
                         self.favs.get(cat, []), pos))
        del self.data[cat]
        self.favs.pop(cat, None)
        save_favs(self.favs)
        save_data(self.data)
        if self.selected == cat:
            self.selected = None
        self._render_cats()
        self._select(self.selected if self.selected else
                     (self.categories[0] if self.categories else None))
        self._toast("Deleted  —  Ctrl+Z to undo")

    # ═══════════════════════════════════════════════════════════════
    # ZUFÄLLIGE PROMPTS (Overlay)
    # ═══════════════════════════════════════════════════════════════

    def _open_random(self):
        if not self.selected:
            return
        if self._overlay:
            self._overlay.destroy()

        ov = tk.Frame(self, bg="#020208")
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        ov.lift()
        self._overlay = ov

        card = ctk.CTkFrame(ov, fg_color=SURF, corner_radius=14,
                             border_width=1, border_color=BORD_H,
                             width=800, height=680)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)   # Scrollbar-Spalte
        card.grid_rowconfigure(3, weight=1)

        # ── Header ────────────────────────────────────────────────
        hdr = tk.Frame(card, bg=SURF2, height=56)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Random Prompts", fg=PURP, bg=SURF2,
                  font=("Segoe UI", 16, "bold")).pack(side="left", padx=6, pady=8)

        # ── Steuerung ─────────────────────────────────────────────
        ctrl = ctk.CTkFrame(card, fg_color=SURF2, corner_radius=10,
                             border_width=1, border_color=BORDER)
        ctrl.grid(row=1, column=0, columnspan=2, padx=18, pady=10, sticky="ew")

        tk.Label(ctrl, text="Category", fg=TXT2, bg=SURF2,
                  font=("Segoe UI", 10)).grid(row=0, column=0, padx=(14, 6), pady=(8, 2), sticky="w")
        tk.Label(ctrl, text="Count", fg=TXT2, bg=SURF2,
                  font=("Segoe UI", 10)).grid(row=0, column=2, padx=(14, 6), pady=(8, 2), sticky="w")

        cat_var = ctk.StringVar(value=self.selected)
        ctk.CTkOptionMenu(ctrl, values=self.categories, variable=cat_var,
                          width=200, height=34, font=ctk.CTkFont(size=13),
                          fg_color=SURF3, button_color=BORD_H, button_hover_color=PURP_MID,
                          dropdown_fg_color=SURF2, dropdown_text_color=TXT,
                          text_color=TXT, corner_radius=8).grid(
            row=1, column=0, padx=(14, 6), pady=(0, 12))

        count_var = ctk.StringVar(value="10")
        ctk.CTkEntry(ctrl, textvariable=count_var, width=65, height=34,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     fg_color=SURF3, border_color=BORD_H, border_width=1,
                     text_color=CYAN, justify="center", corner_radius=8).grid(
            row=1, column=2, padx=(14, 6), pady=(0, 12))

        results_ref = {"list": []}

        # ── Info-Label ────────────────────────────────────────────
        info_lbl = tk.Label(card, text="", fg=TXT2, bg=SURF, font=("Segoe UI", 10))
        info_lbl.grid(row=2, column=0, columnspan=2, pady=(0, 2))

        # ── Ergebnis-Canvas mit Scrollbar ─────────────────────────
        res_canvas = tk.Canvas(card, bg=BG, highlightthickness=0)
        res_canvas.grid(row=3, column=0, padx=(18, 0), pady=(0, 8), sticky="nsew")

        res_scroll = tk.Scrollbar(card, orient="vertical", command=res_canvas.yview)
        res_scroll.grid(row=3, column=1, padx=(4, 16), pady=(0, 8), sticky="ns")
        res_canvas.configure(yscrollcommand=res_scroll.set)

        res_inner = tk.Frame(res_canvas, bg=BG)
        res_win = res_canvas.create_window(0, 0, window=res_inner, anchor="nw")

        res_inner.bind("<Configure>",
            lambda e: res_canvas.configure(scrollregion=res_canvas.bbox("all")))
        res_canvas.bind("<Configure>",
            lambda e: res_canvas.itemconfig(res_win, width=e.width))

        # Mausrad-Scrolling: aktiviert wenn Maus im Ergebnis-Bereich
        def _scroll(e):
            res_canvas.yview_scroll(int(-1 * e.delta / 120), "units")

        def _bind_wheel(e=None):
            res_canvas.bind_all("<MouseWheel>", _scroll)

        def _unbind_wheel(e=None):
            res_canvas.unbind_all("<MouseWheel>")

        res_canvas.bind("<Enter>", _bind_wheel)
        res_canvas.bind("<Leave>", _unbind_wheel)
        res_inner.bind("<Enter>", _bind_wheel)

        # ── Generieren ────────────────────────────────────────────
        def generate():
            cat = cat_var.get()
            try:
                n = max(1, int(count_var.get()))
            except ValueError:
                n = 10
            for w in res_inner.winfo_children():
                w.destroy()
            res_canvas.yview_moveto(0)   # zurück nach oben scrollen

            pool = self.data.get(cat, [])
            if not pool:
                tk.Label(res_inner, text="No prompts in this category.",
                          fg=TXT2, bg=BG, font=("Segoe UI", 12)).pack(pady=30)
                copy_btn.configure(state="disabled")
                results_ref["list"] = []
                return

            actual = min(n, len(pool))
            picked = random.sample(pool, actual)
            results_ref["list"] = picked
            note = f" (max. {actual} available)" if actual < n else ""
            info_lbl.configure(
                text=f"{actual} Prompts from \"{cat}\"{note}  —  scroll with mouse wheel")

            for i, p in enumerate(picked):
                c = tk.Frame(res_inner, bg=SURF2,
                              highlightbackground=BORDER, highlightthickness=1)
                c.pack(fill="x", padx=4, pady=3)

                h = tk.Frame(c, bg=SURF2)
                h.pack(fill="x", padx=10, pady=(6, 2))

                tk.Label(h, text=f"#{i+1:02d}", fg=CYAN, bg=SURF2,
                          font=("Consolas", 10, "bold")).pack(side="left")
                flat_btn(h, "Copy",
                         lambda x=p: (self.clipboard_clear(), self.clipboard_append(x)),
                         fg=TXT2, hover_fg=CYAN).pack(side="right")

                tk.Frame(c, height=1, bg=BORDER).pack(fill="x", padx=10, pady=1)

                tk.Label(c, text=p, fg=TXT, bg=SURF2,
                          font=("Consolas", 11), wraplength=680,
                          justify="left", anchor="w").pack(
                    fill="x", padx=10, pady=(2, 8), anchor="w")

                # Mausrad auch auf Karte binden
                for w in (c, h) + tuple(c.winfo_children()) + tuple(h.winfo_children()):
                    w.bind("<Enter>", _bind_wheel)

            copy_btn.configure(state="normal")

        neon_btn(ctrl, "Generate", generate,
                 color=PURP, bg=PURP_DIM, hover=PURP_MID,
                 width=118, height=34, font_size=12).grid(
            row=1, column=3, padx=(10, 14), pady=(0, 12))

        # ── Footer ────────────────────────────────────────────────
        foot = tk.Frame(card, bg=SURF2, height=50)
        foot.grid(row=4, column=0, columnspan=2, sticky="ew")
        foot.pack_propagate(False)

        def close():
            _unbind_wheel()
            ov.destroy()
            self._overlay = None

        copy_btn = neon_btn(foot, "Copy All",
                             lambda: (self.clipboard_clear(),
                                      self.clipboard_append("\n\n".join(results_ref["list"]))),
                             width=128, height=34, state="disabled")
        copy_btn.pack(side="right", padx=(6, 8), pady=8)
        ghost_btn(foot, "Close", close, width=108, height=34, font_size=12).pack(
            side="right", pady=8)

        ov.bind("<Escape>", lambda _: close())
        generate()

    # ═══════════════════════════════════════════════════════════════
    # BUILDER (Baukasten-Tab)
    # ═══════════════════════════════════════════════════════════════

    def _build_builder(self):
        v = tk.Frame(self._main, bg=BG)
        self._builder_view = v   # wird erst per _switch_view gepackt

        # ── Topbar ────────────────────────────────────────────────
        top = tk.Frame(v, bg=SURF, height=66)
        top.pack(side="top", fill="x")
        top.pack_propagate(False)

        left_grp = tk.Frame(top, bg=SURF)
        left_grp.pack(side="left", fill="y", padx=22)
        tk.Label(left_grp, text="Builder", fg=TXT, bg=SURF,
                 font=("Segoe UI", 17, "bold")).pack(side="top", anchor="w", pady=(14, 0))
        self._slot_count_lbl = tk.Label(left_grp, text="0 Slots", fg=TXT2, bg=SURF,
                                        font=("Segoe UI", 10))
        self._slot_count_lbl.pack(side="top", anchor="w")

        right_grp = tk.Frame(top, bg=SURF)
        right_grp.pack(side="right", fill="y", padx=18)

        self._roll_btn = neon_btn(right_grp, "🎲 Randomize", self._builder_randomize,
                                  color=PURP, bg=PURP_DIM, hover=PURP_MID,
                                  width=132, height=34, font_size=12, state="disabled")
        self._roll_btn.pack(side="right", pady=16, padx=(6, 0))

        self._addslot_btn = neon_btn(right_grp, "+ Slot", self._builder_add_slot_menu,
                                     width=92, height=34, font_size=12)
        self._addslot_btn.pack(side="right", pady=16, padx=(6, 0))

        self._tpl_btn = ghost_btn(right_grp, "Templates", self._builder_templates_menu,
                                  width=100, height=34, font_size=12)
        self._tpl_btn.pack(side="right", pady=16, padx=(6, 0))

        self._hist_btn = ghost_btn(right_grp, "History", self._open_history,
                                   width=90, height=34, font_size=12)
        self._hist_btn.pack(side="right", pady=16)

        # ── Ergebnis-Leiste (unten) ───────────────────────────────
        res = tk.Frame(v, bg=SURF)
        res.pack(side="bottom", fill="x")
        tk.Frame(res, height=1, bg=BORDER).pack(side="top", fill="x")

        res_top = tk.Frame(res, bg=SURF)
        res_top.pack(fill="x", padx=22, pady=(10, 2))

        tk.Label(res_top, text="RESULT", fg=TXT3, bg=SURF,
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        self._copy_result_btn = neon_btn(res_top, "Copy", self._builder_copy_result,
                                         width=92, height=30, font_size=12, state="disabled")
        self._copy_result_btn.pack(side="right")

        self._save_result_btn = neon_btn(res_top, "★ Save", self._builder_save_result_menu,
                                         color=GOLD, bg="#332200", hover="#554400",
                                         width=92, height=30, font_size=12, state="disabled")
        self._save_result_btn.pack(side="right", padx=(0, 6))

        tk.Label(res_top, text="Separator", fg=TXT2, bg=SURF,
                 font=("Segoe UI", 10)).pack(side="right", padx=(0, 6))
        sep_wrap = tk.Frame(res_top, bg=SURF)
        sep_wrap.pack(side="right", padx=(0, 12))
        self._sep_var = tk.StringVar(value=", ")
        self._sep_var.trace_add("write", lambda *_: self._update_result())
        ctk.CTkEntry(sep_wrap, textvariable=self._sep_var, width=60, height=30,
                     fg_color=SURF2, border_color=BORD_H, border_width=1,
                     text_color=CYAN, justify="center", corner_radius=8,
                     font=cfont(12)).pack(side="right", padx=(0, 6))

        self._result_lbl = tk.Label(res, text="—", fg=TXT, bg=SURF,
                                    font=("Consolas", 12), wraplength=940,
                                    justify="left", anchor="w")
        self._result_lbl.pack(fill="x", padx=22, pady=(2, 12), anchor="w")

        # ── Slot-Liste (scrollbar) ────────────────────────────────
        self._slot_canvas = tk.Canvas(v, bg=BG, highlightthickness=0)
        self._slot_canvas.pack(side="top", fill="both", expand=True, padx=14, pady=12)

        slot_scroll = tk.Scrollbar(v, orient="vertical", command=self._slot_canvas.yview)
        self._slot_canvas.configure(yscrollcommand=slot_scroll.set)
        slot_scroll.place(in_=self._slot_canvas, relx=1, rely=0, relheight=1, anchor="ne")

        self._slot_inner = tk.Frame(self._slot_canvas, bg=BG)
        slot_win = self._slot_canvas.create_window(0, 0, window=self._slot_inner, anchor="nw")

        self._slot_inner.bind("<Configure>",
            lambda e: self._slot_canvas.configure(scrollregion=self._slot_canvas.bbox("all")))
        self._slot_canvas.bind("<Configure>",
            lambda e: self._slot_canvas.itemconfig(slot_win, width=e.width))

        def _scroll(e):
            self._slot_canvas.yview_scroll(int(-1 * e.delta / 120), "units")
        self._slot_bind_wheel = lambda e=None: self._slot_canvas.bind_all("<MouseWheel>", _scroll)
        self._slot_unbind_wheel = lambda e=None: self._slot_canvas.unbind_all("<MouseWheel>")
        self._slot_canvas.bind("<Enter>", self._slot_bind_wheel)
        self._slot_canvas.bind("<Leave>", self._slot_unbind_wheel)

        self._render_slots()

    # ── Slots rendern ─────────────────────────────────────────────

    def _render_slots(self):
        for w in self._slot_inner.winfo_children():
            w.destroy()

        n = len(self._slots)
        self._slot_count_lbl.configure(text=f"{n} Slot{'s' if n != 1 else ''}")
        self._roll_btn.configure(state="normal" if n else "disabled")

        if not self._slots:
            tk.Label(self._slot_inner,
                     text="No slots yet.\nClick  + Slot  to add a category or free text,\n"
                          "then  🎲 Randomize  (or press Space) to roll.",
                     fg=TXT2, bg=BG, font=("Segoe UI", 13), justify="center").pack(pady=60)
            self._update_result()
            return

        for i, slot in enumerate(self._slots):
            self._make_slot_card(i, slot)
        self._update_result()

    def _make_slot_card(self, i, slot):
        is_text = slot.get("type") == "text"
        card = tk.Frame(self._slot_inner, bg=SURF2,
                        highlightbackground=BORD_H if slot["locked"] else BORDER,
                        highlightthickness=1)
        card.pack(fill="x", padx=4, pady=5)

        hdr = tk.Frame(card, bg=SURF2)
        hdr.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(hdr, text=f"#{i + 1:02d}", fg=CYAN, bg=SURF2,
                 font=("Consolas", 10, "bold")).pack(side="left")

        if is_text:
            tk.Label(hdr, text="✏ Free Text", fg=CYAN, bg=SURF2,
                     font=("Segoe UI", 11, "bold")).pack(side="left", padx=(10, 0))
        else:
            missing = slot["cat"] not in self.data
            tk.Label(hdr, text=slot["cat"] + ("  (missing)" if missing else ""),
                     fg=RED if missing else PURP, bg=SURF2,
                     font=("Segoe UI", 11, "bold")).pack(side="left", padx=(10, 0))

        btn_f = tk.Frame(hdr, bg=SURF2)
        btn_f.pack(side="right")

        flat_btn(btn_f, "↑", lambda x=i: self._builder_move(x, -1),
                 fg=TXT2, hover_fg=CYAN).pack(side="left", padx=2)
        flat_btn(btn_f, "↓", lambda x=i: self._builder_move(x, 1),
                 fg=TXT2, hover_fg=CYAN).pack(side="left", padx=2)
        if is_text:
            flat_btn(btn_f, "Edit", lambda x=i: self._builder_edit_text(x),
                     fg=PURP, hover=PURP_DIM).pack(side="left", padx=2)
        else:
            w = slot.get("weight", 100)
            flat_btn(btn_f, f"{w}%", lambda x=i: self._builder_cycle_weight(x),
                     fg=CYAN if w < 100 else TXT2, hover_fg=CYAN).pack(side="left", padx=2)
            flat_btn(btn_f, "🔒" if slot["locked"] else "🔓",
                     lambda x=i: self._builder_toggle_lock(x),
                     fg=CYAN if slot["locked"] else TXT2, hover_fg=CYAN).pack(side="left", padx=2)
            flat_btn(btn_f, "Pick", lambda x=i: self._builder_pick(x),
                     fg=PURP, hover=PURP_DIM).pack(side="left", padx=2)
            flat_btn(btn_f, "🎲", lambda x=i: self._builder_reroll(x),
                     fg=PURP, hover=PURP_DIM).pack(side="left", padx=2)
        flat_btn(btn_f, "✕", lambda x=i: self._builder_remove(x),
                 fg=RED, hover=RED_DIM).pack(side="left", padx=2)

        tk.Frame(card, height=1, bg=BORDER).pack(fill="x", padx=12, pady=2)

        if slot["value"]:
            val, fg = slot["value"], TXT
        elif is_text:
            val, fg = "(empty text)", TXT2
        elif slot["cat"] not in self.data or not self.data.get(slot["cat"]):
            val, fg = "(no prompts in this category)", TXT2
        elif slot.get("weight", 100) < 100:
            val, fg = "— skipped this roll —", TXT2
        else:
            val, fg = "— not rolled yet —", TXT2
        tk.Label(card, text=val, fg=fg, bg=SURF2,
                 font=("Consolas", 12), wraplength=860,
                 justify="left", anchor="w").pack(fill="x", padx=12, pady=(4, 10), anchor="w")

        # Mausrad auch über den Karten aktiv halten
        for w in (card, hdr, btn_f) + tuple(card.winfo_children()) + tuple(hdr.winfo_children()):
            w.bind("<Enter>", self._slot_bind_wheel)

    # ── Slot-Aktionen ─────────────────────────────────────────────

    def _roll_slot(self, slot, force=False):
        if slot.get("type") == "text":
            slot["value"] = slot.get("text", "")
            return
        pool = self.data.get(slot["cat"], [])
        if not pool:
            slot["value"] = None
            return
        # Gewichtung: Slot bleibt mit (100 - weight)% Wahrscheinlichkeit leer
        if not force and random.randint(1, 100) > slot.get("weight", 100):
            slot["value"] = None
            return
        slot["value"] = random.choice(pool)

    def _builder_add_slot_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=SURF2, fg=TXT,
                       activebackground=SURF3, activeforeground=CYAN,
                       relief="flat", borderwidth=0)
        menu.add_command(label="✏  Free text...", command=self._builder_add_text_slot)
        if self.categories:
            menu.add_separator()
            for cat in self.categories:
                n = len(self.data.get(cat, []))
                menu.add_command(label=f"{cat}  ({n})",
                                 command=lambda c=cat: self._builder_add_slot(c))
        menu.tk_popup(self._addslot_btn.winfo_rootx(),
                      self._addslot_btn.winfo_rooty() + self._addslot_btn.winfo_height())

    def _builder_add_slot(self, cat):
        slot = {"type": "cat", "cat": cat, "value": None,
                "locked": False, "weight": 100}
        self._roll_slot(slot, force=True)
        self._slots.append(slot)
        self._render_slots()

    def _builder_add_text_slot(self):
        def on_save(text):
            self._slots.append({"type": "text", "text": text, "value": text,
                                "locked": False, "weight": 100})
            self._render_slots()
        self._show_editor(title="Free Text Slot",
                          hint="Fixed text, e.g. quality tags — never rerolled",
                          on_save=on_save)

    def _builder_edit_text(self, i):
        slot = self._slots[i]
        def on_save(text):
            slot["text"] = text
            slot["value"] = text
            self._render_slots()
        self._show_editor(title="Edit Free Text Slot",
                          initial=slot.get("text", ""), on_save=on_save)

    def _builder_cycle_weight(self, i):
        steps = [100, 75, 50, 25]
        cur = self._slots[i].get("weight", 100)
        self._slots[i]["weight"] = steps[(steps.index(cur) + 1) % len(steps)] \
            if cur in steps else 100
        self._render_slots()

    def _builder_remove(self, i):
        self._slots.pop(i)
        self._render_slots()

    def _builder_move(self, i, delta):
        j = i + delta
        if 0 <= j < len(self._slots):
            self._slots[i], self._slots[j] = self._slots[j], self._slots[i]
            self._render_slots()

    def _builder_toggle_lock(self, i):
        self._slots[i]["locked"] = not self._slots[i]["locked"]
        self._render_slots()

    def _builder_reroll(self, i):
        self._roll_slot(self._slots[i], force=True)
        self._render_slots()
        self._record_history()

    def _builder_randomize(self):
        if not self._slots:
            return
        for slot in self._slots:
            if not slot["locked"]:
                self._roll_slot(slot)
        self._render_slots()
        self._record_history()

    # ── Manuelle Auswahl (Pick) ───────────────────────────────────

    def _builder_pick(self, i):
        slot = self._slots[i]
        pool = self.data.get(slot["cat"], [])
        if not pool:
            messagebox.showinfo("Builder",
                f'No prompts in "{slot["cat"]}".', parent=self)
            return
        if self._overlay:
            self._overlay.destroy()

        ov = tk.Frame(self, bg="#020208")
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        ov.lift()
        self._overlay = ov

        card = ctk.CTkFrame(ov, fg_color=SURF, corner_radius=14,
                            border_width=1, border_color=BORD_H,
                            width=680, height=520)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        hdr = tk.Frame(card, bg=SURF2, height=48)
        hdr.pack(side="top", fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"Pick Prompt  —  {slot['cat']}", fg=PURP, bg=SURF2,
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=18, pady=10)

        search_var = tk.StringVar()
        ctk.CTkEntry(card, textvariable=search_var, placeholder_text="  Search...",
                     height=34, fg_color=SURF2, border_color=BORD_H, border_width=1,
                     text_color=TXT, corner_radius=10, font=cfont(12)).pack(
            fill="x", padx=18, pady=(12, 6))

        lb_frame = tk.Frame(card, bg=SURF)
        lb_frame.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        lb = tk.Listbox(lb_frame, bg=SURF2, fg=TXT, font=("Consolas", 11),
                        selectbackground=PURP_MID, selectforeground=TXT,
                        relief="flat", activestyle="none",
                        highlightthickness=1, highlightbackground=BORD_H)
        lb_scroll = tk.Scrollbar(lb_frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=lb_scroll.set)
        lb_scroll.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)

        filtered = {"list": pool}

        def fill():
            q = search_var.get().strip().lower()
            filtered["list"] = [p for p in pool if not q or q in p.lower()]
            lb.delete(0, "end")
            for p in filtered["list"]:
                lb.insert("end", p)
        search_var.trace_add("write", lambda *_: fill())
        fill()

        bot = tk.Frame(card, bg=SURF)
        bot.pack(side="bottom", anchor="e", padx=18, pady=(0, 16))

        def close():
            ov.destroy()
            self._overlay = None

        def use(_=None):
            sel = lb.curselection()
            if not sel:
                return
            slot["value"] = filtered["list"][sel[0]]
            slot["locked"] = True   # manuelle Wahl sperren, damit Randomize sie nicht überschreibt
            close()
            self._render_slots()

        ghost_btn(bot, "Cancel", close, width=100, height=32, font_size=12).pack(side="left", padx=(0, 8))
        neon_btn(bot, "Use", use, color=PURP, bg=PURP_DIM, hover=PURP_MID,
                 width=100, height=32, font_size=12).pack(side="left")

        lb.bind("<Double-Button-1>", use)
        ov.bind("<Escape>", lambda _: close())

    # ── Ergebnis ──────────────────────────────────────────────────

    def _result_text(self):
        parts = [s["value"] for s in self._slots if s["value"]]
        return self._sep_var.get().join(parts) if parts else ""

    def _update_result(self):
        text = self._result_text()
        self._result_lbl.configure(text=text if text else "—",
                                   fg=TXT if text else TXT2)
        state = "normal" if text else "disabled"
        self._copy_result_btn.configure(state=state)
        self._save_result_btn.configure(state=state)

    def _builder_copy_result(self):
        text = self._result_text()
        if text:
            self._copy(text)
            self._toast("Result copied")

    def _builder_save_result_menu(self):
        text = self._result_text()
        if not text:
            return
        if not self.categories:
            messagebox.showinfo("Builder", "No categories available.", parent=self)
            return
        menu = tk.Menu(self, tearoff=0, bg=SURF2, fg=TXT,
                       activebackground=SURF3, activeforeground=GOLD,
                       relief="flat", borderwidth=0)
        for cat in self.categories:
            menu.add_command(label=f"Save to \"{cat}\"",
                             command=lambda c=cat: self._builder_save_result(c))
        menu.tk_popup(self._save_result_btn.winfo_rootx(),
                      self._save_result_btn.winfo_rooty() + self._save_result_btn.winfo_height())

    def _builder_save_result(self, cat):
        text = self._result_text()
        if not text:
            return
        if self._is_dup(cat, text):
            self._toast(f'Already in "{cat}"')
            return
        self.data[cat].append(text)
        save_data(self.data)
        self._refresh()
        self._toast(f'Saved to "{cat}"')

    # ── History ───────────────────────────────────────────────────

    def _record_history(self):
        text = self._result_text()
        if text and (not self._history or self._history[0] != text):
            self._history.insert(0, text)
            del self._history[20:]

    def _open_history(self):
        if self._overlay:
            self._overlay.destroy()

        ov = tk.Frame(self, bg="#020208")
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        ov.lift()
        self._overlay = ov

        card = ctk.CTkFrame(ov, fg_color=SURF, corner_radius=14,
                            border_width=1, border_color=BORD_H,
                            width=800, height=600)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        hdr = tk.Frame(card, bg=SURF2, height=48)
        hdr.pack(side="top", fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"History  —  last {len(self._history)} results",
                 fg=PURP, bg=SURF2,
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=18, pady=10)

        def close():
            h_canvas.unbind_all("<MouseWheel>")
            ov.destroy()
            self._overlay = None

        bot = tk.Frame(card, bg=SURF)
        bot.pack(side="bottom", anchor="e", padx=18, pady=(0, 14))
        ghost_btn(bot, "Close", close, width=100, height=32, font_size=12).pack()

        h_canvas = tk.Canvas(card, bg=BG, highlightthickness=0)
        h_canvas.pack(side="left", fill="both", expand=True, padx=(18, 0), pady=(12, 8))
        h_scroll = tk.Scrollbar(card, orient="vertical", command=h_canvas.yview)
        h_scroll.pack(side="right", fill="y", padx=(4, 16), pady=(12, 8))
        h_canvas.configure(yscrollcommand=h_scroll.set)

        h_inner = tk.Frame(h_canvas, bg=BG)
        h_win = h_canvas.create_window(0, 0, window=h_inner, anchor="nw")
        h_inner.bind("<Configure>",
            lambda e: h_canvas.configure(scrollregion=h_canvas.bbox("all")))
        h_canvas.bind("<Configure>",
            lambda e: h_canvas.itemconfig(h_win, width=e.width))

        def _bind_wheel(e=None):
            h_canvas.bind_all("<MouseWheel>",
                lambda ev: h_canvas.yview_scroll(int(-1 * ev.delta / 120), "units"))
        h_canvas.bind("<Enter>", _bind_wheel)
        h_inner.bind("<Enter>", _bind_wheel)

        if not self._history:
            tk.Label(h_inner, text="No results yet.\nRoll the dice first.",
                     fg=TXT2, bg=BG, font=("Segoe UI", 13), justify="center").pack(pady=60)
        for i, text in enumerate(self._history):
            c = tk.Frame(h_inner, bg=SURF2,
                         highlightbackground=BORDER, highlightthickness=1)
            c.pack(fill="x", padx=4, pady=3)
            h = tk.Frame(c, bg=SURF2)
            h.pack(fill="x", padx=10, pady=(6, 2))
            tk.Label(h, text=f"#{i + 1:02d}", fg=CYAN, bg=SURF2,
                     font=("Consolas", 10, "bold")).pack(side="left")
            flat_btn(h, "Copy", lambda x=text: (self._copy(x), self._toast("Copied")),
                     fg=TXT2, hover_fg=CYAN).pack(side="right")
            tk.Frame(c, height=1, bg=BORDER).pack(fill="x", padx=10, pady=1)
            tk.Label(c, text=text, fg=TXT, bg=SURF2,
                     font=("Consolas", 11), wraplength=680,
                     justify="left", anchor="w").pack(fill="x", padx=10, pady=(2, 8), anchor="w")
            for w in (c, h) + tuple(c.winfo_children()) + tuple(h.winfo_children()):
                w.bind("<Enter>", _bind_wheel)

        ov.bind("<Escape>", lambda _: close())

    # ── Vorlagen ──────────────────────────────────────────────────

    def _builder_templates_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=SURF2, fg=TXT,
                       activebackground=SURF3, activeforeground=CYAN,
                       relief="flat", borderwidth=0)
        menu.add_command(label="Save as template...",
                         command=self._builder_save_template,
                         state="normal" if self._slots else "disabled")
        templates = load_templates()
        if templates:
            menu.add_separator()
            for name in templates:
                menu.add_command(label=f"Load: {name}",
                                 command=lambda n=name: self._builder_load_template(n))
            del_menu = tk.Menu(menu, tearoff=0, bg=SURF2, fg=RED,
                               activebackground=SURF3, activeforeground=RED,
                               relief="flat", borderwidth=0)
            for name in templates:
                del_menu.add_command(label=name,
                                     command=lambda n=name: self._builder_del_template(n))
            menu.add_separator()
            menu.add_cascade(label="Delete template", menu=del_menu)
        menu.tk_popup(self._tpl_btn.winfo_rootx(),
                      self._tpl_btn.winfo_rooty() + self._tpl_btn.winfo_height())

    def _builder_save_template(self):
        def on_save(name):
            templates = load_templates()
            entries = []
            for s in self._slots:
                if s.get("type") == "text":
                    entries.append({"type": "text", "text": s.get("text", "")})
                else:
                    entries.append({"type": "cat", "cat": s["cat"],
                                    "weight": s.get("weight", 100)})
            templates[name] = entries
            save_templates(templates)
            self._toast(f'Template "{name}" saved')
        self._show_name_dialog("Save Template", on_save=on_save, taken={})

    def _builder_load_template(self, name):
        entries = load_templates().get(name, [])
        self._slots = []
        for e in entries:
            if isinstance(e, str):   # altes Format: nur Kategoriename
                e = {"type": "cat", "cat": e, "weight": 100}
            if e.get("type") == "text":
                text = e.get("text", "")
                slot = {"type": "text", "text": text, "value": text,
                        "locked": False, "weight": 100}
            else:
                slot = {"type": "cat", "cat": e.get("cat", ""), "value": None,
                        "locked": False, "weight": e.get("weight", 100)}
                self._roll_slot(slot)
            self._slots.append(slot)
        self._render_slots()
        self._record_history()

    def _builder_del_template(self, name):
        if not messagebox.askyesno("Delete Template?", f'Delete "{name}"?', parent=self):
            return
        templates = load_templates()
        templates.pop(name, None)
        save_templates(templates)

    # ═══════════════════════════════════════════════════════════════
    # TASTENKÜRZEL
    # ═══════════════════════════════════════════════════════════════

    def _bind_shortcuts(self):
        self.bind("<Control-z>", self._shortcut_undo)
        self.bind("<Control-f>", self._shortcut_search)
        self.bind("<Control-c>", self._shortcut_copy)
        self.bind("<space>", self._shortcut_space)

    def _typing(self):
        # True, wenn der Fokus in einem Eingabefeld liegt (Shortcuts unterdrücken)
        return isinstance(self.focus_get(), (tk.Entry, tk.Text, tk.Listbox))

    def _shortcut_undo(self, _):
        if not self._typing():
            self._undo()

    def _shortcut_search(self, _):
        if self._overlay:
            return
        self._switch_view("library")
        self._search_entry.focus_set()
        return "break"

    def _shortcut_copy(self, _):
        if self._typing():
            return
        if self._active_view == "builder":
            self._builder_copy_result()

    def _shortcut_space(self, _):
        if self._typing() or self._overlay or self._active_view != "builder":
            return
        self._builder_randomize()
        return "break"

    # ═══════════════════════════════════════════════════════════════
    # EXPORT / IMPORT
    # ═══════════════════════════════════════════════════════════════

    def _export_data(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="Export prompts",
            defaultextension=".json", initialfile="promptvault_export.json",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showerror("Export", f"Could not write file:\n{e}", parent=self)
            return
        total = sum(len(v) for v in self.data.values())
        self._toast(f"Exported {total} prompts")

    def _import_data(self):
        path = filedialog.askopenfilename(
            parent=self, title="Import prompts",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                imported = json.load(f)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            messagebox.showerror("Import", "Could not read this file as JSON.", parent=self)
            return
        if not isinstance(imported, dict):
            messagebox.showerror("Import",
                "Invalid format — expected  {category: [prompts]}.", parent=self)
            return
        new_cats = added = skipped = 0
        for cat, prompts in imported.items():
            if not isinstance(cat, str) or not isinstance(prompts, list):
                continue
            if cat not in self.data:
                self.data[cat] = []
                new_cats += 1
            for p in prompts:
                if not isinstance(p, str) or not p.strip():
                    continue
                p = p.strip()
                if self._is_dup(cat, p):
                    skipped += 1
                else:
                    self.data[cat].append(p)
                    added += 1
        save_data(self.data)
        self._render_cats()
        if self.selected is None and self.categories:
            self._select(self.categories[0])
        else:
            self._refresh()
        messagebox.showinfo("Import",
            f"{added} prompt{'s' if added != 1 else ''} added\n"
            f"{skipped} duplicate{'s' if skipped != 1 else ''} skipped\n"
            f"{new_cats} new categor{'ies' if new_cats != 1 else 'y'}", parent=self)

    # ═══════════════════════════════════════════════════════════════
    # HILFE
    # ═══════════════════════════════════════════════════════════════

    def _refresh(self):
        self._select(self.selected)
        # Badge-Zähler aktualisieren
        for cat, row in self._cat_rows.items():
            row.update_count(len(self.data.get(cat, [])))


if __name__ == "__main__":
    app = PromptVaultApp()
    app.mainloop()
