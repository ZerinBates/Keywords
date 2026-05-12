"""Adventurer (player character) with equipment slots and special abilities."""

import random
from typing import Dict, List, Optional, Tuple

from .item import Item
from .keyword import KeywordRegistry


class Adventurer:
    """A character that can be equipped with items and fight monsters."""

    def __init__(self, char_id: str, data: dict):
        self.id = char_id
        self.name = data['name']
        self.slots = data['slots']
        self.ability_name = data['ability_name']
        self.ability_desc = data['ability_desc']
        self.ability_effect = data.get('ability_effect', {})
        self.equipped_items: List[Item] = []
        self.is_dead = False

    # ----- Equipment management -----

    def can_equip(self) -> bool:
        return len(self.equipped_items) < self.slots

    def equip(self, item: Item) -> bool:
        if self.can_equip():
            self.equipped_items.append(item)
            return True
        return False

    def unequip(self, item: Item) -> bool:
        if item in self.equipped_items:
            self.equipped_items.remove(item)
            return True
        return False

    def unequip_all(self) -> List[Item]:
        items = self.equipped_items.copy()
        self.equipped_items.clear()
        return items

    # ----- Keyword aggregation (handles ability effects) -----

    def get_all_keywords(self) -> List[str]:
        """Get all keywords from equipped items, applying double_keywords ability."""
        keywords: List[str] = []
        for item in self.equipped_items:
            keywords.extend(item.keywords)

        # Handle double_keywords ability (list of keywords to double)
        double_targets = self.ability_effect.get('double_keywords', [])
        # Also support legacy singular format
        if 'double_keyword' in self.ability_effect:
            legacy = self.ability_effect['double_keyword']
            if isinstance(legacy, str):
                double_targets = [legacy]

        for target_kw in double_targets:
            extra = keywords.count(target_kw)
            if extra > 0:
                keywords.extend([target_kw] * extra)

        return keywords

    def get_keyword_counts(self) -> Dict[str, int]:
        """Get counts of each keyword, applying fuse_keywords ability."""
        keywords = self.get_all_keywords()
        counts: Dict[str, int] = {}
        for kw in keywords:
            counts[kw] = counts.get(kw, 0) + 1

        # fuse_keywords: listed keywords stack their counts together
        if 'fuse_keywords' in self.ability_effect:
            fused = self.ability_effect['fuse_keywords']
            total = sum(counts.get(kw, 0) for kw in fused)
            for kw in fused:
                if kw in counts:
                    counts[kw] = total

        return counts

    # ----- Power calculation -----

    def get_base_points(self) -> int:
        return sum(item.points for item in self.equipped_items)

    def get_multiplier(self) -> int:
        """Calculate keyword-stacking multiplier, with element bonus and fuse handling."""
        counts = self.get_keyword_counts()
        multiplier = 0
        counted_fused = set()

        for kw, count in counts.items():
            # For fused keywords, only count once
            if 'fuse_keywords' in self.ability_effect:
                fused = self.ability_effect['fuse_keywords']
                if kw in fused:
                    fused_key = tuple(sorted(fused))
                    if fused_key in counted_fused:
                        continue
                    counted_fused.add(fused_key)

            if count >= 2:
                multiplier += count

        # Element bonus
        if 'element_bonus' in self.ability_effect:
            elements = ['fire', 'water', 'earth', 'nature', 'lightning', 'ice', 'light', 'dark']
            for kw in counts:
                if kw in elements and counts[kw] >= 1:
                    multiplier += self.ability_effect['element_bonus']

        return max(1, multiplier)

    def get_weakness_count(self, enemy_keywords: List[str], keyword_registry: KeywordRegistry) -> int:
        """Count how many of the enemy's keywords we're weak to (respecting immunities)."""
        my_keywords = self.get_all_keywords()
        weakness_count = 0

        # Build immunity set from ability_effect
        immune_to = self.ability_effect.get('immune_weakness', [])
        if isinstance(immune_to, str):
            immune_to = [immune_to]  # Support legacy single-string format
        immune_set = set(immune_to)

        for my_kw in my_keywords:
            kw_obj = keyword_registry.get(my_kw)
            if kw_obj:
                for enemy_kw in enemy_keywords:
                    if enemy_kw in immune_set:
                        continue
                    if kw_obj.is_weak_against(enemy_kw):
                        weakness_count += 1

        return weakness_count

    def calculate_power(self, enemy_keywords: List[str], keyword_registry: KeywordRegistry
                        ) -> Tuple[int, int, int, int]:
        """Calculate final power against an enemy. Returns (final, base, mult, weakness)."""
        base = self.get_base_points()
        mult = self.get_multiplier()
        weakness = self.get_weakness_count(enemy_keywords, keyword_registry)
        final = int((base * mult) / (1 + weakness))
        return final, base, mult, weakness

    def copy(self) -> 'Adventurer':
        """Create a copy of this adventurer (without items)."""
        return Adventurer(self.id, {
            'name': self.name,
            'slots': self.slots,
            'ability_name': self.ability_name,
            'ability_desc': self.ability_desc,
            'ability_effect': self.ability_effect.copy(),
        })


class AdventurerRegistry:
    """Registry for adventurer templates."""

    def __init__(self):
        self.templates: Dict[str, dict] = {}

    def register(self, char_id: str, data: dict):
        self.templates[char_id] = data

    def create(self, char_id: str) -> Optional[Adventurer]:
        data = self.templates.get(char_id)
        return Adventurer(char_id, data) if data else None

    def load_from_dict(self, data: dict):
        for char_id, char_data in data.items():
            self.register(char_id, char_data)

    def random_adventurer(self) -> Optional[Adventurer]:
        if self.templates:
            char_id = random.choice(list(self.templates.keys()))
            return self.create(char_id)
        return None
