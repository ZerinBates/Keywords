"""Theme manager — the single source of truth for colour and spacing.

Everything visual flows from here. The game's runtime palette
(``config.COLORS``) is *derived* from the active 6-colour palette below, so
the whole game re-themes at once.

To try a different look:
    1. Edit ``ACTIVE_PALETTE`` to another key in ``PALETTES`` (or add your own
       6-colour entry), then restart the game.
That's it — menu, panels, buttons, text boxes and every screen follow.

A palette is exactly SIX roles. The main menu uses *only* these six:

    bg       window background (darkest)
    surface  panels / cards / text boxes
    primary  interactive highlight (borders, headers, selection)
    text     primary readable text (lightest)
    muted    secondary / dim text, subtle lines
    accent   call-to-action / reward highlight

Semantic status colours (success / danger / warning) and keyword element
colours live outside the 6-colour palette so meaning stays constant no matter
which palette is active.
"""

# ---------------------------------------------------------------------------
# Spacing scale (pixels) — use these tokens instead of magic numbers.
# ---------------------------------------------------------------------------
PADDING = {
    'XS': 4,
    'S':  8,
    'M':  16,
    'L':  24,
    'XL': 40,
}
# Convenience aliases (so callers can write `theme.M` instead of PADDING['M']).
XS, S, M, L, XL = PADDING['XS'], PADDING['S'], PADDING['M'], PADDING['L'], PADDING['XL']

# Corner radii + standard border thickness, also standardized.
# Kept tight/square for the chunky pixel-art aesthetic.
RADIUS = {'S': 2, 'M': 3, 'L': 4, 'PILL': 999}
BORDER_W = 2


# ---------------------------------------------------------------------------
# 6-colour palettes. Active one drives the whole game.
# ---------------------------------------------------------------------------
PALETTES = {
    # Double Edged: dark plum/purple pixel-art look (mockup palette).
    'double_edged': {
        'bg':      (17, 12, 23),     # #110C17  near-black plum
        'surface': (40, 30, 54),     # #281E36  purple panel
        'primary': (183, 162, 222),  # #B7A2DE  lavender
        'text':    (240, 234, 248),  # #F0EAF8  pale lavender-white
        'muted':   (142, 128, 168),  # #8E80A8  dusty violet
        'accent':  (242, 198, 92),   # #F2C65C  coin gold
    },
    # Cool, modern. Dark slate + teal primary + warm amber accent.
    'slate_teal': {
        'bg':      (15, 20, 25),     # #0F1419  ink slate
        'surface': (28, 38, 48),     # #1C2630  panel
        'primary': (45, 212, 191),   # #2DD4BF  teal
        'text':    (241, 245, 249),  # #F1F5F9  near-white
        'muted':   (148, 163, 184),  # #94A3B8  slate grey
        'accent':  (251, 191, 36),   # #FBBF24  amber
    },
    # Refined version of the game's original navy + cyan identity.
    'midnight': {
        'bg':      (22, 22, 30),     # #16161E
        'surface': (35, 35, 51),     # #232333
        'primary': (122, 162, 247),  # #7AA2F7  cyan-blue
        'text':    (236, 236, 242),  # #ECECF2
        'muted':   (138, 143, 163),  # #8A8FA3
        'accent':  (224, 175, 104),  # #E0AF68  amber/gold
    },
    # Purple + gold fantasy feel.
    'royal': {
        'bg':      (26, 22, 38),     # #1A1626
        'surface': (42, 36, 64),     # #2A2440
        'primary': (167, 139, 250),  # #A78BFA  violet
        'text':    (243, 240, 255),  # #F3F0FF
        'muted':   (153, 144, 181),  # #9990B5
        'accent':  (252, 211, 77),   # #FCD34D  gold
    },
}

# >>> Change this line to re-theme the whole game. <<<
ACTIVE_PALETTE = 'double_edged'


# ---------------------------------------------------------------------------
# Semantic status colours — shared across palettes (meaning must stay stable).
# ---------------------------------------------------------------------------
SEMANTIC = {
    'success': (90, 200, 120),
    'danger':  (240, 100, 100),
    'warning': (245, 180, 70),
}

# Keyword / element colours — game data, intentionally palette-independent.
ELEMENTS = {
    'fire':   (255, 100, 50),
    'water':  (50, 150, 255),
    'earth':  (150, 120, 80),
    'nature': (80, 200, 80),
    'dark':   (100, 50, 150),
    'light':  (255, 255, 200),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def shift(color, amount):
    """Lighten (amount > 0) or darken (amount < 0) an RGB colour, clamped."""
    return tuple(max(0, min(255, c + amount)) for c in color[:3])


def mix(a, b, t):
    """Blend two RGB colours; t in [0,1] (0 = a, 1 = b)."""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def palette(name=None):
    """Return the active (or named) 6-colour palette dict."""
    return PALETTES[name or ACTIVE_PALETTE]


def pad(*tokens):
    """Sum one or more padding tokens, e.g. pad('M') or pad('S', 'XS')."""
    return sum(PADDING[t] for t in tokens)


# ---------------------------------------------------------------------------
# Derived runtime colour map. config.COLORS is built from this so every
# `COLORS['name']` reference across the codebase re-themes automatically.
# ---------------------------------------------------------------------------
def build_colors(name=None):
    p = palette(name)
    surface = p['surface']
    return {
        # --- six core roles (also exposed under their own names) ---
        'bg':           p['bg'],
        'surface':      surface,
        'primary':      p['primary'],
        'muted':        p['muted'],

        # --- game-wide aliases mapped onto the six roles + derived tones ---
        'panel':        surface,
        'panel_light':  shift(surface, 18),     # raised cards / hover
        'panel_dark':   shift(surface, -10),    # inset wells / list bg
        'well':         shift(p['bg'], 8),      # text-box / search inset
        'border':       shift(surface, 34),     # standard 1-2px borders
        'divider':      shift(surface, 24),     # hairline separators
        'text':         p['text'],
        'text_dim':     p['muted'],
        'accent':       p['primary'],

        # --- semantic status colours ---
        'success':      SEMANTIC['success'],
        'danger':       SEMANTIC['danger'],
        'warning':      SEMANTIC['warning'],
        'gold':         p['accent'],

        # --- keyword / element colours ---
        **ELEMENTS,
    }
