"""Library-Ansicht: Prompt-Liste, Karten, CRUD, Mehrfachauswahl, Detailansicht,
Random-Picker und Tag-Filter."""

import os
import random
import tkinter as tk
from tkinter import messagebox

from storage import make_prompt, now_iso, split_batch, estimate_tokens, normalize_tags
from theme import C, F, px
from widgets import (ghost_btn, neon_btn, flat_btn, chip, styled_menu, entry, option_menu,
                     checkbox, ScrollFrame, Overlay, DragReorder, load_thumb, fmt_ts,
                     make_textbox, textbox_set, Tooltip)

SORT_OPTIONS = [
    ("manual", "Manual"),
    ("alpha", "A → Z"),
    ("used", "Most used"),
    ("recent", "Recently used"),
    ("newest", "Newest"),
    ("longest", "Longest"),
]


class LibraryMixin:

    # ═══════════════════════════════════════════════════════════════
    # AUFBAU
    # ═══════════════════════════════════════════════════════════════

    def _build_content(self):
        content = tk.Frame(self._main, bg=C.BG)
        content.pack(fill="both", expand=True)
        self._lib_view = content

        # ── Topbar ────────────────────────────────────────────────
        top = tk.Frame(content, bg=C.SURF, height=px(66))
        top.pack(side="top", fill="x")
        top.pack_propagate(False)

        left_grp = tk.Frame(top, bg=C.SURF)
        left_grp.pack(side="left", fill="y", padx=22)

        self._title_lbl = tk.Label(left_grp, text="Select Category",
                                   fg=C.TXT, bg=C.SURF, font=F(17, bold=True))
        self._title_lbl.pack(side="top", anchor="w", pady=(14, 0))
        self._count_lbl = tk.Label(left_grp, text="", fg=C.TXT2, bg=C.SURF, font=F(10))
        self._count_lbl.pack(side="top", anchor="w")

        right_grp = tk.Frame(top, bg=C.SURF)
        right_grp.pack(side="right", fill="y", padx=18)

        self._rnd_btn = neon_btn(right_grp, "  Random", self._open_random,
                                 color=C.PURP, bg=C.PURP_DIM, hover=C.PURP_MID,
                                 width=110, height=34, font_size=12, state="disabled")
        self._rnd_btn.pack(side="right", pady=16, padx=(6, 0))
        self._batch_btn = neon_btn(right_grp, "+ Batch", self._add_batch,
                                   width=92, height=34, font_size=12, state="disabled")
        self._batch_btn.pack(side="right", pady=16, padx=(6, 0))
        self._add_btn = neon_btn(right_grp, "+ Prompt", self._add_prompt,
                                 width=100, height=34, font_size=12, state="disabled")
        self._add_btn.pack(side="right", pady=16, padx=(6, 0))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        self._search_entry = entry(right_grp, self._search_var, width=170,
                                   placeholder="  Search…  (tag:xyz)")
        self._search_entry.pack(side="right", pady=16)
        Tooltip(self._search_entry, "Ctrl+F · searches text, title, note and tags\n"
                                    "tag:name filters by tag")

        self._all_var = tk.BooleanVar(value=False)
        checkbox(right_grp, "All", self._all_var, self._render_prompts).pack(
            side="right", pady=16, padx=(0, 8))

        self._fav_btn = ghost_btn(right_grp, "☆", self._toggle_fav_filter,
                                  width=38, height=34, font_size=15)
        self._fav_btn.pack(side="right", pady=16, padx=(0, 6))
        Tooltip(self._fav_btn, "Show favorites only")

        self._sort_var = tk.StringVar(value=self._sort_label(self.store.get("prompt_sort", "manual")))
        self._sort_menu = option_menu(right_grp, [l for _, l in SORT_OPTIONS], self._sort_var,
                                      width=124, command=lambda *_: self._on_sort_change())
        self._sort_menu.pack(side="right", pady=16, padx=(0, 6))

        # ── Tag-Leiste + Bulk-Leiste ──────────────────────────────
        self._tag_bar = tk.Frame(content, bg=C.BG)
        self._tag_bar.pack(side="top", fill="x", padx=18, pady=(8, 0))
        self._bulk_bar = tk.Frame(content, bg=C.SURF2, highlightbackground=C.ACC, highlightthickness=1)
        # wird nur bei Auswahl gepackt

        # ── Prompt-Liste ──────────────────────────────────────────
        self._list = ScrollFrame(content, bg=C.BG)
        self._list.pack(side="top", fill="both", expand=True, padx=14, pady=12)
        self._drag = DragReorder(self, self._on_prompt_drop)
        self._card_by_id = {}

        tk.Label(self._list.inner, text="← Select a category on the left",
                 fg=C.TXT3, bg=C.BG, font=F(14)).pack(pady=80)

    @staticmethod
    def _sort_label(key):
        return dict(SORT_OPTIONS).get(key, "Manual")

    def _sort_key(self):
        lab = self._sort_var.get()
        for k, l in SORT_OPTIONS:
            if l == lab:
                return k
        return "manual"

    def _on_sort_change(self):
        self.store.set("prompt_sort", self._sort_key())
        self._render_prompts()

    # ═══════════════════════════════════════════════════════════════
    # AUSWAHL DER KATEGORIE
    # ═══════════════════════════════════════════════════════════════

    def _select(self, cat):
        if self.selected and self.selected in self._cat_rows:
            self._cat_rows[self.selected].set_selected(False)
        prev = self.selected
        self.selected = cat
        if prev != cat:
            self._clear_selection(render=False)
            self._tag_filter.clear()
        if cat is None:
            self._title_lbl.configure(text="Select Category")
            self._count_lbl.configure(text="")
            for b in (self._add_btn, self._batch_btn, self._rnd_btn):
                b.configure(state="disabled")
            self._search_var.set("")
            self._render_prompts()
            return
        if cat in self._cat_rows:
            self._cat_rows[cat].set_selected(True)
        n = len(self.data.get(cat, []))
        self._title_lbl.configure(text=cat)
        self._count_lbl.configure(text=self._cat_stats(cat))
        self._add_btn.configure(state="normal")
        self._batch_btn.configure(state="normal")
        self._rnd_btn.configure(state="normal" if n > 0 else "disabled")
        if prev != cat:
            self._search_var.set("")
        self._render_prompts()

    def _cat_stats(self, cat):
        lst = self.data.get(cat, [])
        n = len(lst)
        favs = sum(1 for p in lst if p.get("fav"))
        s = f"{n} Prompt{'s' if n != 1 else ''}"
        if favs:
            s += f"  ·  {favs} ★"
        tags = {t for p in lst for t in p.get("tags", [])}
        if tags:
            s += f"  ·  {len(tags)} tag{'s' if len(tags) != 1 else ''}"
        return s

    # ═══════════════════════════════════════════════════════════════
    # RENDERN
    # ═══════════════════════════════════════════════════════════════

    def _on_search(self):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(250, self._render_prompts)

    def _visible_items(self):
        """[(cat, index, prompt)] nach Filter und Sortierung."""
        q_raw = self._search_var.get().strip().lower()
        tag_terms = []
        words = []
        for tok in q_raw.split():
            if tok.startswith("tag:") and len(tok) > 4:
                tag_terms.append(tok[4:])
            else:
                words.append(tok)
        global_mode = self._all_var.get()
        cats = self.categories if global_mode else ([self.selected] if self.selected else [])

        def matches(p):
            if self._fav_filter and not p.get("fav"):
                return False
            ptags = p.get("tags", [])
            if self._tag_filter and not self._tag_filter.issubset(ptags):
                return False
            if tag_terms and not all(any(t in pt for pt in ptags) for t in tag_terms):
                return False
            if words:
                hay = " ".join([p["text"], p.get("title", ""), p.get("note", ""),
                                " ".join(ptags), " ".join(p.get("variants", []))]).lower()
                if not all(w in hay for w in words):
                    return False
            return True

        items = [(cat, i, p) for cat in cats
                 for i, p in enumerate(self.data.get(cat, [])) if matches(p)]
        key = self._sort_key()
        if key == "alpha":
            items.sort(key=lambda t: (t[2].get("title") or t[2]["text"]).lower())
        elif key == "used":
            items.sort(key=lambda t: t[2].get("uses", 0), reverse=True)
        elif key == "recent":
            items.sort(key=lambda t: t[2].get("last_used") or "", reverse=True)
        elif key == "newest":
            items.sort(key=lambda t: t[2].get("created") or "", reverse=True)
        elif key == "longest":
            items.sort(key=lambda t: len(t[2]["text"]), reverse=True)
        return items

    def _drag_enabled(self):
        return (self._sort_key() == "manual" and not self._all_var.get()
                and not self._search_var.get().strip() and not self._fav_filter
                and not self._tag_filter)

    def _render_prompts(self):
        if self._search_job:
            self.after_cancel(self._search_job)
            self._search_job = None
        if self._render_job:
            self.after_cancel(self._render_job)
            self._render_job = None
        self._render_queue = []
        self._list.clear()
        self._drag.reset()
        self._card_by_id.clear()
        self._render_tag_bar()
        self._render_bulk_bar()

        if not self._all_var.get() and not self.selected:
            return

        items = self._visible_items()
        self._visible_cache = items
        if not items:
            q = self._search_var.get().strip()
            if q:
                msg = f'No results for "{q}"'
            elif self._fav_filter:
                msg = "No favorites yet.\nClick  ☆  on a prompt to star it."
            elif self._tag_filter:
                msg = "No prompts with these tags."
            else:
                msg = "No prompts yet.\nClick  + Prompt  to add one  (Ctrl+N)."
            tk.Label(self._list.inner, text=msg, fg=C.TXT2, bg=C.BG, font=F(13)).pack(pady=60)
            return

        show_cat = self._all_var.get()
        self._render_queue = [(n, cat, i, p, show_cat) for n, (cat, i, p) in enumerate(items)]
        self._render_batch()

    def _render_batch(self):
        self._render_job = None
        chunk, self._render_queue = self._render_queue[:30], self._render_queue[30:]
        for n, cat, real_i, prompt, show_cat in chunk:
            self._make_card(n, cat, real_i, prompt, show_cat)
        if self._render_queue:
            self._render_job = self.after(10, self._render_batch)

    def _make_card(self, n, cat, real_i, p, show_cat=False):
        pid = p["id"]
        selected = pid in self._selection
        card = tk.Frame(self._list.inner, bg=C.SEL if selected else C.SURF2,
                        highlightbackground=C.ACC if selected else C.BORDER, highlightthickness=1)
        card.pack(fill="x", padx=4, pady=5)
        bg = C.SEL if selected else C.SURF2
        self._card_by_id[pid] = card

        hdr = tk.Frame(card, bg=bg)
        hdr.pack(fill="x", padx=10, pady=(7, 3))

        # Checkbox (Mehrfachauswahl)
        cb = tk.Label(hdr, text="☑" if selected else "☐", fg=C.ACC if selected else C.TXT2,
                      bg=bg, font=F(12), cursor="hand2")
        cb.pack(side="left", padx=(0, 6))
        cb.bind("<Button-1>", lambda _e, i=pid: self._toggle_select(i))

        # Drag-Griff
        if self._drag_enabled():
            grip = tk.Label(hdr, text="⋮⋮", fg=C.TXT3, bg=bg, font=F(11))
            grip.pack(side="left", padx=(0, 6))
            self._drag.register(grip, card, real_i)

        tk.Label(hdr, text=f"#{real_i + 1:02d}", fg=C.ACC, bg=bg,
                 font=F(10, bold=True, mono=True)).pack(side="left")
        if show_cat:
            chip(hdr, cat, cmd=lambda c=cat: (self._all_var.set(False), self._select(c))).pack(
                side="left", padx=(8, 0))
        if p.get("title"):
            tk.Label(hdr, text=p["title"], fg=C.TXT, bg=bg, font=F(11, bold=True)).pack(
                side="left", padx=(10, 0))

        btn_f = tk.Frame(hdr, bg=bg)
        btn_f.pack(side="right")
        fav = p.get("fav")
        flat_btn(btn_f, "★" if fav else "☆", lambda i=pid: self._toggle_fav(i),
                 fg=C.GOLD if fav else C.TXT2, bg=bg, hover_fg=C.GOLD).pack(side="left", padx=2)
        flat_btn(btn_f, "Copy", lambda i=pid: self._copy_prompt(i),
                 fg=C.TXT2, bg=bg, hover_fg=C.ACC).pack(side="left", padx=2)
        flat_btn(btn_f, "Move", lambda i=pid: self._move_prompt_menu([i]),
                 fg=C.TXT2, bg=bg, hover_fg=C.ACC).pack(side="left", padx=2)
        flat_btn(btn_f, "Edit", lambda i=pid: self._edit_prompt(i),
                 fg=C.PURP, bg=bg, hover=C.PURP_DIM).pack(side="left", padx=2)
        flat_btn(btn_f, "Delete", lambda i=pid: self._del_prompts([i]),
                 fg=C.RED, bg=bg, hover=C.RED_DIM).pack(side="left", padx=2)

        tk.Frame(card, height=1, bg=C.BORDER).pack(fill="x", padx=10, pady=2)

        body = tk.Frame(card, bg=bg)
        body.pack(fill="x", padx=10, pady=(3, 6))

        if p.get("image") and self.store.get("show_thumbnails", True):
            ph = load_thumb(self.store.image_path(p["image"]), px(56))
            if ph:
                il = tk.Label(body, image=ph, bg=bg, cursor="hand2")
                il.image = ph
                il.pack(side="left", padx=(0, 10), anchor="n")
                il.bind("<Button-1>", lambda _e, i=pid: self._open_image(i))

        txt = tk.Label(body, text=p["text"], fg=C.TXT, bg=bg, font=F(12, mono=True),
                       wraplength=px(860), justify="left", anchor="w", cursor="hand2")
        txt.pack(fill="x", anchor="w")
        txt.bind("<Button-1>", lambda _e, i=pid: self._open_detail(i))
        txt.bind("<Double-Button-1>", lambda _e, i=pid: self._edit_prompt(i))

        # Fußzeile: Tags, Varianten, Nutzung
        foot = tk.Frame(card, bg=bg)
        has_foot = False
        for t in p.get("tags", []):
            chip(foot, "#" + t, fg=C.ACC if t in self._tag_filter else C.TXT2,
                 bg=bg if t not in self._tag_filter else C.ACC_DIM,
                 cmd=lambda tt=t: self._toggle_tag_filter(tt)).pack(side="left", padx=(0, 4))
            has_foot = True
        if p.get("variants"):
            chip(foot, f"+{len(p['variants'])} variant{'s' if len(p['variants']) != 1 else ''}",
                 fg=C.PURP, bg=bg).pack(side="left", padx=(0, 4))
            has_foot = True
        if p.get("note"):
            chip(foot, "✎ note", fg=C.TXT2, bg=bg,
                 cmd=lambda i=pid: self._open_detail(i)).pack(side="left", padx=(0, 4))
            has_foot = True
        if p.get("uses"):
            tk.Label(foot, text=f"used {p['uses']}×", fg=C.TXT3, bg=bg, font=F(9)).pack(side="right")
            has_foot = True
        if p.get("weight", 5) != 5:
            tk.Label(foot, text=f"weight {p['weight']}/10", fg=C.TXT3, bg=bg, font=F(9)).pack(
                side="right", padx=(0, 10))
            has_foot = True
        if has_foot:
            foot.pack(fill="x", padx=10, pady=(0, 7))

        # Rechtsklick-Menü + Mausrad
        for w in (card, hdr, body, txt, foot):
            w.bind("<Button-3>", lambda e, i=pid: self._card_menu(e, i))
        self._list.bind_children_wheel(card)

    # ── Tag-Leiste ────────────────────────────────────────────────

    def _all_tags(self, cats=None):
        cats = cats or (self.categories if self._all_var.get() else [self.selected])
        counts = {}
        for c in cats:
            for p in self.data.get(c, []):
                for t in p.get("tags", []):
                    counts[t] = counts.get(t, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    def _render_tag_bar(self):
        for w in self._tag_bar.winfo_children():
            w.destroy()
        if not self.selected and not self._all_var.get():
            return
        tags = self._all_tags()
        if not tags:
            return
        tk.Label(self._tag_bar, text="TAGS", fg=C.TXT3, bg=C.BG, font=F(9, bold=True)).pack(
            side="left", padx=(0, 8))
        for t, n in tags[:30]:
            on = t in self._tag_filter
            chip(self._tag_bar, f"#{t} {n}", fg=C.ACC if on else C.TXT2,
                 bg=C.ACC_DIM if on else C.SURF2,
                 cmd=lambda tt=t: self._toggle_tag_filter(tt)).pack(side="left", padx=(0, 4), pady=2)
        if self._tag_filter:
            chip(self._tag_bar, "✕ clear", fg=C.RED, bg=C.SURF2,
                 cmd=lambda: (self._tag_filter.clear(), self._render_prompts())).pack(side="left", padx=(6, 0))

    def _toggle_tag_filter(self, tag):
        if tag in self._tag_filter:
            self._tag_filter.discard(tag)
        else:
            self._tag_filter.add(tag)
        self._render_prompts()

    # ── Favoriten ─────────────────────────────────────────────────

    def _toggle_fav(self, pid):
        found = self._find_prompt(pid)
        if not found:
            return
        _, _, p = found
        p["fav"] = not p.get("fav")
        self._save()
        self._refresh()

    def _toggle_fav_filter(self):
        self._fav_filter = not self._fav_filter
        self._fav_btn.configure(text="★" if self._fav_filter else "☆",
                                text_color=C.GOLD if self._fav_filter else C.TXT2,
                                border_color=C.GOLD if self._fav_filter else C.BORD_H)
        self._render_prompts()

    # ═══════════════════════════════════════════════════════════════
    # MEHRFACHAUSWAHL
    # ═══════════════════════════════════════════════════════════════

    def _toggle_select(self, pid):
        if pid in self._selection:
            self._selection.discard(pid)
        else:
            self._selection.add(pid)
        self._render_prompts()

    def _select_all_visible(self):
        ids = {p["id"] for _, _, p in getattr(self, "_visible_cache", [])}
        if ids and ids.issubset(self._selection):
            self._selection.clear()
        else:
            self._selection |= ids
        self._render_prompts()

    def _clear_selection(self, render=True):
        self._selection.clear()
        if render:
            self._render_prompts()

    def _render_bulk_bar(self):
        for w in self._bulk_bar.winfo_children():
            w.destroy()
        if not self._selection:
            self._bulk_bar.pack_forget()
            return
        self._bulk_bar.pack(side="top", fill="x", padx=18, pady=(8, 0), before=self._list)
        n = len(self._selection)
        tk.Label(self._bulk_bar, text=f"  {n} selected", fg=C.ACC, bg=C.SURF2,
                 font=F(11, bold=True)).pack(side="left", padx=8, pady=6)
        ids = list(self._selection)
        for label, cmd, fg in (
                ("Copy", lambda: self._copy_prompts(ids), C.ACC),
                ("Move…", lambda: self._move_prompt_menu(ids), C.ACC),
                ("★ Star", lambda: self._bulk_fav(ids, True), C.GOLD),
                ("☆ Unstar", lambda: self._bulk_fav(ids, False), C.TXT2),
                ("Tag…", lambda: self._bulk_tag(ids), C.PURP),
                ("Delete", lambda: self._del_prompts(ids), C.RED),
        ):
            flat_btn(self._bulk_bar, label, cmd, fg=fg, bg=C.SURF2, hover=C.SURF3).pack(
                side="left", padx=3, pady=6)
        flat_btn(self._bulk_bar, "Clear", self._clear_selection, fg=C.TXT2, bg=C.SURF2).pack(
            side="right", padx=8, pady=6)
        flat_btn(self._bulk_bar, "Select all (Ctrl+A)", self._select_all_visible,
                 fg=C.TXT2, bg=C.SURF2).pack(side="right", padx=3, pady=6)

    def _bulk_fav(self, ids, value):
        for pid in ids:
            f = self._find_prompt(pid)
            if f:
                f[2]["fav"] = value
        self._save()
        self._refresh()

    def _bulk_tag(self, ids):
        def on_save(text):
            tags = normalize_tags(text)
            remove = [t[1:] for t in tags if t.startswith("-")]
            add = [t for t in tags if not t.startswith("-")]
            for pid in ids:
                f = self._find_prompt(pid)
                if not f:
                    continue
                p = f[2]
                cur = [t for t in p.get("tags", []) if t not in remove]
                for t in add:
                    if t not in cur:
                        cur.append(t)
                p["tags"] = cur
            self._save()
            self._refresh()
            self._toast(f"Tags updated on {len(ids)} prompts")
        self._show_name_dialog("Add tags (comma-separated, -tag removes)", on_save=on_save,
                               taken={}, placeholder="anime, realistic, -old")

    # ═══════════════════════════════════════════════════════════════
    # CRUD
    # ═══════════════════════════════════════════════════════════════

    def _find_prompt(self, pid):
        for cat, lst in self.data.items():
            for i, p in enumerate(lst):
                if p["id"] == pid:
                    return cat, i, p
        return None

    def _is_dup(self, cat, text, skip_id=None):
        low = text.strip().lower()
        return any(p["text"].lower() == low for p in self.data.get(cat, []) if p["id"] != skip_id)

    def _find_dup_anywhere(self, text, skip_id=None):
        low = text.strip().lower()
        for cat, lst in self.data.items():
            for p in lst:
                if p["id"] != skip_id and p["text"].lower() == low:
                    return cat
        return None

    def _add_prompt(self):
        if not self.selected:
            return
        cat = self.selected

        def on_save(p):
            if self._is_dup(cat, p["text"]) and not messagebox.askyesno(
                    "Duplicate", f'This prompt already exists in "{cat}".\nAdd anyway?', parent=self):
                return
            self.data[cat].append(p)
            self._save()
            self._refresh()
            self._toast("Prompt added")
        self._show_prompt_editor(title=f"Add Prompt  —  {cat}", cat=cat, on_save=on_save)

    def _add_batch(self):
        if not self.selected:
            return
        cat = self.selected

        def on_save(text):
            prompts = split_batch(text)
            if not prompts:
                return
            added = skipped = 0
            for t in prompts:
                if self._is_dup(cat, t):
                    skipped += 1
                else:
                    self.data[cat].append(make_prompt(t))
                    added += 1
            self._save()
            self._refresh()
            msg = f"{added} prompt{'s' if added != 1 else ''} added to \"{cat}\"."
            if skipped:
                msg += f"\n{skipped} duplicate{'s' if skipped != 1 else ''} skipped."
            messagebox.showinfo("Batch", msg, parent=self)
        self._show_editor(title=f"Add Batch  —  {cat}",
                          hint="Numbered (1: … 2. … 3) …) or one prompt per line",
                          on_save=on_save)

    def _edit_prompt(self, pid):
        found = self._find_prompt(pid)
        if not found:
            return
        cat, index, cur = found

        def on_save(p):
            if p["text"] != cur["text"] and self._is_dup(cat, p["text"], skip_id=pid) and \
                    not messagebox.askyesno("Duplicate",
                                            f'This prompt already exists in "{cat}".\nSave anyway?',
                                            parent=self):
                return
            self.data[cat][index] = p
            self._save()
            self._refresh()
        self._show_prompt_editor(title="Edit Prompt", cat=cat, prompt=cur, on_save=on_save)

    def _del_prompts(self, ids, confirm=None):
        entries = []
        for pid in ids:
            f = self._find_prompt(pid)
            if f:
                entries.append(f)
        if not entries:
            return
        if confirm is None:
            confirm = self.store.get("confirm_delete", True)
        if confirm:
            if len(entries) == 1:
                t = entries[0][2]["text"]
                prev = (t[:70] + "...") if len(t) > 70 else t
                msg = f'"{prev}"'
            else:
                msg = f"Delete {len(entries)} prompts?"
            if not messagebox.askyesno("Delete?", msg, parent=self):
                return
        # Von hinten löschen, damit Indizes stabil bleiben
        entries.sort(key=lambda e: (e[0], -e[1]))
        undo = []
        for cat, idx, p in entries:
            self.data[cat].pop(idx)
            undo.append((cat, idx, p))
            self._trash.insert(0, {"cat": cat, "prompt": p, "deleted": now_iso()})
            self._selection.discard(p["id"])
        self._trash = self.store.save_trash(self._trash)
        self._push_undo(("prompts", undo))
        self._save()
        self._refresh()
        self._toast(f"Deleted {len(entries)}  —  Ctrl+Z to undo")

    def _move_prompt_menu(self, ids):
        srcs = {self._find_prompt(i)[0] for i in ids if self._find_prompt(i)}
        others = [c for c in self.categories if not (len(srcs) == 1 and c in srcs)]
        if not others:
            self._toast("No other category to move to")
            return
        menu = styled_menu(self)
        for target in others:
            menu.add_command(label=f"Move to \"{target}\"",
                             command=lambda t=target: self._move_prompts(ids, t))
        menu.add_separator()
        menu.add_command(label="＋ New category…",
                         command=lambda: self._show_name_dialog(
                             "New Category", on_save=lambda name: (
                                 self.data.__setitem__(name, []), self._render_cats(),
                                 self._move_prompts(ids, name))))
        menu.tk_popup(*self.winfo_pointerxy())

    def _move_prompts(self, ids, target):
        if target not in self.data:
            self.data[target] = []
        moved = 0
        for pid in ids:
            f = self._find_prompt(pid)
            if not f or f[0] == target:
                continue
            cat, idx, p = f
            if self._is_dup(target, p["text"]) and not messagebox.askyesno(
                    "Duplicate", f'"{p["text"][:60]}" already exists in "{target}".\nMove anyway?',
                    parent=self):
                continue
            self.data[cat].pop(idx)
            self.data[target].append(p)
            moved += 1
        self._selection.clear()
        self._save()
        self._refresh()
        self._toast(f'Moved {moved} to "{target}"')

    def _duplicate_prompt(self, pid):
        f = self._find_prompt(pid)
        if not f:
            return
        cat, idx, p = f
        copy = make_prompt(p["text"], title=p.get("title", ""), tags=list(p.get("tags", [])),
                           note=p.get("note", ""), weight=p.get("weight", 5),
                           variants=list(p.get("variants", [])))
        self.data[cat].insert(idx + 1, copy)
        self._save()
        self._refresh()
        self._toast("Duplicated")

    def _mark_used(self, prompts, save=True):
        for p in prompts:
            p["uses"] = p.get("uses", 0) + 1
            p["last_used"] = now_iso()
        if save:
            self._save()

    def _copy_prompt(self, pid):
        f = self._find_prompt(pid)
        if not f:
            return
        self._copy(f[2]["text"])
        self._mark_used([f[2]])
        if self._sort_key() in ("used", "recent"):
            self._render_prompts()
        self._toast("Copied")

    def _copy_prompts(self, ids):
        ps = [self._find_prompt(i)[2] for i in ids if self._find_prompt(i)]
        if not ps:
            return
        self._copy("\n".join(p["text"] for p in ps))
        self._mark_used(ps)
        self._toast(f"Copied {len(ps)} prompts")

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _open_image(self, pid):
        f = self._find_prompt(pid)
        if f and f[2].get("image"):
            path = self.store.image_path(f[2]["image"])
            if os.path.exists(path):
                try:
                    os.startfile(path)
                except OSError:
                    self._toast("Could not open image")

    def _on_prompt_drop(self, src, dst):
        cat = self.selected
        lst = self.data.get(cat)
        if not lst or not (0 <= src < len(lst)) or not (0 <= dst < len(lst)):
            return
        p = lst.pop(src)
        lst.insert(dst, p)
        self._save()
        self._render_prompts()

    # ── Kontextmenü ──────────────────────────────────────────────

    def _card_menu(self, event, pid):
        f = self._find_prompt(pid)
        if not f:
            return
        cat, idx, p = f
        m = styled_menu(self)
        m.add_command(label="Copy", command=lambda: self._copy_prompt(pid))
        m.add_command(label="Details", command=lambda: self._open_detail(pid))
        m.add_command(label="Edit", command=lambda: self._edit_prompt(pid))
        m.add_command(label="Unstar" if p.get("fav") else "Star ★", command=lambda: self._toggle_fav(pid))
        m.add_command(label="Duplicate", command=lambda: self._duplicate_prompt(pid))
        m.add_separator()
        mv = styled_menu(m)
        for target in self.categories:
            if target != cat:
                mv.add_command(label=target, command=lambda t=target: self._move_prompts([pid], t))
        m.add_cascade(label="Move to", menu=mv)
        m.add_command(label="Use in Builder", command=lambda: self._use_in_builder(pid))
        if self.store.get("sd.url"):
            m.add_command(label="Send to image backend", command=lambda: self._sd_send(p["text"], ""))
        m.add_separator()
        m.add_command(label="Select" if pid not in self._selection else "Deselect",
                      command=lambda: self._toggle_select(pid))
        m.add_command(label="Delete", command=lambda: self._del_prompts([pid]))
        m.tk_popup(event.x_root, event.y_root)

    def _use_in_builder(self, pid):
        f = self._find_prompt(pid)
        if not f:
            return
        cat, _, p = f
        self._slots.append({"type": "cat", "cat": cat, "value": p["text"], "locked": True,
                            "weight": 100, "count_min": 1, "count_max": 1, "negative": False,
                            "tag_filter": ""})
        self._switch_view("builder")
        self._toast(f'Added locked slot from "{cat}"')

    # ═══════════════════════════════════════════════════════════════
    # DETAILANSICHT
    # ═══════════════════════════════════════════════════════════════

    def _open_detail(self, pid):
        f = self._find_prompt(pid)
        if not f:
            return
        cat, idx, p = f
        ov = Overlay(self, 760, 620, title=p.get("title") or f"Prompt #{idx + 1}",
                     hint=cat)
        body = ov.body

        meta = tk.Frame(body, bg=C.SURF)
        meta.pack(fill="x")
        info = (f"created {fmt_ts(p.get('created'))}   ·   used {p.get('uses', 0)}×"
                f"   ·   last {fmt_ts(p.get('last_used'))}   ·   weight {p.get('weight', 5)}/10"
                f"   ·   ~{estimate_tokens(p['text'])} tokens")
        tk.Label(meta, text=info, fg=C.TXT2, bg=C.SURF, font=F(10)).pack(side="left")

        if p.get("tags"):
            tg = tk.Frame(body, bg=C.SURF)
            tg.pack(fill="x", pady=(8, 0))
            for t in p["tags"]:
                chip(tg, "#" + t, cmd=lambda tt=t: (ov.close(), self._toggle_tag_filter(tt))).pack(
                    side="left", padx=(0, 4))

        mid = tk.Frame(body, bg=C.SURF)
        mid.pack(fill="both", expand=True, pady=(10, 0))

        if p.get("image"):
            ph = load_thumb(self.store.image_path(p["image"]), px(260))
            if ph:
                il = tk.Label(mid, image=ph, bg=C.SURF, cursor="hand2")
                il.image = ph
                il.pack(side="right", padx=(12, 0), anchor="n")
                il.bind("<Button-1>", lambda _e: self._open_image(pid))

        tb = make_textbox(mid, height=160, font_size=13)
        tb.pack(fill="both", expand=True)
        textbox_set(tb, p["text"])
        tb.configure(state="disabled")

        if p.get("variants"):
            tk.Label(body, text="VARIANTS", fg=C.TXT3, bg=C.SURF, font=F(9, bold=True)).pack(
                anchor="w", pady=(10, 2))
            for v in p["variants"]:
                row = tk.Frame(body, bg=C.SURF2, highlightbackground=C.BORDER, highlightthickness=1)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=v, fg=C.TXT, bg=C.SURF2, font=F(11, mono=True),
                         wraplength=px(600), justify="left", anchor="w").pack(side="left", padx=8, pady=4)
                flat_btn(row, "Copy", lambda x=v: (self._copy(x), self._toast("Copied")),
                         fg=C.TXT2, hover_fg=C.ACC).pack(side="right", padx=6)

        if p.get("note"):
            tk.Label(body, text="NOTE", fg=C.TXT3, bg=C.SURF, font=F(9, bold=True)).pack(
                anchor="w", pady=(10, 2))
            tk.Label(body, text=p["note"], fg=C.TXT2, bg=C.SURF, font=F(11), wraplength=px(700),
                     justify="left", anchor="w").pack(fill="x")

        ov.buttons(
            ("Delete", lambda: (ov.close(), self._del_prompts([pid])), "red"),
            ("Edit", lambda: (ov.close(), self._edit_prompt(pid)), "purp"),
            ("Unstar" if p.get("fav") else "★ Star", lambda: (ov.close(), self._toggle_fav(pid)), "gold"),
            ("Copy", lambda: (self._copy_prompt(pid)), "neon"),
        )
        if self.store.get("sd.url"):
            ghost_btn(ov.footer, "→ Image backend", lambda: self._sd_send(p["text"], ""),
                      width=130, height=32, font_size=12).pack(side="left")

    # ═══════════════════════════════════════════════════════════════
    # ZUFÄLLIGE PROMPTS
    # ═══════════════════════════════════════════════════════════════

    def _open_random(self):
        if not self.selected:
            return
        ov = Overlay(self, 820, 680, title="  Random Prompts", title_color=C.PURP)
        body = ov.body

        ctrl = tk.Frame(body, bg=C.SURF2, highlightbackground=C.BORDER, highlightthickness=1)
        ctrl.pack(fill="x", pady=(0, 8))
        tk.Label(ctrl, text="Category", fg=C.TXT2, bg=C.SURF2, font=F(10)).grid(
            row=0, column=0, padx=(14, 6), pady=(8, 2), sticky="w")
        tk.Label(ctrl, text="Count", fg=C.TXT2, bg=C.SURF2, font=F(10)).grid(
            row=0, column=1, padx=(14, 6), pady=(8, 2), sticky="w")
        tk.Label(ctrl, text="Tag filter", fg=C.TXT2, bg=C.SURF2, font=F(10)).grid(
            row=0, column=2, padx=(14, 6), pady=(8, 2), sticky="w")

        cat_var = tk.StringVar(value=self.selected)
        option_menu(ctrl, self.categories, cat_var, width=200).grid(
            row=1, column=0, padx=(14, 6), pady=(0, 12))
        count_var = tk.StringVar(value=str(self.store.get("random_count", 10)))
        entry(ctrl, count_var, width=65, height=32).grid(row=1, column=1, padx=(14, 6), pady=(0, 12))
        tag_var = tk.StringVar()
        entry(ctrl, tag_var, width=140, height=32, placeholder="tag").grid(
            row=1, column=2, padx=(14, 6), pady=(0, 12))
        fav_only = tk.BooleanVar(value=False)
        checkbox(ctrl, "★ only", fav_only).grid(row=1, column=3, padx=(6, 6), pady=(0, 12))

        info_lbl = tk.Label(body, text="", fg=C.TXT2, bg=C.SURF, font=F(10))
        info_lbl.pack(pady=(0, 2))
        res = ScrollFrame(body, bg=C.BG)
        res.pack(fill="both", expand=True)
        results = {"list": []}

        def generate():
            cat = cat_var.get()
            try:
                n = max(1, int(count_var.get()))
            except ValueError:
                n = 10
            res.clear()
            pool = self.data.get(cat, [])
            tag = tag_var.get().strip().lower()
            if tag:
                pool = [p for p in pool if any(tag in t for t in p.get("tags", []))]
            if fav_only.get():
                pool = [p for p in pool if p.get("fav")]
            if not pool:
                tk.Label(res.inner, text="No prompts match.", fg=C.TXT2, bg=C.BG,
                         font=F(12)).pack(pady=30)
                copy_btn.configure(state="disabled")
                results["list"] = []
                return
            actual = min(n, len(pool))
            picked = random.sample(pool, actual)
            results["list"] = picked
            note = f" (max. {actual} available)" if actual < n else ""
            info_lbl.configure(text=f"{actual} Prompts from \"{cat}\"{note}")
            for i, p in enumerate(picked):
                c = tk.Frame(res.inner, bg=C.SURF2, highlightbackground=C.BORDER, highlightthickness=1)
                c.pack(fill="x", padx=4, pady=3)
                h = tk.Frame(c, bg=C.SURF2)
                h.pack(fill="x", padx=10, pady=(6, 2))
                tk.Label(h, text=f"#{i + 1:02d}", fg=C.ACC, bg=C.SURF2,
                         font=F(10, bold=True, mono=True)).pack(side="left")
                flat_btn(h, "Copy", lambda x=p: (self._copy(x["text"]), self._mark_used([x]),
                                                 self._toast("Copied")),
                         fg=C.TXT2, hover_fg=C.ACC).pack(side="right")
                tk.Frame(c, height=1, bg=C.BORDER).pack(fill="x", padx=10, pady=1)
                tk.Label(c, text=p["text"], fg=C.TXT, bg=C.SURF2, font=F(11, mono=True),
                         wraplength=px(700), justify="left", anchor="w").pack(
                    fill="x", padx=10, pady=(2, 8), anchor="w")
                res.bind_children_wheel(c)
            copy_btn.configure(state="normal")

        neon_btn(ctrl, "Generate", generate, color=C.PURP, bg=C.PURP_DIM, hover=C.PURP_MID,
                 width=110, height=32, font_size=12).grid(row=1, column=4, padx=(10, 14), pady=(0, 12))

        def copy_all():
            self._copy("\n\n".join(p["text"] for p in results["list"]))
            self._mark_used(results["list"])
            self._toast("Copied all")

        copy_btn, = ov.buttons(("Copy All", copy_all, "neon"))
        copy_btn.configure(state="disabled")
        generate()
