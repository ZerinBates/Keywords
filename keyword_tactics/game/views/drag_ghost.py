"""Drag ghost - the semi-transparent card that follows the cursor during a drag."""

import pygame

from ..config import COLORS
from ..models import GamePhase
from ..config import SCREEN_WIDTH


def draw_drag_ghost(screen, fonts, state, drag_adv_index: int, drag_pos):
    """Draw the ghost card following the cursor and any drop-zone highlights."""
    if drag_adv_index < 0 or drag_adv_index >= len(state.party):
        return

    adv = state.party[drag_adv_index]
    dx, dy = drag_pos

    # Card dimensions
    cw, ch = 140, 100
    gx = dx - cw // 2
    gy = dy - ch // 2

    # Semi-transparent ghost surface
    ghost = pygame.Surface((cw, ch), pygame.SRCALPHA)
    ghost.fill((60, 80, 120, 180))
    pygame.draw.rect(ghost, (100, 200, 255, 220), (0, 0, cw, ch), 3, border_radius=8)

    # Name
    ghost.blit(fonts['medium'].render(adv.name, True, (255, 255, 255)), (8, 8))

    # Power summary
    power = adv.get_base_points()
    mult = adv.get_multiplier()
    stat_text = f"Pwr: {power}x{mult}={power * mult}"
    ghost.blit(fonts['small'].render(stat_text, True, (200, 220, 255)), (8, 42))

    # Keywords
    keywords = adv.get_all_keywords()[:3]
    kw_text = ", ".join(keywords) if keywords else "none"
    ghost.blit(fonts['small'].render(kw_text, True, (180, 180, 200)), (8, 65))

    screen.blit(ghost, (gx, gy))

    # Drop-zone highlights
    if state.phase == GamePhase.DELVE_SETUP:
        square_rects = [
            pygame.Rect(20, 128, 300, 200),
            pygame.Rect(330, 128, 300, 200),
            pygame.Rect(640, 128, 300, 200),
            pygame.Rect(950, 128, 300, 200),
        ]
        for i, rect in enumerate(square_rects):
            if i < len(state.front_row):
                sq = state.front_row[i]
                if sq['adventurer'] is None and rect.collidepoint(dx, dy):
                    highlight = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                    highlight.fill((100, 200, 255, 50))
                    screen.blit(highlight, rect.topleft)
                    pygame.draw.rect(screen, (100, 200, 255, 180), rect, 3, border_radius=8)

    elif state.phase == GamePhase.BOSS_CHOICE:
        boss_rect = pygame.Rect(SCREEN_WIDTH // 2 - 200, 80, 400, 250)
        if boss_rect.collidepoint(dx, dy):
            highlight = pygame.Surface((boss_rect.w, boss_rect.h), pygame.SRCALPHA)
            highlight.fill((255, 100, 100, 50))
            screen.blit(highlight, boss_rect.topleft)
            pygame.draw.rect(screen, (255, 150, 100, 200), boss_rect, 3, border_radius=8)
