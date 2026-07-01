"""Hover tooltips that show weakness/strength info during combat phases."""

from typing import List, Tuple

import pygame

from ..config import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT
from ..models import Adventurer, GamePhase, Monster


# ---------------------------------------------------------------------------
# Information gathering (pure analysis, no rendering)
# ---------------------------------------------------------------------------

def get_weakness_info_for_adventurer(state, adv: Adventurer) -> dict:
    """Build a weakness/strength summary for an adventurer vs the current front row."""
    kr = state.keyword_registry
    adv_kws = adv.get_all_keywords()

    # What the adventurer is weak to (enemy keywords that hurt them)
    weak_to = set()
    for kw_id in adv_kws:
        kw = kr.get(kw_id)
        if kw:
            for w in kw.weak_against:
                weak_to.add(w)

    # Immunities
    immune = adv.ability_effect.get('immune_weakness', [])
    if isinstance(immune, str):
        immune = [immune]
    immune_set = set(immune)

    # What the adventurer is strong against
    strong_vs = set()
    for other_id in kr.all_ids():
        other_kw = kr.get(other_id)
        if other_kw:
            for adv_kw_id in adv_kws:
                if adv_kw_id in other_kw.weak_against:
                    strong_vs.add(other_id)
                    break

    # Per-monster matchups
    matchups = []
    for sq in state.front_row:
        monster = sq['monster']
        adv_weakness = 0
        for ak in adv_kws:
            kw_obj = kr.get(ak)
            if kw_obj:
                for mk in monster.keywords:
                    if mk not in immune_set and kw_obj.is_weak_against(mk):
                        adv_weakness += 1
        mon_weakness = 0
        for mk in monster.keywords:
            kw_obj = kr.get(mk)
            if kw_obj:
                for ak in adv_kws:
                    if kw_obj.is_weak_against(ak):
                        mon_weakness += 1
        matchups.append({
            'monster_name': monster.name,
            'adv_weakness': adv_weakness,
            'mon_weakness': mon_weakness,
        })

    return {
        'weak_to': sorted(weak_to),
        'strong_vs': sorted(strong_vs),
        'immune_to': sorted(immune_set),
        'matchups': matchups,
    }


