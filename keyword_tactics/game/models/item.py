"""Equippable items/skills with keywords and point values."""

import random
from typing import Dict, List, Optional


class Item:
    """An equippable item/skill with keywords and point value."""

    def __init__(self, item_id: str, data: dict):
        self.id = item_id
        self.name = data['name']
        self.keywords: List[str] = data['keywords']
        self.points = data['points']
        self.rarity = data.get('rarity', 'common')
        self.slot = data.get('slot', 'misc')   # <-- add this

    def get_keyword_counts(self) -> Dict[str, int]:
        """Returns count of each keyword on this item."""
        counts: Dict[str, int] = {}
        for kw in self.keywords:
            counts[kw] = counts.get(kw, 0) + 1
        return counts

    def copy(self) -> 'Item':
        return Item(self.id, {
            'name': self.name,
            'keywords': self.keywords.copy(),
            'points': self.points,
            'rarity': self.rarity,
            'slot': self.slot,                  # <-- add this
        })


class ItemRegistry:
    """Registry for all available items."""

    def __init__(self):
        self.items: Dict[str, Item] = {}

    def register(self, item_id: str, data: dict):
        self.items[item_id] = Item(item_id, data)

    def get(self, item_id: str) -> Optional[Item]:
        return self.items.get(item_id)

    def create_copy(self, item_id: str) -> Optional[Item]:
        """Create a new instance of an item by id."""
        item = self.get(item_id)
        return item.copy() if item else None

    def load_from_dict(self, data: dict):
        for item_id, item_data in data.items():
            self.register(item_id, item_data)

    def get_by_rarity(self, rarity: str) -> List[Item]:
        return [i for i in self.items.values() if i.rarity == rarity]

    def random_item(self, rarity: Optional[str] = None) -> Optional[Item]:
        if rarity:
            items = self.get_by_rarity(rarity)
        else:
            items = list(self.items.values())
        return random.choice(items).copy() if items else None
