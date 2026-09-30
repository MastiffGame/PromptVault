"""Builder-Ansicht: Slots, Regeln, Ergebnis, Batch, History und Templates."""

import random
import tkinter as tk
from tkinter import messagebox, filedialog

from storage import make_prompt, now_iso, estimate_tokens, prompt_all_texts
from theme import C, F, px
from widgets import (ghost_btn, neon_btn, flat_btn, chip, styled_menu, entry, option_menu,
                     checkbox, slider, ScrollFrame, Overlay, DragReorder, fmt_ts, Tooltip)


def new_slot(kind="cat", cat="", text=""):
    return {"type": kind, "cat": cat, "text": text, "value": text if kind == "text" else None,
            "locked": False, "weight": 100, "count_min": 1, "count_max": 1,
            "negative": False, "tag_filter": ""}


def normalize_slot(s):
    base = new_slot(s.get("type", "cat"), s.get("cat", ""), s.get("text", ""))
    for k in base:
        if k in s and s[k] is not None:
            base[k] = s[k]
    if base["type"] == "text":
        base["value"] = base["text"]
    try:
        base["weight"] = max(0, min(100, int(base["weight"])))
        base["count_min"] = max(1, int(base["count_min"]))
        base["count_max"] = max(base["count_min"], int(base["count_max"]))
    except (TypeError, ValueError):
        base["weight"], base["count_min"], base["count_max"] = 100, 1, 1
    return base


def terms_match(text, tags, terms):
    """True, wenn einer der Begriffe im Text vorkommt oder ein Tag exakt trifft."""
    low = text.lower()
    for t in terms:
        t = t.strip().lower()
        if not t:
            continue
        if t in low or t in tags:
            return True
    return False


def split_terms(s):
    return [t.strip() for t in (s or "").replace(";", ",").split(",") if t.strip()]