def get_weakness_info_for_monster(state, monster: Monster) -> dict:
    """Build weakness/strength summary for a monster vs the current party."""
    kr = state.keyword_registry
    mon_kws = monster.keywords

    # What this monster is weak to
    weak_to = set()
    for kw_id in mon_kws:
        kw = kr.get(kw_id)
        if kw:
            for w in kw.weak_against:
                weak_to.add(w)

    # What this monster exploits
    exploits = set()
    for other_id in kr.all_ids():
        other_kw = kr.get(other_id)
        if other_kw:
            for mk in mon_kws:
                if mk in other_kw.weak_against:
                    exploits.add(other_id)
                    break

    matchups = []
    for adv in state.party:
        if adv.is_dead:
            matchups.append({
                'adv_name': adv.name,
                'adv_weakness': 0,
                'mon_weakness': 0,
                'dead': True,
            })
            continue

        adv_kws = adv.get_all_keywords()
        immune = adv.ability_effect.get('immune_weakness', [])
        if isinstance(immune, str):
            immune = [immune]
        immune_set = set(immune)

        adv_weakness = 0
        for ak in adv_kws:
            kw_obj = kr.get(ak)
            if kw_obj:
                for mk in mon_kws:
                    if mk not in immune_set and kw_obj.is_weak_against(mk):
                        adv_weakness += 1
        mon_weakness = 0
        for mk in mon_kws:
            kw_obj = kr.get(mk)
            if kw_obj:
                for ak in adv_kws:
                    if kw_obj.is_weak_against(ak):
                        mon_weakness += 1
        matchups.append({
            'adv_name': adv.name,
            'adv_weakness': adv_weakness,
            'mon_weakness': mon_weakness,
            'dead': False,
        })

    return {
        'weak_to': sorted(weak_to),
        'exploits': sorted(exploits),
        'matchups': matchups,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def draw_tooltip_panel(screen, font_tiny, lines: List[Tuple[str, tuple]],
                       anchor_x: int, anchor_y: int):
    """Draw a floating tooltip panel with colored text lines.

    `lines` is a list of (text, color) tuples.
    Anchor will be clamped to screen bounds.
    """
    if not lines:
        return

    pad = 8
    line_h = 18

    # Measure required width
    max_w = 0
    for text, _ in lines:
        w = font_tiny.render(text, True, (255, 255, 255)).get_width()
        if w > max_w:
            max_w = w

    panel_w = max_w + pad * 2
    panel_h = len(lines) * line_h + pad * 2

    # Clamp to screen bounds
    tx, ty = anchor_x, anchor_y
    if tx + panel_w > SCREEN_WIDTH - 5:
        tx = SCREEN_WIDTH - panel_w - 5
    if ty + panel_h > SCREEN_HEIGHT - 5:
        ty = SCREEN_HEIGHT - panel_h - 5
    tx = max(5, tx)
    ty = max(5, ty)

    # Background
    tooltip_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    tooltip_surf.fill((*COLORS['bg'], 235))
    pygame.draw.rect(tooltip_surf, (*COLORS['accent'], 220),
                     (0, 0, panel_w, panel_h), 2, border_radius=6)
    screen.blit(tooltip_surf, (tx, ty))

    # Text
    for i, (text, color) in enumerate(lines):
        surf = font_tiny.render(text, True, color)
        screen.blit(surf, (tx + pad, ty + pad + i * line_h))


def draw_combat_tooltip(screen, fonts, state, hover_pos: Tuple[int, int]):
    """Draw hover tooltip during combat phases (DELVE_SETUP / RESULTS / BOSS_CHOICE)."""
    mx, my = hover_pos
    CXS = [20, 330, 640, 950]
    CW = 300
    font_tiny = fonts['tiny']

    # --- Front row monster cards ---
    if state.phase in (GamePhase.DELVE_SETUP, GamePhase.DELVE_RESULTS):
        front_y = 128 if state.phase == GamePhase.DELVE_SETUP else 90
        front_h = 200

        for i, sq in enumerate(state.front_row):
            rect = pygame.Rect(CXS[i], front_y, CW, front_h)
            if rect.collidepoint(mx, my):
                monster = sq['monster']
                info = get_weakness_info_for_monster(state, monster)

                lines = [
                    (f"--- {monster.name} ---", COLORS['warning']),
                    (f"Keywords: {', '.join(monster.keywords[:6])}", COLORS['text_dim']),
                ]

                weak_display = info['weak_to'][:10]
                if weak_display:
                    lines.append(("Weak to:", COLORS['success']))
                    for j in range(0, len(weak_display), 4):
                        chunk = ", ".join(weak_display[j:j + 4])
                        lines.append((f"  {chunk}", COLORS['success']))

                exploit_display = info['exploits'][:10]
                if exploit_display:
                    lines.append(("Exploits (hurts adventurers with):", COLORS['danger']))
                    for j in range(0, len(exploit_display), 4):
                        chunk = ", ".join(exploit_display[j:j + 4])
                        lines.append((f"  {chunk}", COLORS['danger']))

                # Matchups vs party
                lines.append(("", COLORS['text']))
                lines.append(("--- Party Matchups ---", COLORS['accent']))
                for m in info['matchups']:
                    if m['dead']:
                        lines.append((f"  {m['adv_name']}: DEAD", COLORS['text_dim']))
                    else:
                        adv_w, mon_w = m['adv_weakness'], m['mon_weakness']
                        if mon_w > adv_w:
                            mc, verdict = COLORS['success'], "GOOD"
                        elif adv_w > mon_w:
                            mc, verdict = COLORS['danger'], "BAD"
                        else:
                            mc, verdict = COLORS['warning'], "EVEN"
                        lines.append((
                            f"  {m['adv_name']}: adv takes -{adv_w}  mon takes -{mon_w}  [{verdict}]",
                            mc,
                        ))

                # Position right of card, fall back to left
                tip_x = CXS[i] + CW + 8
                if tip_x + 320 > SCREEN_WIDTH:
                    tip_x = CXS[i] - 320
                draw_tooltip_panel(screen, font_tiny, lines, tip_x, front_y)
                return

    # --- Party adventurer cards (DELVE_SETUP) ---
    if state.phase == GamePhase.DELVE_SETUP:
        party_y = 345
        party_h = 160

        for i, adv in enumerate(state.party):
            cx = CXS[i] if i < 4 else 20
            rect = pygame.Rect(cx, party_y, CW, party_h)
            if rect.collidepoint(mx, my):
                if adv.is_dead:
                    lines = [
                        (f"--- {adv.name} ---", COLORS['danger']),
                        ("DEAD", COLORS['danger']),
                    ]
                    draw_tooltip_panel(screen, font_tiny, lines, cx, party_y - 200)
                    return

                info = get_weakness_info_for_adventurer(state, adv)
                lines = [(f"--- {adv.name} ---", COLORS['accent'])]
                if adv.ability_name:
                    lines.append((f"{adv.ability_name}: {adv.ability_desc}", COLORS['text_dim']))

                kws = adv.get_all_keywords()[:8]
                lines.append((f"Keywords: {', '.join(kws)}", COLORS['text_dim']))

                if info['immune_to']:
                    lines.append((
                        f"Immune to: {', '.join(info['immune_to'][:6])}",
                        (180, 140, 255),
                    ))

                weak_display = info['weak_to'][:10]
                if weak_display:
                    lines.append(("Weak to (enemy keywords that hurt you):", COLORS['danger']))
                    for j in range(0, len(weak_display), 4):
                        chunk = ", ".join(weak_display[j:j + 4])
                        lines.append((f"  {chunk}", COLORS['danger']))

                strong_display = info['strong_vs'][:10]
                if strong_display:
                    lines.append(("Strong vs (enemy keywords you exploit):", COLORS['success']))
                    for j in range(0, len(strong_display), 4):
                        chunk = ", ".join(strong_display[j:j + 4])
                        lines.append((f"  {chunk}", COLORS['success']))

                # Per-monster matchups
                if state.front_row:
                    lines.append(("", COLORS['text']))
                    lines.append(("--- Monster Matchups ---", COLORS['warning']))
                    for m in info['matchups']:
                        adv_w, mon_w = m['adv_weakness'], m['mon_weakness']
                        if mon_w > adv_w:
                            mc, verdict = COLORS['success'], "GOOD"
                        elif adv_w > mon_w:
                            mc, verdict = COLORS['danger'], "BAD"
                        else:
                            mc, verdict = COLORS['warning'], "EVEN"
                        lines.append((
                            f"  {m['monster_name']}: you take -{adv_w}  it takes -{mon_w}  [{verdict}]",
                            mc,
                        ))

                # Position above the party card
                est_h = len(lines) * 18 + 16
                tip_y = max(5, party_y - est_h - 5)
                draw_tooltip_panel(screen, font_tiny, lines, cx, tip_y)
                return

    # --- Party area in DELVE_RESULTS ---
    if state.phase == GamePhase.DELVE_RESULTS:
        py = 570
        alive = [a for a in state.party if not a.is_dead]
        ex = 20
        for adv in alive:
            adv_rect = pygame.Rect(ex, py + 25, 210, 25)
            if adv_rect.collidepoint(mx, my):
                info = get_weakness_info_for_adventurer(state, adv)
                lines = [(f"--- {adv.name} ---", COLORS['accent'])]
                if adv.ability_name:
                    ability_text = f"{adv.ability_name}: {adv.ability_desc}"
                    if len(ability_text) > 60:
                        ability_text = ability_text[:59] + "..."
                    lines.append((ability_text, COLORS['text_dim']))
                kws = adv.get_all_keywords()[:8]
                lines.append((f"Keywords: {', '.join(kws)}", COLORS['text_dim']))
                if info['immune_to']:
                    lines.append((
                        f"Immune to: {', '.join(info['immune_to'][:6])}",
                        (180, 140, 255),
                    ))
                weak_display = info['weak_to'][:8]
                if weak_display:
                    lines.append(("Weak to:", COLORS['danger']))
                    for j in range(0, len(weak_display), 4):
                        chunk = ", ".join(weak_display[j:j + 4])
                        lines.append((f"  {chunk}", COLORS['danger']))
                strong_display = info['strong_vs'][:8]
                if strong_display:
                    lines.append(("Strong vs:", COLORS['success']))
                    for j in range(0, len(strong_display), 4):
                        chunk = ", ".join(strong_display[j:j + 4])
                        lines.append((f"  {chunk}", COLORS['success']))
                est_h = len(lines) * 18 + 16
                draw_tooltip_panel(screen, font_tiny, lines, ex, py - est_h - 5)
                return
            ex += 220

    # --- Boss square in BOSS_CHOICE ---
    if state.phase == GamePhase.BOSS_CHOICE and state.boss_square:
        boss_rect = pygame.Rect(SCREEN_WIDTH // 2 - 220, 80, 440, 280)
        if boss_rect.collidepoint(mx, my):
            monster = state.boss_square['monster']
            info = get_weakness_info_for_monster(state, monster)
            lines = [
                (f"--- BOSS: {monster.name} ---", COLORS['danger']),
                (f"Keywords: {', '.join(monster.keywords[:6])}", COLORS['text_dim']),
            ]
            weak_display = info['weak_to'][:10]
            if weak_display:
                lines.append(("Weak to:", COLORS['success']))
                for j in range(0, len(weak_display), 4):
                    chunk = ", ".join(weak_display[j:j + 4])
                    lines.append((f"  {chunk}", COLORS['success']))
            exploit_display = info['exploits'][:10]
            if exploit_display:
                lines.append(("Exploits:", COLORS['danger']))
                for j in range(0, len(exploit_display), 4):
                    chunk = ", ".join(exploit_display[j:j + 4])
                    lines.append((f"  {chunk}", COLORS['danger']))
            lines.append(("", COLORS['text']))
            lines.append(("--- Party Matchups ---", COLORS['accent']))
            for m in info['matchups']:
                if m['dead']:
                    lines.append((f"  {m['adv_name']}: DEAD", COLORS['text_dim']))
                else:
                    adv_w, mon_w = m['adv_weakness'], m['mon_weakness']
                    if mon_w > adv_w:
                        mc, verdict = COLORS['success'], "GOOD"
                    elif adv_w > mon_w:
                        mc, verdict = COLORS['danger'], "BAD"
                    else:
                        mc, verdict = COLORS['warning'], "EVEN"
                    lines.append((
                        f"  {m['adv_name']}: adv -{adv_w}  boss -{mon_w}  [{verdict}]",
                        mc,
                    ))
            draw_tooltip_panel(screen, font_tiny, lines, SCREEN_WIDTH // 2 + 210, 80)
            return



# ---------------------------------------------------------------------------
# Item hover tooltips (used by preparation + delve inventory panel)
# ---------------------------------------------------------------------------

def build_item_tooltip_lines(state, item) -> List[Tuple[str, tuple]]:
    """Lines for an Item tooltip — name, rarity, points, keywords, sell price."""
    rarity_color = {
        'scrap':    (130, 110, 100),
        'common':   COLORS['text_dim'],
        'uncommon': COLORS['success'],
        'rare':     COLORS['accent'],
    }.get(item.rarity, COLORS['text'])

    lines: List[Tuple[str, tuple]] = []
    lines.append((f"--- {item.name} ---", COLORS['accent']))
    lines.append((f"Rarity: {item.rarity}", rarity_color))
    lines.append((f"Points: +{item.points}", COLORS['gold']))

    if item.keywords:
        kw_names = []
        kr = state.keyword_registry
        for kw_id in item.keywords:
            kw = kr.get(kw_id)
            kw_names.append(kw.name if kw else kw_id)
        # Chunk into lines of up to 4 keywords
        lines.append(("Keywords:", COLORS['warning']))
        for j in range(0, len(kw_names), 4):
            chunk = ", ".join(kw_names[j:j + 4])
            lines.append((f"  {chunk}", COLORS['text']))

        # What this item is weak to / strong against
        kr = state.keyword_registry
        weak_to = set()
        strong_vs = set()
        for kw_id in item.keywords:
            kw = kr.get(kw_id)
            if kw:
                for wk in kw.weak_against:
                    weak_to.add(wk)
        for other_id in kr.all_ids():
            other = kr.get(other_id)
            if other:
                for kw_id in item.keywords:
                    if kw_id in other.weak_against:
                        strong_vs.add(other_id)
                        break
        if weak_to:
            wt_names = [kr.get(w).name if kr.get(w) else w for w in sorted(weak_to)]
            lines.append((f"Weak to: {', '.join(wt_names[:6])}", COLORS['danger']))
        if strong_vs:
            sv_names = [kr.get(s).name if kr.get(s) else s for s in sorted(strong_vs)]
            lines.append((f"Strong vs: {', '.join(sv_names[:6])}", COLORS['success']))

    # Sell price hint
    try:
        sp = state.get_item_sell_price(item)
        lines.append((f"Sell price: {sp} coin(s)", COLORS['text_dim']))
    except AttributeError:
        pass
    return lines


def build_adventurer_tooltip_lines(state, adv) -> List[Tuple[str, tuple]]:
    """Lines for a class/ability tooltip — name, ability, slots, role, keywords."""
    lines: List[Tuple[str, tuple]] = []
    lines.append((f"--- {adv.name} ---", COLORS['accent']))

    # Role badge in the tooltip too
    if hasattr(state, 'hero_king') and adv is state.hero_king:
        lines.append(("HERO KING — +2x power, ignores biggest weakness",
                      COLORS['gold']))
    elif hasattr(state, 'hero_dunce') and adv is state.hero_dunce:
        lines.append(("HERO DUNCE — final power /2",
                      COLORS['text_dim']))

    if adv.ability_name:
        lines.append((f"{adv.ability_name}", COLORS['warning']))
        # Wrap ability description into ~60-char lines
        desc = adv.ability_desc or ""
        words = desc.split()
        cur = ""
        for w in words:
            if len(cur) + len(w) + 1 > 60:
                lines.append((f"  {cur}", COLORS['text']))
                cur = w
            else:
                cur = (cur + " " + w) if cur else w
        if cur:
            lines.append((f"  {cur}", COLORS['text']))

    lines.append((f"Slots: {len(adv.equipped_items)}/{adv.slots}", COLORS['text_dim']))

    if adv.is_dead:
        lines.append(("DEAD", COLORS['danger']))
        return lines

    kws = adv.get_all_keywords()
    if kws:
        # Count keyword occurrences for the player
        counts = {}
        for k in kws:
            counts[k] = counts.get(k, 0) + 1
        parts = []
        for k, c in sorted(counts.items()):
            kw = state.keyword_registry.get(k)
            name = kw.name if kw else k
            parts.append(f"{name} x{c}" if c > 1 else name)
        # Chunk
        lines.append(("Keywords (from items):", COLORS['warning']))
        for j in range(0, len(parts), 3):
            chunk = ", ".join(parts[j:j + 3])
            lines.append((f"  {chunk}", COLORS['text']))
    else:
        lines.append(("No items equipped", COLORS['text_dim']))

    try:
        base = adv.get_base_points()
        mult = adv.get_multiplier()
        lines.append((f"Power: {base} x {mult} = {base * mult}", COLORS['success']))
    except Exception:
        pass

    return lines


def draw_item_tooltip(screen, fonts, state, item, hover_pos: Tuple[int, int]):
    """Draw a tooltip for an item at the cursor position."""
    lines = build_item_tooltip_lines(state, item)
    mx, my = hover_pos
    draw_tooltip_panel(screen, fonts['tiny'], lines, mx + 16, my + 8)


def draw_adventurer_tooltip(screen, fonts, state, adv, hover_pos: Tuple[int, int]):
    """Draw a tooltip for an adventurer/class at the cursor position."""
    lines = build_adventurer_tooltip_lines(state, adv)
    mx, my = hover_pos
    draw_tooltip_panel(screen, fonts['tiny'], lines, mx + 16, my + 8)


# ---------------------------------------------------------------------------
# Preparation-phase hover tooltips
# ---------------------------------------------------------------------------

def draw_preparation_tooltip(screen, fonts, state, hover_pos: Tuple[int, int]):
    """Hover tooltips during the PREPARATION phase.

    Covers: roster rows, party rows, inventory rows, shop items, shop adventurers,
    and the paper-doll card's item chips.
    """
    from .screens.preparation import (
        ROSTER_RECT, INV_PANEL_RECT, SHOP_RECT, CARD_RECT,
        SHOP_ITEM_ROW_H,
    )
    from . import paper_doll

    mx, my = hover_pos

    # --- Roster rows ---
    if ROSTER_RECT.collidepoint(hover_pos):
        y_off = my - (ROSTER_RECT.y + 30)
        if y_off >= 0:
            idx = (y_off // 52) + state.roster_scroll
            if 0 <= idx < len(state.roster):
                draw_adventurer_tooltip(screen, fonts, state, state.roster[idx], hover_pos)
                return

    # --- Paper-doll item chips (selected roster member) ---
    if (CARD_RECT.collidepoint(hover_pos)
            and 0 <= state.selected_party_index < len(state.roster)):
        adv = state.roster[state.selected_party_index]
        chip_idx = paper_doll.hit_test_chip(CARD_RECT.x, CARD_RECT.y, hover_pos, adv)
        if chip_idx is not None and 0 <= chip_idx < len(adv.equipped_items):
            draw_item_tooltip(screen, fonts, state, adv.equipped_items[chip_idx], hover_pos)
            return

    # --- Equipped items side panel (shared widget) ---
    from .screens.preparation import STATS_RECT as _STATS_RECT
    if (_STATS_RECT.collidepoint(hover_pos)
            and 0 <= state.selected_party_index < len(state.roster)):
        adv = state.roster[state.selected_party_index]
        row_rects = getattr(state, '_prep_equipped_rows', []) or []
        for item, rr in row_rects:
            if rr.collidepoint(hover_pos):
                draw_item_tooltip(screen, fonts, state, item, hover_pos)
                return

    # --- Inventory rows (shared widget layout) ---
    if INV_PANEL_RECT.collidepoint(hover_pos):
        from .widgets import hit_test_item_list
        filtered = state.get_filtered_inventory()
        idx, item = hit_test_item_list(
            INV_PANEL_RECT, filtered, state.inventory_scroll, hover_pos)
        if item is not None:
            draw_item_tooltip(screen, fonts, state, item, hover_pos)
            return

    # --- Shop items (merged with dead_adv_loot) ---
    if SHOP_RECT.collidepoint(hover_pos):
        merged = list(state.shop_items) + list(state.dead_adv_loot)
        items_y_start = SHOP_RECT.y + 34 + 20
        for i, item in enumerate(merged):
            iy = items_y_start + i * SHOP_ITEM_ROW_H
            if iy + SHOP_ITEM_ROW_H > SHOP_RECT.bottom - 6:
                break
            row_rect = pygame.Rect(SHOP_RECT.x + 4, iy,
                                   SHOP_RECT.w - 8, SHOP_ITEM_ROW_H - 4)
            if row_rect.collidepoint(hover_pos):
                draw_item_tooltip(screen, fonts, state, item, hover_pos)
                return

        adv_y_start = items_y_start + len(merged) * SHOP_ITEM_ROW_H + 20 \
            if merged else SHOP_RECT.y + 34 + 20
        for i, adv in enumerate(state.shop_adventurers):
            iy = adv_y_start + i * SHOP_ITEM_ROW_H
            if iy + SHOP_ITEM_ROW_H > SHOP_RECT.bottom - 6:
                break
            row_rect = pygame.Rect(SHOP_RECT.x + 4, iy,
                                   SHOP_RECT.w - 8, SHOP_ITEM_ROW_H - 4)
            if row_rect.collidepoint(hover_pos):
                draw_adventurer_tooltip(screen, fonts, state, adv, hover_pos)
                return


# ---------------------------------------------------------------------------
# Delve-phase hover tooltips for the in-fight inventory overlay
# ---------------------------------------------------------------------------

def draw_delve_inv_tooltip(screen, fonts, state, hover_pos: Tuple[int, int]):
    """Hover tooltips when state.delve_inv_open is True.

    Covers: adventurer rows in the left column, items in the equipped side
    panel, item chips on the centre paper-doll card, and rows in the
    right-column merged list.
    """
    from . import paper_doll

    PX, PY, PW, PH = 60, 40, 1160, 710
    col_top = PY + 55
    left_x = PX + 10
    left_w = 220
    equip_x = left_x + left_w + 15
    equip_w = 220
    center_x = equip_x + equip_w + 10
    center_w = 290
    right_x = center_x + center_w + 15
    right_w = PX + PW - right_x - 10

    # --- Equipped items side panel: hover over a row → tooltip ---
    if 0 <= state.delve_selected_adv_idx < len(state.party):
        adv = state.party[state.delve_selected_adv_idx]
        row_rects = getattr(state, '_delve_equipped_rows', []) or []
        for item, rr in row_rects:
            if rr.collidepoint(hover_pos):
                draw_item_tooltip(screen, fonts, state, item, hover_pos)
                return

    # --- Left column: party member rows ---
    party_row_h = 70
    for i, adv in enumerate(state.party):
        ay = col_top + 30 + i * party_row_h
        if ay + party_row_h > PY + PH - 8:
            break
        adv_rect = pygame.Rect(left_x, ay, left_w, party_row_h)
        if adv_rect.collidepoint(hover_pos):
            draw_adventurer_tooltip(screen, fonts, state, adv, hover_pos)
            return

    # --- Centre column: paper-doll card chips ---
    if 0 <= state.delve_selected_adv_idx < len(state.party):
        adv = state.party[state.delve_selected_adv_idx]
        card_x = center_x + (center_w - paper_doll.CARD_W) // 2
        card_y = col_top + 30
        card_rect = pygame.Rect(card_x, card_y,
                                paper_doll.CARD_W, paper_doll.CARD_H)
        if card_rect.collidepoint(hover_pos):
            chip_idx = paper_doll.hit_test_chip(card_x, card_y, hover_pos, adv)
            if chip_idx is not None and 0 <= chip_idx < len(adv.equipped_items):
                draw_item_tooltip(screen, fonts, state,
                                  adv.equipped_items[chip_idx], hover_pos)
                return

    # --- Right column: merged item rows ---
    from .widgets import (
        ITEM_LIST_HEADER_H, ITEM_LIST_SEARCH_H, ITEM_LIST_ROW_H,
    )
    list_top = col_top + ITEM_LIST_HEADER_H + 4 + ITEM_LIST_SEARCH_H + 6
    list_h   = PY + PH - list_top - 50
    list_rect = pygame.Rect(right_x, list_top, right_w, list_h)
    if list_rect.collidepoint(hover_pos):
        filtered = state.get_filtered_delve_items()
        scroll = state.delve_inv_scroll
        visible_count = list_h // ITEM_LIST_ROW_H
        for k in range(visible_count):
            idx = scroll + k
            if idx >= len(filtered):
                break
            iy = list_top + 4 + k * ITEM_LIST_ROW_H
            row_rect = pygame.Rect(right_x + 4, iy,
                                   right_w - 8, ITEM_LIST_ROW_H - 4)
            if row_rect.collidepoint(hover_pos):
                draw_item_tooltip(screen, fonts, state, filtered[idx], hover_pos)
                return