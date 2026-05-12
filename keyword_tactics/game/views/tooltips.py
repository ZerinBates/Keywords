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
    tooltip_surf.fill((20, 20, 35, 230))
    pygame.draw.rect(tooltip_surf, (100, 200, 255, 200),
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
                        lines.append((f"  {chunk}", (120, 220, 140)))

                exploit_display = info['exploits'][:10]
                if exploit_display:
                    lines.append(("Exploits (hurts adventurers with):", COLORS['danger']))
                    for j in range(0, len(exploit_display), 4):
                        chunk = ", ".join(exploit_display[j:j + 4])
                        lines.append((f"  {chunk}", (255, 140, 140)))

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
                        lines.append((f"  {chunk}", (255, 140, 140)))

                strong_display = info['strong_vs'][:10]
                if strong_display:
                    lines.append(("Strong vs (enemy keywords you exploit):", COLORS['success']))
                    for j in range(0, len(strong_display), 4):
                        chunk = ", ".join(strong_display[j:j + 4])
                        lines.append((f"  {chunk}", (120, 220, 140)))

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
                        lines.append((f"  {chunk}", (255, 140, 140)))
                strong_display = info['strong_vs'][:8]
                if strong_display:
                    lines.append(("Strong vs:", COLORS['success']))
                    for j in range(0, len(strong_display), 4):
                        chunk = ", ".join(strong_display[j:j + 4])
                        lines.append((f"  {chunk}", (120, 220, 140)))
                est_h = len(lines) * 18 + 16
                draw_tooltip_panel(screen, font_tiny, lines, ex, py - est_h - 5)
                return
            ex += 220

    # --- Boss square in BOSS_CHOICE ---
    if state.phase == GamePhase.BOSS_CHOICE and state.boss_square:
        boss_rect = pygame.Rect(SCREEN_WIDTH // 2 - 200, 80, 400, 250)
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
                    lines.append((f"  {chunk}", (120, 220, 140)))
            exploit_display = info['exploits'][:10]
            if exploit_display:
                lines.append(("Exploits:", COLORS['danger']))
                for j in range(0, len(exploit_display), 4):
                    chunk = ", ".join(exploit_display[j:j + 4])
                    lines.append((f"  {chunk}", (255, 140, 140)))
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
