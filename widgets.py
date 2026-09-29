"""Wiederverwendbare Widgets und UI-Helfer."""

import os
import re
import tkinter as tk

import customtkinter as ctk

from theme import C, F, cfont, px

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:      # pragma: no cover
    HAS_PIL = False


# ─── Buttons ──────────────────────────────────────────────────────────────────

def ghost_btn(parent, text, cmd, *, color=None, hover=None,
              width=90, height=28, font_size=11, **kw):
    return ctk.CTkButton(
        parent, text=text, command=cmd,
        fg_color="transparent", hover_color=hover or C.SURF3,
        border_width=1, border_color=C.BORD_H,
        text_color=color or C.TXT2, corner_radius=8,
        font=cfont(font_size),
        width=width, height=height, **kw)


def neon_btn(parent, text, cmd, *, color=None, bg=None, hover=None,
             width=120, height=34, font_size=13, state="normal", **kw):
    color = color or C.ACC
    return ctk.CTkButton(
        parent, text=text, command=cmd,
        fg_color=bg or C.ACC_DIM, hover_color=hover or C.ACC_MID,
        border_width=1, border_color=color,
        text_color=color, corner_radius=10,
        font=cfont(font_size, "bold"),
        width=width, height=height, state=state, **kw)


def flat_btn(parent, text, cmd, *, fg=None, bg=None, hover=None, hover_fg=None, tip=None):
    """Leichter tk-Button für Listenkarten — viel schneller als CTkButton."""
    fg = fg or C.TXT2
    bg = bg or C.SURF2
    hover = hover or C.SURF3
    lbl = tk.Label(parent, text=text, fg=fg, bg=bg,
                   font=F(9), padx=10, pady=2, cursor="hand2",
                   highlightbackground=C.BORD_H, highlightthickness=1)
    lbl.bind("<Button-1>", lambda _: cmd())
    lbl.bind("<Enter>", lambda _: lbl.configure(bg=hover, fg=hover_fg or fg))
    lbl.bind("<Leave>", lambda _: lbl.configure(bg=bg, fg=fg))
    if tip:
        Tooltip(lbl, tip)
    return lbl


def chip(parent, text, *, fg=None, bg=None, cmd=None, font_size=9):
    lbl = tk.Label(parent, text=text, fg=fg or C.PURP, bg=bg or C.SURF3,
                   font=F(font_size, bold=True), padx=7, pady=1)
    if cmd:
        lbl.configure(cursor="hand2")
        lbl.bind("<Button-1>", lambda _: cmd())
    return lbl


def styled_menu(parent, active_fg=None):
    return tk.Menu(parent, tearoff=0, bg=C.SURF2, fg=C.TXT,
                   activebackground=C.SURF3, activeforeground=active_fg or C.ACC,
                   relief="flat", borderwidth=0)


def entry(parent, textvariable=None, width=200, height=34, placeholder="", **kw):
    return ctk.CTkEntry(parent, textvariable=textvariable, placeholder_text=placeholder,
                        width=width, height=height,
                        fg_color=C.SURF2, border_color=C.BORD_H, border_width=1,
                        text_color=C.TXT, corner_radius=10, font=cfont(12), **kw)


def option_menu(parent, values, variable, width=180, command=None):
    return ctk.CTkOptionMenu(parent, values=values, variable=variable, command=command,
                             width=width, height=32, font=cfont(12),
                             fg_color=C.SURF3, button_color=C.BORD_H,
                             button_hover_color=C.PURP_MID,
                             dropdown_fg_color=C.SURF2, dropdown_text_color=C.TXT,
                             dropdown_hover_color=C.SURF3,
                             text_color=C.TXT, corner_radius=8)


def checkbox(parent, text, variable, command=None):
    return ctk.CTkCheckBox(parent, text=text, variable=variable, command=command,
                           height=22, checkbox_width=18, checkbox_height=18,
                           fg_color=C.ACC_MID, hover_color=C.ACC_MID, border_color=C.BORD_H,
                           checkmark_color=C.ACC, text_color=C.TXT2, font=cfont(11))


