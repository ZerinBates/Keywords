"""Shop screen rendering."""

from ..widgets import Panel
from ...config import COLORS


def draw(screen, fonts, state):
    """Render the between-rounds shop screen."""
    # Header
    header = fonts['large'].render("SHOP", True, COLORS['accent'])
    screen.blit(header, (20, 20))

    coins = fonts['medium'].render(f"Coins: {state.coins}", True, COLORS['gold'])
    screen.blit(coins, (20, 60))

    cleared = len(state.completed_decks)
    total = len(state.active_decks)
    cleared_text = fonts['medium'].render(
        f"Dungeons Cleared: {cleared}/{total}", True, COLORS['success'],
    )
    screen.blit(cleared_text, (200, 60))

    # Progress-based drop info
    total_kills = state.get_total_monsters_defeated()
    scrap_w, common_w, uncommon_w, rare_w = state.get_shop_rarity_weights()
    total_w = scrap_w + common_w + uncommon_w + rare_w
    rare_pct = int(rare_w / total_w * 100)
    uncommon_pct = int(uncommon_w / total_w * 100)

    progress_text = (
        f"Monsters Slain: {total_kills} | Shop Rates: "
        f"{uncommon_pct}% uncommon, {rare_pct}% rare"
    )
    screen.blit(fonts['small'].render(progress_text, True, COLORS['text_dim']),
                (500, 65))

    # ---- Items for sale ----
    items_panel = Panel(20, 100, 600, 350, "Items for Sale (click to buy)")
    items_panel.draw(screen, fonts['small'], fonts['medium'])

    rarity_color_map = {
        'scrap':    (120, 120, 120),
        'common':   COLORS['text_dim'],
        'uncommon': COLORS['success'],
        'rare':     COLORS['accent'],
    }

    y = 140
    for item in state.shop_items:
        price = state.get_item_price(item)
        color = COLORS['text'] if state.coins >= price else COLORS['text_dim']

        text = (
            f"{item.name} (+{item.points}) [{', '.join(item.keywords)}] - "
            f"{price} coins"
        )
        screen.blit(fonts['small'].render(text, True, color), (40, y))

        rarity_color = rarity_color_map.get(item.rarity, COLORS['text'])
        rarity_surf = fonts['small'].render(f"[{item.rarity}]", True, rarity_color)
        screen.blit(rarity_surf, (550, y))
        y += 45

    # ---- Adventurers for sale ----
    adv_panel = Panel(650, 100, 600, 350, "Adventurers for Hire (click to buy)")
    adv_panel.draw(screen, fonts['small'], fonts['medium'])

    y = 140
    for adv in state.shop_adventurers:
        price = state.get_adventurer_price(adv)
        color = COLORS['text'] if state.coins >= price else COLORS['text_dim']

        text = f"{adv.name} [{adv.slots} slots] - {price} coins"
        screen.blit(fonts['medium'].render(text, True, color), (670, y))

        ability_text = f"{adv.ability_name}: {adv.ability_desc}"
        screen.blit(fonts['small'].render(ability_text, True, COLORS['text_dim']),
                    (680, y + 30))
        y += 80

    # ---- Roster summary ----
    summary_panel = Panel(20, 470, 1240, 220, "Your Collection")
    summary_panel.draw(screen, fonts['small'], fonts['medium'])

    roster_text = (
        f"Adventurers: {len(state.roster)} | "
        f"Items in inventory: {len(state.inventory)}"
    )
    screen.blit(fonts['medium'].render(roster_text, True, COLORS['text']), (40, 510))

    y = 550
    for adv in state.roster[:5]:
        text = f"* {adv.name} [{len(adv.equipped_items)}/{adv.slots}]"
        screen.blit(fonts['small'].render(text, True, COLORS['text_dim']), (40, y))
        y += 25
