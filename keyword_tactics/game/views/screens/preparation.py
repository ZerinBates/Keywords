"""Preparation phase: build your party, equip items, buy/sell in the shop."""

import pygame

from ..widgets import Panel
from .. import widgets
from ...config import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT
from .. import paper_doll

# ---------------------------------------------------------------------------
# Layout constants (kept in one place so renderer + input_handler agree)
# ---------------------------------------------------------------------------
ROSTER_RECT  = pygame.Rect(20,  100, 380, 340)
PARTY_RECT   = pygame.Rect(420, 100, 380, 340)

# Inventory: one unified rect — widgets.draw_item_list_panel subdivides it
# into header / search / list sections internally.
INV_PANEL_RECT  = pygame.Rect(820, 100, 440, 340)

# Stats / paper-doll (lower area)
STATS_RECT   = pygame.Rect(420, 460, 230, 320)
CARD_RECT    = pygame.Rect(660, 460, paper_doll.CARD_W, paper_doll.CARD_H)

# Shop panel (lower-right, to the right of the paper-doll card)
SHOP_X       = 660 + paper_doll.CARD_W + 14
SHOP_Y       = 460
SHOP_W       = SCREEN_WIDTH - SHOP_X - 10
SHOP_H       = 320
SHOP_RECT    = pygame.Rect(SHOP_X, SHOP_Y, SHOP_W, SHOP_H)
SHOP_ITEM_ROW_H = 36    # px per item row inside the shop panel


def draw(screen, fonts, state):
    """Render the preparation screen."""
    # Tag adventurers with their roles so paper_doll thumbnails render the
    # KING/DUNCE crown.  Roles only meaningful inside a delve, but tagging
    # in prep lets the player see who'd be king if last_king_slayer is set.
    for adv in state.roster:
        if adv is state.hero_king:
            setattr(adv, '_role_badge', 'king')
        elif adv is state.hero_dunce:
            setattr(adv, '_role_badge', 'dunce')
        elif adv is state.last_king_slayer:
            # Show pre-emptive king status while in prep
            setattr(adv, '_role_badge', 'king')
        else:
            setattr(adv, '_role_badge', None)

    # Header
    header = fonts['large'].render("PREPARE YOUR PARTY", True, COLORS['accent'])
    screen.blit(header, (20, 20))

    # Coins
    coins_text = fonts['medium'].render(f"Coins: {state.coins}", True, COLORS['gold'])
    screen.blit(coins_text, (20, 60))

    # Decks cleared status
    cleared = len(state.completed_decks)
    total = len(state.active_decks)
    cleared_text = fonts['medium'].render(
        f"Dungeons Cleared: {cleared}/{total}", True, COLORS['success'],
    )
    screen.blit(cleared_text, (200, 60))

    # ---- Roster panel ----
    panel = Panel(ROSTER_RECT.x, ROSTER_RECT.y, ROSTER_RECT.w, ROSTER_RECT.h,
                  "Roster (click to add to party)")
    panel.draw(screen, fonts['small'], fonts['medium'])

    if state.roster_scroll > 0:
        screen.blit(fonts['small'].render("^ scroll up", True, COLORS['text_dim']),
                    (300, ROSTER_RECT.y + 5))

    y = ROSTER_RECT.y + 30
    visible_roster = state.roster[state.roster_scroll:state.roster_scroll + 6]
    for adv in visible_roster:
        color = COLORS['text_dim'] if adv.is_dead else COLORS['text']
        if adv in state.party:
            color = COLORS['success']

        adv_id = getattr(adv, 'id', adv.name)
        # Portrait + item chips thumbnail (#1)
        paper_doll.draw_adventurer_thumbnail(screen, adv, ROSTER_RECT.x + 10, y + 2, 36)

        text = f"{adv.name} [{adv.slots} slots] - {adv.ability_name}"
        screen.blit(fonts['small'].render(text, True, color), (ROSTER_RECT.x + 52, y + 5))

        if adv.is_dead:
            screen.blit(fonts['small'].render("DEAD", True, COLORS['danger']),
                        (ROSTER_RECT.x + ROSTER_RECT.w - 60, y + 5))
        y += 52

    if state.roster_scroll + 6 < len(state.roster):
        screen.blit(
            fonts['small'].render("v scroll down", True, COLORS['text_dim']),
            (ROSTER_RECT.x + 10, ROSTER_RECT.bottom - 20),
        )

    # ---- Party panel ----
    panel2 = Panel(PARTY_RECT.x, PARTY_RECT.y, PARTY_RECT.w, PARTY_RECT.h,
                   f"Party ({len(state.party)}/4) - Shift+click to remove")
    panel2.draw(screen, fonts['small'], fonts['medium'])

    y = PARTY_RECT.y + 30
    for i, adv in enumerate(state.party):
        color = COLORS['accent'] if i == state.selected_party_index else COLORS['text']
        # Portrait + item chips thumbnail (#1)
        paper_doll.draw_adventurer_thumbnail(screen, adv, PARTY_RECT.x + 10, y + 2, 36)
        text = f"{adv.name} [{len(adv.equipped_items)}/{adv.slots}]"
        screen.blit(fonts['small'].render(text, True, color), (PARTY_RECT.x + 52, y + 5))

        keywords = adv.get_all_keywords()
        if keywords:
            kw_text = ", ".join(keywords[:6])
            if len(keywords) > 6:
                kw_text += "..."
            screen.blit(fonts['small'].render(kw_text, True, COLORS['text_dim']),
                        (PARTY_RECT.x + 52, y + 24))
        y += 52

    # ---- Inventory: search + scrollable list (shared widget; #2) ----
    filtered_inv = state.get_filtered_inventory()
    widgets.draw_item_list_panel(
        screen, fonts, state, INV_PANEL_RECT,
        items=filtered_inv,
        scroll=state.inventory_scroll,
        search_text=state.prep_inv_search,
        search_active=state.prep_inv_search_active,
        header_text=f"Inventory ({len(state.inventory)}) — click: equip | Ctrl+click: sell",
        sell_price_func=lambda it: state.get_item_sell_price(it),
        paper_doll_module=paper_doll,
    )

    # ---- Left stats/items panel — shared widget (#2) ----
    state._prep_equipped_rows = []  # transient: stores [(item, rect)] for clicks
    if 0 <= state.selected_party_index < len(state.party):
        adv = state.party[state.selected_party_index]
        state._prep_equipped_rows = widgets.draw_equipped_items_panel(
            screen, fonts, state, STATS_RECT, adv,
            paper_doll_module=paper_doll,
        )

    # ---- Selected adventurer paper-doll card ----
    if 0 <= state.selected_party_index < len(state.party):
        adv = state.party[state.selected_party_index]
        paper_doll.draw_character_card(
            screen, fonts, state, CARD_RECT.x, CARD_RECT.y, adv, selected=True,
        )
        hint = fonts['small'].render(
            "Click an item chip to unequip", True, COLORS['text_dim'],
        )
        screen.blit(hint, (CARD_RECT.x, CARD_RECT.y - 20))

    # ---- Shop panel (#5) ----
    _draw_shop_panel(screen, fonts, state)

    # Instructions
    inst = fonts['small'].render(
        "Hover any card/item for details  |  Click roster → party  |  "
        "Click inventory → equip  |  Ctrl+click inventory → sell  |  "
        "Shift+click party → remove",
        True, COLORS['text_dim'],
    )
    screen.blit(inst, (20, SCREEN_HEIGHT - 28))


