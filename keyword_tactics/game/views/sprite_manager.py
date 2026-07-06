"""SpriteManager: loads, caches, and serves sprites for characters/monsters/items."""

from pathlib import Path
from typing import Dict, Optional, Set, Tuple

import pygame


class SpriteManager:
    """Manages loading and caching sprites for characters, monsters, and items."""

    # Category name -> subdirectory under assets/ (aliases the existing layout).
    CATEGORY_DIRS = {
        'characters': 'portraits',
        'monsters':   'monsters',
        'items':      'items',
    }

    def __init__(self, base_path: Optional[Path] = None):
        if base_path is None:
            try:
                base_path = Path(__file__).parent.parent.parent / "assets"
            except NameError:
                base_path = Path.cwd() / "assets"
        self.base_path = Path(base_path) if not isinstance(base_path, Path) else base_path
        self.sprites: Dict[str, pygame.Surface] = {}
        self.missing: Set[str] = set()  # Track missing sprites to skip repeat lookups

    def get_sprite(self, category: str, name: str,
                   size: Optional[Tuple[int, int]] = None) -> Optional[pygame.Surface]:
        """Get a sprite for a character, monster, or item.

        Args:
            category: 'characters', 'monsters', or 'items'
            name: The id/name (will look for name.png)
            size: Optional (width, height) for scaling

        Returns:
            pygame.Surface or None if not found
        """
        cache_key = f"{category}/{name}"
        if size:
            cache_key += f"_{size[0]}x{size[1]}"

        if cache_key in self.sprites:
            return self.sprites[cache_key]

        base_key = f"{category}/{name}"
        if base_key in self.missing:
            return None

        cat_dir = self.CATEGORY_DIRS.get(category, category)
        sprite_path = self.base_path / cat_dir / f"{name}.png"
        if sprite_path.exists():
            try:
                sprite = pygame.image.load(str(sprite_path)).convert_alpha()
                if size:
                    sprite = pygame.transform.scale(sprite, size)
                self.sprites[cache_key] = sprite
                return sprite
            except pygame.error as e:
                print(f"Error loading sprite {sprite_path}: {e}")
                self.missing.add(base_key)
                return None
        else:
            self.missing.add(base_key)
            return None

    def get_character_sprite(self, char_id: str,
                             size: Tuple[int, int] = (64, 64)) -> Optional[pygame.Surface]:
        return self.get_sprite("characters", char_id, size)

    def get_monster_sprite(self, monster_name: str,
                           size: Tuple[int, int] = (96, 96)) -> Optional[pygame.Surface]:
        safe_name = monster_name.lower().replace(" ", "_").replace("'", "")
        sprite = self.get_sprite("monsters", safe_name, size)
        if sprite is None:
            # Generic stand-in until this monster gets its own art.
            sprite = self.get_sprite("monsters", "_default_monster", size)
        return sprite

    def get_item_sprite(self, item_id: str,
                        size: Tuple[int, int] = (32, 32)) -> Optional[pygame.Surface]:
        return self.get_sprite("items", item_id, size)

    def preload_all(self):
        """Preload all sprites from the sprites directory."""
        if not self.base_path.exists():
            return
        for category in ("characters", "monsters", "items"):
            category_path = self.base_path / category
            if category_path.exists():
                for sprite_file in category_path.glob("*.png"):
                    self.get_sprite(category, sprite_file.stem)
