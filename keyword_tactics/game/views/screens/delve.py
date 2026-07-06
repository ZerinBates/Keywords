"""Delve phase rendering: setup, results, square cards, inventory & recruit overlays."""

import os

import pygame

from ... import theme
from ...config import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT
from ...controllers import combat
from .. import paper_doll
from .. import widgets


# ---------------------------------------------------------------------------
# Shared delve layout geometry. Drag-and-drop hit-testing in input_handler
# reads these, so the squares/party cards the player clicks line up exactly
# with what's drawn. Change spacing here and both views + input stay in sync.
# ---------------------------------------------------------------------------
DELVE_CARD_W  = 300
DELVE_CARD_XS = (20, 330, 640, 950)
FRONT_ROW_Y   = 104
FRONT_ROW_H   = 322
# The party is one continuous strip (heroes on a scenic background),
# not individual boxed cards.
PARTY_STRIP   = pygame.Rect(20, 460, 1240, 246)
PARTY_SLOT_W  = 310


def party_slot_rects(state):
    """Per-hero hit-boxes inside the party strip (drag + click info)."""
    return [
        pygame.Rect(PARTY_STRIP.x + i * PARTY_SLOT_W, PARTY_STRIP.y,
                    PARTY_SLOT_W, PARTY_STRIP.h)
        for i in range(min(len(state.party), 4))
    ]


# Shared with the Shop screen via widgets (same look everywhere).
_collapse_keywords = widgets.collapse_keywords


# Items-overlay ("HERO LOADOUT") three-column geometry — shared with
# input_handler so clicks and wheel-scroll match what's drawn.
INV_LEFT_RECT  = pygame.Rect(20, 44, 300, 660)
INV_MID_RECT   = pygame.Rect(340, 44, 420, 660)
INV_RIGHT_RECT = pygame.Rect(780, 44, 480, 660)
INV_CARD_H     = 84
INV_CARD_GAP   = 10


# ---------------------------------------------------------------------------
# Setup screen
# ---------------------------------------------------------------------------

# Chunky pixel-art panel (shared with widgets/other screens).
_pixel_box = widgets.draw_pixel_box


def _draw_header(screen, fonts, state, sprite_manager):
    """Streamlined top bar: delve name / coins / matched count / final boss."""
    deck_name = state.current_deck.name if state.current_deck else "Unknown"

    title_box = pygame.Rect(16, 8, 620, 56)
    _pixel_box(screen, title_box)
    t = fonts['large'].render(f"DELVE - {deck_name}", True, COLORS['text'])
    if t.get_width() > title_box.w - 32:
        t = fonts['medium'].render(f"DELVE - {deck_name}", True, COLORS['text'])
    screen.blit(t, t.get_rect(midleft=(title_box.x + 16, title_box.centery)))

    coins_box = pygame.Rect(648, 8, 190, 56)
    _pixel_box(screen, coins_box)
    lbl = fonts['medium'].render("Coins: ", True, COLORS['text'])
    val = fonts['medium'].render(str(state.coins), True, COLORS['gold'])
    cx0 = coins_box.centerx - (lbl.get_width() + val.get_width()) // 2
    screen.blit(lbl, lbl.get_rect(midleft=(cx0, coins_box.centery)))
    screen.blit(val, val.get_rect(midleft=(cx0 + lbl.get_width(), coins_box.centery)))

    placed = state.count_front_placed()
    need = min(state.count_alive_party(), len(state.front_row))
    match_box = pygame.Rect(850, 8, 200, 56)
    _pixel_box(screen, match_box)
    mc = COLORS['success'] if (need and placed >= need) else COLORS['text']
    m = fonts['medium'].render(f"Matched: {placed}/{need}", True, mc)
    screen.blit(m, m.get_rect(center=match_box.center))

    boss_box = pygame.Rect(1062, 8, 202, 56)
    _pixel_box(screen, boss_box)
    boss = state.boss_square
    boss_mon = (boss['monster'] if boss
                else getattr(state.current_deck, 'boss_monster', None))
    # Hover target: tooltip shows the boss's gear + rounds until the fight.
    state._boss_icon_rect = boss_box if boss_mon else None
    boss_name = boss_mon.name if boss_mon else "???"
    lb = fonts['tiny'].render("Final Boss:", True, COLORS['text_dim'])
    screen.blit(lb, (boss_box.x + 10, boss_box.y + 7))
    nm = fonts['small'].render(boss_name[:16], True, COLORS['text'])
    screen.blit(nm, (boss_box.x + 10, boss_box.y + 26))
    if boss_mon:
        spr = sprite_manager.get_monster_sprite(boss_mon.name, (44, 44))
        if spr:
            screen.blit(spr, (boss_box.right - 52, boss_box.y + 6))


