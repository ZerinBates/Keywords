"""Boss phase rendering: choice and result screens."""

import pygame

from ..widgets import Panel
from ...config import COLORS, SCREEN_WIDTH


def draw_choice(screen, fonts, state, sprite_manager,
                dragging: bool, drag_adv_index: int):
    """Render the boss-challenge choice screen with party drag-target."""
    header = fonts['title'].render("CHALLENGE THE BOSS?", True, COLORS['warning'])
    header_rect = header.get_rect(centerx=SCREEN_WIDTH // 2, y=20)
    screen.blit(header, header_rect)

    boss = state.boss_square
    if boss:
        monster = boss['monster']
        boss_mult = boss['multiplier']

        # Boss panel
        boss_panel = Panel(SCREEN_WIDTH // 2 - 200, 80, 400, 250, f"{boss_mult}x BOSS")
        boss_panel.draw(screen, fonts['small'], fonts['large'])

        # Monster name
        name_surf = fonts['large'].render(monster.name, True, COLORS['danger'])
        name_rect = name_surf.get_rect(centerx=SCREEN_WIDTH // 2, y=120)
        screen.blit(name_surf, name_rect)

        # Keywords (visible)
        kw_x = SCREEN_WIDTH // 2 - 180
        kw_y = 170
        for kw_id in monster.keywords:
            kw = state.keyword_registry.get(kw_id)
            if kw:
                pygame.draw.rect(screen, kw.color, (kw_x, kw_y, 80, 25), border_radius=4)
                kw_text = fonts['small'].render(kw.name[:10], True, COLORS['bg'])
                screen.blit(kw_text, (kw_x + 5, kw_y + 3))
                kw_x += 88
                if kw_x > SCREEN_WIDTH // 2 + 160:
                    kw_x = SCREEN_WIDTH // 2 - 180
                    kw_y += 30

        # Hidden score
        hidden = fonts['large'].render(
            f"Score: ??? x {boss_mult} = ???", True, COLORS['danger'],
        )
        hidden_rect = hidden.get_rect(centerx=SCREEN_WIDTH // 2, y=230)
        screen.blit(hidden, hidden_rect)

        # Bonus
        bonus = boss['bonus']
        if bonus['type'] != 'none':
            if bonus['type'] == 'keyword_buff':
                bonus_text = f"Square Bonus: +{bonus['keyword']}"
            else:
                bonus_text = f"Square Bonus: Resist {bonus['keyword']}"
            bonus_surf = fonts['medium'].render(bonus_text, True, COLORS['accent'])
            bonus_rect = bonus_surf.get_rect(centerx=SCREEN_WIDTH // 2, y=280)
            screen.blit(bonus_surf, bonus_rect)

        # Risk/reward info
        info_lines = [
            "Your adventurer keeps their earned multiplier from the last square they beat!",
            "Boss rewards: 1/8 bonus slot, 1/8 keyword steal, else stat boost",
            "If you lose, your adventurer dies!",
        ]
        y = 340
        for line in info_lines:
            color = COLORS['warning'] if "lose" in line.lower() else COLORS['text_dim']
            info_surf = fonts['small'].render(line, True, color)
            info_rect = info_surf.get_rect(centerx=SCREEN_WIDTH // 2, y=y)
            screen.blit(info_surf, info_rect)
            y += 25

    # Party - drag onto boss
    party_label = fonts['medium'].render(
        "DRAG ADVENTURER ONTO BOSS (uses earned multiplier):",
        True, COLORS['text'],
    )
    screen.blit(party_label, (20, 440))

    x = 30
    for i, adv in enumerate(state.party):
        if adv.is_dead:
            continue

        is_selected = (i == state.boss_adventurer_index)
        is_being_dragged = dragging and drag_adv_index == i

        if is_being_dragged:
            color = (40, 45, 55)
        elif is_selected:
            color = COLORS['accent']
        else:
            color = COLORS['panel_light']

        card_rect = pygame.Rect(x, 480, 280, 200)
        pygame.draw.rect(screen, color, card_rect, border_radius=8)

        if is_selected:
            border = COLORS['gold']
        elif not is_being_dragged:
            border = COLORS['accent']
        else:
            border = COLORS['text_dim']
        pygame.draw.rect(screen, border, card_rect, 2, border_radius=8)

        # Grab handle bars
        if not is_selected and not is_being_dragged:
            for bar_y in range(486, 500, 5):
                pygame.draw.line(screen, (100, 130, 170),
                                 (x + 55, bar_y), (x + 95, bar_y), 1)

        # Character sprite
        char_sprite = sprite_manager.get_character_sprite(adv.id, (48, 48))
        if char_sprite:
            screen.blit(char_sprite, (x + 50, 488))
            name_y = 540
        else:
            name_y = 490

        screen.blit(fonts['small'].render(adv.name, True, COLORS['text']),
                    (x + 8, name_y))

        # Earned multiplier
        earned_m = state.get_adventurer_multiplier(adv)
        em_color = COLORS['gold'] if earned_m > 1 else COLORS['text_dim']
        screen.blit(fonts['small'].render(f"Earned: {earned_m}x", True, em_color),
                    (x + 8, name_y + 22))

        # Boosted power
        base = adv.get_base_points()
        boosted = base * earned_m
        mult = adv.get_multiplier()
        pwr_text = f"Pwr: {base}x{earned_m}x{mult}={boosted * mult}"
        screen.blit(fonts['small'].render(pwr_text, True, COLORS['success']),
                    (x + 8, name_y + 42))

        equip_text = f"Items: {len(adv.equipped_items)}/{adv.slots}"
        screen.blit(fonts['small'].render(equip_text, True, COLORS['text_dim']),
                    (x + 8, name_y + 62))

        x += 300


def draw_result(screen, fonts, state):
    """Render the boss-fight result screen."""
    boss = state.boss_square
    if not boss or not boss['result']:
        return

    result = boss['result']
    victory = result['victory']

    # Title
    if victory:
        title = fonts['title'].render("BOSS DEFEATED!", True, COLORS['gold'])
    else:
        title = fonts['title'].render("BOSS WINS!", True, COLORS['danger'])
    title_rect = title.get_rect(centerx=SCREEN_WIDTH // 2, y=30)
    screen.blit(title, title_rect)

    adv = result['adventurer']
    monster = result['monster']

    # ---- Adventurer side ----
    adv_panel = Panel(50, 100, 500, 300, adv.name)
    adv_panel.draw(screen, fonts['small'], fonts['large'])

    y = 140
    calc_text = (
        f"Base: {result['adv_base']} x Square: {result['adv_square_mult']}x = "
        f"{result['adv_boosted_base']}"
    )
    screen.blit(fonts['small'].render(calc_text, True, COLORS['text']), (70, y))
    y += 25
    calc_text2 = (
        f"x Keyword Mult: {result['adv_mult']} / "
        f"(1 + {result['adv_weakness']} weakness)"
    )
    screen.blit(fonts['small'].render(calc_text2, True, COLORS['text']), (70, y))
    y += 30

    power_text = f"Final Power: {result['adv_power']}"
    screen.blit(fonts['large'].render(power_text, True, COLORS['accent']), (70, y))
    y += 50

    screen.blit(fonts['medium'].render("Equipment:", True, COLORS['text']), (70, y))
    y += 25
    for item in adv.equipped_items:
        screen.blit(
            fonts['small'].render(f"* {item.name} (+{item.points})", True, COLORS['text_dim']),
            (80, y),
        )
        y += 22

    # ---- Monster side ----
    mon_panel = Panel(630, 100, 500, 300, f"{monster.name} ({result['multiplier']}x BOSS)")
    mon_panel.draw(screen, fonts['small'], fonts['large'])

    y = 140
    calc_text = (
        f"Base: {result['monster_base']} x {result['multiplier']} = "
        f"{result['monster_multiplied_base']}"
    )
    screen.blit(fonts['small'].render(calc_text, True, COLORS['text']), (650, y))
    y += 25
    calc_text2 = (
        f"x Keyword Mult: {result['monster_mult']} / "
        f"(1 + {result['monster_weakness']} weakness)"
    )
    screen.blit(fonts['small'].render(calc_text2, True, COLORS['text']), (650, y))
    y += 30

    power_text = f"Final Power: {result['monster_power']}"
    screen.blit(fonts['large'].render(power_text, True, COLORS['danger']), (650, y))
    y += 50

    screen.blit(fonts['medium'].render("Keywords:", True, COLORS['text']), (650, y))
    y += 25
    for kw_id in monster.keywords:
        kw = state.keyword_registry.get(kw_id)
        if kw:
            screen.blit(
                fonts['small'].render(f"* {kw.name}", True, COLORS['text_dim']),
                (660, y),
            )
            y += 22

    # ---- Result details ----
    y = 430
    if victory:
        boss_reward = result.get('boss_reward')
        if boss_reward:
            reward_color = (
                COLORS['gold']
                if boss_reward['type'] == 'bonus_slot'
                else COLORS['success']
            )
            screen.blit(fonts['large'].render("BOSS REWARD:", True, COLORS['gold']),
                        (50, y))
            screen.blit(
                fonts['medium'].render(boss_reward['desc'], True, reward_color),
                (50, y + 45),
            )

        reward_item = result.get('reward_item')
        if reward_item:
            drop_text = (
                f"Drop: {reward_item.name} (+{reward_item.points}) "
                f"[{reward_item.rarity}]"
            )
            screen.blit(fonts['medium'].render(drop_text, True, COLORS['text']),
                        (50, y + 80))

        coins_text = f"+{result.get('reward_coins', 0)} coins"
        screen.blit(fonts['medium'].render(coins_text, True, COLORS['gold']),
                    (50, y + 110))
    else:
        screen.blit(
            fonts['large'].render(f"{adv.name} has fallen!", True, COLORS['danger']),
            (50, y),
        )
        lost_items = result.get('lost_items', [])
        if lost_items:
            lost_text = "Lost items: " + ", ".join(i.name for i in lost_items)
            screen.blit(fonts['small'].render(lost_text, True, COLORS['text_dim']),
                        (50, y + 45))
