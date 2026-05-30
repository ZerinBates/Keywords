"""
Global configuration: screen dimensions, FPS, color palette.

Visual constants are now centralized in ``game/theme.py`` (the theme manager).
``COLORS`` is *derived* from the active 6-colour palette there, so changing
``theme.ACTIVE_PALETTE`` re-themes the entire game. Spacing tokens
(XS/S/M/L/XL) are re-exported here too for convenience.
"""

from . import theme

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800
FPS = 60

# Runtime colour map, built from the active theme palette. Every
# `COLORS['name']` lookup across the game flows from the theme manager.
COLORS = theme.build_colors()

# Standardized spacing scale (pixels), re-exported for convenience.
PADDING = theme.PADDING
XS, S, M, L, XL = theme.XS, theme.S, theme.M, theme.L, theme.XL
RADIUS = theme.RADIUS
