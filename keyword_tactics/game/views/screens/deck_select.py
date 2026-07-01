"""Deck select phase: pick a dungeon to delve into."""

import pygame

from ... import theme
from ...config import COLORS, SCREEN_HEIGHT, SCREEN_WIDTH


# Layout constants shared with input_handler / app.py.
DECK_ROW_H = 105
# Carve a list viewport between the header (~120px) and the bottom hint bar.
DECK_LIST_RECT = pygame.Rect(
    SCREEN_WIDTH // 2 - 360, 120, 720, SCREEN_HEIGHT - 160,
)


def deck_visible_count() -> int:
    """How many deck rows fit inside DECK_LIST_RECT."""
    return max(1, DECK_LIST_RECT.h // DECK_ROW_H)


def draw(screen, fonts, state):
    """Render the deck-select screen."""
    title = fonts['large'].render("SELECT A DUNGEON", True, COLORS['accent'])
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 50))
    screen.blit(title, title_rect)

    cleared = len(state.completed_decks)
    total = len(state.active_decks)
    progress = fonts['medium'].render(
        f"Progress: {cleared}/{total} Dungeons Cleared", True, COLORS['success'],
    )
    progress_rect = progress.get_rect(center=(SCREEN_WIDTH // 2, 90))
    screen.blit(progress, progress_rect)

    # Clip deck drawing to the viewport so scrolled content can't bleed over
    # the header or bottom hint.
    prev_clip = screen.get_clip()
    screen.set_clip(DECK_LIST_RECT)

    all_ids = list(state.deck_registry.all_ids())
    scroll = state.deck_select_scroll
    visible = deck_visible_count()
    visible_ids = all_ids[scroll:scroll + visible]

    base_y = DECK_LIST_RECT.y + 10
    for i, deck_id in enumerate(visible_ids):
        y = base_y + i * DECK_ROW_H
        _draw_deck_row(screen, fonts, state, deck_id, y)

    screen.set_clip(prev_clip)

    # Scroll indicators outside the clip area.
    if scroll > 0:
        screen.blit(
            fonts['small'].render("^ scroll up", True, COLORS['text_dim']),
            (DECK_LIST_RECT.right - 110, DECK_LIST_RECT.y - 18),
        )
    if scroll + visible < len(all_ids):
        screen.blit(
            fonts['small'].render("v scroll down", True, COLORS['text_dim']),
            (DECK_LIST_RECT.right - 110, DECK_LIST_RECT.bottom + 2),
        )


def _draw_deck_row(screen, fonts, state, deck_id, y):
    deck_data = state.deck_registry.decks[deck_id]
    active_deck = state.active_decks.get(deck_id)

    monsters_left = active_deck.get_remaining_count() if active_deck else 0
    total_monsters = (
        active_deck.total_monsters if active_deck else len(deck_data['monsters'])
    )
    is_completed = active_deck and (active_deck.is_completed or active_deck.is_empty())

    panel_rect = pygame.Rect(SCREEN_WIDTH // 2 - 350, y - 10, 700, 95)
    panel_color = (theme.mix(COLORS['bg'], COLORS['success'], 0.22)
                   if is_completed else COLORS['panel'])
    pygame.draw.rect(screen, panel_color, panel_rect, border_radius=8)
    pygame.draw.rect(screen, COLORS['panel_light'], panel_rect, 2, border_radius=8)

    if is_completed:
        name_text = f"WIN {deck_data['name']} - CLEARED!"
        name_color = COLORS['success']
    else:
        name_text = deck_data['name']
        name_color = COLORS['accent']
    screen.blit(
        fonts['medium'].render(name_text, True, name_color),
        (SCREEN_WIDTH // 2 - 340, y),
    )

    desc = deck_data.get('description', '')
    screen.blit(
        fonts['small'].render(desc, True, COLORS['text_dim']),
        (SCREEN_WIDTH // 2 - 340, y + 30),
    )

    if not is_completed:
        monsters_text = f"Monsters: {monsters_left}/{total_monsters}"
        screen.blit(
            fonts['small'].render(monsters_text, True, COLORS['warning']),
            (SCREEN_WIDTH // 2 + 220, y),
        )

        kills = active_deck.monsters_defeated if active_deck else 0
        if kills > 0:
            rare_chance = min(20, 3 + kills * 2.5)
            kills_text = f"Kills: {kills} | Drop bonus: +{int(rare_chance - 3)}% rare"
            screen.blit(
                fonts['small'].render(kills_text, True, COLORS['success']),
                (SCREEN_WIDTH // 2 + 180, y + 26),
            )

        common_kw = deck_data.get('common_keywords', [])[:5]
        if common_kw:
            kw_text = "Keywords: " + ", ".join(common_kw)
            screen.blit(
                fonts['small'].render(kw_text, True, COLORS['text_dim']),
                (SCREEN_WIDTH // 2 - 340, y + 58),
            )
