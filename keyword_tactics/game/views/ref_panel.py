"""Keyword reference panel - the always-available TAB overlay."""

import pygame

from ..config import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT


def draw_ref_panel(screen, fonts, state):
    """Draw the keyword reference panel overlay (TAB to toggle)."""
    # Semi-transparent overlay
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 100))
    screen.blit(overlay, (0, 0))

    # Main panel
    panel_rect = pygame.Rect(20, 60, 500, 600)
    pygame.draw.rect(screen, COLORS['panel'], panel_rect, border_radius=10)
    pygame.draw.rect(screen, COLORS['accent'], panel_rect, 3, border_radius=10)

    # Title
    title = fonts['large'].render("Keyword Reference", True, COLORS['accent'])
    screen.blit(title, (30, 70))

    # Search box
    search_rect = pygame.Rect(30, 110, 200, 30)
    pygame.draw.rect(screen, COLORS['panel_light'], search_rect, border_radius=5)
    pygame.draw.rect(screen, COLORS['text_dim'], search_rect, 2, border_radius=5)

    search_text = state.ref_search_text or "Type to search..."
    search_color = COLORS['text'] if state.ref_search_text else COLORS['text_dim']
    screen.blit(fonts['small'].render(search_text, True, search_color), (35, 117))

    # Instructions
    inst = fonts['small'].render(
        "TAB to toggle | ESC to close | Click to select", True, COLORS['text_dim'],
    )
    screen.blit(inst, (240, 117))

    # Keyword list
    screen.blit(fonts['medium'].render("Keywords:", True, COLORS['text']), (30, 150))

    filtered_keywords = state.get_filtered_keywords(state.ref_search_text)
    y = 180
    visible_start = state.ref_scroll
    visible_end = min(visible_start + 12, len(filtered_keywords))

    for i in range(visible_start, visible_end):
        kw = filtered_keywords[i]
        is_selected = kw['id'] == state.ref_selected_keyword

        if is_selected:
            sel_rect = pygame.Rect(28, y - 2, 175, 23)
            pygame.draw.rect(screen, COLORS['accent'], sel_rect, border_radius=3)

        pygame.draw.rect(screen, kw['color'], (30, y, 15, 18), border_radius=2)

        name_color = COLORS['bg'] if is_selected else COLORS['text']
        screen.blit(fonts['small'].render(kw['name'], True, name_color), (50, y))
        y += 25

    # Scroll indicator
    if len(filtered_keywords) > 12:
        scroll_text = f"^v {visible_start + 1}-{visible_end}/{len(filtered_keywords)}"
        screen.blit(fonts['small'].render(scroll_text, True, COLORS['text_dim']), (30, 480))

    # Adventurer selection
    screen.blit(fonts['medium'].render("Adventurers:", True, COLORS['text']), (220, 150))

    adventurers = state.party if state.party else state.roster[:6]
    y = 180
    for adv in adventurers:
        is_selected = adv == state.ref_selected_adventurer
        if is_selected:
            sel_rect = pygame.Rect(218, y - 2, 185, 26)
            pygame.draw.rect(screen, COLORS['success'], sel_rect, border_radius=3)
        name_color = COLORS['bg'] if is_selected else COLORS['text']
        equip_count = len(adv.equipped_items)
        adv_text = f"{adv.name} [{equip_count}/{adv.slots}]"
        screen.blit(fonts['small'].render(adv_text, True, name_color), (220, y))
        y += 30

    # Deck selection
    screen.blit(fonts['medium'].render("Decks:", True, COLORS['text']), (220, 360))
    y = 390
    for deck_id, deck in state.active_decks.items():
        is_selected = deck_id == state.ref_selected_deck_id
        if is_selected:
            sel_rect = pygame.Rect(218, y - 2, 185, 23)
            pygame.draw.rect(screen, COLORS['warning'], sel_rect, border_radius=3)
        if is_selected:
            name_color = COLORS['bg']
        else:
            name_color = COLORS['text_dim'] if deck.is_completed else COLORS['text']
        status = "WIN" if deck.is_completed else f"({deck.get_remaining_count()})"
        deck_text = f"{deck.name} {status}"
        screen.blit(fonts['small'].render(deck_text, True, name_color), (220, y))
        y += 25

    # Clear button
    clear_rect = pygame.Rect(30, 510, 100, 25)
    pygame.draw.rect(screen, COLORS['panel_light'], clear_rect, border_radius=5)
    screen.blit(fonts['small'].render("Clear All", True, COLORS['text']), (45, 513))

    # Analysis section
    _draw_ref_analysis(screen, fonts, state)