def slider(parent, from_, to, variable, steps=None, width=200, command=None):
    return ctk.CTkSlider(parent, from_=from_, to=to, variable=variable,
                         number_of_steps=steps, width=width, height=16,
                         fg_color=C.SURF3, progress_color=C.ACC_MID,
                         button_color=C.ACC, button_hover_color=C.ACC, command=command)


def section_label(parent, text, **pack):
    lbl = tk.Label(parent, text=text.upper(), fg=C.TXT3, bg=pack.pop("bg", C.SURF),
                   font=F(9, bold=True))
    lbl.pack(anchor="w", **pack)
    return lbl


# ─── Tooltip ──────────────────────────────────────────────────────────────────

class Tooltip:
    def __init__(self, widget, text, delay=600):
        self.widget, self.text, self.delay = widget, text, delay
        self._job = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._job = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._job:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _show(self):
        if self._tip or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, bg=C.SURF3, fg=C.TXT, font=F(9),
                 padx=8, pady=4, highlightbackground=C.BORD_H, highlightthickness=1).pack()

    def _hide(self, _=None):
        self._cancel()
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


# ─── Scrollbarer Bereich ──────────────────────────────────────────────────────

class ScrollFrame(tk.Frame):
    """Canvas + inneres Frame + Scrollbar; Mausrad wirkt, solange die Maus darüber ist."""

    def __init__(self, parent, bg=None, scrollbar=True, **kw):
        bg = bg or C.BG
        super().__init__(parent, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        if scrollbar:
            self.vbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.vbar.pack(side="right", fill="y")
            self.canvas.configure(yscrollcommand=self.vbar.set)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._win, width=e.width))
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)
        self.inner.bind("<Enter>", self._bind_wheel)

    def _on_inner(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _scroll(self, e):
        # Nur scrollen, wenn Inhalt größer als Sichtbereich
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-1 * e.delta / 120), "units")

    def _bind_wheel(self, _=None):
        self.canvas.bind_all("<MouseWheel>", self._scroll)

    def _unbind_wheel(self, _=None):
        self.canvas.unbind_all("<MouseWheel>")

    def bind_children_wheel(self, widget):
        """Kinder rekursiv so binden, dass das Mausrad über Karten weiter scrollt."""
        widget.bind("<Enter>", self._bind_wheel, add="+")
        for ch in widget.winfo_children():
            self.bind_children_wheel(ch)

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.canvas.yview_moveto(0)

    def scroll_top(self):
        self.canvas.yview_moveto(0)

    def destroy(self):
        self._unbind_wheel()
        super().destroy()


# ─── Overlay / Modal ──────────────────────────────────────────────────────────

