"""Unlock-reveal screen - shown after a delve when the player has unlocked
new classes (boss-kill) and/or new items (deck-clear).

Renders a paginated grid of cards: each card shows the sprite, the name,
and a small type/rarity badge for items or ability name for characters.
A Continue button at the bottom (built in app.py) acknowledges the reveal
and transitions back to PREPARATION.
"""

from typing import List, Tuple

import pygame

from ..widgets import Panel  # noqa: F401
from ...config import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT


# Layout constants
_TITLE_Y         = 60
_SUBTITLE_Y      = 110
_GRID_TOP        = 160
_GRID_BOTTOM     = SCREEN_HEIGHT - 110   # leave room for Continue button
_CARD_W          = 220
_CARD_H          = 200
_CARD_GAP_X      = 24
_CARD_GAP_Y      = 24
_CARDS_PER_ROW   = 4
_CARDS_PER_PAGE  = _CARDS_PER_ROW * 3    # 12 per page

# Rarity color & background mapping (matches preparation/shop styling)
_RARITY_BORDER = {
    'scrap':    (120, 120, 120),
    'common':   COLORS['text_dim'],
    'uncommon': COLORS['success'],
    'rare':     COLORS['accent'],
}
_RARITY_BG = {
    'scrap':    (42, 38, 38),
    'common':   (40, 42, 50),
    'uncommon': (32, 50, 36),
    'rare':     (36, 40, 58),
}


def _resolve_entry(state, entry: dict):
    """Look up display data for a pending_unlock_reveals entry.

    Returns a dict with keys: type, id, name, subtitle, border_color,
    bg_color, sprite_key. Returns None if the id is no longer valid.
    """
    etype = entry.get('type')
    eid = entry.get('id')
    if etype == 'character':
        tmpl = state.adventurer_registry.get_template(eid)
        if not tmpl:
            return None
        return {
            'type':         'character',
            'id':           eid,
            'name':         tmpl.get('name', eid),
            'subtitle':     tmpl.get('ability_name') or "New Class",
            'border_color': COLORS['gold'],
            'bg_color':     (50, 46, 30),
        }
    if etype == 'item':
        item = state.item_registry.items.get(eid)
        if not item:
            return None
        rarity = getattr(item, 'rarity', 'common')
        return {
            'type':         'item',
            'id':           eid,
            'name':         getattr(item, 'name', eid),
            'subtitle':     rarity.capitalize(),
            'border_color': _RARITY_BORDER.get(rarity, COLORS['text']),
            'bg_color':     _RARITY_BG.get(rarity, COLORS['panel']),
        }
    return None


def _layout_grid(num_cards: int) -> List[Tuple[int, int]]:
    """Compute (x, y) positions for up to _CARDS_PER_PAGE cards, centered."""
    positions: List[Tuple[int, int]] = []
    rows = (num_cards + _CARDS_PER_ROW - 1) // _CARDS_PER_ROW
    total_w = _CARDS_PER_ROW * _CARD_W + (_CARDS_PER_ROW - 1) * _CARD_GAP_X
    start_x = (SCREEN_WIDTH - total_w) // 2

    for i in range(num_cards):
        row = i // _CARDS_PER_ROW
        col = i % _CARDS_PER_ROW
        # Last row may be short: center its cards within the row
        if row == rows - 1:
            last_row_count = num_cards - row * _CARDS_PER_ROW
            row_w = last_row_count * _CARD_W + (last_row_count - 1) * _CARD_GAP_X
            row_start_x = (SCREEN_WIDTH - row_w) // 2
            col_in_row = i - row * _CARDS_PER_ROW
            x = row_start_x + col_in_row * (_CARD_W + _CARD_GAP_X)
        else:
            x = start_x + col * (_CARD_W + _CARD_GAP_X)
        y = _GRID_TOP + row * (_CARD_H + _CARD_GAP_Y)
        positions.append((x, y))
    return positions


