import customtkinter as ctk
import tkinter as tk
import json
import os
import sys
import random
from tkinter import messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(_APP_DIR, "prompts.json")
CATEGORIES = ["Clothing", "Hairstyle", "Environment", "Appearance", "Position", "Character"]

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


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Fehlende Standardkategorien ergänzen
        changed = False
        for cat in CATEGORIES:
            if cat not in data:
                data[cat] = []
                changed = True
        if changed:
            save_data(data)
        return data
    data = {cat: [] for cat in CATEGORIES}
    save_data(data)
    return data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── Button-Helfer ────────────────────────────────────────────────────────────

def ghost_btn(parent, text, cmd, *, color=TXT2, hover=SURF3,
              width=90, height=28, font_size=11, **kw):
    return ctk.CTkButton(
        parent, text=text, command=cmd,
        fg_color="transparent", hover_color=hover,
        border_width=1, border_color=BORD_H,
        text_color=color, corner_radius=8,
        font=ctk.CTkFont(size=font_size),
        width=width, height=height, **kw)


def neon_btn(parent, text, cmd, *, color=CYAN, bg=CYAN_DIM, hover=CYAN_MID,
             width=120, height=34, font_size=13, state="normal", **kw):
    return ctk.CTkButton(
        parent, text=text, command=cmd,
        fg_color=bg, hover_color=hover,
        border_width=1, border_color=color,
        text_color=color, corner_radius=10,
        font=ctk.CTkFont(size=font_size, weight="bold"),
        width=width, height=height, state=state, **kw)


def danger_btn(parent, text, cmd, *, width=80, height=26, font_size=11, **kw):
    return ctk.CTkButton(
        parent, text=text, command=cmd,
        fg_color=RED_DIM, hover_color=RED_MID,
        border_width=1, border_color=RED,
        text_color=RED, corner_radius=8,
        font=ctk.CTkFont(size=font_size),
        width=width, height=height, **kw)


# ─── Kategorie-Zeile ──────────────────────────────────────────────────────────

