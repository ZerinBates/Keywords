"""Boss phase rendering: choice and result screens.

The boss is fought as an interactive relay. On BOSS_CHOICE the player sees the
boss's CURRENT total score + 30% threshold and clicks one hero to send at it.
That single attack resolves on BOSS_RESULT, the boss state updates, and the
player returns here to pick the next hero — until the boss falls, or the last
hero (the finisher, no threshold) decides it.
"""

import pygame

from ..widgets import Panel
from ...config import COLORS, SCREEN_WIDTH
from ...controllers import combat


def _draw_boss_panel(screen, fonts, state, boss):
    """Boss summary panel: name, current keywords, current score + threshold."""
    monster = boss['monster']
    keywords = boss.get('keywords', monster.keywords)
    score = boss.get('score', combat.boss_total_score(monster.base_points, monster.keywords))
    total = boss.get('total', score)
    threshold = combat.boss_threshold(score)

    panel = Panel(SCREEN_WIDTH // 2 - 220, 78, 440, 232, "BOSS")
    panel.draw(screen, fonts['small'], fonts['large'])

    name_surf = fonts['large'].render(monster.name, True, COLORS['danger'])
    screen.blit(name_surf, name_surf.get_rect(centerx=SCREEN_WIDTH // 2, y=112))

    # Current keywords
    kw_x = SCREEN_WIDTH // 2 - 200
    kw_y = 156
    if keywords:
        for kw_id in keywords:
            kw = state.keyword_registry.get(kw_id)
            if kw:
                pygame.draw.rect(screen, kw.color, (kw_x, kw_y, 80, 24), border_radius=4)
                screen.blit(fonts['small'].render(kw.name[:10], True, COLORS['bg']),
                            (kw_x + 5, kw_y + 3))
                kw_x += 88
                if kw_x > SCREEN_WIDTH // 2 + 130:
                    kw_x = SCREEN_WIDTH // 2 - 200
                    kw_y += 28
    else:
        screen.blit(fonts['small'].render("(no keywords left)", True, COLORS['text_dim']),
                    (kw_x, kw_y))

    # Current score (with original for reference if reduced)
    if score != total:
        score_text = f"Score: {score}  (of {total})"
    else:
        score_text = f"Total Score: {score}"
    score_surf = fonts['large'].render(score_text, True, COLORS['danger'])
    screen.blit(score_surf, score_surf.get_rect(centerx=SCREEN_WIDTH // 2, y=224))

    thr_surf = fonts['medium'].render(
        f"Threshold to beat (30%): {threshold}", True, COLORS['warning'],
    )
    screen.blit(thr_surf, thr_surf.get_rect(centerx=SCREEN_WIDTH // 2, y=268))


def _draw_history(screen, fonts, state, boss):
    """Compact log of resolved steps so far."""
    log = boss.get('log', [])
    if not log:
        return
    screen.blit(fonts['small'].render("So far:", True, COLORS['text']), (40, 318))
    y = 346
    for i, step in enumerate(log[-4:]):
        adv = step['adventurer']
        if step['killed_boss']:
            mark, mc = "KO!", COLORS['gold']
        elif step['survived']:
            mark, mc = "ok ", COLORS['success']
        else:
            mark, mc = "fell", COLORS['danger']
        bits = [f"{mark} {adv.name}: power {step['power']}"]
        if step['damage'] and not step['is_final']:
            bits.append(f"-{step['damage']}")
        if step['removed_keyword']:
            bits.append(f"strip {step['removed_keyword']}")
        bits.append(f"({step['boss_score_before']}->{step['boss_score_after']})")
        screen.blit(fonts['small'].render("  ".join(bits), True, mc), (52, y))
        y += 26


def draw_choice(screen, fonts, state, sprite_manager,
                dragging: bool, drag_adv_index: int):
    """Render the 'send a hero' screen for the interactive boss relay."""
    header = fonts['title'].render("BOSS FIGHT", True, COLORS['warning'])
    screen.blit(header, header.get_rect(centerx=SCREEN_WIDTH // 2, y=14))

    boss = state.boss_square
    if not boss:
        return

    _draw_boss_panel(screen, fonts, state, boss)
    _draw_history(screen, fonts, state, boss)

    available = state.boss_available_heroes()
    is_relay_finisher = (len(available) == 1)

    if is_relay_finisher:
        prompt = "FINISHER — no threshold. Click them to deliver the final blow:"
        pcol = COLORS['gold']
    else:
        prompt = "Click a hero to send them at the boss next:"
        pcol = COLORS['text']
    screen.blit(fonts['medium'].render(prompt, True, pcol), (20, 470))

    bonus = boss['bonus']
    threshold = combat.boss_threshold(boss.get('score', 0))

    x = 30
    for adv in available:
        card_rect = pygame.Rect(x, 505, 280, 200)
        pygame.draw.rect(screen, COLORS['panel_light'], card_rect, border_radius=8)
        border = COLORS['gold'] if is_relay_finisher else COLORS['accent']
        pygame.draw.rect(screen, border, card_rect, 2, border_radius=8)

        # Click affordance bars
        for bar_y in range(512, 526, 5):
            pygame.draw.line(screen, COLORS['muted'],
                             (x + 120, bar_y), (x + 160, bar_y), 1)

        char_sprite = sprite_manager.get_character_sprite(adv.id, (48, 48))
        if char_sprite:
            screen.blit(char_sprite, (x + 116, 528))

        screen.blit(fonts['small'].render(adv.name, True, COLORS['text']), (x + 14, 566))

        ap = combat.adventurer_boss_power(
            adv, boss.get('keywords', []), bonus, state.keyword_registry,
        )
        screen.blit(fonts['medium'].render(f"Power: {ap['power']}", True, COLORS['success']),
                    (x + 14, 592))

        # Pass/risk preview vs current threshold
        if is_relay_finisher:
            verdict = "Finisher (no threshold)"
            vcol = COLORS['gold']
        elif ap['power'] >= threshold:
            verdict = f"Beats threshold ({threshold})"
            vcol = COLORS['success']
        else:
            verdict = f"BELOW threshold ({threshold})!"
            vcol = COLORS['danger']
        screen.blit(fonts['small'].render(verdict, True, vcol), (x + 14, 624))

        detail = f"base {ap['base']} x{ap['mult']} / weak {ap['weakness']}"
        screen.blit(fonts['small'].render(detail, True, COLORS['text_dim']), (x + 14, 650))
        screen.blit(fonts['small'].render(
            f"Items: {len(adv.equipped_items)}/{adv.slots}", True, COLORS['text_dim']),
            (x + 14, 676))

        x += 300


def draw_result(screen, fonts, state):
    """Render the result of the most recent single boss attack."""
    boss = state.boss_square
    if not boss or not boss.get('result'):
        return

    step = boss['result']
    outcome = boss.get('outcome')
    adv = step['adventurer']
    monster = boss['monster']

    # ---- Title ----
    if outcome == 'victory':
        title = fonts['title'].render("BOSS DEFEATED!", True, COLORS['gold'])
    elif outcome == 'defeat':
        title = fonts['title'].render("BOSS WINS!", True, COLORS['danger'])
    elif step['survived']:
        title = fonts['title'].render(f"{adv.name} HOLDS!", True, COLORS['success'])
    else:
        title = fonts['title'].render(f"{adv.name} HAS FALLEN!", True, COLORS['danger'])
    screen.blit(title, title.get_rect(centerx=SCREEN_WIDTH // 2, y=24))

    # ---- This attack's breakdown ----
    panel = Panel(SCREEN_WIDTH // 2 - 360, 100, 720, 250, f"{adv.name}'s attack")
    panel.draw(screen, fonts['small'], fonts['large'])

    x = SCREEN_WIDTH // 2 - 340
    y = 150
    if step['is_final']:
        thr_line = "Finisher — no threshold"
    else:
        thr_line = f"Threshold: {step['threshold']}"
    screen.blit(fonts['large'].render(f"Power {step['power']}   vs   {thr_line}",
                                      True, COLORS['accent']), (x, y))
    y += 50

    screen.blit(fonts['small'].render(
        f"base {step['adv_base']} x mult {step['adv_mult']} / "
        f"(1 + {step['adv_weakness']} weakness)", True, COLORS['text_dim']), (x, y))
    y += 34

    if step['survived']:
        if step['is_final']:
            line = "Out-scored the boss — finishing blow!"
        else:
            line = f"Beat the threshold: dealt {step['damage']} damage."
        screen.blit(fonts['medium'].render(line, True, COLORS['success']), (x, y))
    else:
        if step['is_final']:
            line = "The finisher fell short — the battle is lost."
        else:
            line = "Missed the threshold and was slain."
        screen.blit(fonts['medium'].render(line, True, COLORS['danger']), (x, y))
    y += 34

    if step['removed_keyword']:
        screen.blit(fonts['medium'].render(
            f"Stripped the boss's '{step['removed_keyword']}' keyword!",
            True, COLORS['accent']), (x, y))
        y += 34

    score_line = (
        f"Boss score: {step['boss_score_before']}  ->  {step['boss_score_after']}"
    )
    screen.blit(fonts['medium'].render(score_line, True, COLORS['danger']), (x, y))
    y += 32
    kw_after = step.get('boss_keywords_after', [])
    kw_text = ", ".join(kw_after) if kw_after else "(none left)"
    screen.blit(fonts['small'].render(f"Boss keywords now: {kw_text}",
                                      True, COLORS['text_dim']), (x, y))

    lost_items = step.get('lost_items')
    if lost_items:
        lost_text = "Dropped: " + ", ".join(i.name for i in lost_items)
        screen.blit(fonts['small'].render(lost_text[:70], True, COLORS['text_dim']),
                    (x, y + 26))

    # ---- Outcome footer ----
    fy = 380
    if outcome == 'victory':
        boss_reward = boss.get('boss_reward')
        if boss_reward and boss_reward.get('type') != 'none':
            screen.blit(fonts['large'].render("BOSS REWARD:", True, COLORS['gold']),
                        (SCREEN_WIDTH // 2 - 360, fy))
            screen.blit(fonts['medium'].render(boss_reward['desc'], True, COLORS['success']),
                        (SCREEN_WIDTH // 2 - 360, fy + 42))
            fy += 80

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
                f"Drop: {reward_item.name} (+{reward_item.points}) [{reward_item.rarity}]",
                True, COLORS['text']), (SCREEN_WIDTH // 2 - 360, fy))
            fy += 32

        screen.blit(fonts['medium'].render(
            f"+{boss.get('reward_coins', 0)} coins", True, COLORS['gold']),
            (SCREEN_WIDTH // 2 - 360, fy))

        unlocked_msg = boss.get('unlocked_classes_msg')
        if unlocked_msg:
            screen.blit(fonts['medium'].render(unlocked_msg, True, COLORS['accent']),
                        (SCREEN_WIDTH // 2 - 360, fy + 32))
    elif outcome == 'defeat':
        screen.blit(fonts['medium'].render(
            "The boss resets to full strength for your next attempt.",
            True, COLORS['warning']), (SCREEN_WIDTH // 2 - 360, fy))
    else:
        # Relay continues.
        remaining = len(state.boss_available_heroes())
        msg = (f"{remaining} hero(es) left to send. "
               "Click 'Next Hero' to choose who attacks next.")
        screen.blit(fonts['medium'].render(msg, True, COLORS['text']),
                    (SCREEN_WIDTH // 2 - 360, fy))
