"""Shop phase: three-column loadout layout — roster / hero loadout / armory.

Mirrors the delve Items screen: PARTY ROSTER on the left (with per-hero
Unequip + Unequip All), the merged HERO LOADOUT column in the middle, and a
right column that toggles between your Inventory and the Shop stock, with
search + keyword filter.

Every interactive rect is stashed in ``state._prep_ui`` each frame so the
input handler hit-tests exactly what was drawn.
"""

import pygame

from ... import theme
from ...config import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT
from .. import paper_doll
from .. import widgets

# ---------------------------------------------------------------------------
# Layout constants (kept in one place so renderer + input_handler agree)
# ---------------------------------------------------------------------------
PREP_LEFT_RECT  = pygame.Rect(20, 68, 300, 676)
PREP_MID_RECT   = pygame.Rect(340, 68, 420, 676)
PREP_RIGHT_RECT = pygame.Rect(780, 68, 480, 676)
PREP_CARD_H     = 132
PREP_CARD_GAP   = 10
# Space reserved at the bottom of the roster column for [Unequip All].
PREP_ROSTER_FOOTER = 48

_pixel_box = widgets.draw_pixel_box


def prep_roster_visible_count() -> int:
    """How many roster cards fit above the Unequip All footer."""
    return max(1, (PREP_LEFT_RECT.h - PREP_ROSTER_FOOTER - 20)
               // (PREP_CARD_H + PREP_CARD_GAP))


def draw(screen, fonts, state):
    """Render the shop screen."""
    # Clear any leftover king/dunce role badges from the previous delve.
    for adv in state.roster:
        setattr(adv, '_role_badge', None)

    ui = {'roster_cards': [], 'unequip_btns': [], 'unequip_all': None,
          'toggle_rects': {}, 'filter_btn': None, 'filter_chips': [],
          'filter_clear': None, 'filter_panel': None, 'search_rect': None,
          'item_rows': [], 'hire_rows': []}
    state._prep_ui = ui

    # ---- Top bar: title + coins + progress ----
    screen.blit(fonts['medium'].render("SHOP", True, COLORS['accent']), (20, 12))
    screen.blit(fonts['medium'].render(f"Coins: {state.coins}", True,
                                       COLORS['gold']), (130, 12))
    cleared = len(state.completed_decks)
    total = len(state.active_decks)
    screen.blit(fonts['medium'].render(
        f"Dungeons Cleared: {cleared}/{total}", True, COLORS['success']),
        (320, 12))

    # ---- Column headers ----
    sel_ok = 0 <= state.selected_party_index < len(state.roster)
    sel_adv = state.roster[state.selected_party_index] if sel_ok else None
    mid_title = f"HERO LOADOUT - {sel_adv.name}" if sel_adv else "HERO LOADOUT"
    right_title = ("ARMORY & INVENTORY" if state.prep_view == 'inventory'
                   else "SHOP STOCK")
    for text, rect in (("PARTY ROSTER", PREP_LEFT_RECT),
                       (mid_title, PREP_MID_RECT),
                       (right_title, PREP_RIGHT_RECT)):
        hs = fonts['medium'].render(text, True, COLORS['text'])
        screen.blit(hs, hs.get_rect(centerx=rect.centerx, y=42))

    # ---- LEFT: roster (scrollable) + unequip controls ----
    _pixel_box(screen, PREP_LEFT_RECT)
    visible_n = prep_roster_visible_count()
    max_scroll = max(0, len(state.roster) - visible_n)
    state.roster_scroll = max(0, min(state.roster_scroll, max_scroll))
    if state.roster_scroll > 0:
        screen.blit(fonts['tiny'].render("^ scroll up", True, COLORS['text_dim']),
                    (PREP_LEFT_RECT.right - 84, PREP_LEFT_RECT.y + 4))

    end = min(len(state.roster), state.roster_scroll + visible_n)
    for row, roster_idx in enumerate(range(state.roster_scroll, end)):
        adv = state.roster[roster_idx]
        cy = PREP_LEFT_RECT.y + 14 + row * (PREP_CARD_H + PREP_CARD_GAP)
        card = pygame.Rect(PREP_LEFT_RECT.x + 8, cy,
                           PREP_LEFT_RECT.w - 16, PREP_CARD_H)
        ub = widgets.draw_roster_card(
            screen, fonts, state, card, adv,
            roster_idx == state.selected_party_index, paper_doll)
        ui['roster_cards'].append((roster_idx, card))
        if ub is not None:
            ui['unequip_btns'].append((roster_idx, ub))

    if end < len(state.roster):
        screen.blit(fonts['tiny'].render("v scroll down", True, COLORS['text_dim']),
                    (PREP_LEFT_RECT.right - 94,
                     PREP_LEFT_RECT.bottom - PREP_ROSTER_FOOTER - 12))

    ua = pygame.Rect(PREP_LEFT_RECT.x + 8, PREP_LEFT_RECT.bottom - 42,
                     PREP_LEFT_RECT.w - 16, 32)
    pygame.draw.rect(screen, COLORS['panel_dark'], ua, border_radius=3)
    pygame.draw.rect(screen, COLORS['danger'], ua, 2, border_radius=3)
    uas = fonts['small'].render("[ Unequip All ]", True, COLORS['text'])
    screen.blit(uas, uas.get_rect(center=ua.center))
    ui['unequip_all'] = ua

    # ---- MIDDLE: hero loadout (shared widget) ----
    state._prep_equipped_rows = widgets.draw_hero_loadout_column(
        screen, fonts, state, PREP_MID_RECT, sel_adv,
        state.prep_equipped_scroll, paper_doll)

    # ---- RIGHT: Inventory / Shop toggle ----
    if state.prep_view == 'inventory':
        items = state.get_filtered_inventory()
        res = widgets.draw_item_list_panel(
            screen, fonts, state, PREP_RIGHT_RECT,
            items=items,
            scroll=state.inventory_scroll,
            search_text=state.prep_inv_search,
            search_active=state.prep_inv_search_active,
            header_text=(f"Inventory ({len(state.inventory)}) — "
                         "click: equip | Ctrl+click: sell"),
            sell_price_func=lambda it: state.get_item_sell_price(it),
            paper_doll_module=paper_doll,
            hover_pos=state.hover_pos,
            toggle_labels=("Inventory", "Shop"),
            toggle_active=0,
            filter_selected=state.prep_kw_filter,
            filter_open=state.prep_filter_open,
        )
        pool = list(state.inventory)
    else:
        stock = list(state.shop_items) + list(state.dead_adv_loot)
        stock = widgets.filter_items(stock, state.prep_inv_search,
                                     state.keyword_registry)
        stock = state._apply_kw_filter(stock, state.prep_kw_filter)
        hire_h = 170
        items_rect = pygame.Rect(PREP_RIGHT_RECT.x, PREP_RIGHT_RECT.y,
                                 PREP_RIGHT_RECT.w, PREP_RIGHT_RECT.h - hire_h)
        kills = state.get_total_monsters_defeated()
        res = widgets.draw_item_list_panel(
            screen, fonts, state, items_rect,
            items=stock,
            scroll=state.shop_scroll,
            search_text=state.prep_inv_search,
            search_active=state.prep_inv_search_active,
            header_text=f"Shop — click to buy  |  Slain: {kills}",
            is_fallen_func=lambda it: it in state.dead_adv_loot,
            buy_price_func=lambda it: state.get_item_price(it),
            paper_doll_module=paper_doll,
            hover_pos=state.hover_pos,
            toggle_labels=("Inventory", "Shop"),
            toggle_active=1,
            filter_selected=state.prep_kw_filter,
            filter_open=state.prep_filter_open,
        )
        pool = list(state.shop_items) + list(state.dead_adv_loot)
        _draw_hire_strip(screen, fonts, state, ui, pygame.Rect(
            PREP_RIGHT_RECT.x, PREP_RIGHT_RECT.bottom - hire_h + 6,
            PREP_RIGHT_RECT.w, hire_h - 6))

    ui['toggle_rects'] = res['toggle_rects']
    ui['filter_btn'] = res['filter_btn_rect']
    ui['search_rect'] = res['search_rect']
    ui['item_rows'] = res['visible']

    # Keyword-filter dropdown drawn last so it overlays the list.
    if state.prep_filter_open:
        dd = widgets.draw_kw_filter_dropdown(
            screen, fonts, state, res['search_rect'], pool,
            state.prep_kw_filter)
        ui['filter_chips'] = dd['chips']
        ui['filter_clear'] = dd['clear_rect']
        ui['filter_panel'] = dd['panel_rect']


def _draw_hire_strip(screen, fonts, state, ui, rect):
    """Adventurers for hire — pinned under the shop stock list."""
    _pixel_box(screen, rect, border=COLORS['gold'])
    title = fonts['small'].render("Adventurers for Hire (click to buy):", True,
                                  COLORS['gold'])
    screen.blit(title, (rect.x + 10, rect.y + 8))
    if not state.shop_adventurers:
        screen.blit(fonts['small'].render(
            "No one for hire — defeat monsters to refresh", True,
            COLORS['text_dim']), (rect.x + 10, rect.y + 40))
        return

    y = rect.y + 34
    row_h = 42
    for i, adv in enumerate(state.shop_adventurers):
        if y + row_h > rect.bottom - 6:
            break
        r = pygame.Rect(rect.x + 8, y, rect.w - 16, row_h - 4)
        price = state.get_adventurer_price(adv)
        can = state.coins >= price
        pygame.draw.rect(screen, COLORS['panel_dark'], r, border_radius=3)
        pygame.draw.rect(screen, COLORS['success'] if can else COLORS['border'],
                         r, 1, border_radius=3)
        paper_doll.draw_adventurer_thumbnail(screen, adv, r.x + 4, r.y + 3, 32)
        nc = COLORS['text'] if can else COLORS['text_dim']
        screen.blit(fonts['small'].render(adv.name, True, nc), (r.x + 44, r.y + 2))
        ab = adv.ability_name or f"[{adv.slots} slots]"
        if len(ab) > 34:
            ab = ab[:33] + ".."
        screen.blit(fonts['tiny'].render(ab, True, COLORS['text_dim']),
                    (r.x + 44, r.y + 22))
        ps = fonts['small'].render(f"{price}¢", True,
                                   COLORS['gold'] if can else COLORS['text_dim'])
        screen.blit(ps, (r.right - ps.get_width() - 10, r.y + 8))
        ui['hire_rows'].append((i, r))
        y += row_h