class CategoryRow(tk.Frame):
    """Einfache Kategorie-Schaltfläche ohne customtkinter-Overhead."""
    def __init__(self, parent, label, count, command, selected=False):
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

        self._build_sidebar()
        self._build_content()
        # Erste Kategorie automatisch auswählen
        if CATEGORIES:
            self._select(CATEGORIES[0])

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

        # Label
        tk.Label(sb, text="CATEGORIES", fg=TXT3, bg=SURF,
                 font=("Segoe UI", 9, "bold")).pack(side="top", anchor="w", padx=18, pady=(10, 4))

        # Kategorie-Canvas (scrollbar)
        self._cat_canvas = tk.Canvas(sb, bg=SURF, highlightthickness=0)
        self._cat_canvas.pack(side="top", fill="both", expand=True, padx=0)

        self._cat_inner = tk.Frame(self._cat_canvas, bg=SURF)
        self._cat_win = self._cat_canvas.create_window(0, 0, window=self._cat_inner, anchor="nw")

        self._cat_inner.bind("<Configure>",
            lambda e: self._cat_canvas.configure(scrollregion=self._cat_canvas.bbox("all")))
        self._cat_canvas.bind("<Configure>",
            lambda e: self._cat_canvas.itemconfig(self._cat_win, width=e.width))
        self._cat_canvas.bind_all("<MouseWheel>",
            lambda e: self._cat_canvas.yview_scroll(int(-1 * e.delta / 120), "units"))

        self._render_cats()

    def _render_cats(self):
        for w in self._cat_inner.winfo_children():
            w.destroy()
        self._cat_rows.clear()
        for cat in CATEGORIES:
            count = len(self.data.get(cat, []))
            sel = cat == self.selected
            row = CategoryRow(self._cat_inner, cat, count,
                               command=lambda c=cat: self._select(c),
                               selected=sel)
            row.pack(fill="x", padx=6, pady=2)
            self._cat_rows[cat] = row

    def _select(self, cat):
        if self.selected and self.selected in self._cat_rows:
            self._cat_rows[self.selected].set_selected(False)
        self.selected = cat
        if cat in self._cat_rows:
            self._cat_rows[cat].set_selected(True)

        n = len(self.data.get(cat, []))
        self._title_lbl.configure(text=cat)
        self._count_lbl.configure(text=f"{n} Prompt{'s' if n != 1 else ''}")
        self._add_btn.configure(state="normal")
        self._rnd_btn.configure(state="normal" if n > 0 else "disabled")
        self._search_var.set("")
        self._render_prompts()

    # ═══════════════════════════════════════════════════════════════
    # CONTENT
    # ═══════════════════════════════════════════════════════════════

    def _build_content(self):
        content = tk.Frame(self, bg=BG)
        content.pack(side="left", fill="both", expand=True)

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

        self._add_btn = neon_btn(right_grp, "+ Prompt", self._add_prompt,
                                  width=108, height=34, font_size=12, state="disabled")
        self._add_btn.pack(side="right", pady=16, padx=(6, 0))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._render_prompts())
        search = ctk.CTkEntry(right_grp, textvariable=self._search_var,
                               placeholder_text="  Search...",
                               width=165, height=34,
                               fg_color=SURF2, border_color=BORD_H, border_width=1,
                               text_color=TXT, corner_radius=10,
                               font=ctk.CTkFont(size=12))
        search.pack(side="right", pady=16)

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

    def _render_prompts(self):
        for w in self._list_inner.winfo_children():
            w.destroy()

        if not self.selected:
            return

        q = self._search_var.get().strip().lower()
        prompts = self.data.get(self.selected, [])
        filtered = [(i, p) for i, p in enumerate(prompts) if not q or q in p.lower()]

        if not filtered:
            msg = f'No results for "{self._search_var.get()}"' if q \
                  else "No prompts yet.\nClick  + Prompt  to add one."
            tk.Label(self._list_inner, text=msg, fg=TXT2, bg=BG,
                      font=("Segoe UI", 13)).pack(pady=60)
            return

        for row_i, (real_i, prompt) in enumerate(filtered):
            self._make_card(row_i, real_i, prompt)

    def _make_card(self, row_i, real_i, prompt):
        card = tk.Frame(self._list_inner, bg=SURF2,
                         highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", padx=4, pady=5)

        # Header
        hdr = tk.Frame(card, bg=SURF2)
        hdr.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(hdr, text=f"#{real_i + 1:02d}", fg=CYAN, bg=SURF2,
                  font=("Consolas", 10, "bold")).pack(side="left")

        btn_f = tk.Frame(hdr, bg=SURF2)
        btn_f.pack(side="right")

        ghost_btn(btn_f, "Copy",    lambda p=prompt: self._copy(p),
                  width=76, height=24, font_size=10).pack(side="left", padx=2)
        ghost_btn(btn_f, "Edit",  lambda i=real_i: self._edit_prompt(i),
                  color=PURP, hover=PURP_DIM, width=88, height=24, font_size=10).pack(side="left", padx=2)
        danger_btn(btn_f, "Delete",   lambda i=real_i: self._del_prompt(i),
                   width=74, height=24, font_size=10).pack(side="left", padx=2)

        # Trennlinie
        tk.Frame(card, height=1, bg=BORDER).pack(fill="x", padx=12, pady=2)

        # Text
        tk.Label(card, text=prompt, fg=TXT, bg=SURF2,
                  font=("Consolas", 12), wraplength=900,
                  justify="left", anchor="w").pack(fill="x", padx=12, pady=(4, 10), anchor="w")

    # ═══════════════════════════════════════════════════════════════
    # PROMPT EDITOR (In-Window Overlay — kein Toplevel)
    # ═══════════════════════════════════════════════════════════════

    def _show_editor(self, title="Prompt hinzufügen", initial="", on_save=None):
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
                             width=680, height=400)
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

    def _add_prompt(self):
        def on_save(text):
            self.data[self.selected].append(text)
            save_data(self.data)
            self._refresh()
        self._show_editor(title=f"Add Prompt  —  {self.selected}", on_save=on_save)

    def _edit_prompt(self, index):
        cur = self.data[self.selected][index]
        def on_save(text):
            self.data[self.selected][index] = text
            save_data(self.data)
            self._refresh()
        self._show_editor(title="Edit Prompt", initial=cur, on_save=on_save)

    def _del_prompt(self, index):
        p = self.data[self.selected][index]
        prev = (p[:70] + "...") if len(p) > 70 else p
        if messagebox.askyesno("Delete?", f'"{prev}"', parent=self):
            self.data[self.selected].pop(index)
            save_data(self.data)
            self._refresh()

    def _copy(self, prompt):
        self.clipboard_clear()
        self.clipboard_append(prompt)

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
        ctk.CTkOptionMenu(ctrl, values=CATEGORIES, variable=cat_var,
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
                ghost_btn(h, "Copy",
                          lambda x=p: (self.clipboard_clear(), self.clipboard_append(x)),
                          width=76, height=22, font_size=10).pack(side="right")

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
