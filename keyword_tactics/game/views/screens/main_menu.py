"""Main menu screen rendering."""

from ..widgets import Panel  # noqa: F401  (keeps Panel available if you extend)
from ...config import COLORS, SCREEN_WIDTH


def draw(screen, fonts, state):
    """Render the title screen with instructions."""
    title = fonts['title'].render("KEYWORD TACTICS", True, COLORS['accent'])
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 150))
    screen.blit(title, title_rect)

    subtitle = fonts['medium'].render("A Tactical Deck Builder", True, COLORS['text_dim'])
    sub_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 220))
    screen.blit(subtitle, sub_rect)

    instructions = [
        "Build a party of 4 adventurers",
        "Equip them with items containing keywords",
        "",
        " Seamless delve: rows of 4 monsters, escalating multipliers ",
        " Place ALL adventurers each row - multiplier boosts YOUR power ",
        " Win a square = keep that multiplier (highest stays!) ",
        " Swap items mid-delve with loot you find! ",
        " Risk the hidden Boss for epic rewards! ",
        "",
        " TAB: keyword reference    F11: fullscreen",
        "Clear all dungeons to win!",
    ]

    y = 555
    for line in instructions:
        color = COLORS['text_dim']
        if "ALL" in line:
            color = COLORS['warning']
        elif "highest" in line.lower():
            color = COLORS['gold']
        elif "swap" in line.lower() or "loot" in line.lower():
            color = COLORS['success']
        elif "TAB" in line or "F11" in line:
            color = COLORS['accent']
        elif "Boss" in line:
            color = COLORS['danger']
        elif "win" in line.lower() and "clear" in line.lower():
            color = COLORS['gold']

        text = fonts['small'].render(line, True, color)
        rect = text.get_rect(center=(SCREEN_WIDTH // 2, y))
        screen.blit(text, rect)
        y += 22