def _draw_card(screen, fonts, sprite_manager, card_data: dict,
               x: int, y: int):
    """Draw a single unlock card."""
    rect = pygame.Rect(x, y, _CARD_W, _CARD_H)

    # Background + border
    pygame.draw.rect(screen, card_data['bg_color'], rect, border_radius=8)
    pygame.draw.rect(screen, card_data['border_color'], rect, width=2, border_radius=8)

    # Type badge in top-left corner (NEW)
    badge_text = "NEW CLASS" if card_data['type'] == 'character' else "NEW ITEM"
    badge_color = (
        COLORS['gold'] if card_data['type'] == 'character'
        else card_data['border_color']
    )
    badge_surf = fonts['tiny'].render(badge_text, True, badge_color)
    screen.blit(badge_surf, (x + 10, y + 8))

    # Sprite area (centered horizontally, upper portion of card)
    sprite_size = 96 if card_data['type'] == 'character' else 80
    sprite = None
    if sprite_manager is not None:
        try:
            if card_data['type'] == 'character':
                sprite = sprite_manager.get_character_sprite(
                    card_data['id'], (sprite_size, sprite_size),
                )
            else:
                sprite = sprite_manager.get_item_sprite(
                    card_data['id'], (sprite_size, sprite_size),
                )
        except Exception:
            sprite = None

    sprite_y = y + 32
    if sprite is not None:
        sprite_rect = sprite.get_rect(
            center=(x + _CARD_W // 2, sprite_y + sprite_size // 2),
        )
        screen.blit(sprite, sprite_rect)
    else:
        # Placeholder if sprite missing
        ph_rect = pygame.Rect(
            x + (_CARD_W - sprite_size) // 2, sprite_y,
            sprite_size, sprite_size,
        )
        pygame.draw.rect(screen, COLORS['panel_light'], ph_rect, border_radius=6)
        glyph = "?" if card_data['type'] == 'item' else "@"
        gsurf = fonts['title'].render(glyph, True, COLORS['text_dim'])
        screen.blit(gsurf, gsurf.get_rect(center=ph_rect.center))

    # Name (truncated if needed)
    name_text = card_data['name']
    name_surf = fonts['medium'].render(name_text, True, COLORS['text'])
    if name_surf.get_width() > _CARD_W - 20:
        # Try smaller font then truncate with ellipsis
        name_surf = fonts['small'].render(name_text, True, COLORS['text'])
        while name_surf.get_width() > _CARD_W - 20 and len(name_text) > 4:
            name_text = name_text[:-1]
            name_surf = fonts['small'].render(name_text + "…", True, COLORS['text'])
    name_rect = name_surf.get_rect(
        center=(x + _CARD_W // 2, y + _CARD_H - 42),
    )
    screen.blit(name_surf, name_rect)

    # Subtitle (ability name or rarity)
    sub_surf = fonts['small'].render(
        card_data['subtitle'], True, card_data['border_color'],
    )
    if sub_surf.get_width() > _CARD_W - 20:
        sub_surf = fonts['tiny'].render(
            card_data['subtitle'], True, card_data['border_color'],
        )
    sub_rect = sub_surf.get_rect(
        center=(x + _CARD_W // 2, y + _CARD_H - 18),
    )
    screen.blit(sub_surf, sub_rect)


def draw(screen, fonts, state, sprite_manager):
    """Render the unlock-reveal screen.

    Reads state.unlock_reveal_page (defaulting to 0) for pagination
    when there are more than _CARDS_PER_PAGE unlocks.
    """
    entries = state.pending_unlock_reveals or []
    resolved = [r for r in (_resolve_entry(state, e) for e in entries) if r]

    total = len(resolved)
    page = max(0, getattr(state, 'unlock_reveal_page', 0))
    if total == 0:
        page_count = 1
    else:
        page_count = (total + _CARDS_PER_PAGE - 1) // _CARDS_PER_PAGE
    if page >= page_count:
        page = page_count - 1
        state.unlock_reveal_page = page

    start = page * _CARDS_PER_PAGE
    visible = resolved[start:start + _CARDS_PER_PAGE]

    # ---- Title ----
    title_surf = fonts['title'].render(
        "New Unlocks!", True, COLORS['gold'],
    )
    screen.blit(title_surf, title_surf.get_rect(
        center=(SCREEN_WIDTH // 2, _TITLE_Y),
    ))

    # ---- Subtitle: counts ----
    n_classes = sum(1 for r in resolved if r['type'] == 'character')
    n_items = sum(1 for r in resolved if r['type'] == 'item')
    parts = []
    if n_classes:
        parts.append(f"{n_classes} class" + ("es" if n_classes != 1 else ""))
    if n_items:
        parts.append(f"{n_items} item" + ("s" if n_items != 1 else ""))
    if parts:
        subtitle = "Unlocked: " + " and ".join(parts)
    else:
        subtitle = "Nothing new this run."
    sub_surf = fonts['medium'].render(subtitle, True, COLORS['text_dim'])
    screen.blit(sub_surf, sub_surf.get_rect(
        center=(SCREEN_WIDTH // 2, _SUBTITLE_Y),
    ))

    # ---- Grid of cards ----
    positions = _layout_grid(len(visible))
    for card_data, (x, y) in zip(visible, positions):
        _draw_card(screen, fonts, sprite_manager, card_data, x, y)

    # ---- Page indicator (only when >1 page) ----
    if page_count > 1:
        page_text = f"Page {page + 1} / {page_count}"
        page_surf = fonts['small'].render(page_text, True, COLORS['text_dim'])
        screen.blit(page_surf, page_surf.get_rect(
            center=(SCREEN_WIDTH // 2, _GRID_BOTTOM + 8),
        ))
