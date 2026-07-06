"""Boss phase rendering: choice and result screens.

The boss carries equipped items that add points and keywords to its total.
On BOSS_CHOICE the player picks a hero, then a target: smash one of the
boss's items (destroying it strips its keywords/points and drops the total)
or challenge the boss itself — which ends the fight, win or lose. Winning
while the boss still has items intact claims them all as bonus loot.

Interactive rects are stashed in state._boss_ui for the input handler.
"""

import pygame

from ... import theme
from ...config import COLORS, SCREEN_WIDTH
from ...controllers import combat
from .. import paper_doll
from .. import widgets

_pixel_box = widgets.draw_pixel_box


def _draw_boss_panel(screen, fonts, state, sprite_manager, boss, selected):
    """Boss target panel: sprite, name, current score, current keywords."""
    panel = pygame.Rect(SCREEN_WIDTH // 2 - 300, 58, 600, 190)
    border = COLORS['gold'] if selected else COLORS['danger']
    _pixel_box(screen, panel, border=border,
               fill=theme.mix(COLORS['bg'], COLORS['danger'], 0.08))

    monster = boss['monster']
    spr = sprite_manager.get_monster_sprite(monster.name, (110, 110))
    if spr:
        screen.blit(spr, (panel.x + 24, panel.y + 40))

    name_surf = fonts['large'].render(monster.name, True, COLORS['danger'])
    screen.blit(name_surf, (panel.x + 150, panel.y + 14))

    score = boss.get('score', 0)
    total = boss.get('total', score)
    sc = fonts['huge'].render(str(score), True, COLORS['danger'])
    if sc.get_width() > 220:
        sc = fonts['title'].render(str(score), True, COLORS['danger'])
    screen.blit(sc, (panel.x + 150, panel.y + 52))
    if score != total:
        was = fonts['small'].render(f"(was {total})", True, COLORS['text_dim'])
        screen.blit(was, (panel.x + 160 + sc.get_width(), panel.y + 96))

    # Current keywords (collapsed, coloured)
    kx = panel.x + 150
    ky = panel.y + 138
    for kw_id, count in widgets.collapse_keywords(boss.get('keywords', []))[:6]:
        kw = state.keyword_registry.get(kw_id)
        label = kw.name if kw else kw_id
        if count > 1:
            label = f"{count}x {label}"
        ks = fonts['small'].render(label, True,
                                   kw.color if kw else COLORS['text_dim'])
        if kx + ks.get_width() > panel.right - 12:
            break
        screen.blit(ks, (kx, ky))
        kx += ks.get_width() + 12

    if selected:
        hint = fonts['small'].render("CLICK TO CHALLENGE THE BOSS!", True,
                                     COLORS['gold'])
        screen.blit(hint, hint.get_rect(centerx=panel.centerx,
                                        y=panel.bottom - 26))
    return panel


def _draw_item_cards(screen, fonts, state, boss, ui, selected):
    """The boss's equipped items — attackable targets."""
    items = boss.get('items', [])
    destroyed = boss.get('destroyed_items', [])
    total_slots = len(items) + len(destroyed)
    if total_slots == 0:
        return

    label = fonts['small'].render(
        "Boss gear — destroy it to weaken the boss, or leave it as bonus loot:",
        True, COLORS['text_dim'])
    screen.blit(label, label.get_rect(centerx=SCREEN_WIDTH // 2, y=258))

    card_w, card_h, gap = 300, 150, 24
    n = max(total_slots, 1)
    row_w = n * card_w + (n - 1) * gap
    x = SCREEN_WIDTH // 2 - row_w // 2
    y = 284

    slot_i = 0
    for item_idx, item in enumerate(items):
        rect = pygame.Rect(x + slot_i * (card_w + gap), y, card_w, card_h)
        border = COLORS['gold'] if selected else COLORS['border']
        _pixel_box(screen, rect, border=border)

        paper_doll.draw_item_thumbnail(screen, item, rect.x + 10, rect.y + 10, 44)
        nm = item.name if len(item.name) <= 20 else item.name[:19] + ".."
        screen.blit(fonts['medium'].render(nm, True, COLORS['text']),
                    (rect.x + 62, rect.y + 10))
        screen.blit(fonts['small'].render(f"+{item.points} pts to boss", True,
                                          COLORS['gold']),
                    (rect.x + 62, rect.y + 40))

        kx = rect.x + 12
        for kw_id, count in widgets.collapse_keywords(item.keywords)[:3]:
            kw = state.keyword_registry.get(kw_id)
            lab = kw.name if kw else kw_id
            if count > 1:
                lab = f"{count}x {lab}"
            ks = fonts['small'].render(lab, True,
                                       kw.color if kw else COLORS['text_dim'])
            if kx + ks.get_width() > rect.right - 10:
                break
            screen.blit(ks, (kx, rect.y + 68))
            kx += ks.get_width() + 10

        defense = combat.boss_item_defense(item, boss.get('keywords', []))
        ds = fonts['medium'].render(f"DEF {defense}", True, COLORS['danger'])
        screen.blit(ds, (rect.x + 12, rect.y + 100))
        if selected:
            hit = fonts['small'].render("CLICK TO SMASH", True, COLORS['gold'])
            screen.blit(hit, (rect.right - hit.get_width() - 12, rect.y + 106))

        ui['item_cards'].append((item_idx, rect))
        slot_i += 1

    for item in destroyed:
        rect = pygame.Rect(x + slot_i * (card_w + gap), y, card_w, card_h)
        _pixel_box(screen, rect, border=COLORS['divider'],
                   fill=theme.mix(COLORS['bg'], COLORS['surface'], 0.25))
        nm = item.name if len(item.name) <= 20 else item.name[:19] + ".."
        screen.blit(fonts['medium'].render(nm, True, COLORS['text_dim']),
                    (rect.x + 12, rect.y + 12))
        d = fonts['medium'].render("DESTROYED", True, COLORS['danger'])
        screen.blit(d, d.get_rect(center=(rect.centerx, rect.centery + 16)))
        slot_i += 1


def _draw_history(screen, fonts, state, boss):
    """Compact log of resolved steps so far (left edge)."""
    log = boss.get('log', [])
    if not log:
        return
    screen.blit(fonts['small'].render("So far:", True, COLORS['text']), (16, 60))
    y = 84
    for step in log[-5:]:
        adv = step['adventurer']
        if step.get('killed_boss'):
            mark, mc = "KO!", COLORS['gold']
            what = f"slew the boss ({step['power']} vs {step['threshold']})"
        elif step.get('kind') == 'item' and step.get('destroyed'):
            mark, mc = "ok", COLORS['success']
            what = (f"smashed {step['item'].name} "
                    f"({step['boss_score_before']}->{step['boss_score_after']})")
        elif step.get('kind') == 'item':
            mark, mc = "fell", COLORS['danger']
            what = f"{step['power']} vs {step['threshold']} on {step['item'].name}"
        else:
            mark, mc = "fell", COLORS['danger']
            what = f"{step['power']} vs {step['threshold']} challenging"
        line = f"{mark} {adv.name}: {what}"
        screen.blit(fonts['tiny'].render(line[:46], True, mc), (16, y))
        y += 20


def draw_choice(screen, fonts, state, sprite_manager,
                dragging: bool, drag_adv_index: int):
    """Render the 'pick a hero, pick a target' boss screen."""
    boss = state.boss_square
    if not boss:
        return

    ui = {'hero_cards': [], 'item_cards': [], 'boss_rect': None}
    state._boss_ui = ui

    header = fonts['title'].render("BOSS FIGHT", True, COLORS['warning'])
    screen.blit(header, header.get_rect(centerx=SCREEN_WIDTH // 2, y=8))

    sel = state.boss_selected_hero
    sel_ok = 0 <= sel < len(state.party)

    ui['boss_rect'] = _draw_boss_panel(screen, fonts, state, sprite_manager,
                                       boss, sel_ok)
    _draw_item_cards(screen, fonts, state, boss, ui, sel_ok)
    _draw_history(screen, fonts, state, boss)

    if boss.get('items'):
        bonus = fonts['small'].render(
            f"Win with items intact: claim all {len(boss['items'])} as bonus loot!",
            True, COLORS['gold'])
        screen.blit(bonus, bonus.get_rect(centerx=SCREEN_WIDTH // 2, y=444))

    if sel_ok:
        prompt = f"{state.party[sel].name} is ready — click an item to smash, or the BOSS to challenge!"
        pcol = COLORS['gold']
    else:
        prompt = "Click a hero to choose who acts next:"
        pcol = COLORS['text']
    ps = fonts['medium'].render(prompt, True, pcol)
    screen.blit(ps, ps.get_rect(centerx=SCREEN_WIDTH // 2, y=470))

    # ---- Hero cards ----
    available = state.boss_available_heroes()
    boss_score = boss.get('score', 0)
    x = 30
    for adv in available:
        party_idx = state.party.index(adv)
        card_rect = pygame.Rect(x, 505, 280, 200)
        is_sel = (party_idx == sel)
        fill = (theme.mix(COLORS['bg'], COLORS['gold'], 0.10)
                if is_sel else None)
        _pixel_box(screen, card_rect,
                   border=COLORS['gold'] if is_sel else COLORS['accent'],
                   fill=fill)

        paper_doll.draw_adventurer_thumbnail(screen, adv, x + 108, 516, 64)
        screen.blit(fonts['small'].render(adv.name, True, COLORS['text']),
                    (x + 14, 556))

        ap = combat.adventurer_boss_power(
            adv, boss.get('keywords', []), boss['bonus'],
            state.keyword_registry,
        )
        screen.blit(fonts['medium'].render(f"Power: {ap['power']}", True,
                                           COLORS['success']),
                    (x + 14, 584))

        if ap['power'] >= boss_score:
            verdict = f"Can slay the boss ({boss_score})!"
            vcol = COLORS['gold']
        else:
            verdict = f"Below boss score ({boss_score})"
            vcol = COLORS['danger']
        screen.blit(fonts['small'].render(verdict, True, vcol), (x + 14, 620))

        detail = f"base {ap['base']} x{ap['mult']} / weak {ap['weakness']}"
        screen.blit(fonts['tiny'].render(detail, True, COLORS['text_dim']),
                    (x + 14, 648))
        if is_sel:
            tag = fonts['small'].render("SELECTED", True, COLORS['gold'])
            screen.blit(tag, (x + 14, 674))
        else:
            screen.blit(fonts['tiny'].render(
                f"Items: {len(adv.equipped_items)}/{adv.slots}", True,
                COLORS['text_dim']), (x + 14, 676))

        ui['hero_cards'].append((party_idx, card_rect))
        x += 300


def draw_result(screen, fonts, state):
    """Render the result of the most recent boss-fight action."""
    boss = state.boss_square
    if not boss or not boss.get('result'):
        return

    step = boss['result']
    outcome = boss.get('outcome')
    adv = step['adventurer']
    kind = step.get('kind', 'boss')

    # ---- Title ----
    if outcome == 'victory':
        title = fonts['title'].render("BOSS DEFEATED!", True, COLORS['gold'])
    elif kind == 'item' and step.get('destroyed'):
        item_name = step['item'].name.upper()
        title = fonts['title'].render(f"{item_name} DESTROYED!", True,
                                      COLORS['success'])
    elif outcome == 'defeat':
        title = fonts['title'].render("BOSS WINS!", True, COLORS['danger'])
    else:
        title = fonts['title'].render(f"{adv.name} HAS FALLEN!", True,
                                      COLORS['danger'])
    screen.blit(title, title.get_rect(centerx=SCREEN_WIDTH // 2, y=24))

    # ---- This action's breakdown ----
    panel = pygame.Rect(SCREEN_WIDTH // 2 - 360, 96, 720, 240)
    _pixel_box(screen, panel)
    hdr = fonts['medium'].render(f"{adv.name}'s strike", True, COLORS['accent'])
    screen.blit(hdr, (panel.x + 20, panel.y + 10))

    x = panel.x + 20
    y = panel.y + 48
    if kind == 'item':
        target_line = f"Target: {step['item'].name}  (defense {step['threshold']})"
    else:
        target_line = f"Target: THE BOSS  (score {step['threshold']})"
    screen.blit(fonts['medium'].render(target_line, True, COLORS['text']), (x, y))
    y += 34

    screen.blit(fonts['large'].render(
        f"Power {step['power']}  vs  {step['threshold']}", True,
        COLORS['success'] if step['survived'] else COLORS['danger']), (x, y))
    y += 44

    screen.blit(fonts['small'].render(
        f"base {step['adv_base']} x mult {step['adv_mult']} / "
        f"(1 + {step['adv_weakness']} weakness)", True, COLORS['text_dim']),
        (x, y))
    y += 30

    if kind == 'item':
        if step.get('destroyed'):
            item = step['item']
            kws = ", ".join(item.keywords) if item.keywords else "none"
            screen.blit(fonts['medium'].render(
                f"Boss loses +{item.points} pts and keywords: {kws}", True,
                COLORS['success']), (x, y))
            y += 30
            screen.blit(fonts['medium'].render(
                f"Boss score: {step['boss_score_before']} -> "
                f"{step['boss_score_after']}", True, COLORS['danger']), (x, y))
        else:
            screen.blit(fonts['medium'].render(
                "The blow glanced off the boss's gear — they were struck down.",
                True, COLORS['danger']), (x, y))
    else:
        if step['survived']:
            screen.blit(fonts['medium'].render(
                "Out-scored the boss — a killing blow!", True,
                COLORS['success']), (x, y))
        else:
            screen.blit(fonts['medium'].render(
                "The challenge failed — the battle is lost.", True,
                COLORS['danger']), (x, y))

    lost_items = step.get('lost_items')
    if lost_items:
        lost_text = "Dropped: " + ", ".join(i.name for i in lost_items)
        screen.blit(fonts['small'].render(lost_text[:80], True,
                                          COLORS['text_dim']),
                    (panel.x + 20, panel.bottom - 28))

    # ---- Outcome footer ----
    fy = 360
    if outcome == 'victory':
        bonus_items = boss.get('bonus_items')
        if bonus_items:
            screen.blit(fonts['large'].render(
                f"BONUS LOOT — {len(bonus_items)} intact item(s) claimed:",
                True, COLORS['gold']), (SCREEN_WIDTH // 2 - 360, fy))
            fy += 42
            for it in bonus_items[:3]:
                screen.blit(fonts['medium'].render(
                    f"* {it.name} (+{it.points}) [{it.rarity}]", True,
                    COLORS['gold']), (SCREEN_WIDTH // 2 - 340, fy))
                fy += 30
            fy += 6

        boss_reward = boss.get('boss_reward')
        if boss_reward and boss_reward.get('type') != 'none':
            screen.blit(fonts['medium'].render(
                f"BOSS REWARD: {boss_reward['desc']}", True,
                COLORS['success']), (SCREEN_WIDTH // 2 - 360, fy))
            fy += 32

        guaranteed_item = boss.get('guaranteed_item')
        if guaranteed_item:
            screen.blit(fonts['medium'].render(
                f"Guaranteed drop: {guaranteed_item.name} "
                f"(+{guaranteed_item.points}) [{guaranteed_item.rarity}]",
                True, COLORS['gold']), (SCREEN_WIDTH // 2 - 360, fy))
            fy += 32

        reward_item = boss.get('reward_item')
        if reward_item:
            screen.blit(fonts['medium'].render(
                f"Drop: {reward_item.name} (+{reward_item.points}) "
                f"[{reward_item.rarity}]",
                True, COLORS['text']), (SCREEN_WIDTH // 2 - 360, fy))
            fy += 32

        screen.blit(fonts['medium'].render(
            f"+{boss.get('reward_coins', 0)} coins", True, COLORS['gold']),
            (SCREEN_WIDTH // 2 - 360, fy))

        unlocked_msg = boss.get('unlocked_classes_msg')
        if unlocked_msg:
            screen.blit(fonts['medium'].render(unlocked_msg, True,
                                               COLORS['accent']),
                        (SCREEN_WIDTH // 2 - 360, fy + 32))
    elif outcome == 'defeat':
        screen.blit(fonts['medium'].render(
            "The boss resets to full strength (gear and all) for your next attempt.",
            True, COLORS['warning']), (SCREEN_WIDTH // 2 - 360, fy))
    else:
        remaining = len(state.boss_available_heroes())
        intact = len(boss.get('items', []))
        msg = (f"{remaining} hero(es) left.  Boss items intact: {intact}. "
               "Click 'Next Hero' to continue.")
        screen.blit(fonts['medium'].render(msg, True, COLORS['text']),
                    (SCREEN_WIDTH // 2 - 360, fy))
