"""Main menu screen rendering.

Rewritten against the theme manager: this screen uses ONLY the six roles of
the active palette (bg / surface / primary / text / muted / accent) and the
standardized padding scale (XS/S/M/L/XL). Swap ``theme.ACTIVE_PALETTE`` to
re-skin it instantly.
"""

import pygame

from ... import theme
from ...config import SCREEN_WIDTH, SCREEN_HEIGHT

# Spacing tokens.
XS, S, M, L, XL = theme.XS, theme.S, theme.M, theme.L, theme.XL
R_M, R_L = theme.RADIUS['M'], theme.RADIUS['L']


def _chip(screen, font, text, color, center_x, y, pal):
    """A small rounded status chip drawn in surface + a coloured label."""
    label = font.render(text, True, color)
    w = label.get_width() + 2 * M
    h = label.get_height() + 2 * XS
    rect = pygame.Rect(center_x - w // 2, y, w, h)
    pygame.draw.rect(screen, pal['surface'], rect, border_radius=R_M)
    pygame.draw.rect(screen, color, rect, 1, border_radius=R_M)
    screen.blit(label, label.get_rect(center=rect.center))
    return rect.bottom


def draw(screen, fonts, state):
    """Render the title screen with instructions, six-colour palette only."""
    pal = theme.palette()
    cx = SCREEN_WIDTH // 2

    # ---- Title block ----
    title = fonts['title'].render("KEYWORD TACTICS", True, pal['primary'])
    screen.blit(title, title.get_rect(center=(cx, 96)))

    # Accent underline beneath the title.
    underline = pygame.Rect(0, 0, title.get_width() + 2 * M, 3)
    underline.center = (cx, 96 + title.get_height() // 2 + S)
    pygame.draw.rect(screen, pal['accent'], underline, border_radius=R_M)

    subtitle = fonts['medium'].render("A Tactical Deck Builder", True, pal['muted'])
    screen.blit(subtitle, subtitle.get_rect(center=(cx, 150)))

    # ---- Status chips (debug / saved run) ----
    sy = 184
    if getattr(state, 'debug_unlock_all', False):
        sy = _chip(screen, fonts['small'], "DEBUG: ALL UNLOCKED",
                   pal['accent'], cx, sy, pal) + S
    if state.has_resumable_run():
        sy = _chip(screen, fonts['small'], "Saved run available",
                   pal['primary'], cx, sy, pal) + S

    # ---- Unlock progress (subtle) ----
    try:
        if not getattr(state, 'debug_unlock_all', False):
            total_chars = len(state.adventurer_registry.all_ids())
            total_items = len(state.item_registry.all_ids())
            unlocked_c = len(state.unlocked_characters)
            unlocked_i = len(state.unlocked_items)
            progress = (f"Classes {unlocked_c}/{total_chars}"
                        f"     Items {unlocked_i}/{total_items}")
            surf = fonts['small'].render(progress, True, pal['muted'])
            screen.blit(surf, surf.get_rect(center=(cx, sy + S)))
    except Exception:
        pass

    # ---- Instructions panel (bottom) ----
    # The action buttons (New Game, etc.) are drawn by the renderer between the
    # title block and this panel.
    panel = pygame.Rect(0, 0, 720, 232)
    panel.center = (cx, SCREEN_HEIGHT - M - panel.height // 2)
    pygame.draw.rect(screen, pal['surface'], panel, border_radius=R_L)
    pygame.draw.rect(screen, pal['primary'], panel, theme.BORDER_W, border_radius=R_L)

    heading = fonts['medium'].render("How to play", True, pal['primary'])
    screen.blit(heading, (panel.x + M, panel.y + M))
    pygame.draw.line(
        screen, pal['muted'],
        (panel.x + M, panel.y + M + heading.get_height() + XS),
        (panel.right - M, panel.y + M + heading.get_height() + XS), 1,
    )

    instructions = [
        ("Seamless delve: rows of 4 monsters, escalating multipliers", 'text'),
        ("Place ALL adventurers each row — multipliers boost your power", 'text'),
        ("Swap items mid-delve with the loot you find", 'text'),
        ("Risk the hidden Boss for epic rewards and new classes", 'accent'),
        ("Clear every deck fully to win the run", 'accent'),
        ("TAB  keyword reference          F11  fullscreen", 'primary'),
    ]
    y = panel.y + M + heading.get_height() + S + XS
    row_h = (panel.bottom - S - y) // len(instructions)
    for text_str, role in instructions:
        surf = fonts['small'].render(text_str, True, pal[role])
        screen.blit(surf, (panel.x + M, y))
        y += row_h