class Overlay:
    """Modales Overlay im Hauptfenster (kein Toplevel).

    `Overlay(app, width, height)` liefert `.card` (CTkFrame) und `.close()`.
    """

    def __init__(self, app, width=680, height=440, title="", title_color=None,
                 hint=None, on_close=None):
        self.app = app
        self.on_close = on_close
        if getattr(app, "_overlay", None):
            app._overlay.close()
        self.frame = ov = tk.Frame(app, bg=C.OVERLAY)
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        ov.lift()
        app._overlay = self

        # Karte nicht größer als das Fenster (CTk skaliert width/height selbst)
        app.update_idletasks()
        width = min(width, max(320, int((app.winfo_width() - px(40)) / C.dpi)))
        height = min(height, max(240, int((app.winfo_height() - px(40)) / C.dpi)))

        self.card = ctk.CTkFrame(ov, fg_color=C.SURF, corner_radius=14,
                                 border_width=1, border_color=C.BORD_H,
                                 width=width, height=height)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.card.pack_propagate(False)

        self.header = tk.Frame(self.card, bg=C.SURF2, height=px(48))
        self.header.pack(side="top", fill="x", padx=1, pady=(1, 0))
        self.header.pack_propagate(False)
        self.title_lbl = tk.Label(self.header, text=title, fg=title_color or C.ACC, bg=C.SURF2,
                                  font=F(14, bold=True))
        self.title_lbl.pack(side="left", padx=18, pady=10)
        if hint:
            tk.Label(self.header, text=hint, fg=C.TXT2, bg=C.SURF2,
                     font=F(10)).pack(side="left", padx=(0, 18), pady=10)
        flat_btn(self.header, "✕", self.close, fg=C.TXT2, bg=C.SURF2,
                 hover=C.RED_DIM, hover_fg=C.RED).pack(side="right", padx=10)

        self.footer = tk.Frame(self.card, bg=C.SURF)
        self.footer.pack(side="bottom", fill="x", padx=18, pady=(4, 14))

        self.body = tk.Frame(self.card, bg=C.SURF)
        self.body.pack(side="top", fill="both", expand=True, padx=18, pady=(12, 4))

        ov.bind("<Escape>", lambda _: self.close())
        ov.focus_set()
        self._closed = False

    def close(self, _=None):
        if self._closed:
            return
        self._closed = True
        try:
            self.app.unbind_all("<MouseWheel>")
        except Exception:
            pass
        self.frame.destroy()
        if getattr(self.app, "_overlay", None) is self:
            self.app._overlay = None
        if self.on_close:
            self.on_close()

    def buttons(self, *specs):
        """specs: (label, cmd, kind) mit kind in {ghost, neon, purp, gold, red}."""
        made = []
        for label, cmd, kind in specs:
            if kind == "ghost":
                b = ghost_btn(self.footer, label, cmd, width=100, height=32, font_size=12)
            elif kind == "purp":
                b = neon_btn(self.footer, label, cmd, color=C.PURP, bg=C.PURP_DIM,
                             hover=C.PURP_MID, width=110, height=32, font_size=12)
            elif kind == "gold":
                b = neon_btn(self.footer, label, cmd, color=C.GOLD, bg=C.GOLD_DIM,
                             hover=C.GOLD_MID, width=110, height=32, font_size=12)
            elif kind == "red":
                b = neon_btn(self.footer, label, cmd, color=C.RED, bg=C.RED_DIM,
                             hover=C.RED_MID, width=110, height=32, font_size=12)
            else:
                b = neon_btn(self.footer, label, cmd, width=110, height=32, font_size=12)
            b.pack(side="right", padx=(8, 0))
            made.append(b)
        return made


# ─── Textbox mit Syntax-Hervorhebung und Zähler ──────────────────────────────

_HL_PATTERNS = [
    ("weight", re.compile(r"\((?:[^()]|\([^()]*\))*:\s*-?\d+(?:\.\d+)?\s*\)")),
    ("emph",   re.compile(r"\(+[^():]*\)+")),
    ("deemph", re.compile(r"\[[^\[\]]*\]")),
    ("wild",   re.compile(r"__[A-Za-z0-9 _\-/]+__")),
    ("lora",   re.compile(r"<[^<>]+>")),
    ("brk",    re.compile(r"\bBREAK\b")),
]


def make_textbox(parent, height=160, font_size=13, highlight=True):
    tb = ctk.CTkTextbox(parent, font=cfont(font_size, family="Consolas"),
                        wrap="word", fg_color=C.SURF2, height=height,
                        border_color=C.BORD_H, border_width=1,
                        text_color=C.TXT, corner_radius=10,
                        scrollbar_button_color=C.SURF3)
    if highlight:
        raw = tb._textbox
        raw.tag_configure("weight", foreground=C.ACC)
        raw.tag_configure("emph", foreground=C.GOLD)
        raw.tag_configure("deemph", foreground=C.TXT2)
        raw.tag_configure("wild", foreground=C.PURP)
        raw.tag_configure("lora", foreground=C.GREEN)
        raw.tag_configure("brk", foreground=C.RED, font=F(font_size, bold=True, mono=True))
        tb._hl_job = None

        def schedule(_=None):
            if tb._hl_job:
                tb.after_cancel(tb._hl_job)
            tb._hl_job = tb.after(120, lambda: highlight_textbox(tb))
        raw.bind("<KeyRelease>", schedule, add="+")
        tb._hl_schedule = schedule
    return tb


