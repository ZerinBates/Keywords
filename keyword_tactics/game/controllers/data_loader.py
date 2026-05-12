"""Loads game data (keywords, items, characters, decks) from JSON files."""

import json
import sys
from pathlib import Path
from typing import List

from ..models import (
    KeywordRegistry, ItemRegistry, AdventurerRegistry, DeckRegistry,
)


def _candidate_data_dirs() -> List[Path]:
    """Return ordered list of candidate locations for the data folder."""
    paths: List[Path] = []

    # 1) Relative to this source file (game/controllers/data_loader.py
    #    -> project_root/data)
    try:
        this_file = Path(__file__).resolve()
        # this_file -> .../game/controllers/data_loader.py
        # parents[2] -> project root containing data/
        paths.append(this_file.parents[2] / "data")
    except (NameError, IndexError):
        pass

    # 2) Current working directory
    paths.append(Path.cwd() / "data")

    # 3) Directory where the script was invoked from
    if hasattr(sys, 'argv') and sys.argv[0]:
        try:
            script_dir = Path(sys.argv[0]).parent.resolve()
            paths.append(script_dir / "data")
        except Exception:
            pass

    return paths


def _find_data_dir() -> Path:
    """Locate the data directory, raising FileNotFoundError with a helpful message."""
    candidates = _candidate_data_dirs()
    for path in candidates:
        if path.exists() and (path / "keywords.json").exists():
            return path

    searched = "\n  - ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        "Data directory not found!\n"
        f"Searched in:\n  - {searched}\n\n"
        "Make sure the 'data' folder (containing keywords.json, items.json, "
        "characters.json, decks.json) is at the project root next to main.py."
    )


def _load_json_filtered(path: Path) -> dict:
    """Load a JSON file, stripping any keys that begin with underscore (comments)."""
    if not path.exists():
        raise FileNotFoundError(f"{path.name} not found at: {path}")
    with open(path, 'r') as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith('_')}


def load_all_data(
    keyword_registry: KeywordRegistry,
    item_registry: ItemRegistry,
    adventurer_registry: AdventurerRegistry,
    deck_registry: DeckRegistry,
) -> Path:
    """Populate all four registries from JSON files in the data directory.

    Returns the data directory used (for diagnostic logging).
    """
    data_dir = _find_data_dir()
    print(f"Loading data from: {data_dir}")

    keywords_data = _load_json_filtered(data_dir / "keywords.json")
    keyword_registry.load_from_dict(keywords_data)
    print(f"Loaded {len(keywords_data)} keywords from JSON")

    items_data = _load_json_filtered(data_dir / "items.json")
    item_registry.load_from_dict(items_data)
    print(f"Loaded {len(items_data)} items from JSON")

    chars_data = _load_json_filtered(data_dir / "characters.json")
    adventurer_registry.load_from_dict(chars_data)
    print(f"Loaded {len(chars_data)} characters from JSON")

    decks_data = _load_json_filtered(data_dir / "decks.json")
    deck_registry.load_from_dict(decks_data)
    print(f"Loaded {len(decks_data)} decks from JSON")

    return data_dir
