"""Dungeon deck model - a persistent ordered collection of monsters."""

import random
from typing import Dict, Iterable, List, Optional

from .item import Item, ItemRegistry
from .monster import Monster


class Deck:
    """A dungeon deck of monsters to fight.

    Decks are persistent: monsters that die stay dead, and progress through
    a deck improves drop rates for that specific deck.
    """

    def __init__(self, deck_id: str, data: dict):
        self.id = deck_id
        self.name = data['name']
        self.description = data.get('description', '')
        self.color = data.get('color', (100, 100, 100))
        self.is_completed = False                          # All monsters defeated
        self.total_monsters = len(data['monsters'])        # Original count
        self.monsters_defeated = 0                         # For drop-rate scaling

        # Deck-specific drop tables
        self.common_keywords: List[str] = data.get('common_keywords', [])
        self.drop_items: List[str] = data.get('drop_items', [])

        # Monsters kept in original order (weakest -> strongest)
        self.monsters: List[Monster] = []
        for m_data in data['monsters']:
            self.monsters.append(Monster(
                m_data['name'],
                m_data['keywords'],
                m_data['base_points'],
            ))

        # Current round's pool (monsters pulled for this exploration)
        self.round_monsters: List[Monster] = []

    # ----- Round management -----

    def prepare_round(self, count: int = 4):
        """Pull monsters from front of deck for this round.

        Monsters stay in weakest-first order in the deck, but the pulled
        round is shuffled so combat order has variety.
        """
        self.round_monsters = []
        pull_count = min(count, len(self.monsters))
        for _ in range(pull_count):
            self.round_monsters.append(self.monsters.pop(0))
        random.shuffle(self.round_monsters)

    def draw(self) -> Optional[Monster]:
        """Draw and remove the next monster from this round's pool."""
        if self.round_monsters:
            return self.round_monsters.pop(0)
        return None

    def peek(self) -> Optional[Monster]:
        """Look at the next monster without removing it."""
        return self.round_monsters[0] if self.round_monsters else None

    def return_monster(self, monster: Monster):
        """Return an undefeated monster to the FRONT of the deck.

        That means you'll face it again next round - you must beat it to progress!
        """
        if not self.is_completed:
            self.monsters.insert(0, monster)

    def return_unused_round_monsters(self):
        """Return any undrawn round monsters back to the front of the deck."""
        for monster in reversed(self.round_monsters):
            self.monsters.insert(0, monster)
        self.round_monsters = []

    # ----- State queries -----

    def is_empty(self) -> bool:
        return len(self.monsters) == 0 and len(self.round_monsters) == 0

    def rounds_monsters_empty(self) -> bool:
        return len(self.round_monsters) == 0

    def check_completion(self) -> bool:
        """Mark the deck completed if all monsters defeated. Returns True if just completed."""
        if self.is_empty() and not self.is_completed:
            self.is_completed = True
            return True
        return False

    def get_remaining_count(self) -> int:
        return len(self.monsters) + len(self.round_monsters)

    def record_kill(self):
        """Record a monster kill for drop-rate scaling."""
        self.monsters_defeated += 1

    # ----- Loot generation -----

    def get_drop_item(
        self,
        item_registry: ItemRegistry,
        allowed_ids: Optional[Iterable[str]] = None,
    ) -> Optional[Item]:
        """Generate a drop item from this deck's specific drop table.

        Drop rates improve as you defeat more monsters in this deck:
        - Base: 50% scrap, 35% common, 12% uncommon, 3% rare
        - Each kill adds ~2% to better rarities

        If ``allowed_ids`` is provided, the deck-specific drop table is
        restricted to items in that set, and the generic-fallback random pull
        is similarly restricted. The deck's OWN drop_items are *always*
        eligible (defeating any monster in a deck implicitly trusts that
        deck's loot table, even if the deck-clear unlock hasn't happened yet).
        """
        kills = self.monsters_defeated

        # Scaled weights
        scrap_weight    = max(10, 50 - kills * 6)        # 50 -> 10 over 7 kills
        common_weight   = 35                              # Stable
        uncommon_weight = min(40, 12 + kills * 4)         # 12 -> 40 over 7 kills
        rare_weight     = min(20, 3 + kills * 2.5)        # 3 -> 20 over 7 kills

        rarity = random.choices(
            ['scrap', 'common', 'uncommon', 'rare'],
            weights=[scrap_weight, common_weight, uncommon_weight, rare_weight],
        )[0]

        # For uncommon+ try deck-specific drops first.  Deck drops always
        # bypass the unlock filter: clearing this deck IS what unlocks them
        # globally, and we still want them as in-delve loot beforehand.
        if rarity in ['uncommon', 'rare'] and self.drop_items:
            item_id = random.choice(self.drop_items)
            item = item_registry.create_copy(item_id)
            if item:
                # Upgrade rarity: rare roll on uncommon item -> 50% reroll for actual rare
                if rarity == 'rare' and item.rarity == 'uncommon':
                    rare_items = [
                        i for i in self.drop_items
                        if item_registry.get(i) and item_registry.get(i).rarity == 'rare'
                    ]
                    if rare_items and random.random() < 0.5:
                        item = item_registry.create_copy(random.choice(rare_items))
                return item

        # Fallback: random item of the rolled rarity, respecting the global
        # unlock filter (with deck-local drops always unioned in).
        if allowed_ids is not None:
            allowed = set(allowed_ids) | set(self.drop_items)
        else:
            allowed = None
        return item_registry.random_item(rarity, allowed_ids=allowed)


class DeckRegistry:
    """Registry for all dungeon decks."""

    def __init__(self):
        self.decks: Dict[str, dict] = {}

    def register(self, deck_id: str, data: dict):
        self.decks[deck_id] = data

    def create(self, deck_id: str) -> Optional[Deck]:
        data = self.decks.get(deck_id)
        return Deck(deck_id, data) if data else None

    def load_from_dict(self, data: dict):
        for deck_id, deck_data in data.items():
            self.register(deck_id, deck_data)

    def all_ids(self) -> List[str]:
        return list(self.decks.keys())