def _draw_ref_analysis(screen, fonts, state):
    """Bottom analysis section: shows selected keyword/adventurer/deck details."""
    y_start = 540
    x_start = 30

    # Selected keyword info
    if state.ref_selected_keyword:
        kw = state.keyword_registry.get(state.ref_selected_keyword)
        if kw:
            pygame.draw.rect(screen, kw.color, (x_start, y_start, 20, 20), border_radius=3)
            screen.blit(
                fonts['medium'].render(f"{kw.name}:", True, COLORS['accent']),
                (x_start + 25, y_start - 2),
            )

            if kw.weak_against:
                weak_text = "Weak vs: " + ", ".join(kw.weak_against)
                screen.blit(
                    fonts['small'].render(weak_text, True, COLORS['danger']),
                    (x_start, y_start + 25),
                )

            strong_against = []
            for other_id in state.keyword_registry.all_ids():
                other_kw = state.keyword_registry.get(other_id)
                if other_kw and state.ref_selected_keyword in other_kw.weak_against:
                    strong_against.append(other_id)
            if strong_against:
                strong_text = "Strong vs: " + ", ".join(strong_against)
                screen.blit(
                    fonts['small'].render(strong_text, True, COLORS['success']),
                    (x_start, y_start + 45),
                )

    # Selected adventurer info
    if state.ref_selected_adventurer:
        adv = state.ref_selected_adventurer
        analysis = state.get_adventurer_keywords_analysis(adv)

        x_offset = 250
        screen.blit(
            fonts['small'].render(f"{adv.name}'s Keywords:", True, COLORS['success']),
            (x_offset, y_start),
        )

        if analysis['keywords']:
            kw_list = ", ".join(f"{k}({v})" for k, v in analysis['keywords'].items())
            if len(kw_list) > 35:
                kw_list = kw_list[:35] + "..."
            screen.blit(
                fonts['small'].render(kw_list, True, COLORS['text_dim']),
                (x_offset, y_start + 20),
            )

        if analysis['weak_to']:
            weak_list = ", ".join(f"{k}({v})" for k, v in list(analysis['weak_to'].items())[:4])
            screen.blit(
                fonts['small'].render(f"Weak to: {weak_list}", True, COLORS['danger']),
                (x_offset, y_start + 40),
            )

    # Comparison: keyword vs adventurer
    if state.ref_selected_keyword and state.ref_selected_adventurer:
        comparison = state.compare_keyword_vs_adventurer(
            state.ref_selected_keyword,
            state.ref_selected_adventurer,
        )
        kw = state.keyword_registry.get(state.ref_selected_keyword)
        adv = state.ref_selected_adventurer

        comp_y = y_start + 65
        screen.blit(
            fonts['small'].render(f" {kw.name} vs {adv.name}:", True, COLORS['warning']),
            (x_start, comp_y),
        )

        if comparison['weakness_count'] > 0:
            weak_result = f"  {adv.name} takes {comparison['weakness_count']} weakness penalty"
            screen.blit(
                fonts['small'].render(weak_result, True, COLORS['danger']),
                (x_start, comp_y + 18),
            )

        if comparison['strength_count'] > 0:
            strong_result = (
                f"  Enemy with {kw.name} takes {comparison['strength_count']} weakness penalty"
            )
            screen.blit(
                fonts['small'].render(strong_result, True, COLORS['success']),
                (x_start, comp_y + 36),
            )

        if comparison['weakness_count'] == 0 and comparison['strength_count'] == 0:
            screen.blit(
                fonts['small'].render("  No weakness interactions", True, COLORS['text_dim']),
                (x_start, comp_y + 18),
            )

    # Deck analysis
    if state.ref_selected_deck_id:
        deck = state.active_decks.get(state.ref_selected_deck_id)
        if deck and not deck.is_completed:
            analysis = state.get_deck_keywords_analysis(state.ref_selected_deck_id)
            if analysis['effective_against']:
                eff_y = y_start + 85
                eff_title = f"Keywords effective vs {deck.name}:"
                screen.blit(
                    fonts['small'].render(eff_title, True, COLORS['warning']),
                    (x_start, eff_y),
                )
                sorted_eff = sorted(
                    analysis['effective_against'].items(), key=lambda x: -x[1],
                )[:5]
                eff_list = ", ".join(f"{k}({v})" for k, v in sorted_eff)
                screen.blit(
                    fonts['small'].render(eff_list, True, COLORS['success']),
                    (x_start, eff_y + 18),
                )
