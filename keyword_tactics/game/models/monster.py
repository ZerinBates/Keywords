"""Monster (enemy) model."""

from typing import Dict, List, Tuple

from .keyword import KeywordRegistry


class Monster:
    """An enemy that adventurers fight."""

    def __init__(self, name: str, keywords: List[str], base_points: int):
        self.name = name
        self.keywords = keywords
        self.base_points = base_points

    def get_keyword_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for kw in self.keywords:
            counts[kw] = counts.get(kw, 0) + 1
        return counts

    def get_multiplier(self) -> int:
        counts = self.get_keyword_counts()
        multiplier = sum(c for c in counts.values() if c >= 2)
        return max(1, multiplier)

    def get_weakness_count(self, adventurer_keywords: List[str],
                           keyword_registry: KeywordRegistry) -> int:
        """Count how many adventurer keywords the monster is weak to."""
        weakness_count = 0
        for my_kw in self.keywords:
            kw_obj = keyword_registry.get(my_kw)
            if kw_obj:
                for adv_kw in adventurer_keywords:
                    if kw_obj.is_weak_against(adv_kw):
                        weakness_count += 1
        return weakness_count

    def calculate_power(self, adventurer_keywords: List[str],
                        keyword_registry: KeywordRegistry) -> Tuple[int, int, int, int]:
        """Calculate final power against an adventurer. Returns (final, base, mult, weakness)."""
        mult = self.get_multiplier()
        weakness = self.get_weakness_count(adventurer_keywords, keyword_registry)
        final = int((self.base_points * mult) / (1 + weakness))
        return final, self.base_points, mult, weakness

    def copy(self) -> 'Monster':
        return Monster(self.name, self.keywords.copy(), self.base_points)