class BuilderMixin:

    # ═══════════════════════════════════════════════════════════════
    # AUFBAU
    # ═══════════════════════════════════════════════════════════════

    def _build_builder(self):
        v = tk.Frame(self._main, bg=C.BG)
        self._builder_view = v

        # ── Topbar ────────────────────────────────────────────────
        top = tk.Frame(v, bg=C.SURF, height=px(66))
        top.pack(side="top", fill="x")
        top.pack_propagate(False)
        left_grp = tk.Frame(top, bg=C.SURF)
        left_grp.pack(side="left", fill="y", padx=22)
        tk.Label(left_grp, text="Builder", fg=C.TXT, bg=C.SURF, font=F(17, bold=True)).pack(
            side="top", anchor="w", pady=(14, 0))
        self._slot_count_lbl = tk.Label(left_grp, text="0 Slots", fg=C.TXT2, bg=C.SURF, font=F(10))
        self._slot_count_lbl.pack(side="top", anchor="w")

        right_grp = tk.Frame(top, bg=C.SURF)
        right_grp.pack(side="right", fill="y", padx=18)
        self._roll_btn = neon_btn(right_grp, "🎲 Randomize", self._builder_randomize,
                                  color=C.PURP, bg=C.PURP_DIM, hover=C.PURP_MID,
                                  width=128, height=34, font_size=12, state="disabled")
        self._roll_btn.pack(side="right", pady=16, padx=(6, 0))
        Tooltip(self._roll_btn, "Space")
        self._addslot_btn = neon_btn(right_grp, "+ Slot", self._builder_add_slot_menu,
                                     width=84, height=34, font_size=12)
        self._addslot_btn.pack(side="right", pady=16, padx=(6, 0))
        self._batch_gen_btn = ghost_btn(right_grp, "Batch ×N", self._open_batch_generate,
                                        width=84, height=34, font_size=12)
        self._batch_gen_btn.pack(side="right", pady=16, padx=(6, 0))
        self._rules_btn = ghost_btn(right_grp, "Rules", self._open_rules,
                                    width=70, height=34, font_size=12)
        self._rules_btn.pack(side="right", pady=16, padx=(6, 0))
        self._tpl_btn = ghost_btn(right_grp, "Templates", self._builder_templates_menu,
                                  width=92, height=34, font_size=12)
        self._tpl_btn.pack(side="right", pady=16, padx=(6, 0))
        self._hist_btn = ghost_btn(right_grp, "History", self._open_history,
                                   width=80, height=34, font_size=12)
        self._hist_btn.pack(side="right", pady=16)

        # ── Ergebnis-Leiste (unten) ───────────────────────────────
        res = tk.Frame(v, bg=C.SURF)
        res.pack(side="bottom", fill="x")
        tk.Frame(res, height=1, bg=C.BORDER).pack(side="top", fill="x")

        res_top = tk.Frame(res, bg=C.SURF)
        res_top.pack(fill="x", padx=22, pady=(10, 2))
        tk.Label(res_top, text="RESULT", fg=C.TXT3, bg=C.SURF, font=F(9, bold=True)).pack(side="left")
        self._tok_lbl = tk.Label(res_top, text="", fg=C.TXT2, bg=C.SURF, font=F(9))
        self._tok_lbl.pack(side="left", padx=(10, 0))
        self._tpl_name_lbl = tk.Label(res_top, text="", fg=C.PURP, bg=C.SURF, font=F(9, bold=True))
        self._tpl_name_lbl.pack(side="left", padx=(10, 0))

        self._copy_result_btn = neon_btn(res_top, "Copy", self._builder_copy_result,
                                         width=84, height=30, font_size=12, state="disabled")
        self._copy_result_btn.pack(side="right")
        self._save_result_btn = neon_btn(res_top, "★ Save", self._builder_save_result_menu,
                                         color=C.GOLD, bg=C.GOLD_DIM, hover=C.GOLD_MID,
                                         width=84, height=30, font_size=12, state="disabled")
        self._save_result_btn.pack(side="right", padx=(0, 6))
        self._send_btn = neon_btn(res_top, "→ Generate", self._builder_send_sd,
                                  color=C.GREEN, bg=C.SURF3, hover=C.SURF3,
                                  width=100, height=30, font_size=12, state="disabled")
        self._send_btn.pack(side="right", padx=(0, 6))
        Tooltip(self._send_btn, "Send to Automatic1111 / ComfyUI (see Settings)")

        self._wild_var = tk.BooleanVar(value=False)
        checkbox(res_top, "Wildcard syntax", self._wild_var, self._update_result).pack(
            side="right", padx=(0, 12))
        Tooltip(res_top, "")

        tk.Label(res_top, text="Separator", fg=C.TXT2, bg=C.SURF, font=F(10)).pack(
            side="right", padx=(0, 6))
        self._sep_var = tk.StringVar(value=self.store.get("default_sep", ", "))
        self._sep_var.trace_add("write", lambda *_: self._update_result())
        entry(res_top, self._sep_var, width=60, height=30).pack(side="right", padx=(0, 12))

        self._result_lbl = tk.Label(res, text="—", fg=C.TXT, bg=C.SURF, font=F(12, mono=True),
                                    wraplength=px(940), justify="left", anchor="w")
        self._result_lbl.pack(fill="x", padx=22, pady=(2, 4), anchor="w")
        self._neg_frame = tk.Frame(res, bg=C.SURF)
        tk.Label(self._neg_frame, text="NEGATIVE", fg=C.RED, bg=C.SURF, font=F(9, bold=True)).pack(
            side="left", anchor="n", pady=2)
        self._neg_lbl = tk.Label(self._neg_frame, text="", fg=C.TXT2, bg=C.SURF, font=F(11, mono=True),
                                 wraplength=px(860), justify="left", anchor="w")
        self._neg_lbl.pack(side="left", fill="x", padx=(10, 0))
        flat_btn(self._neg_frame, "Copy", self._builder_copy_negative, fg=C.TXT2, bg=C.SURF,
                 hover_fg=C.ACC).pack(side="right")
        # wird nur gepackt, wenn Negative-Slots existieren

        # ── Slot-Liste ────────────────────────────────────────────
        self._slot_list = ScrollFrame(v, bg=C.BG)
        self._slot_list.pack(side="top", fill="both", expand=True, padx=14, pady=12)
        self._slot_drag = DragReorder(self, self._on_slot_drop)
        self._render_slots()

    # ═══════════════════════════════════════════════════════════════
    # SLOTS RENDERN
    # ═══════════════════════════════════════════════════════════════

    def _render_slots(self):
        self._slot_list.clear()
        self._slot_drag.reset()
        n = len(self._slots)
        self._slot_count_lbl.configure(text=f"{n} Slot{'s' if n != 1 else ''}"
                                       + (f"  ·  {len(self._rules)} rule{'s' if len(self._rules) != 1 else ''}"
                                          if self._rules else ""))
        self._roll_btn.configure(state="normal" if n else "disabled")
        self._tpl_name_lbl.configure(text=f"⌘ {self._active_template}" if self._active_template else "")

        if not self._slots:
            tk.Label(self._slot_list.inner,
                     text="No slots yet.\nClick  + Slot  to add a category or free text,\n"
                          "then  🎲 Randomize  (or press Space) to roll.",
                     fg=C.TXT2, bg=C.BG, font=F(13), justify="center").pack(pady=60)
            self._update_result()
            return
        for i, slot in enumerate(self._slots):
            self._make_slot_card(i, slot)
        self._update_result()
        self._save_builder_state()

    def _make_slot_card(self, i, slot):
        is_text = slot.get("type") == "text"
        neg = slot.get("negative")
        card = tk.Frame(self._slot_list.inner, bg=C.SURF2,
                        highlightbackground=C.ACC if slot["locked"] else (C.RED_MID if neg else C.BORDER),
                        highlightthickness=1)
        card.pack(fill="x", padx=4, pady=5)

        hdr = tk.Frame(card, bg=C.SURF2)
        hdr.pack(fill="x", padx=10, pady=(7, 3))

        grip = tk.Label(hdr, text="⋮⋮", fg=C.TXT3, bg=C.SURF2, font=F(11))
        grip.pack(side="left", padx=(0, 6))
        self._slot_drag.register(grip, card, i)

        tk.Label(hdr, text=f"#{i + 1:02d}", fg=C.ACC, bg=C.SURF2,
                 font=F(10, bold=True, mono=True)).pack(side="left")
        if is_text:
            tk.Label(hdr, text="✏ Free Text", fg=C.ACC, bg=C.SURF2, font=F(11, bold=True)).pack(
                side="left", padx=(10, 0))
        else:
            missing = slot["cat"] not in self.data
            tk.Label(hdr, text=slot["cat"] + ("  (missing)" if missing else ""),
                     fg=C.RED if missing else C.PURP, bg=C.SURF2, font=F(11, bold=True)).pack(
                side="left", padx=(10, 0))
        if neg:
            chip(hdr, "NEG", fg=C.RED, bg=C.RED_DIM).pack(side="left", padx=(8, 0))
        if not is_text:
            if slot.get("count_max", 1) > 1 or slot.get("count_min", 1) > 1:
                lo, hi = slot["count_min"], slot["count_max"]
                chip(hdr, f"×{lo}" if lo == hi else f"×{lo}–{hi}", fg=C.ACC, bg=C.ACC_DIM).pack(
                    side="left", padx=(8, 0))
            if slot.get("tag_filter"):
                chip(hdr, f"#{slot['tag_filter']}", fg=C.TXT2, bg=C.SURF3).pack(side="left", padx=(8, 0))

        btn_f = tk.Frame(hdr, bg=C.SURF2)
        btn_f.pack(side="right")
        if is_text:
            flat_btn(btn_f, "Edit", lambda x=i: self._builder_edit_text(x),
                     fg=C.PURP, hover=C.PURP_DIM).pack(side="left", padx=2)
        else:
            w = slot.get("weight", 100)
            flat_btn(btn_f, f"{w}%", lambda x=i: self._slot_settings(x),
                     fg=C.ACC if w < 100 else C.TXT2, hover_fg=C.ACC,
                     tip="Probability that this slot is filled").pack(side="left", padx=2)
            flat_btn(btn_f, "⚙", lambda x=i: self._slot_settings(x),
                     fg=C.TXT2, hover_fg=C.ACC, tip="Slot settings").pack(side="left", padx=2)
            flat_btn(btn_f, "🔒" if slot["locked"] else "🔓",
                     lambda x=i: self._builder_toggle_lock(x),
                     fg=C.ACC if slot["locked"] else C.TXT2, hover_fg=C.ACC).pack(side="left", padx=2)
            flat_btn(btn_f, "Pick", lambda x=i: self._builder_pick(x),
                     fg=C.PURP, hover=C.PURP_DIM).pack(side="left", padx=2)
            flat_btn(btn_f, "🎲", lambda x=i: self._builder_reroll(x),
                     fg=C.PURP, hover=C.PURP_DIM).pack(side="left", padx=2)
        flat_btn(btn_f, "NEG" if not neg else "POS", lambda x=i: self._builder_toggle_neg(x),
                 fg=C.RED if not neg else C.GREEN, hover=C.RED_DIM,
                 tip="Move to negative / positive prompt").pack(side="left", padx=2)
        flat_btn(btn_f, "✕", lambda x=i: self._builder_remove(x),
                 fg=C.RED, hover=C.RED_DIM).pack(side="left", padx=2)

        tk.Frame(card, height=1, bg=C.BORDER).pack(fill="x", padx=10, pady=2)

        val = self._slot_value_text(slot)
        if val:
            fg = C.TXT
        elif is_text:
            val, fg = "(empty text)", C.TXT2
        elif not self._slot_pool(slot):
            val, fg = "(no prompts match this slot)", C.TXT2
        elif slot.get("weight", 100) < 100:
            val, fg = "— skipped this roll —", C.TXT2
        else:
            val, fg = "— not rolled yet —", C.TXT2
        tk.Label(card, text=val, fg=fg, bg=C.SURF2, font=F(12, mono=True),
                 wraplength=px(860), justify="left", anchor="w").pack(fill="x", padx=10, pady=(3, 8), anchor="w")
        self._slot_list.bind_children_wheel(card)

    def _slot_value_text(self, slot):
        v = slot.get("value")
        if isinstance(v, list):
            return self._sep_var.get().join(x for x in v if x)
        return v or ""

    # ═══════════════════════════════════════════════════════════════
    # WÜRFELN
    # ═══════════════════════════════════════════════════════════════

    def _slot_pool(self, slot, extra_filters=None):
        """Prompt-Objekte, die für diesen Slot in Frage kommen."""
        pool = list(self.data.get(slot.get("cat", ""), []))
        tf = (slot.get("tag_filter") or "").strip().lower()
        if tf:
            terms = split_terms(tf)
            pool = [p for p in pool if any(any(t in tag for tag in p.get("tags", [])) for t in terms)]
        for mode, terms in (extra_filters or []):
            if mode == "only":
                pool = [p for p in pool if terms_match(p["text"], p.get("tags", []), terms)]
            else:
                pool = [p for p in pool if not terms_match(p["text"], p.get("tags", []), terms)]
        return pool

    @staticmethod
    def _weighted_sample(pool, k):
        pool = list(pool)
        out = []
        while pool and len(out) < k:
            weights = [max(1, int(p.get("weight", 5))) for p in pool]
            pick = random.choices(pool, weights=weights, k=1)[0]
            out.append(pick)
            pool.remove(pick)
        return out

    def _roll_slot(self, slot, force=False, extra_filters=None):
        if slot.get("type") == "text":
            slot["value"] = slot.get("text", "")
            return
        pool = self._slot_pool(slot, extra_filters)
        if not pool:
            slot["value"] = None
            return
        if not force and random.randint(1, 100) > slot.get("weight", 100):
            slot["value"] = None
            return
        lo, hi = slot.get("count_min", 1), slot.get("count_max", 1)
        k = random.randint(lo, max(lo, hi))
        picked = self._weighted_sample(pool, k)
        texts = [random.choice(prompt_all_texts(p)) for p in picked]
        slot["value"] = texts[0] if k == 1 and hi == 1 else texts

    def _rule_filters(self):
        """{slot_index: [(mode, terms), ...]} anhand der aktuellen Slot-Werte."""
        out = {}
        for rule in self._rules:
            if not rule.get("if_cat") or not rule.get("then_cat"):
                continue
            trig_terms = split_terms(rule.get("if_match", ""))
            triggered = False
            for s in self._slots:
                if s.get("type") != "cat" or s.get("cat") != rule["if_cat"]:
                    continue
                vals = s.get("value")
                vals = vals if isinstance(vals, list) else ([vals] if vals else [])
                if not vals:
                    continue
                if not trig_terms or any(terms_match(v, [], trig_terms) for v in vals):
                    triggered = True
                    break
            if not triggered:
                continue
            terms = split_terms(rule.get("terms", ""))
            for idx, s in enumerate(self._slots):
                if s.get("type") == "cat" and s.get("cat") == rule["then_cat"]:
                    out.setdefault(idx, []).append((rule.get("mode", "only"), terms))
        return out

    def _apply_rules(self, force=False):
        for _ in range(2):
            filters = self._rule_filters()
            changed = False
            for idx, fl in filters.items():
                s = self._slots[idx]
                if s["locked"]:
                    continue
                allowed = {t for p in self._slot_pool(s, fl) for t in prompt_all_texts(p)}
                vals = s.get("value")
                vals = vals if isinstance(vals, list) else ([vals] if vals else [])
                if vals and all(v in allowed for v in vals):
                    continue
                if not vals and not force:
                    continue
                self._roll_slot(s, force=bool(vals) or force, extra_filters=fl)
                changed = True
            if not changed:
                break

    def _builder_randomize(self):
        if not self._slots:
            return
        for slot in self._slots:
            if not slot["locked"]:
                self._roll_slot(slot)
        self._apply_rules()
        self._render_slots()
        self._record_history()

    def _builder_reroll(self, i):
        self._roll_slot(self._slots[i], force=True)
        self._apply_rules()
        self._render_slots()
        self._record_history()

    # ═══════════════════════════════════════════════════════════════
    # SLOT-AKTIONEN
    # ═══════════════════════════════════════════════════════════════

    def _builder_add_slot_menu(self):
        menu = styled_menu(self)
        menu.add_command(label="✏  Free text…", command=self._builder_add_text_slot)
        if self.categories:
            menu.add_separator()
            for cat in self.categories:
                n = len(self.data.get(cat, []))
                menu.add_command(label=f"{cat}  ({n})", command=lambda c=cat: self._builder_add_slot(c))
        menu.tk_popup(self._addslot_btn.winfo_rootx(),
                      self._addslot_btn.winfo_rooty() + self._addslot_btn.winfo_height())

    def _builder_add_slot(self, cat):
        slot = new_slot("cat", cat)
        self._roll_slot(slot, force=True)
        self._slots.append(slot)
        self._render_slots()

    def _builder_add_text_slot(self):
        def on_save(text):
            self._slots.append(new_slot("text", text=text))
            self._render_slots()
        self._show_editor(title="Free Text Slot", hint="Fixed text, e.g. quality tags — never rerolled",
                          on_save=on_save)

    def _builder_edit_text(self, i):
        slot = self._slots[i]

        def on_save(text):
            slot["text"] = text
            slot["value"] = text
            self._render_slots()
        self._show_editor(title="Edit Free Text Slot", initial=slot.get("text", ""), on_save=on_save)

    def _builder_remove(self, i):
        self._slots.pop(i)
        self._render_slots()

    def _on_slot_drop(self, src, dst):
        s = self._slots.pop(src)
        self._slots.insert(dst, s)
        self._render_slots()

    def _builder_toggle_lock(self, i):
        self._slots[i]["locked"] = not self._slots[i]["locked"]
        self._render_slots()

    def _builder_toggle_neg(self, i):
        self._slots[i]["negative"] = not self._slots[i].get("negative")
        self._render_slots()

    def _slot_settings(self, i):
        slot = self._slots[i]
        ov = Overlay(self, 520, 420, title=f"Slot Settings  —  {slot['cat']}", title_color=C.PURP)
        b = ov.body

        tk.Label(b, text="Fill probability", fg=C.TXT2, bg=C.SURF, font=F(10)).pack(anchor="w")
        row = tk.Frame(b, bg=C.SURF)
        row.pack(fill="x", pady=(2, 10))
        w_var = tk.IntVar(value=slot.get("weight", 100))
        w_lbl = tk.Label(row, text=f"{w_var.get()} %", fg=C.ACC, bg=C.SURF, font=F(12, bold=True), width=6)
        w_lbl.pack(side="right")
        slider(row, 0, 100, w_var, steps=20, width=360,
               command=lambda v: w_lbl.configure(text=f"{int(float(v))} %")).pack(side="left", fill="x", expand=True)

        tk.Label(b, text="How many prompts to draw (min – max)", fg=C.TXT2, bg=C.SURF, font=F(10)).pack(anchor="w")
        row2 = tk.Frame(b, bg=C.SURF)
        row2.pack(fill="x", pady=(2, 10))
        lo_var = tk.StringVar(value=str(slot.get("count_min", 1)))
        hi_var = tk.StringVar(value=str(slot.get("count_max", 1)))
        entry(row2, lo_var, width=60, height=32).pack(side="left")
        tk.Label(row2, text=" – ", fg=C.TXT2, bg=C.SURF, font=F(12)).pack(side="left")
        entry(row2, hi_var, width=60, height=32).pack(side="left")
        tk.Label(row2, text="   e.g. 2 – 4 for accessories", fg=C.TXT3, bg=C.SURF, font=F(9)).pack(side="left")

        tk.Label(b, text="Only prompts with tag (comma = any of)", fg=C.TXT2, bg=C.SURF, font=F(10)).pack(anchor="w")
        tag_var = tk.StringVar(value=slot.get("tag_filter", ""))
        entry(b, tag_var, width=400, height=32, placeholder="e.g. summer, beach").pack(anchor="w", pady=(2, 10))
        tags = sorted({t for p in self.data.get(slot["cat"], []) for t in p.get("tags", [])})
        if tags:
            tk.Label(b, text="Available: " + ", ".join(tags[:20]) + (" …" if len(tags) > 20 else ""),
                     fg=C.TXT3, bg=C.SURF, font=F(9), wraplength=px(460), justify="left").pack(anchor="w")

        neg_var = tk.BooleanVar(value=bool(slot.get("negative")))
        checkbox(b, "Goes into the negative prompt", neg_var).pack(anchor="w", pady=(10, 0))

        def save():
            try:
                lo = max(1, int(lo_var.get()))
                hi = max(lo, int(hi_var.get()))
            except ValueError:
                lo, hi = 1, 1
            slot["weight"] = int(w_var.get())
            slot["count_min"], slot["count_max"] = lo, hi
            slot["tag_filter"] = tag_var.get().strip()
            slot["negative"] = neg_var.get()
            ov.close()
            self._roll_slot(slot, force=True)
            self._render_slots()

        ov.buttons(("Save & roll", save, "purp"), ("Cancel", ov.close, "ghost"))

    # ── Manuelle Auswahl (Pick) ───────────────────────────────────

    def _builder_pick(self, i):
        slot = self._slots[i]
        pool = self._slot_pool(slot)
        if not pool:
            messagebox.showinfo("Builder", f'No prompts in "{slot["cat"]}".', parent=self)
            return
        ov = Overlay(self, 700, 540, title=f"Pick Prompt  —  {slot['cat']}", title_color=C.PURP,
                     hint="double-click to use · Ctrl-click for several")
        search_var = tk.StringVar()
        entry(ov.body, search_var, width=600, height=32, placeholder="  Search…").pack(fill="x", pady=(0, 6))
        lb_frame = tk.Frame(ov.body, bg=C.SURF)
        lb_frame.pack(fill="both", expand=True)
        lb = tk.Listbox(lb_frame, bg=C.SURF2, fg=C.TXT, font=F(11, mono=True),
                        selectbackground=C.PURP_MID, selectforeground=C.TXT,
                        relief="flat", activestyle="none", selectmode="extended",
                        highlightthickness=1, highlightbackground=C.BORD_H)
        sb = tk.Scrollbar(lb_frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)
        filtered = {"list": pool}

        def fill():
            q = search_var.get().strip().lower()
            filtered["list"] = [p for p in pool if not q or q in p["text"].lower()
                                or any(q in t for t in p.get("tags", []))]
            lb.delete(0, "end")
            for p in filtered["list"]:
                lb.insert("end", ("★ " if p.get("fav") else "") + p["text"])
        search_var.trace_add("write", lambda *_: fill())
        fill()

        def use(_=None):
            sel = lb.curselection()
            if not sel:
                return
            texts = [filtered["list"][s]["text"] for s in sel]
            slot["value"] = texts[0] if len(texts) == 1 else texts
            slot["locked"] = True
            ov.close()
            self._render_slots()

        lb.bind("<Double-Button-1>", use)
        ov.buttons(("Use", use, "purp"), ("Cancel", ov.close, "ghost"))

    # ═══════════════════════════════════════════════════════════════
    # ERGEBNIS
    # ═══════════════════════════════════════════════════════════════

    def _result_parts(self, negative=False, wildcard=None):
        wildcard = self._wild_var.get() if wildcard is None else wildcard
        parts = []
        for s in self._slots:
            if bool(s.get("negative")) != negative:
                continue
            if wildcard and s.get("type") == "cat" and not s["locked"]:
                n = s.get("count_max", 1)
                parts.extend([f"__{s['cat']}__"] * max(1, s.get("count_min", 1)) if n > 1 else [f"__{s['cat']}__"])
                continue
            v = s.get("value")
            if isinstance(v, list):
                parts.extend(x for x in v if x)
            elif v:
                parts.append(v)
        return parts

    def _result_text(self, negative=False, wildcard=None):
        parts = self._result_parts(negative, wildcard)
        return self._sep_var.get().join(parts) if parts else ""

    def _update_result(self):
        text = self._result_text()
        neg = self._result_text(negative=True)
        self._result_lbl.configure(text=text if text else "—", fg=C.TXT if text else C.TXT2)
        if any(s.get("negative") for s in self._slots):
            self._neg_lbl.configure(text=neg or "—")
            self._neg_frame.pack(fill="x", padx=22, pady=(0, 10), after=self._result_lbl)
        else:
            self._neg_frame.pack_forget()
        if text:
            tok = estimate_tokens(text)
            self._tok_lbl.configure(text=f"{len(text)} chars · ~{tok} tokens"
                                    + (f" · {(tok + 74) // 75} chunks" if tok > 75 else ""),
                                    fg=C.RED if tok > 150 else C.TXT2)
        else:
            self._tok_lbl.configure(text="")
        state = "normal" if text else "disabled"
        self._copy_result_btn.configure(state=state)
        self._save_result_btn.configure(state=state)
        self._send_btn.configure(state=state if self.store.get("sd.url") else "disabled")

    def _builder_copy_result(self):
        text = self._result_text()
        if text:
            self._copy(text)
            self._mark_slot_usage()
            self._toast("Result copied")

    def _builder_copy_negative(self):
        text = self._result_text(negative=True)
        if text:
            self._copy(text)
            self._toast("Negative copied")

    def _mark_slot_usage(self):
        """Nutzungszähler der Prompts erhöhen, die im Ergebnis stecken."""
        used = []
        for s in self._slots:
            if s.get("type") != "cat":
                continue
            vals = s.get("value")
            vals = vals if isinstance(vals, list) else ([vals] if vals else [])
            if not vals:
                continue
            for p in self.data.get(s["cat"], []):
                if any(v in prompt_all_texts(p) for v in vals):
                    used.append(p)
        if used:
            self._mark_used(used)

    def _builder_save_result_menu(self):
        text = self._result_text()
        if not text:
            return
        menu = styled_menu(self, active_fg=C.GOLD)
        for cat in self.categories:
            menu.add_command(label=f"Save to \"{cat}\"", command=lambda c=cat: self._builder_save_result(c))
        menu.add_separator()
        menu.add_command(label="＋ New category…", command=lambda: self._show_name_dialog(
            "New Category", on_save=lambda name: (self.data.__setitem__(name, []), self._render_cats(),
                                                  self._builder_save_result(name))))
        menu.tk_popup(self._save_result_btn.winfo_rootx(),
                      self._save_result_btn.winfo_rooty() + self._save_result_btn.winfo_height())

    def _builder_save_result(self, cat):
        text = self._result_text()
        if not text:
            return
        if self._is_dup(cat, text):
            self._toast(f'Already in "{cat}"')
            return
        self.data.setdefault(cat, []).append(make_prompt(text, tags=["builder"]))
        self._save()
        self._refresh()
        self._toast(f'Saved to "{cat}"')

    def _builder_send_sd(self):
        text = self._result_text(wildcard=False)
        if text:
            self._mark_slot_usage()
            self._sd_send(text, self._result_text(negative=True, wildcard=False))

    # ═══════════════════════════════════════════════════════════════
    # BATCH-GENERIERUNG
    # ═══════════════════════════════════════════════════════════════

    def _roll_copy(self):
        """Würfelt eine Kopie der Slots (Locks bleiben) und gibt (pos, neg) zurück."""
        backup = [dict(s) for s in self._slots]
        try:
            for s in self._slots:
                if not s["locked"]:
                    self._roll_slot(s)
            self._apply_rules()
            return self._result_text(wildcard=False), self._result_text(negative=True, wildcard=False)
        finally:
            for s, b in zip(self._slots, backup):
                s.update(b)

    def _open_batch_generate(self):
        if not self._slots:
            self._toast("Add slots first")
            return
        ov = Overlay(self, 860, 680, title="Batch Generate", title_color=C.PURP,
                     hint="rolls the current slots N times")
        ctrl = tk.Frame(ov.body, bg=C.SURF)
        ctrl.pack(fill="x", pady=(0, 8))
        tk.Label(ctrl, text="Count", fg=C.TXT2, bg=C.SURF, font=F(10)).pack(side="left")
        n_var = tk.StringVar(value="10")
        entry(ctrl, n_var, width=70, height=32).pack(side="left", padx=(6, 12))
        uniq = tk.BooleanVar(value=True)
        checkbox(ctrl, "unique only", uniq).pack(side="left")
        info = tk.Label(ctrl, text="", fg=C.TXT2, bg=C.SURF, font=F(10))
        info.pack(side="left", padx=12)
        res = ScrollFrame(ov.body, bg=C.BG)
        res.pack(fill="both", expand=True)
        results = {"list": []}

        def generate():
            try:
                n = max(1, min(500, int(n_var.get())))
            except ValueError:
                n = 10
            out, seen = [], set()
            for _ in range(n * 4 if uniq.get() else n):
                pos, neg = self._roll_copy()
                if not pos:
                    continue
                if uniq.get() and pos in seen:
                    continue
                seen.add(pos)
                out.append((pos, neg))
                if len(out) >= n:
                    break
            results["list"] = out
            res.clear()
            info.configure(text=f"{len(out)} results")
            for i, (pos, neg) in enumerate(out):
                c = tk.Frame(res.inner, bg=C.SURF2, highlightbackground=C.BORDER, highlightthickness=1)
                c.pack(fill="x", padx=4, pady=3)
                h = tk.Frame(c, bg=C.SURF2)
                h.pack(fill="x", padx=10, pady=(6, 2))
                tk.Label(h, text=f"#{i + 1:02d}", fg=C.ACC, bg=C.SURF2, font=F(10, bold=True, mono=True)).pack(side="left")
                flat_btn(h, "Copy", lambda x=pos: (self._copy(x), self._toast("Copied")),
                         fg=C.TXT2, hover_fg=C.ACC).pack(side="right")
                tk.Label(c, text=pos, fg=C.TXT, bg=C.SURF2, font=F(11, mono=True), wraplength=px(760),
                         justify="left", anchor="w").pack(fill="x", padx=10, pady=(2, 4))
                if neg:
                    tk.Label(c, text="NEG  " + neg, fg=C.TXT2, bg=C.SURF2, font=F(10, mono=True),
                             wraplength=px(760), justify="left", anchor="w").pack(fill="x", padx=10, pady=(0, 6))
                res.bind_children_wheel(c)
            for b in (copy_btn, save_btn, exp_btn):
                b.configure(state="normal" if out else "disabled")
            send_btn.configure(state="normal" if out and self.store.get("sd.url") else "disabled")

        neon_btn(ctrl, "Generate", generate, color=C.PURP, bg=C.PURP_DIM, hover=C.PURP_MID,
                 width=110, height=32, font_size=12).pack(side="right")

        def copy_all():
            self._copy("\n".join(p for p, _ in results["list"]))
            self._toast(f"Copied {len(results['list'])} results")

        def export_txt():
            path = filedialog.asksaveasfilename(parent=self, title="Export results",
                                                defaultextension=".txt", initialfile="promptvault_batch.txt",
                                                filetypes=[("Text", "*.txt")])
            if not path:
                return
            with open(path, "w", encoding="utf-8") as f:
                for pos, neg in results["list"]:
                    f.write(pos + "\n")
                    if neg:
                        f.write("NEGATIVE: " + neg + "\n")
                    f.write("\n")
            self._toast("Exported")

        def save_all():
            menu = styled_menu(self, active_fg=C.GOLD)

            def do(cat):
                added = 0
                for pos, _ in results["list"]:
                    if not self._is_dup(cat, pos):
                        self.data.setdefault(cat, []).append(make_prompt(pos, tags=["builder"]))
                        added += 1
                self._save()
                self._refresh()
                self._toast(f'Saved {added} to "{cat}"')
            for cat in self.categories:
                menu.add_command(label=f"Save all to \"{cat}\"", command=lambda c=cat: do(c))
            menu.tk_popup(*self.winfo_pointerxy())

        def send_all():
            n = len(results["list"])
            if not n:
                return
            if n > 20 and not messagebox.askyesno(
                    "Send all", f"Queue {n} jobs on the image backend?", parent=self):
                return
            self._sd_send_many(results["list"])

        copy_btn, save_btn, exp_btn = ov.buttons(("Copy All", copy_all, "neon"),
                                                 ("★ Save all…", save_all, "gold"),
                                                 ("Export .txt", export_txt, "ghost"))
        send_btn = neon_btn(ov.footer, "→ Send all", send_all, color=C.GREEN, bg=C.SURF3,
                            hover=C.SURF3, width=110, height=32, font_size=12)
        send_btn.pack(side="left")
        Tooltip(send_btn, "Queue every result on the local image backend (Settings)")
        if not self.store.get("sd.url"):
            send_btn.configure(state="disabled")
        for b in (copy_btn, save_btn, exp_btn):
            b.configure(state="disabled")

    # ═══════════════════════════════════════════════════════════════
    # REGELN
    # ═══════════════════════════════════════════════════════════════

    def _open_rules(self):
        ov = Overlay(self, 900, 640, title="Rules", title_color=C.PURP,
                     hint="if a slot of category A rolled X, restrict category B")
        body = ov.body
        lst = ScrollFrame(body, bg=C.BG)
        lst.pack(fill="both", expand=True)

        def render():
            lst.clear()
            if not self._rules:
                tk.Label(lst.inner, text="No rules yet.\nExample: if Outfit contains “bikini” → Environment only “beach, pool”",
                         fg=C.TXT2, bg=C.BG, font=F(12), justify="center").pack(pady=30)
            for i, r in enumerate(self._rules):
                c = tk.Frame(lst.inner, bg=C.SURF2, highlightbackground=C.BORDER, highlightthickness=1)
                c.pack(fill="x", padx=4, pady=3)
                cond = f'if  {r["if_cat"]}' + (f'  contains  “{r["if_match"]}”' if r.get("if_match") else "  is filled")
                act = f'→  {r["then_cat"]}  {"only" if r.get("mode") == "only" else "exclude"}  “{r.get("terms", "")}”'
                tk.Label(c, text=cond, fg=C.TXT, bg=C.SURF2, font=F(11)).pack(side="left", padx=10, pady=6)
                tk.Label(c, text=act, fg=C.PURP, bg=C.SURF2, font=F(11, bold=True)).pack(side="left", padx=4)
                flat_btn(c, "✕", lambda x=i: (self._rules.pop(x), render(), self._render_slots()),
                         fg=C.RED, hover=C.RED_DIM).pack(side="right", padx=8)
                lst.bind_children_wheel(c)

        # Formular
        form = tk.Frame(body, bg=C.SURF2, highlightbackground=C.BORDER, highlightthickness=1)
        form.pack(fill="x", pady=(8, 0))
        cats = self.categories or [""]
        if_cat = tk.StringVar(value=cats[0])
        if_match = tk.StringVar()
        then_cat = tk.StringVar(value=cats[-1])
        mode = tk.StringVar(value="only")
        terms = tk.StringVar()
        r1 = tk.Frame(form, bg=C.SURF2)
        r1.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(r1, text="IF", fg=C.TXT2, bg=C.SURF2, font=F(10, bold=True)).pack(side="left")
        option_menu(r1, cats, if_cat, width=160).pack(side="left", padx=6)
        tk.Label(r1, text="contains", fg=C.TXT2, bg=C.SURF2, font=F(10)).pack(side="left")
        entry(r1, if_match, width=220, height=30, placeholder="bikini, swimsuit  (empty = any)").pack(side="left", padx=6)
        r2 = tk.Frame(form, bg=C.SURF2)
        r2.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(r2, text="THEN", fg=C.TXT2, bg=C.SURF2, font=F(10, bold=True)).pack(side="left")
        option_menu(r2, cats, then_cat, width=160).pack(side="left", padx=6)
        option_menu(r2, ["only", "exclude"], mode, width=100).pack(side="left")
        entry(r2, terms, width=220, height=30, placeholder="beach, pool  (text or tag)").pack(side="left", padx=6)

        def add():
            if not terms.get().strip():
                self._toast("Enter terms for the THEN part")
                return
            self._rules.append({"if_cat": if_cat.get(), "if_match": if_match.get().strip(),
                                "then_cat": then_cat.get(), "mode": mode.get(), "terms": terms.get().strip()})
            terms.set("")
            if_match.set("")
            render()
            self._render_slots()

        neon_btn(r2, "+ Add rule", add, color=C.PURP, bg=C.PURP_DIM, hover=C.PURP_MID,
                 width=100, height=30, font_size=12).pack(side="right")
        render()
        ov.buttons(("Close", ov.close, "ghost"))

    # ═══════════════════════════════════════════════════════════════
    # HISTORY (persistent)
    # ═══════════════════════════════════════════════════════════════

    def _record_history(self):
        text = self._result_text(wildcard=False)
        if not text:
            return
        if self._history and self._history[0].get("text") == text:
            return
        self._history.insert(0, {"text": text, "neg": self._result_text(negative=True, wildcard=False),
                                 "template": self._active_template or "", "ts": now_iso(), "pinned": False})
        self._history = self.store.save_history(self._history)

    def _open_history(self):
        ov = Overlay(self, 860, 640, title=f"History  —  {len(self._history)} results", title_color=C.PURP)
        search = tk.StringVar()
        entry(ov.body, search, width=600, height=32, placeholder="  Filter…").pack(fill="x", pady=(0, 6))
        lst = ScrollFrame(ov.body, bg=C.BG)
        lst.pack(fill="both", expand=True)

        def render():
            lst.clear()
            q = search.get().strip().lower()
            shown = [e for e in self._history if not q or q in e["text"].lower()
                     or q in (e.get("template") or "").lower()]
            if not shown:
                tk.Label(lst.inner, text="No results yet.\nRoll the dice first.", fg=C.TXT2, bg=C.BG,
                         font=F(13), justify="center").pack(pady=60)
            for e in shown:
                c = tk.Frame(lst.inner, bg=C.SURF2,
                             highlightbackground=C.GOLD if e.get("pinned") else C.BORDER, highlightthickness=1)
                c.pack(fill="x", padx=4, pady=3)
                h = tk.Frame(c, bg=C.SURF2)
                h.pack(fill="x", padx=10, pady=(6, 2))
                tk.Label(h, text=fmt_ts(e.get("ts")), fg=C.TXT2, bg=C.SURF2, font=F(9)).pack(side="left")
                if e.get("template"):
                    chip(h, e["template"]).pack(side="left", padx=(8, 0))
                flat_btn(h, "✕", lambda x=e: (self._history.remove(x), self._store_history(), render()),
                         fg=C.RED, hover=C.RED_DIM).pack(side="right", padx=2)
                flat_btn(h, "📌" if not e.get("pinned") else "Unpin",
                         lambda x=e: (x.__setitem__("pinned", not x.get("pinned")), self._store_history(), render()),
                         fg=C.GOLD if e.get("pinned") else C.TXT2, hover_fg=C.GOLD).pack(side="right", padx=2)
                flat_btn(h, "★ Save", lambda x=e: self._save_text_menu(x["text"]),
                         fg=C.GOLD, hover_fg=C.GOLD).pack(side="right", padx=2)
                flat_btn(h, "Copy", lambda x=e: (self._copy(x["text"]), self._toast("Copied")),
                         fg=C.TXT2, hover_fg=C.ACC).pack(side="right", padx=2)
                tk.Frame(c, height=1, bg=C.BORDER).pack(fill="x", padx=10, pady=1)
                tk.Label(c, text=e["text"], fg=C.TXT, bg=C.SURF2, font=F(11, mono=True), wraplength=px(760),
                         justify="left", anchor="w").pack(fill="x", padx=10, pady=(2, 4))
                if e.get("neg"):
                    tk.Label(c, text="NEG  " + e["neg"], fg=C.TXT2, bg=C.SURF2, font=F(10, mono=True),
                             wraplength=px(760), justify="left", anchor="w").pack(fill="x", padx=10, pady=(0, 6))
                lst.bind_children_wheel(c)
        search.trace_add("write", lambda *_: render())
        render()

        def clear_all():
            if messagebox.askyesno("History", "Delete all unpinned history entries?", parent=self):
                self._history = [e for e in self._history if e.get("pinned")]
                self._store_history()
                render()
        ov.buttons(("Close", ov.close, "ghost"), ("Clear unpinned", clear_all, "red"))

    def _store_history(self):
        self._history = self.store.save_history(self._history)

    def _save_text_menu(self, text):
        menu = styled_menu(self, active_fg=C.GOLD)

        def do(cat):
            if self._is_dup(cat, text):
                self._toast(f'Already in "{cat}"')
                return
            self.data[cat].append(make_prompt(text, tags=["builder"]))
            self._save()
            self._refresh()
            self._toast(f'Saved to "{cat}"')
        for cat in self.categories:
            menu.add_command(label=f"Save to \"{cat}\"", command=lambda c=cat: do(c))
        menu.tk_popup(*self.winfo_pointerxy())

    # ═══════════════════════════════════════════════════════════════
    # TEMPLATES
    # ═══════════════════════════════════════════════════════════════

    def _template_payload(self):
        slots = []
        for s in self._slots:
            if s.get("type") == "text":
                slots.append({"type": "text", "text": s.get("text", ""), "negative": s.get("negative", False)})
            else:
                slots.append({k: s[k] for k in ("type", "cat", "weight", "count_min", "count_max",
                                                "negative", "tag_filter")})
        return {"slots": slots, "rules": [dict(r) for r in self._rules]}

    def _builder_templates_menu(self):
        menu = styled_menu(self)
        menu.add_command(label="Save as template…", command=self._builder_save_template,
                         state="normal" if self._slots else "disabled")
        if self._active_template:
            menu.add_command(label=f"Overwrite \"{self._active_template}\"",
                             command=lambda: self._builder_store_template(self._active_template))
        templates = self.store.load_templates()
        if templates:
            menu.add_separator()
            for name, t in templates.items():
                n = len(t.get("slots", []))
                menu.add_command(label=f"Load: {name}  ({n})", command=lambda x=name: self._builder_load_template(x))
            menu.add_separator()
            ren = styled_menu(menu)
            dele = styled_menu(menu, active_fg=C.RED)
            for name in templates:
                ren.add_command(label=name, command=lambda x=name: self._builder_rename_template(x))
                dele.add_command(label=name, command=lambda x=name: self._builder_del_template(x))
            menu.add_cascade(label="Rename template", menu=ren)
            menu.add_cascade(label="Delete template", menu=dele)
        menu.tk_popup(self._tpl_btn.winfo_rootx(), self._tpl_btn.winfo_rooty() + self._tpl_btn.winfo_height())

    def _builder_save_template(self):
        def on_save(name):
            templates = self.store.load_templates()
            if name in templates and not messagebox.askyesno("Template", f'Overwrite "{name}"?', parent=self):
                return
            self._builder_store_template(name)
        self._show_name_dialog("Save Template", initial=self._active_template or "", on_save=on_save, taken={})

    def _builder_store_template(self, name):
        templates = self.store.load_templates()
        templates[name] = self._template_payload()
        self.store.save_templates(templates)
        self._active_template = name
        self._render_slots()
        self._toast(f'Template "{name}" saved')

    def _builder_load_template(self, name):
        t = self.store.load_templates().get(name)
        if not t:
            return
        self._slots = [normalize_slot(s) for s in t.get("slots", [])]
        self._rules = [dict(r) for r in t.get("rules", [])]
        for s in self._slots:
            if s["type"] == "cat":
                self._roll_slot(s)
        self._apply_rules()
        self._active_template = name
        self._render_slots()
        self._record_history()

    def _builder_rename_template(self, name):
        def on_save(new):
            if new == name:
                return
            templates = self.store.load_templates()
            if new in templates:
                messagebox.showwarning("Template", f'"{new}" already exists.', parent=self)
                return
            templates = {(new if k == name else k): v for k, v in templates.items()}
            self.store.save_templates(templates)
            if self._active_template == name:
                self._active_template = new
                self._render_slots()
            self._toast("Template renamed")
        self._show_name_dialog(f'Rename "{name}"', initial=name, on_save=on_save, taken={})

    def _builder_del_template(self, name):
        if not messagebox.askyesno("Delete Template?", f'Delete "{name}"?', parent=self):
            return
        templates = self.store.load_templates()
        templates.pop(name, None)
        self.store.save_templates(templates)
        if self._active_template == name:
            self._active_template = None
            self._render_slots()

    # ═══════════════════════════════════════════════════════════════
    # ZUSTAND SPEICHERN
    # ═══════════════════════════════════════════════════════════════

    def _save_builder_state(self):
        if self._state_job:
            self.after_cancel(self._state_job)
        self._state_job = self.after(800, self._save_builder_state_now)

    def _save_builder_state_now(self):
        self._state_job = None
        try:
            self.store.save_state({"slots": self._slots, "rules": self._rules,
                                   "sep": self._sep_var.get(), "template": self._active_template,
                                   "wildcard": self._wild_var.get()})
        except OSError:
            pass

    def _restore_builder_state(self):
        st = self.store.load_state()
        self._slots = [normalize_slot(s) for s in st.get("slots", []) if isinstance(s, dict)]
        self._rules = [r for r in st.get("rules", []) if isinstance(r, dict)]
        self._active_template = st.get("template") or None
        return st
