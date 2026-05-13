"""Delve phase rendering: setup, results, square cards, inventory & recruit overlays."""

import pygame

from ...config import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT
from .. import paper_doll
from .. import widgets


# ---------------------------------------------------------------------------
# Square card (used by both setup and results)
# ---------------------------------------------------------------------------

def draw_square_card(screen, fonts, state, x: int, y: int, w: int, h: int,
                     sq: dict, index: int, show_result: bool = False):
    """Draw a single front-row square card.

    Top banner shows TOTAL POWER for both sides (#3).  Monster role
    (KING/DUNCE) is shown in place of the old multiplier badge (#6).
    Bottom section shows a larger adventurer portrait with equipped items (#2).
    """
    monster = sq['monster']
    adv = sq['adventurer']
    bonus = sq['bonus']
    result = sq.get('result')
    is_king  = bool(sq.get('is_king'))
    is_dunce = bool(sq.get('is_dunce'))
    pad = 10

    # Background color
    if show_result and result:
        bg_color = (35, 75, 35) if result['victory'] else (75, 35, 35)
    elif adv:
        bg_color = (48, 52, 64)
    else:
        bg_color = COLORS['panel']

    card_rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(screen, bg_color, card_rect, border_radius=10)

    # Border by role
    if is_king:
        border_color = COLORS['gold']
    elif is_dunce:
        border_color = COLORS['text_dim']
    else:
        border_color = COLORS['accent']
    pygame.draw.rect(screen, border_color, card_rect, 3, border_radius=10)

    # ---- POWER BANNER (feature #3) ----
    # Show monster total and, if placed, adventurer total at top.
    # King: ×2 monster.  Dunce: ÷2 monster.  Same for hero on the adv side.
    mon_total = monster.base_points
    if is_king:
        mon_total *= 2
    elif is_dunce:
        mon_total = mon_total // 2

    if adv and not show_result:
        adv_base = adv.get_base_points()
        adv_km   = adv.get_multiplier()
        adv_total = adv_base * adv_km
        adv_is_king  = (adv is state.hero_king)
        adv_is_dunce = (adv is state.hero_dunce)
        if adv_is_king:
            adv_total *= 2
        elif adv_is_dunce:
            adv_total = adv_total // 2

        if adv_total > mon_total * 1.5:
            pw_color = COLORS['success']
        elif adv_total > mon_total * 0.8:
            pw_color = COLORS['warning']
        else:
            pw_color = COLORS['danger']
        pwr_banner = f"ATK {adv_total}  vs  DEF {mon_total}"
        pb_surf = fonts['small'].render(pwr_banner, True, pw_color)
        screen.blit(pb_surf, pb_surf.get_rect(centerx=x + w // 2, y=y + 2))
    elif not adv and not show_result:
        mon_pwr_surf = fonts['small'].render(
            f"DEF {mon_total}", True, COLORS['text_dim'])
        screen.blit(mon_pwr_surf, mon_pwr_surf.get_rect(
            centerx=x + w // 2, y=y + 2))

    # Row 1: monster name + role badge
    mon_name = monster.name
    max_name = (w - 80) // 10
    if len(mon_name) > max_name:
        mon_name = mon_name[:max_name - 1] + "..."
    screen.blit(fonts['medium'].render(mon_name, True, COLORS['text']), (x + pad, y + 18))

    # Role badge in place of the old multiplier
    if is_king:
        badge_surf = fonts['medium'].render("KING", True, COLORS['gold'])
        screen.blit(badge_surf, (x + w - badge_surf.get_width() - 8, y + 16))
    elif is_dunce:
        badge_surf = fonts['medium'].render("DUNCE", True, COLORS['text_dim'])
        screen.blit(badge_surf, (x + w - badge_surf.get_width() - 8, y + 16))

    # Row 2: keywords as colored tags
    kw_x = x + pad
    kw_y = y + 48
    tag_h = 20
    for kw_id in monster.keywords[:4]:
        kw = state.keyword_registry.get(kw_id)
        if kw:
            label = kw.name[:9]
            tw = fonts['small'].render(label, True, COLORS['bg']).get_width() + 10
            if kw_x + tw > x + w - pad:
                break
            pygame.draw.rect(screen, kw.color, (kw_x, kw_y, tw, tag_h), border_radius=4)
            screen.blit(fonts['small'].render(label, True, COLORS['bg']), (kw_x + 5, kw_y + 2))
            kw_x += tw + 5

    # Row 3: monster stats + bonus
    info_y = y + 76
    pts_text = f"Enemy: {monster.base_points} pts"
    screen.blit(fonts['small'].render(pts_text, True, COLORS['text_dim']), (x + pad, info_y))

    if bonus['type'] == 'keyword_buff':
        screen.blit(
            fonts['small'].render(f"Buff: +{bonus['keyword']}", True, COLORS['success']),
            (x + pad, info_y + 16),
        )
    elif bonus['type'] == 'keyword_resist':
        screen.blit(
            fonts['small'].render(f"Resist: {bonus['keyword']}", True, COLORS['accent']),
            (x + pad, info_y + 16),
        )

    # Row 4: adventurer slot (or drop zone, or result)
    slot_y = y + 118
    if adv:
        pygame.draw.line(screen, (80, 80, 100),
                         (x + pad, slot_y - 3), (x + w - pad, slot_y - 3), 1)

        adv_color = COLORS['success'] if not adv.is_dead else COLORS['danger']
        adv_name = adv.name
        max_an = (w - 20) // 10
        if len(adv_name) > max_an:
            adv_name = adv_name[:max_an - 1] + "..."
        screen.blit(
            fonts['medium'].render(f"> {adv_name}", True, adv_color),
            (x + pad, slot_y),
        )

        if not show_result:
            raw = adv.get_base_points()
            km  = adv.get_multiplier()
            pwr = raw * km
            role = ""
            if adv is state.hero_king:
                pwr *= 2
                role = "  KING x2"
            elif adv is state.hero_dunce:
                pwr = pwr // 2
                role = "  DUNCE /2"
            calc = f"{raw} x {km} = {pwr}{role}"
            screen.blit(
                fonts['small'].render(calc, True, COLORS['success']),
                (x + pad, slot_y + 22),
            )
    elif not show_result:
        drop_rect = pygame.Rect(x + pad, slot_y, w - pad * 2, 40)
        pygame.draw.rect(screen, (55, 55, 70), drop_rect, border_radius=6)
        pygame.draw.rect(screen, COLORS['text_dim'], drop_rect, 1, border_radius=6)
        drop_text = fonts['medium'].render("Drop Here", True, COLORS['text_dim'])
        drop_rect_c = drop_text.get_rect(center=(x + w // 2, slot_y + 20))
        screen.blit(drop_text, drop_rect_c)

    # ---- ADVENTURER PORTRAIT + EQUIPPED ITEMS (feature #2) ----
    # Larger portrait (80 px) centred at the bottom of the card,
    # with equipped item chips in a row beneath it.
    if adv:
        adv_id = getattr(adv, 'id', adv.name)
        port_size = 72
        px = x + w - port_size - 6
        py = y + h - port_size - 8
        # Dark backing frame
        pygame.draw.rect(screen, (18, 20, 28),
                         (px - 2, py - 2, port_size + 4, port_size + 4),
                         border_radius=6)
        # Draw adventurer thumbnail with item chips (feature #1/#2)
        paper_doll.draw_adventurer_thumbnail(screen, adv, px, py, port_size)
        adv_color = COLORS['success'] if not adv.is_dead else COLORS['danger']
        pygame.draw.rect(screen, adv_color,
                         (px - 2, py - 2, port_size + 4, port_size + 4),
                         1, border_radius=6)

    # Result overlay
    if show_result and result:
        ry = y + 118
        pygame.draw.line(screen, (80, 80, 100),
                         (x + pad, ry - 3), (x + w - pad, ry - 3), 1)

        if result['victory']:
            screen.blit(fonts['medium'].render("WIN", True, COLORS['success']),
                        (x + pad, ry))
            score = f"{result['adv_power']}  vs  {result['monster_power']}"
            screen.blit(fonts['small'].render(score, True, COLORS['text']),
                        (x + pad, ry + 24))
            if result.get('reward_item'):
                rn = result['reward_item'].name
                if len(rn) > 20:
                    rn = rn[:19] + "..."
                screen.blit(fonts['small'].render(f"+ {rn}", True, COLORS['gold']),
                            (x + pad, ry + 44))
        else:
            screen.blit(fonts['medium'].render("LOSS", True, COLORS['danger']),
                        (x + pad, ry))
            score = f"{result['adv_power']}  vs  {result['monster_power']}"
            screen.blit(fonts['small'].render(score, True, COLORS['text']),
                        (x + pad, ry + 24))
            if adv:
                screen.blit(
                    fonts['small'].render(f"{adv.name} died", True, COLORS['danger']),
                    (x + pad, ry + 44),
                )
    elif show_result and not adv:
        ry = y + 130
        screen.blit(fonts['medium'].render("- Skipped -", True, COLORS['text_dim']),
                    (x + pad, ry))


# ---------------------------------------------------------------------------
# Setup screen
# ---------------------------------------------------------------------------

def draw_setup(screen, fonts, state, dragging: bool, drag_adv_index: int):
    """Render the seamless delve setup screen."""
    CW = 300
    CXS = [20, 330, 640, 950]

    deck_name = state.current_deck.name if state.current_deck else "Unknown"

    # Header bar
    screen.blit(fonts['large'].render(f"DELVE - {deck_name}", True, COLORS['accent']), (20, 10))

    row_text = f"Row {state.rows_completed + 1}"
    screen.blit(fonts['medium'].render(row_text, True, COLORS['warning']), (450, 18))

    # King/Dunce banner — explicit display of who's who this row
    parts = []
    if state.hero_king:
        parts.append(("HERO KING: " + state.hero_king.name, COLORS['gold']))
    if state.hero_dunce:
        parts.append(("HERO DUNCE: " + state.hero_dunce.name, COLORS['text_dim']))
    if not parts:
        parts.append(("First match — no hero king/dunce yet", COLORS['text_dim']))

    # Find the monster king/dunce names too
    king_mon = next((sq['monster'].name for sq in state.front_row if sq.get('is_king')), None)
    dunce_mon = next((sq['monster'].name for sq in state.front_row if sq.get('is_dunce')), None)
    if king_mon:
        parts.append((f"MONSTER KING: {king_mon}", COLORS['gold']))
    if dunce_mon:
        parts.append((f"MONSTER DUNCE: {dunce_mon}", COLORS['text_dim']))

    bx = 450
    for txt, c in parts:
        s = fonts['small'].render(txt, True, c)
        screen.blit(s, (bx, 42))
        bx += s.get_width() + 18

    # Rules legend (smaller, second line)
    rules = fonts['tiny'].render(
        "KING: ×2 power, ignores biggest weakness    DUNCE: power ÷2",
        True, COLORS['text_dim'])
    screen.blit(rules, (450, 62))

    alive = state.count_alive_party()
    placed = state.count_front_placed()
    need = min(alive, len(state.front_row))
    status_color = COLORS['success'] if placed >= need else COLORS['text']
    status = (
        f"Placed: {placed}/{need}   Loot: {len(state.delve_loot)}   "
        f"Coins: {state.coins}"
    )
    screen.blit(fonts['medium'].render(status, True, status_color), (750, 18))

    # Back row preview (dimmed)
    by = 52
    if state.back_row:
        screen.blit(fonts['small'].render("NEXT ROW:", True, COLORS['text_dim']), (20, by))
        for i, sq in enumerate(state.back_row):
            bx = CXS[i] if i < 4 else 20
            rect = pygame.Rect(bx, by + 18, CW, 50)
            pygame.draw.rect(screen, (35, 35, 48), rect, border_radius=6)
            pygame.draw.rect(screen, (60, 60, 75), rect, 1, border_radius=6)

            # role badge (or blank) for back row preview
            back_badge = ""
            if sq.get('is_king'):  back_badge = "K"
            elif sq.get('is_dunce'): back_badge = "D"
            if back_badge:
                bc = COLORS['gold'] if back_badge == 'K' else COLORS['text_dim']
                screen.blit(fonts['medium'].render(back_badge, True, bc),
                            (bx + CW - 22, by + 22))
            name = sq['monster'].name
            if len(name) > 22:
                name = name[:21] + "..."
            screen.blit(
                fonts['small'].render(name, True, (140, 110, 110)),
                (bx + 10, by + 22),
            )
            kws = ", ".join(sq['monster'].keywords[:3])
            if len(kws) > 28:
                kws = kws[:27] + "..."
            screen.blit(
                fonts['small'].render(
                    f"{sq['monster'].base_points}pts  {kws}", True, COLORS['text_dim'],
                ),
                (bx + 10, by + 44),
            )
    else:
        label = "BOSS waits beyond!" if state.boss_square else "Final row!"
        color = COLORS['danger'] if state.boss_square else COLORS['warning']
        screen.blit(fonts['medium'].render(label, True, color), (20, by + 10))

    # Front row
    front_y = 128
    front_h = 200
    screen.blit(
        fonts['medium'].render(
            ">  FRONT ROW  -  drag adventurers onto squares",
            True, COLORS['accent'],
        ),
        (20, front_y - 18),
    )
    for i in range(len(state.front_row)):
        draw_square_card(screen, fonts, state, CXS[i], front_y, CW, front_h,
                         state.front_row[i], i)

    # Party tray
    party_y = 345
    party_h = 160
    screen.blit(
        fonts['medium'].render(
            "YOUR PARTY  -  must place all living adventurers",
            True, COLORS['text'],
        ),
        (20, party_y - 18),
    )

    for i, adv in enumerate(state.party):
        cx = CXS[i] if i < 4 else 20
        current_sq = state.find_adventurer_square(adv)
        is_dragging = dragging and drag_adv_index == i
        earned_m = state.get_adventurer_multiplier(adv)

        if adv.is_dead:    bg = (60, 30, 30)
        elif is_dragging:  bg = (40, 42, 52)
        elif current_sq:   bg = (45, 55, 65)
        else:              bg = COLORS['panel_light']

        rect = pygame.Rect(cx, party_y, CW, party_h)
        pygame.draw.rect(screen, bg, rect, border_radius=10)
        border = COLORS['accent'] if (not adv.is_dead and not is_dragging) else COLORS['text_dim']
        pygame.draw.rect(screen, border, rect, 2, border_radius=10)

        pad = 10
        # Name + KING/DUNCE badge
        screen.blit(fonts['medium'].render(adv.name, True, COLORS['text']),
                    (cx + pad, party_y + 8))
        if adv is state.hero_king and not adv.is_dead:
            badge = fonts['medium'].render("KING", True, COLORS['gold'])
            screen.blit(badge, (cx + CW - badge.get_width() - pad, party_y + 8))
        elif adv is state.hero_dunce and not adv.is_dead:
            badge = fonts['medium'].render("DUNCE", True, COLORS['text_dim'])
            screen.blit(badge, (cx + CW - badge.get_width() - pad, party_y + 8))

        # Portrait + item chips — right side of the tray card
        paper_doll.draw_adventurer_thumbnail(screen, adv,
                                             cx + CW - 68, party_y + 4, 60)

        # Status
        line_y = party_y + 38
        if adv.is_dead:
            screen.blit(fonts['medium'].render("DEAD", True, COLORS['danger']),
                        (cx + pad, line_y))
        elif is_dragging:
            screen.blit(fonts['small'].render("Dragging...", True, COLORS['accent']),
                        (cx + pad, line_y))
        elif current_sq:
            sq_label = "KING sq" if current_sq.get('is_king') else (
                       "DUNCE sq" if current_sq.get('is_dunce') else "Square")
            screen.blit(
                fonts['small'].render(
                    f"Placed on {sq_label}", True, COLORS['warning'],
                ),
                (cx + pad, line_y),
            )
            rb = adv.get_base_points()
            km = adv.get_multiplier()
            pwr = rb * km
            role_tag = ""
            if adv is state.hero_king:
                pwr *= 2; role_tag = "  KING x2"
            elif adv is state.hero_dunce:
                pwr = pwr // 2; role_tag = "  DUNCE /2"
            screen.blit(
                fonts['small'].render(
                    f"Power: {rb} x {km} = {pwr}{role_tag}",
                    True, COLORS['success'],
                ),
                (cx + pad, line_y + 22),
            )
        else:
            rb = adv.get_base_points()
            km = adv.get_multiplier()
            screen.blit(
                fonts['small'].render(
                    f"Base Power: {rb} x {km} = {rb * km}",
                    True, COLORS['text_dim'],
                ),
                (cx + pad, line_y),
            )
            screen.blit(
                fonts['small'].render(
                    f"Items: {len(adv.equipped_items)}/{adv.slots}",
                    True, COLORS['text_dim'],
                ),
                (cx + pad, line_y + 22),
            )

        # Keywords
        kws = adv.get_all_keywords()[:5]
        kw_str = ", ".join(kws) if kws else "none"
        if len(kw_str) > 35:
            kw_str = kw_str[:34] + "..."
        screen.blit(fonts['small'].render(kw_str, True, COLORS['text_dim']),
                    (cx + pad, line_y + 46))

        # Items
        ey = line_y + 66
        for item in adv.equipped_items[:3]:
            iname = item.name if len(item.name) <= 20 else item.name[:19] + "..."
            screen.blit(
                fonts['small'].render(f"* {iname} +{item.points}", True, COLORS['text_dim']),
                (cx + pad, ey),
            )
            ey += 18

    # Overlays
    if state.delve_inv_open:
        draw_inventory_panel(screen, fonts, state)
    if state.delve_recruit_open:
        draw_recruit_panel(screen, fonts, state)


# ---------------------------------------------------------------------------
# Results screen
# ---------------------------------------------------------------------------

def draw_results(screen, fonts, state):
    """Render the post-row results screen."""
    CXS = [20, 330, 640, 950]
    CW = 300

    summary = state.get_front_row_summary()
    hc = COLORS['success'] if summary['wins'] >= summary['losses'] else COLORS['danger']
    header = fonts['title'].render(
        f"ROW {state.rows_completed}:  {summary['wins']} Wins  /  {summary['losses']} Losses",
        True, hc,
    )
    screen.blit(header, header.get_rect(centerx=SCREEN_WIDTH // 2, y=10))

    ny = 55
    if state.back_row:
        nt = fonts['medium'].render(
            f"Next row: {len(state.back_row)} monsters — new King/Dunce ahead",
            True, COLORS['warning'],
        )
        screen.blit(nt, nt.get_rect(centerx=SCREEN_WIDTH // 2, y=ny))
    elif state.boss_square:
        bt = fonts['medium'].render(
            "Boss awaits!", True, COLORS['danger'],
        )
        screen.blit(bt, bt.get_rect(centerx=SCREEN_WIDTH // 2, y=ny))
    else:
        et = fonts['medium'].render("Dungeon clear!", True, COLORS['success'])
        screen.blit(et, et.get_rect(centerx=SCREEN_WIDTH // 2, y=ny))

    for i in range(len(state.front_row)):
        draw_square_card(screen, fonts, state, CXS[i], 90, CW, 200,
                         state.front_row[i], i, show_result=True)

    # Loot list
    ly = 310
    screen.blit(
        fonts['medium'].render(
            f"Delve Loot  ({len(state.delve_loot)} items)", True, COLORS['gold'],
        ),
        (20, ly),
    )
    for item in state.delve_loot[-8:]:
        ly += 24
        rc = {
            'scrap':    (120, 120, 120),
            'common':   COLORS['text_dim'],
            'uncommon': COLORS['success'],
            'rare':     COLORS['accent'],
        }.get(item.rarity, COLORS['text'])
        screen.blit(
            fonts['small'].render(
                f"  {item.name} (+{item.points}) [{item.rarity}]", True, rc,
            ),
            (30, ly),
        )

    # Party status row
    alive = [a for a in state.party if not a.is_dead]
    py = 570
    screen.blit(
        fonts['medium'].render(
            f"Party: {len(alive)} alive   |   Coins: {state.coins}",
            True, COLORS['text'],
        ),
        (20, py),
    )
    ex = 20
    for adv in alive:
        role = ""
        ec = COLORS['text_dim']
        if adv is state.hero_king:
            role = " (KING)"; ec = COLORS['gold']
        elif adv is state.hero_dunce:
            role = " (DUNCE)"; ec = COLORS['text_dim']
        screen.blit(
            fonts['small'].render(f"{adv.name}{role}", True, ec),
            (ex, py + 30),
        )
        ex += 220

    # Overlays
    if state.delve_inv_open:
        draw_inventory_panel(screen, fonts, state)
    if state.delve_recruit_open:
        draw_recruit_panel(screen, fonts, state)


# ---------------------------------------------------------------------------
# Inventory overlay panel
# ---------------------------------------------------------------------------

def draw_inventory_panel(screen, fonts, state):
    """Three-column item-management overlay during delve."""
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.blit(overlay, (0, 0))

    PX, PY, PW, PH = 60, 40, 1160, 710
    pygame.draw.rect(screen, (32, 32, 45), (PX, PY, PW, PH), border_radius=12)
    pygame.draw.rect(screen, COLORS['accent'], (PX, PY, PW, PH), 2, border_radius=12)

    # Title bar
    screen.blit(fonts['large'].render("Manage Equipment", True, COLORS['accent']),
                (PX + 20, PY + 10))
    close_hint = fonts['small'].render("Click  Items  button to close", True, COLORS['text_dim'])
    screen.blit(close_hint, (PX + PW - close_hint.get_width() - 20, PY + 20))

    # ----- LEFT COLUMN: Adventurer Selection -----
    left_x = PX + 10
    left_w = 250
    col_top = PY + 55

    screen.blit(fonts['medium'].render("Party", True, COLORS['text']),
                (left_x + 8, col_top))

    adv_card_h = 80
    adv_gap = 6
    for i, adv in enumerate(state.party):
        cy = col_top + 32 + i * (adv_card_h + adv_gap)
        is_sel = (i == state.delve_selected_adv_idx)
        is_dead = adv.is_dead

        if is_dead:
            bg, border = (55, 30, 30), COLORS['danger']
        elif is_sel:
            bg, border = (40, 55, 80), COLORS['accent']
        else:
            bg, border = COLORS['panel_light'], (80, 80, 95)

        card_rect = pygame.Rect(left_x, cy, left_w, adv_card_h)
        pygame.draw.rect(screen, bg, card_rect, border_radius=8)
        pygame.draw.rect(screen, border, card_rect, 2, border_radius=8)

        # Name
        name_color = COLORS['danger'] if is_dead else (
            COLORS['accent'] if is_sel else COLORS['text']
        )
        screen.blit(fonts['medium'].render(adv.name, True, name_color),
                    (left_x + 10, cy + 6))

        # Portrait thumbnail — right side of card
        adv_id = getattr(adv, 'id', adv.name)
        paper_doll.draw_portrait_thumbnail(screen, adv_id,
                                           left_x + left_w - 52, cy + 4, 46)

        # Slots
        slots_text = f"{len(adv.equipped_items)}/{adv.slots} slots"
        slots_color = (
            COLORS['warning']
            if len(adv.equipped_items) >= adv.slots
            else COLORS['text_dim']
        )
        slots_surf = fonts['small'].render(slots_text, True, slots_color)
        screen.blit(slots_surf, (left_x + left_w - slots_surf.get_width() - 10, cy + 10))

        if is_dead:
            screen.blit(fonts['small'].render("DEAD", True, COLORS['danger']),
                        (left_x + 10, cy + 32))
        else:
            if adv.ability_name:
                ab_text = adv.ability_name
                if len(ab_text) > 25:
                    ab_text = ab_text[:24] + ".."
                screen.blit(fonts['small'].render(ab_text, True, COLORS['text_dim']),
                            (left_x + 10, cy + 32))

            # Keyword preview
            kws = adv.get_all_keywords()[:4]
            kw_str = ", ".join(kws) if kws else "no keywords"
            if len(kw_str) > 28:
                kw_str = kw_str[:27] + ".."
            screen.blit(fonts['small'].render(kw_str, True, COLORS['text_dim']),
                        (left_x + 10, cy + 52))

    # ----- CENTER COLUMN: Selected Adventurer paper-doll card (#1) -----
    center_x = left_x + left_w + 15
    center_w = 370

    if 0 <= state.delve_selected_adv_idx < len(state.party):
        adv = state.party[state.delve_selected_adv_idx]

        # Header
        header_text = f"{adv.name}'s Loadout"
        screen.blit(fonts['medium'].render(header_text, True, COLORS['accent']),
                    (center_x + 8, col_top))

        # KING/DUNCE badge
        if adv is state.hero_king:
            kdb = fonts['small'].render("HERO KING ×2", True, COLORS['gold'])
            screen.blit(kdb, (center_x + center_w - kdb.get_width() - 10, col_top + 4))
        elif adv is state.hero_dunce:
            kdb = fonts['small'].render("HERO DUNCE ÷2", True, COLORS['text_dim'])
            screen.blit(kdb, (center_x + center_w - kdb.get_width() - 10, col_top + 4))

        # Paper-doll card — sized to fit available width.  Card is 280×380;
        # centre it inside the column.
        card_x = center_x + (center_w - paper_doll.CARD_W) // 2
        card_y = col_top + 30
        paper_doll.draw_character_card(
            screen, fonts, state, card_x, card_y, adv, selected=True)

        # Unequip hint
        hint = fonts['tiny'].render("Click any item on the doll to unequip",
                                    True, COLORS['text_dim'])
        screen.blit(hint, (center_x + 8,
                           card_y + paper_doll.CARD_H + 4))
    else:
        prompt = fonts['medium'].render("Select an adventurer", True, COLORS['text_dim'])
        screen.blit(prompt,
                    (center_x + center_w // 2 - prompt.get_width() // 2, col_top + 80))
        arrow = fonts['large'].render("<", True, COLORS['text_dim'])
        screen.blit(arrow,
                    (center_x + center_w // 2 - arrow.get_width() // 2, col_top + 120))

    # ----- RIGHT COLUMN: Available Items — shared widget (#2 + #4) -----
    right_x = center_x + center_w + 15
    right_w = PX + PW - right_x - 10
    right_h = PY + PH - col_top - 50
    right_rect = pygame.Rect(right_x, col_top, right_w, right_h)

    filtered = state.get_filtered_delve_items()
    widgets.draw_item_list_panel(
        screen, fonts, state, right_rect,
        items=filtered,
        scroll=state.delve_inv_scroll,
        search_text=state.delve_item_search,
        search_active=state.delve_item_search_active,
        header_text=(f"Available: {len(state.delve_loot)} new  +  "
                     f"{len(state.inventory)} inventory"),
        is_new_func=lambda it: it in state.delve_loot,
        paper_doll_module=paper_doll,
    )

    # Instructions
    inst_y = PY + PH - 32
    hint = ("Select adventurer > Click equipped item to unequip > "
            "Click available item to equip")
    if state.delve_selected_adv_idx >= 0:
        adv = state.party[state.delve_selected_adv_idx]
        if not adv.can_equip():
            hint = (f"{adv.name} is full — unequip an item first, "
                    "or select a different adventurer")
    screen.blit(fonts['small'].render(hint, True, COLORS['text_dim']),
                (PX + 20, inst_y))


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
            y = 140 + j * 65
            if y > 620:
                break

            rect = pygame.Rect(660, y, 560, 58)
            pygame.draw.rect(screen, COLORS['panel_light'], rect, border_radius=6)
            pygame.draw.rect(screen, COLORS['accent'], rect, 1, border_radius=6)

            # Portrait thumbnail — right side
            adv_id = getattr(adv, 'id', adv.name)
            paper_doll.draw_portrait_thumbnail(screen, adv_id,
                                               660 + 560 - 52, y + 6, 46)

            screen.blit(fonts['medium'].render(adv.name, True, COLORS['text']),
                        (672, y + 4))
            slots_text = f"[{adv.slots} slots]"
            screen.blit(fonts['small'].render(slots_text, True, COLORS['text_dim']),
                        (672 + 180, y + 8))

            ability = f"{adv.ability_name}: {adv.ability_desc}"
            if len(ability) > 65:
                ability = ability[:64] + "..."
            screen.blit(fonts['small'].render(ability, True, COLORS['text_dim']),
                        (672, y + 32))

            eq_count = len(adv.equipped_items)
            if eq_count > 0:
                screen.blit(
                    fonts['small'].render(
                        f"{eq_count} items equipped", True, COLORS['warning'],
                    ),
                    (1100, y + 8),
                )

    screen.blit(
        fonts['small'].render(
            "Click  Recruit again to close. Use  Items to equip new recruits.",
            True, COLORS['text_dim'],
        ),
        (660, 680),
    )