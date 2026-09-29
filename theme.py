"""Farbpalette und Schriften.

Alle Farben hängen als Attribute an der Klasse `C` und werden per
`C.apply(theme, accent)` umgeschaltet. Widgets lesen die Farben erst beim
Erzeugen, deshalb baut die App nach einem Themenwechsel ihre Oberfläche neu.
"""

import customtkinter as ctk

ACCENTS = {
    "cyan":   "#00d4ff",
    "green":  "#22c55e",
    "pink":   "#f472b6",
    "orange": "#fb923c",
    "blue":   "#60a5fa",
    "gold":   "#fbbf24",
}

ACCENTS_LIGHT = {
    "cyan":   "#0284c7",
    "green":  "#15803d",
    "pink":   "#be185d",
    "orange": "#c2410c",
    "blue":   "#1d4ed8",
    "gold":   "#b45309",
}

DARK = dict(
    BG="#06060f", SURF="#0b0b1a", SURF2="#0f0f22", SURF3="#14142e",
    BORDER="#1c1c38", BORD_H="#2c2c55",
    PURP="#a78bfa", PURP_DIM="#1a0d40", PURP_MID="#3d2080",
    RED="#f87171", RED_DIM="#1e0808", RED_MID="#4a1010",
    GOLD="#fbbf24", GOLD_DIM="#332200", GOLD_MID="#554400",
    GREEN="#4ade80",
    TXT="#dce4f5", TXT2="#4a5a78", TXT3="#222840",
    OVERLAY="#020208", SEL="#1b2a4a",
)

LIGHT = dict(
    BG="#eef0f6", SURF="#ffffff", SURF2="#f5f6fb", SURF3="#e6e8f2",
    BORDER="#d6d9e6", BORD_H="#bfc4d8",
    PURP="#6d28d9", PURP_DIM="#ede9fe", PURP_MID="#ddd6fe",
    RED="#dc2626", RED_DIM="#fee2e2", RED_MID="#fecaca",
    GOLD="#b45309", GOLD_DIM="#fef3c7", GOLD_MID="#fde68a",
    GREEN="#15803d",
    TXT="#161a2b", TXT2="#5b6480", TXT3="#9aa1b8",
    OVERLAY="#c9ccd8", SEL="#dbe4ff",
)


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def blend(a, b, t):
    """Mischt Farbe a nach b (t=0 → a, t=1 → b)."""
    ra, rb = _hex_to_rgb(a), _hex_to_rgb(b)
    return _rgb_to_hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


_FONT_CACHE = {}


def px(n):
    """Logische Pixel → physische Pixel (für reine tk-Widgets, die CTk nicht skaliert)."""
    return int(round(n * C.dpi))


class C:
    """Aktive Farbpalette (Klassenattribute, siehe apply)."""
    theme = "dark"
    accent = "cyan"
    font_scale = 1.0
    dpi = 1.0          # Windows-Skalierung (1.5 bei 150 %), wird von der App gesetzt

    @classmethod
    def apply(cls, theme="dark", accent="cyan", font_scale=1.0):
        base = LIGHT if theme == "light" else DARK
        for k, v in base.items():
            setattr(cls, k, v)
        acc = (ACCENTS_LIGHT if theme == "light" else ACCENTS).get(accent, ACCENTS["cyan"])
        cls.ACC = acc
        if theme == "light":
            cls.ACC_DIM = blend(acc, "#ffffff", 0.85)
            cls.ACC_MID = blend(acc, "#ffffff", 0.7)
        else:
            cls.ACC_DIM = blend(acc, base["BG"], 0.82)
            cls.ACC_MID = blend(acc, base["BG"], 0.65)
        cls.theme = theme
        cls.accent = accent
        try:
            cls.font_scale = max(0.7, min(1.6, float(font_scale)))
        except (TypeError, ValueError):
            cls.font_scale = 1.0
        _FONT_CACHE.clear()
        ctk.set_appearance_mode("light" if theme == "light" else "dark")


C.apply()

# ─── Schriften ────────────────────────────────────────────────────────────────

def cfont(size, weight=None, family=None):
    """CTkFont-Objekte sind teuer — einmal erstellen und wiederverwenden."""
    key = ("ctk", size, weight, family)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ctk.CTkFont(size=int(round(size * C.font_scale)),
                                       weight=weight, family=family)
    return _FONT_CACHE[key]


def F(size, bold=False, mono=False):
    """Tk-Font-Tupel, skaliert mit der eingestellten Schriftgröße."""
    fam = "Consolas" if mono else "Segoe UI"
    s = int(round(size * C.font_scale))
    return (fam, s, "bold") if bold else (fam, s)
