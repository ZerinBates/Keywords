"""Main menu screen rendering."""

from ..widgets import Panel  # noqa: F401  (keeps Panel available if you extend)
from ...config import COLORS, SCREEN_WIDTH


def draw(screen, fonts, state):
    """Render the title screen with instructions."""
    title = fonts['title'].render("KEYWORD TACTICS", True, COLORS['accent'])
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 110))
    screen.blit(title, title_rect)

    subtitle = fonts['medium'].render("A Tactical Deck Builder", True, COLORS['text_dim'])
    sub_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 175))
    screen.blit(subtitle, sub_rect)

    # Status line: debug banner + save indicator
    status_parts = []
    if getattr(state, 'debug_unlock_all', False):
        status_parts.append(("DEBUG: ALL UNLOCKED", COLORS['warning']))
    if state.has_resumable_run():
        status_parts.append(("Saved run available", COLORS['success']))

    sy = 215
    for text_str, color in status_parts:
        surf = fonts['small'].render(text_str, True, color)
        rect = surf.get_rect(center=(SCREEN_WIDTH // 2, sy))
        screen.blit(surf, rect)
        sy += 20

    # Unlock progress (small, unobtrusive)
    try:
        total_chars = len(state.adventurer_registry.all_ids())
        total_items = len(state.item_registry.all_ids())
        unlocked_c = len(state.unlocked_characters)
        unlocked_i = len(state.unlocked_items)
        if not getattr(state, 'debug_unlock_all', False):
            progress = f"Classes {unlocked_c}/{total_chars}   Items {unlocked_i}/{total_items}"
            surf = fonts['small'].render(progress, True, COLORS['text_dim'])
            rect = surf.get_rect(center=(SCREEN_WIDTH // 2, sy))
            screen.blit(surf, rect)
    except Exception:
        pass

    instructions = [
        " Seamless delve: rows of 4 monsters, escalating multipliers ",
        " Place ALL adventurers each row - multiplier boosts YOUR power ",
        " Swap items mid-delve with loot you find! ",
        " Risk the hidden Boss for epic rewards! ",
        " Defeat bosses to unlock new classes! ",
        " Clear decks fully to unlock more items! ",
        "",
        " TAB: keyword reference    F11: fullscreen",
        "Clear all dungeons to win!",
    ]

    y = 590
    for line in instructions:
        color = COLORS['text_dim']
        if "ALL" in line:
            color = COLORS['warning']
        elif "swap" in line.lower() or "loot" in line.lower():
            color = COLORS['success']
        elif "TAB" in line or "F11" in line:
            color = COLORS['accent']
        elif "Boss" in line and "unlock" not in line.lower():
            color = COLORS['danger']
        elif "unlock" in line.lower():
            color = COLORS['gold']
        elif "win" in line.lower() and "clear" in line.lower():
            color = COLORS['gold']

        text = fonts['small'].render(line, True, color)
        rect = text.get_rect(center=(SCREEN_WIDTH // 2, y))
        screen.blit(text, rect)
        y += 22