def _square_totals(state, sq):
    """(monster_total, adv_total or None) — exact preview of the resolver.

    With a hero placed this runs the REAL combat calculation (duplicate-
    keyword multipliers, weakness division, king/dunce, square bonus), so
    the numbers shown before the fight match the resolved fight exactly.
    """
    adv = sq['adventurer']
    if adv:
        res = combat.calculate_square_combat(
            sq, state.keyword_registry,
            adv_is_king=(adv is state.hero_king),
            adv_is_dunce=(adv is state.hero_dunce),
        )
        return res['monster_power'], res['adv_power']

    # Empty square: no opponent, so no weakness — base x stacked-keyword
    # multiplier (e.g. construct x3), then the king/dunce modifier.
    monster = sq['monster']
    bonus = sq.get('bonus') or {}
    kws = list(monster.keywords)
    if bonus.get('type') == 'keyword_buff':
        kws.append(bonus['keyword'])
    counts = {}
    for k in kws:
        counts[k] = counts.get(k, 0) + 1
    mult = max(1, sum(c for c in counts.values() if c >= 2))
    mon_total = monster.base_points * mult
    if sq.get('is_king'):
        mon_total *= 2
    elif sq.get('is_dunce'):
        mon_total //= 2
    return mon_total, None


def _draw_monster_card(screen, fonts, state, sprite_manager, x, y, sq, index):
    """One front-row monster: huge matchup numbers, sprite, hero match slot."""
    monster = sq['monster']
    adv = sq['adventurer']
    is_king = bool(sq.get('is_king'))
    is_dunce = bool(sq.get('is_dunce'))
    rect = pygame.Rect(x, y, DELVE_CARD_W, FRONT_ROW_H)

    if adv:
        border = COLORS['success']
    elif is_king:
        border = COLORS['gold']
    elif is_dunce:
        border = COLORS['muted']
    else:
        border = COLORS['border']
    _pixel_box(screen, rect, border=border,
               fill=theme.mix(COLORS['bg'], COLORS['surface'], 0.45))

    if is_king or is_dunce:
        badge = fonts['tiny'].render("KING" if is_king else "DUNCE", True,
                                     COLORS['gold'] if is_king else COLORS['muted'])
        screen.blit(badge, (rect.right - badge.get_width() - 10, y + 8))

    # Massive matchup numbers — no DEF/POWER labels (colour carries meaning).
    # Long numbers step down a font size so they stay inside their half.
    mon_total, adv_total = _square_totals(state, sq)
    def_surf = fonts['huge'].render(str(mon_total), True, COLORS['danger'])
    if def_surf.get_width() > 130:
        def_surf = fonts['title'].render(str(mon_total), True, COLORS['danger'])
    screen.blit(def_surf, def_surf.get_rect(centerx=x + 82, top=y + 2))
    if adv_total is not None:
        pc = (COLORS['success'] if adv_total > mon_total else
              COLORS['danger'] if adv_total < mon_total else COLORS['warning'])
        pw_surf = fonts['huge'].render(str(adv_total), True, pc)
        if pw_surf.get_width() > 130:
            pw_surf = fonts['title'].render(str(adv_total), True, pc)
        screen.blit(pw_surf, pw_surf.get_rect(centerx=x + 218, top=y + 2))
        vs = fonts['small'].render("vs", True, COLORS['text_dim'])
        screen.blit(vs, vs.get_rect(centerx=x + 150, y=y + 40))

    # Monster sprite (left) and hero match slot (right)
    spr = sprite_manager.get_monster_sprite(monster.name, (100, 100))
    if spr:
        screen.blit(spr, (x + 32, y + 104))

    slot = pygame.Rect(x + 164, y + 100, 120, 126)
    pygame.draw.rect(screen, COLORS['well'], slot, border_radius=3)
    if adv:
        paper_doll.draw_adventurer_thumbnail(screen, adv,
                                             slot.x + 12, slot.y + 14, 96)
        pygame.draw.rect(screen, COLORS['success'], slot, 2, border_radius=3)
    else:
        pygame.draw.rect(screen, COLORS['muted'], slot, 2, border_radius=3)
        for j, word in enumerate(("MATCH", "HERO", "HERE")):
            ws = fonts['small'].render(word, True, COLORS['muted'])
            screen.blit(ws, ws.get_rect(centerx=slot.centerx, y=slot.y + 22 + j * 28))

    # Name + type tags
    name = monster.name if len(monster.name) <= 24 else monster.name[:23] + "..."
    ns = fonts['medium'].render(name, True, COLORS['text'])
    screen.blit(ns, ns.get_rect(centerx=rect.centerx, y=y + 230))
    tt = fonts['tiny'].render("Type Tags:", True, COLORS['text_dim'])
    screen.blit(tt, tt.get_rect(centerx=rect.centerx, y=y + 268))

    # Keyword names in their own colours ("2x beast" for duplicates).
    # Rendered at 'small'; drops to 'tiny' if the line would overflow.
    tags = []
    for kw_id, count in _collapse_keywords(monster.keywords)[:4]:
        kw = state.keyword_registry.get(kw_id)
        label = kw.name if kw else kw_id
        if count > 1:
            label = f"{count}x {label}"
        tags.append((label, kw.color if kw else COLORS['text_dim']))

    for font_key in ('small', 'tiny'):
        sep = fonts[font_key].render(", ", True, COLORS['text_dim'])
        pieces = [fonts[font_key].render(label, True, color)
                  for label, color in tags]
        total_w = (sum(p.get_width() for p in pieces)
                   + sep.get_width() * max(0, len(pieces) - 1))
        if total_w <= DELVE_CARD_W - 20 or font_key == 'tiny':
            break
    tx = rect.centerx - total_w // 2
    for j, p in enumerate(pieces):
        screen.blit(p, (tx, y + 290))
        tx += p.get_width()
        if j < len(pieces) - 1:
            screen.blit(sep, (tx, y + 290))
            tx += sep.get_width()