def _draw_shop_panel(screen, fonts, state):
    """Embedded shop panel in the preparation screen (feature #5)."""
    sx, sy, sw, sh = SHOP_RECT.x, SHOP_RECT.y, SHOP_RECT.w, SHOP_RECT.h

    # Panel background
    pygame.draw.rect(screen, (28, 30, 42), SHOP_RECT, border_radius=8)
    pygame.draw.rect(screen, COLORS['gold'], SHOP_RECT, 2, border_radius=8)

    # Title
    title_surf = fonts['medium'].render("Shop", True, COLORS['gold'])
    screen.blit(title_surf, (sx + 10, sy + 8))

    kills = state.get_total_monsters_defeated()
    kills_surf = fonts['tiny'].render(
        f"Refreshes after kills  |  Slain: {kills}", True, COLORS['text_dim'])
    screen.blit(kills_surf, (sx + sw - kills_surf.get_width() - 8, sy + 12))

    has_anything = (state.shop_items or state.shop_adventurers
                    or state.dead_adv_loot)
    if not has_anything:
        msg = fonts['small'].render("No stock — defeat monsters to refresh",
                                    True, COLORS['text_dim'])
        screen.blit(msg, (sx + sw // 2 - msg.get_width() // 2, sy + sh // 2 - 10))
        return

    y = sy + 34
    row_h = SHOP_ITEM_ROW_H

    rarity_color_map = {
        'scrap':    (120, 120, 120),
        'common':   COLORS['text_dim'],
        'uncommon': COLORS['success'],
        'rare':     COLORS['accent'],
    }
    rarity_bg = {
        'scrap':    (42, 38, 38),
        'common':   (40, 42, 50),
        'uncommon': (32, 50, 36),
        'rare':     (36, 40, 58),
    }

    # Merged item list: shop_items first, then dead_adv_loot tagged FALLEN
    all_items = [(it, False) for it in state.shop_items] + \
                [(it, True)  for it in state.dead_adv_loot]

    if all_items:
        items_hdr = fonts['small'].render(
            "Items for Sale  (click to buy):", True, COLORS['warning'])
        screen.blit(items_hdr, (sx + 8, y))
        y += 20

        for i, (item, is_fallen) in enumerate(all_items):
            if y + row_h > sy + sh - 6:
                break
            price = state.get_item_price(item)
            can_afford = state.coins >= price
            bg = rarity_bg.get(item.rarity, (40, 42, 50))
            rc = rarity_color_map.get(item.rarity, COLORS['text'])

            row_rect = pygame.Rect(sx + 4, y, sw - 8, row_h - 4)
            pygame.draw.rect(screen, bg, row_rect, border_radius=5)
            border_c = rc if can_afford else (60, 60, 70)
            pygame.draw.rect(screen, border_c, row_rect, 1, border_radius=5)

            paper_doll.draw_item_thumbnail(screen, item, sx + 8, y + 4, 26)

            iname = item.name[:20] if len(item.name) > 20 else item.name
            name_c = COLORS['text'] if can_afford else COLORS['text_dim']
            screen.blit(fonts['small'].render(iname, True, name_c), (sx + 38, y + 2))

            if is_fallen:
                fallen = fonts['tiny'].render("FALLEN", True, COLORS['danger'])
                screen.blit(fallen, (sx + 38 + fonts['small'].render(
                    iname, True, name_c).get_width() + 4, y + 4))

            price_surf = fonts['small'].render(
                f"{price}¢", True, COLORS['gold'] if can_afford else COLORS['text_dim'])
            screen.blit(price_surf, (sx + sw - price_surf.get_width() - 10, y + 2))

            pts_surf = fonts['tiny'].render(f"+{item.points}", True, COLORS['success'])
            screen.blit(pts_surf, (sx + sw - pts_surf.get_width() - 10, y + 20))

            # Keyword tags
            kw_x = sx + 38
            for kw_id in item.keywords[:3]:
                kw = state.keyword_registry.get(kw_id)
                if kw:
                    label = kw.name[:7]
                    tw = fonts['tiny'].render(label, True, COLORS['bg']).get_width() + 6
                    if kw_x + tw > sx + sw - 50:
                        break
                    pygame.draw.rect(screen, kw.color, (kw_x, y + 20, tw, 10), border_radius=2)
                    screen.blit(fonts['tiny'].render(label, True, COLORS['bg']),
                                (kw_x + 3, y + 20))
                    kw_x += tw + 3

            y += row_h

    # Adventurers for hire
    if state.shop_adventurers:
        adv_hdr = fonts['small'].render("Adventurers for Hire  (click to buy):",
                                        True, COLORS['warning'])
        if y + 20 < sy + sh - 6:
            screen.blit(adv_hdr, (sx + 8, y))
            y += 20

        for i, adv in enumerate(state.shop_adventurers):
            if y + row_h > sy + sh - 6:
                break
            price = state.get_adventurer_price(adv)
            can_afford = state.coins >= price

            row_rect = pygame.Rect(sx + 4, y, sw - 8, row_h - 4)
            bg_c = (35, 40, 55) if can_afford else (35, 35, 45)
            pygame.draw.rect(screen, bg_c, row_rect, border_radius=5)
            pygame.draw.rect(screen, COLORS['accent'] if can_afford else (55, 55, 70),
                             row_rect, 1, border_radius=5)

            paper_doll.draw_adventurer_thumbnail(screen, adv, sx + 8, y + 3, 28)

            name_c = COLORS['text'] if can_afford else COLORS['text_dim']
            screen.blit(fonts['small'].render(adv.name, True, name_c), (sx + 40, y + 2))

            ab_text = f"{adv.ability_name}" if adv.ability_name else f"[{adv.slots} slots]"
            if len(ab_text) > 28:
                ab_text = ab_text[:27] + ".."
            screen.blit(fonts['tiny'].render(ab_text, True, COLORS['text_dim']),
                        (sx + 40, y + 20))

            price_surf = fonts['small'].render(
                f"{price}¢", True, COLORS['gold'] if can_afford else COLORS['text_dim'])
            screen.blit(price_surf, (sx + sw - price_surf.get_width() - 10, y + 8))

            y += row_h