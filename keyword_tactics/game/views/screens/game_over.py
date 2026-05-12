"""Game over (victory or loss) screen."""

from ...config import COLORS, SCREEN_WIDTH


def draw(screen, fonts, state):
    """Render the game-over screen, victory or defeat."""
    all_cleared = all(deck.is_completed for deck in state.active_decks.values())

    if all_cleared:
        title = fonts['title'].render("VICTORY!", True, COLORS['success'])
        subtitle = fonts['medium'].render(
            "You have conquered all dungeons!", True, COLORS['gold'],
        )
    else:
        title = fonts['title'].render("GAME OVER", True, COLORS['danger'])
        subtitle = fonts['medium'].render(
            "All your adventurers have fallen...", True, COLORS['text_dim'],
        )

    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 200))
    screen.blit(title, title_rect)

    sub_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 280))
    screen.blit(subtitle, sub_rect)

    # Final stats
    cleared = len(state.completed_decks)
    total = len(state.active_decks)
    stats = fonts['medium'].render(
        f"Dungeons Cleared: {cleared}/{total}", True, COLORS['text'],
    )
    stats_rect = stats.get_rect(center=(SCREEN_WIDTH // 2, 340))
    screen.blit(stats, stats_rect)