# Cache for party-strip background images ({name: Surface or None}).
_BG_CACHE = {}


def _party_background(state):
    """Per-dungeon strip background: assets/backgrounds/{deck}.png, else _default."""
    deck = state.current_deck
    key = ''
    if deck is not None:
        key = str(getattr(deck, 'name', '')).lower().replace(' ', '_').replace("'", '')
    for name in (key, '_default'):
        if not name:
            continue
        if name not in _BG_CACHE:
            path = os.path.join('assets', 'backgrounds', f'{name}.png')
            surf = None
            if os.path.exists(path):
                try:
                    surf = pygame.image.load(path).convert_alpha()
                    surf = pygame.transform.scale(surf, PARTY_STRIP.size)
                except pygame.error:
                    surf = None
            _BG_CACHE[name] = surf
        if _BG_CACHE[name] is not None:
            return _BG_CACHE[name]
    return None


def _draw_party_hero(screen, fonts, state, slot, adv, is_dragging):
    """One hero on the strip: info block left, big sprite right, no box."""
    sprite_size = 144
    sx = slot.x + 156
    sy = slot.bottom - sprite_size - 10

    info_x = slot.x + 12
    info_y = slot.y + 14

    collapsed = _collapse_keywords(adv.get_all_keywords())
    chips = collapsed[:4]
    extra = len(collapsed) - len(chips)

    name_c = COLORS['danger'] if adv.is_dead else COLORS['text']
    name_surf = fonts['medium'].render(f"{adv.name}:", True, name_c)

    power = adv.get_base_points() * adv.get_multiplier()
    role = ""
    if adv is state.hero_king:
        power *= 2
        role = " (K)"
    elif adv is state.hero_dunce:
        power //= 2
        role = " (D)"
    lbl = fonts['small'].render("Base Power: ", True, COLORS['text'])
    pc = COLORS['danger'] if power <= 0 else COLORS['success']
    val = fonts['small'].render(f"{power}{role}", True, pc)

    # Chip geometry derives from the font so the tabs never overlap.
    chip_h = fonts['tiny'].get_height() + 8
    chip_step = chip_h + 6

    # Translucent backing sized to the content.
    backing_w = min(230, max(150, name_surf.get_width() + 14,
                             lbl.get_width() + val.get_width() + 14))
    backing_h = 92 + len(chips) * chip_step + (20 if extra else 0)
    backing = pygame.Surface((backing_w, backing_h), pygame.SRCALPHA)
    backing.fill((10, 6, 14, 170))
    screen.blit(backing, (info_x - 6, info_y - 6))

    screen.blit(name_surf, (info_x, info_y))
    screen.blit(lbl, (info_x, info_y + 34))
    screen.blit(val, (info_x + lbl.get_width(), info_y + 34))
    screen.blit(fonts['small'].render("Keywords:", True, COLORS['text']),
                (info_x, info_y + 60))

    cy = info_y + 86
    if not chips:
        screen.blit(fonts['small'].render("none", True, COLORS['text_dim']),
                    (info_x + 8, cy))
    for kw_id, count in chips:
        kw = state.keyword_registry.get(kw_id)
        label = (kw.name if kw else str(kw_id))[:12]
        if count > 1:
            label = f"{count}x {label}"
        color = kw.color if kw else COLORS['muted']
        ts = fonts['tiny'].render(label, True, COLORS['bg'])
        chip = pygame.Rect(info_x + 8, cy, ts.get_width() + 14, chip_h)
        pygame.draw.rect(screen, color, chip, border_radius=2)
        screen.blit(ts, (chip.x + 7, chip.y + (chip_h - ts.get_height()) // 2))
        cy += chip_step
    if extra:
        screen.blit(fonts['tiny'].render(f"+{extra} more", True,
                                         COLORS['text_dim']), (info_x + 8, cy))

    # The hero, big, standing on the path (silhouette fallback if no art).
    paper_doll.draw_adventurer_thumbnail(screen, adv, sx, sy, sprite_size)

    if adv.is_dead:
        shade = pygame.Surface((sprite_size, sprite_size), pygame.SRCALPHA)
        shade.fill((120, 20, 20, 130))
        screen.blit(shade, (sx, sy))
        d = fonts['medium'].render("DEAD", True, COLORS['danger'])
        screen.blit(d, d.get_rect(center=(sx + sprite_size // 2,
                                          sy + sprite_size // 2)))
    elif state.find_adventurer_square(adv):
        tag = fonts['small'].render("MATCHED", True, COLORS['gold'])
        screen.blit(tag, tag.get_rect(centerx=sx + sprite_size // 2,
                                      y=slot.bottom - 28))
    if is_dragging:
        pygame.draw.rect(screen, COLORS['accent'], slot.inflate(-6, -6), 2,
                         border_radius=3)


def _wrap_text(text, width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if len(test) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def _draw_hero_info_popup(screen, fonts, state, idx):
    """Dropdown with the hero's full details, opened by clicking them."""
    rects = party_slot_rects(state)
    if idx >= len(rects):
        return
    adv = state.party[idx]
    slot = rects[idx]

    lines = []
    if adv.ability_name:
        for ln in _wrap_text(f"{adv.ability_name}: {adv.ability_desc}", 34)[:3]:
            lines.append((ln, COLORS['text_dim']))
    lines.append((f"Items {len(adv.equipped_items)}/{adv.slots}:", COLORS['text']))
    for item in adv.equipped_items[:4]:
        nm = item.name if len(item.name) <= 26 else item.name[:25] + "..."
        lines.append((f"* {nm} +{item.points}", COLORS['text_dim']))
    if len(adv.equipped_items) > 4:
        lines.append((f"  +{len(adv.equipped_items) - 4} more", COLORS['text_dim']))
    lines.append((f"Multiplier: x{adv.get_multiplier()}", COLORS['accent']))

    w = 400
    h = 52 + len(lines) * 26 + 10
    x = min(max(slot.x, 12), SCREEN_WIDTH - w - 12)
    y = max(12, PARTY_STRIP.y - h - 6)
    _pixel_box(screen, pygame.Rect(x, y, w, h), border=COLORS['accent'],
               fill=theme.mix(COLORS['bg'], COLORS['surface'], 0.35))
    screen.blit(fonts['medium'].render(adv.name, True, COLORS['accent']),
                (x + 12, y + 8))
    ly = y + 50
    for text_str, color in lines:
        screen.blit(fonts['small'].render(text_str, True, color), (x + 12, ly))
        ly += 26


def draw_setup(screen, fonts, state, sprite_manager,
               dragging: bool, drag_adv_index: int):
    """Render the delve setup screen (pixel-art mockup layout)."""
    _draw_header(screen, fonts, state, sprite_manager)

    # Front row
    screen.blit(fonts['small'].render("FRONT ROW", True, COLORS['text_dim']),
                (26, FRONT_ROW_Y - 26))
    for i in range(len(state.front_row)):
        _draw_monster_card(screen, fonts, state, sprite_manager,
                           DELVE_CARD_XS[i], FRONT_ROW_Y, state.front_row[i], i)

    # Party strip — heroes on a continuous scenic background.
    screen.blit(fonts['small'].render("YOUR PARTY", True, COLORS['text_dim']),
                (26, PARTY_STRIP.y - 26))
    bg = _party_background(state)
    if bg:
        screen.blit(bg, PARTY_STRIP.topleft)
    else:
        pygame.draw.rect(screen, COLORS['panel_dark'], PARTY_STRIP, border_radius=3)
    pygame.draw.rect(screen, COLORS['border'], PARTY_STRIP, 2, border_radius=3)

    for i, slot in enumerate(party_slot_rects(state)):
        _draw_party_hero(screen, fonts, state, slot, state.party[i],
                         dragging and drag_adv_index == i)

    # Click-to-open hero dropdown (drawn last so it overlaps neighbours).
    idx = state.delve_hero_info_idx
    if 0 <= idx < len(state.party) and not dragging:
        _draw_hero_info_popup(screen, fonts, state, idx)

    # Overlays
    if state.delve_inv_open:
        draw_inventory_panel(screen, fonts, state)
    if state.delve_recruit_open:
        draw_recruit_panel(screen, fonts, state)


# ---------------------------------------------------------------------------
# Results screen
# ---------------------------------------------------------------------------

def _draw_result_card(screen, fonts, state, sprite_manager, x, y, sq):
    """One resolved square: sprites, big numbers, and WHY it went that way."""
    h = 356
    monster = sq['monster']
    adv = sq['adventurer']
    result = sq.get('result')
    rect = pygame.Rect(x, y, DELVE_CARD_W, h)

    if not result or not adv:
        _pixel_box(screen, rect, border=COLORS['divider'])
        nm = fonts['small'].render(monster.name[:24], True, COLORS['text_dim'])
        screen.blit(nm, nm.get_rect(centerx=rect.centerx, y=y + 14))
        spr = sprite_manager.get_monster_sprite(monster.name, (100, 100))
        if spr:
            screen.blit(spr, spr.get_rect(centerx=rect.centerx, y=y + 70))
        skip = fonts['medium'].render("- Skipped -", True, COLORS['text_dim'])
        screen.blit(skip, skip.get_rect(centerx=rect.centerx, y=y + 210))
        return

    victory = result['victory']
    accent = COLORS['success'] if victory else COLORS['danger']
    _pixel_box(screen, rect, border=accent,
               fill=theme.mix(COLORS['bg'], accent, 0.10))

    adv_p = result['adv_power']
    mon_p = result['monster_power']

    # Big matchup numbers, same spots as the setup screen.
    ds = fonts['huge'].render(str(mon_p), True, COLORS['danger'])
    screen.blit(ds, ds.get_rect(centerx=x + 82, top=y + 2))
    ps = fonts['huge'].render(str(adv_p), True, accent)
    screen.blit(ps, ps.get_rect(centerx=x + 218, top=y + 2))
    vs = fonts['small'].render("vs", True, COLORS['text_dim'])
    screen.blit(vs, vs.get_rect(centerx=x + 150, y=y + 40))

    # Sprites: monster left, hero right; the loser gets shaded red.
    spr = sprite_manager.get_monster_sprite(monster.name, (100, 100))
    if spr:
        screen.blit(spr, (x + 32, y + 104))
    slot = pygame.Rect(x + 164, y + 100, 120, 126)
    pygame.draw.rect(screen, COLORS['well'], slot, border_radius=3)
    paper_doll.draw_adventurer_thumbnail(screen, adv,
                                         slot.x + 12, slot.y + 14, 96)
    pygame.draw.rect(screen, accent, slot, 2, border_radius=3)

    shade = pygame.Surface((120, 126), pygame.SRCALPHA)
    shade.fill((160, 30, 30, 110))
    if victory:
        screen.blit(shade, (x + 22, y + 100))
    else:
        screen.blit(shade, slot.topleft)

    mn = fonts['tiny'].render(monster.name[:16], True, COLORS['text_dim'])
    screen.blit(mn, mn.get_rect(centerx=x + 82, y=y + 232))
    an = fonts['tiny'].render(adv.name[:16], True, COLORS['text_dim'])
    screen.blit(an, an.get_rect(centerx=slot.centerx, y=y + 232))

    # The verdict, and the why, spelled out.
    if victory:
        verdict = fonts['medium'].render("VICTORY", True, COLORS['success'])
        reason = f"Won by {adv_p - mon_p} power"
    else:
        verdict = fonts['medium'].render("DEFEATED", True, COLORS['danger'])
        reason = f"Short by {mon_p - adv_p} power"
    screen.blit(verdict, verdict.get_rect(centerx=rect.centerx, y=y + 258))
    rs = fonts['small'].render(reason, True, COLORS['text'])
    screen.blit(rs, rs.get_rect(centerx=rect.centerx, y=y + 296))

    tail_y = y + 324
    if victory and result.get('reward_item'):
        rn = result['reward_item'].name
        if len(rn) > 24:
            rn = rn[:23] + "..."
        ls = fonts['small'].render(f"+ {rn}", True, COLORS['gold'])
        screen.blit(ls, ls.get_rect(centerx=rect.centerx, y=tail_y))
    elif not victory:
        ds2 = fonts['small'].render(f"{adv.name} is gone", True, COLORS['danger'])
        screen.blit(ds2, ds2.get_rect(centerx=rect.centerx, y=tail_y))


def draw_results(screen, fonts, state, sprite_manager):
    """Render the post-row results screen (pixel-art layout)."""
    summary = state.get_front_row_summary()
    won_row = summary['wins'] >= summary['losses']
    hc = COLORS['success'] if won_row else COLORS['danger']

    # Header banner
    banner = pygame.Rect(SCREEN_WIDTH // 2 - 390, 8, 780, 62)
    _pixel_box(screen, banner, border=hc)
    header = fonts['large'].render(
        f"ROW {state.rows_completed}:  {summary['wins']} Wins / {summary['losses']} Losses",
        True, hc,
    )
    screen.blit(header, header.get_rect(center=banner.center))

    if state.back_row:
        nxt, nc = f"Next row: {len(state.back_row)} monsters ahead", COLORS['warning']
    elif state.boss_square:
        nxt, nc = "The BOSS awaits!", COLORS['danger']
    else:
        nxt, nc = "Dungeon clear!", COLORS['success']
    ns = fonts['medium'].render(nxt, True, nc)
    screen.blit(ns, ns.get_rect(centerx=SCREEN_WIDTH // 2, y=78))

    for i in range(len(state.front_row)):
        _draw_result_card(screen, fonts, state, sprite_manager,
                          DELVE_CARD_XS[i], 118, state.front_row[i])

    # Loot box (left) + party status box (right)
    loot_box = pygame.Rect(20, 490, 760, 206)
    _pixel_box(screen, loot_box, border=COLORS['gold'])
    screen.blit(fonts['medium'].render(
        f"Delve Loot  ({len(state.delve_loot)} items)", True, COLORS['gold']),
        (loot_box.x + 14, loot_box.y + 10))
    ly = loot_box.y + 54
    for item in state.delve_loot[-5:]:
        rc = {
            'scrap':    (120, 120, 120),
            'common':   COLORS['text_dim'],
            'uncommon': COLORS['success'],
            'rare':     COLORS['accent'],
        }.get(item.rarity, COLORS['text'])
        screen.blit(fonts['small'].render(
            f"* {item.name} (+{item.points}) [{item.rarity}]", True, rc),
            (loot_box.x + 20, ly))
        ly += 28

    party_box = pygame.Rect(800, 490, 460, 206)
    _pixel_box(screen, party_box)
    alive = sum(1 for a in state.party if not a.is_dead)
    screen.blit(fonts['medium'].render(
        f"Party: {alive} alive", True, COLORS['text']),
        (party_box.x + 14, party_box.y + 10))
    coins_s = fonts['medium'].render(f"Coins: {state.coins}", True, COLORS['gold'])
    screen.blit(coins_s, (party_box.right - coins_s.get_width() - 14,
                          party_box.y + 10))
    ay = party_box.y + 54
    for adv in state.party[:5]:
        if adv.is_dead:
            line, lc = f"{adv.name} - fell in battle", COLORS['danger']
        else:
            line, lc = adv.name, COLORS['text']
        screen.blit(fonts['small'].render(line, True, lc),
                    (party_box.x + 20, ay))
        ay += 28

    # Overlays
    if state.delve_inv_open:
        draw_inventory_panel(screen, fonts, state)
    if state.delve_recruit_open:
        draw_recruit_panel(screen, fonts, state)


# ---------------------------------------------------------------------------
# Inventory overlay panel
# ---------------------------------------------------------------------------

def draw_inventory_panel(screen, fonts, state):
    """Fullscreen loadout overlay: PARTY ROSTER / HERO LOADOUT / ARMORY.

    Stashes every interactive rect in state._delve_ui so the input handler
    hit-tests exactly what was drawn.
    """
    # Fully opaque: this is its own screen, not a see-through dialog.
    screen.fill(COLORS['bg'])

    sel_ok = 0 <= state.delve_selected_adv_idx < len(state.party)
    sel_adv = state.party[state.delve_selected_adv_idx] if sel_ok else None

    ui = {'unequip_btns': [], 'unequip_all': None, 'filter_btn': None,
          'filter_chips': [], 'filter_clear': None, 'filter_panel': None,
          'search_rect': None, 'item_rows': []}
    state._delve_ui = ui

    # Column headers
    mid_title = f"HERO LOADOUT - {sel_adv.name}" if sel_adv else "HERO LOADOUT"
    for text, rect in (("PARTY ROSTER", INV_LEFT_RECT),
                       (mid_title, INV_MID_RECT),
                       ("ARMORY & INVENTORY", INV_RIGHT_RECT)):
        hs = fonts['medium'].render(text, True, COLORS['text'])
        screen.blit(hs, hs.get_rect(centerx=rect.centerx, y=12))

    # ----- LEFT: party roster -----
    _pixel_box(screen, INV_LEFT_RECT)
    for i, adv in enumerate(state.party):
        cy = INV_LEFT_RECT.y + 10 + i * (INV_CARD_H + INV_CARD_GAP)
        card = pygame.Rect(INV_LEFT_RECT.x + 8, cy,
                           INV_LEFT_RECT.w - 16, INV_CARD_H)
        is_sel = (i == state.delve_selected_adv_idx)
        fill = (theme.mix(COLORS['bg'], COLORS['success'], 0.12)
                if is_sel else COLORS['panel_dark'])
        pygame.draw.rect(screen, fill, card, border_radius=3)
        pygame.draw.rect(screen,
                         COLORS['success'] if is_sel else COLORS['border'],
                         card, 2, border_radius=3)

        paper_doll.draw_adventurer_thumbnail(screen, adv,
                                             card.x + 8, card.y + 10, 64)
        name_c = COLORS['danger'] if adv.is_dead else COLORS['text']
        screen.blit(fonts['medium'].render(adv.name, True, name_c),
                    (card.x + 84, card.y + 12))
        if adv.is_dead:
            sub, sub_c = "DEAD", COLORS['danger']
        else:
            sub = f"Slots: {len(adv.equipped_items)}/{adv.slots}"
            sub_c = (COLORS['warning']
                     if len(adv.equipped_items) >= adv.slots
                     else COLORS['text_dim'])
        screen.blit(fonts['small'].render(sub, True, sub_c),
                    (card.x + 84, card.y + 44))

        # Per-hero [Unequip] button (only when they carry something)
        if adv.equipped_items:
            ub = pygame.Rect(card.right - 76, card.bottom - 28, 68, 22)
            pygame.draw.rect(screen, COLORS['panel_dark'], ub, border_radius=2)
            pygame.draw.rect(screen, COLORS['danger'], ub, 1, border_radius=2)
            us = fonts['tiny'].render("Unequip", True, COLORS['text'])
            screen.blit(us, us.get_rect(center=ub.center))
            ui['unequip_btns'].append((i, ub))

    # [Unequip All] pinned to the bottom of the roster column
    ua = pygame.Rect(INV_LEFT_RECT.x + 8, INV_LEFT_RECT.bottom - 42,
                     INV_LEFT_RECT.w - 16, 32)
    pygame.draw.rect(screen, COLORS['panel_dark'], ua, border_radius=3)
    pygame.draw.rect(screen, COLORS['danger'], ua, 2, border_radius=3)
    uas = fonts['small'].render("[ Unequip All ]", True, COLORS['text'])
    screen.blit(uas, uas.get_rect(center=ua.center))
    ui['unequip_all'] = ua

    # ----- MIDDLE: hero loadout (shared widget) -----
    state._delve_equipped_rows = widgets.draw_hero_loadout_column(
        screen, fonts, state, INV_MID_RECT, sel_adv,
        state.delve_equipped_scroll, paper_doll)

    # ----- RIGHT: armory & inventory — shared search + list widget -----
    filtered = state.get_filtered_delve_items()
    res = widgets.draw_item_list_panel(
        screen, fonts, state, INV_RIGHT_RECT,
        items=filtered,
        scroll=state.delve_inv_scroll,
        search_text=state.delve_item_search,
        search_active=state.delve_item_search_active,
        header_text=(f"{len(state.delve_loot)} new + "
                     f"{len(state.inventory)} stored — click to equip"),
        is_new_func=lambda it: it in state.delve_loot,
        paper_doll_module=paper_doll,
        hover_pos=state.hover_pos,
        filter_selected=state.delve_kw_filter,
        filter_open=state.delve_filter_open,
    )
    ui['filter_btn'] = res['filter_btn_rect']
    ui['search_rect'] = res['search_rect']
    ui['item_rows'] = res['visible']

    # Keyword-filter dropdown drawn last so it overlays the list.
    if state.delve_filter_open:
        pool = list(state.delve_loot) + list(state.inventory)
        dd = widgets.draw_kw_filter_dropdown(
            screen, fonts, state, res['search_rect'], pool,
            state.delve_kw_filter)
        ui['filter_chips'] = dd['chips']
        ui['filter_clear'] = dd['clear_rect']
        ui['filter_panel'] = dd['panel_rect']


# ---------------------------------------------------------------------------
# Recruit overlay panel
# ---------------------------------------------------------------------------

def draw_recruit_panel(screen, fonts, state):
    """Mid-delve recruitment overlay."""
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 120))
    screen.blit(overlay, (0, 0))

    panel_rect = pygame.Rect(640, 80, 620, 620)
    pygame.draw.rect(screen, COLORS['panel'], panel_rect, border_radius=10)
    pygame.draw.rect(screen, COLORS['success'], panel_rect, 3, border_radius=10)

    alive_in_party = sum(1 for a in state.party if not a.is_dead)
    title = fonts['large'].render(
        f"Recruit  ({alive_in_party}/4 alive)", True, COLORS['success'],
    )
    screen.blit(title, (660, 85))

    screen.blit(
        fonts['small'].render(
            "Click an adventurer to add them to your party:",
            True, COLORS['text'],
        ),
        (660, 120),
    )

    available = state.get_available_recruits()
    if not available:
        screen.blit(fonts['medium'].render("No recruits available!", True, COLORS['text_dim']),
                    (660, 170))
        screen.blit(
            fonts['small'].render(
                "Buy more adventurers at the shop between delves.",
                True, COLORS['text_dim'],
            ),
            (660, 210),
        )
    else:
        for j, adv in enumerate(available):
            y = 142 + j * 74
            if y > 620:
                break

            rect = pygame.Rect(660, y, 560, 64)
            pygame.draw.rect(screen, COLORS['panel_light'], rect, border_radius=6)
            pygame.draw.rect(screen, COLORS['accent'], rect, 1, border_radius=6)

            # Portrait thumbnail — right side
            adv_id = getattr(adv, 'id', adv.name)
            paper_doll.draw_portrait_thumbnail(screen, adv_id,
                                               660 + 560 - 54, y + 8, 48)

            screen.blit(fonts['medium'].render(adv.name, True, COLORS['text']),
                        (676, y + 8))
            slots_text = f"[{adv.slots} slots]"
            screen.blit(fonts['small'].render(slots_text, True, COLORS['text_dim']),
                        (676 + 180, y + 12))

            ability = f"{adv.ability_name}: {adv.ability_desc}"
            if len(ability) > 65:
                ability = ability[:64] + "..."
            screen.blit(fonts['small'].render(ability, True, COLORS['text_dim']),
                        (676, y + 38))

            eq_count = len(adv.equipped_items)
            if eq_count > 0:
                screen.blit(
                    fonts['small'].render(
                        f"{eq_count} items equipped", True, COLORS['warning'],
                    ),
                    (1100, y + 12),
                )

    screen.blit(
        fonts['small'].render(
            "Click  Recruit again to close. Use  Items to equip new recruits.",
            True, COLORS['text_dim'],
        ),
        (660, 680),
    )