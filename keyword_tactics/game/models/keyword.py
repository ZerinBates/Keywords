"""Keyword type with rock-paper-scissors weakness relations."""

from typing import Dict, List, Optional


class Keyword:
    """Represents a single keyword type with its weaknesses."""

    def __init__(self, keyword_id: str, data: dict):
        self.id = keyword_id
        self.name = data['name']
        self.color = data['color']
        self.weak_against: List[str] = data.get('weak_against', [])

    def is_weak_against(self, other_id: str) -> bool:
        return other_id in self.weak_against


class KeywordRegistry:
    """Central registry for all keywords. Makes it easy to add new ones."""

    def __init__(self):
        self.keywords: Dict[str, Keyword] = {}

    def register(self, keyword_id: str, data: dict):
        self.keywords[keyword_id] = Keyword(keyword_id, data)

    def get(self, keyword_id: str) -> Optional[Keyword]:
        return self.keywords.get(keyword_id)

    def load_from_dict(self, data: dict):
        for keyword_id, keyword_data in data.items():
            self.register(keyword_id, keyword_data)

    def all_ids(self) -> List[str]:
        return list(self.keywords.keys())