def highlight_textbox(tb):
    tb._hl_job = None
    raw = tb._textbox
    text = raw.get("1.0", "end-1c")
    for tag, _ in _HL_PATTERNS:
        raw.tag_remove(tag, "1.0", "end")
    for tag, pat in _HL_PATTERNS:
        for m in pat.finditer(text):
            raw.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")


def textbox_set(tb, text):
    tb.delete("1.0", "end")
    if text:
        tb.insert("1.0", text)
    if hasattr(tb, "_hl_schedule"):
        highlight_textbox(tb)


def textbox_get(tb):
    return tb.get("1.0", "end-1c")


# ─── Bilder ───────────────────────────────────────────────────────────────────

_THUMB_CACHE = {}


def load_thumb(path, size=56):
    """Gibt ein PhotoImage (gecached) zurück oder None."""
    if not HAS_PIL or not path or not os.path.exists(path):
        return None
    key = (path, size, os.path.getmtime(path))
    if key in _THUMB_CACHE:
        return _THUMB_CACHE[key]
    try:
        img = Image.open(path)
        img.thumbnail((size, size))
        ph = ImageTk.PhotoImage(img)
    except Exception:
        return None
    if len(_THUMB_CACHE) > 400:
        _THUMB_CACHE.clear()
    _THUMB_CACHE[key] = ph
    return ph


# ─── Drag & Drop Umsortierung ────────────────────────────────────────────────

class DragReorder:
    """Ordnet Karten in einem ScrollFrame per Drag-Handle um.

    `register(handle, card, index)` pro Karte, `on_drop(from_idx, to_idx)` wird
    beim Loslassen gerufen.
    """

    def __init__(self, app, on_drop):
        self.app = app
        self.on_drop = on_drop
        self.cards = {}       # card-widget -> index
        self._from = None
        self._target = None
        self._ghost = None

    def reset(self):
        self.cards.clear()
        self._from = self._target = None

    def register(self, handle, card, index):
        self.cards[card] = index
        handle.configure(cursor="fleur")
        handle.bind("<ButtonPress-1>", lambda e, i=index: self._start(e, i))
        handle.bind("<B1-Motion>", self._motion)
        handle.bind("<ButtonRelease-1>", self._release)

    def _card_at_pointer(self):
        w = self.app.winfo_containing(*self.app.winfo_pointerxy())
        while w is not None and w not in self.cards:
            w = getattr(w, "master", None)
        return w

    def _start(self, _e, index):
        self._from = index
        self._target = None

    def _motion(self, _e):
        if self._from is None:
            return
        card = self._card_at_pointer()
        if card is None:
            return
        idx = self.cards[card]
        if idx != self._target:
            self._highlight(None)
            self._target = idx
            self._highlight(card)

    def _highlight(self, card):
        for c, i in self.cards.items():
            if c.winfo_exists():
                c.configure(highlightbackground=C.ACC if c is card else C.BORDER)

    def _release(self, _e):
        if self._from is None:
            return
        src, dst = self._from, self._target
        self._from = self._target = None
        self._highlight(None)
        if dst is not None and dst != src:
            self.on_drop(src, dst)


def fmt_ts(ts):
    """ISO-Zeitstempel → kurz und lesbar."""
    if not ts:
        return "—"
    return ts.replace("T", " ")[:16]
