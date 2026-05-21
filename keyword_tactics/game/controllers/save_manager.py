"""Save manager - persists run state and meta-progression to disk.

Save file layout (single JSON document at SAVE_PATH):

    {
        "version": 1,
        "meta": {                       # Persists across deaths & "New Game"
            "unlocked_characters": [...],
            "unlocked_items": [...],
            "debug_unlock_all": false
        },
        "run": {                        # Cleared on game-over / fresh new game
            "coins": 15,
            "phase": "preparation",
            "roster": [...],
            "inventory": [...],
            "active_decks": {...},
            ...                         # Snapshot of an in-progress run
        } | null
    }

Saves are atomic: write-to-temp + os.replace. Failed reads/writes are logged
and treated as "no save available" — the game keeps running.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


SAVE_VERSION = 1


def _save_dir() -> Path:
    """Per-platform user data directory."""
    if os.name == 'nt':
        base = os.environ.get('APPDATA') or str(Path.home())
        return Path(base) / 'KeywordTactics'
    if 'XDG_DATA_HOME' in os.environ:
        return Path(os.environ['XDG_DATA_HOME']) / 'keyword_tactics'
    return Path.home() / '.local' / 'share' / 'keyword_tactics'


def save_path() -> Path:
    return _save_dir() / 'save.json'


def _ensure_dir():
    _save_dir().mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------

def read_save() -> Optional[Dict[str, Any]]:
    """Read the save file, or None if missing/unreadable.

    Old-version saves are returned as-is; callers can decide what to migrate.
    """
    path = save_path()
    if not path.exists():
        return None
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            print(f"[save] Save file is malformed (not an object): {path}")
            return None
        return data
    except (OSError, ValueError) as e:
        print(f"[save] Failed to read save: {e}")
        return None


def write_save(data: Dict[str, Any]) -> bool:
    """Atomically write the save file. Returns True on success."""
    try:
        _ensure_dir()
        path = save_path()
        tmp = path.with_suffix('.json.tmp')
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp, path)
        return True
    except OSError as e:
        print(f"[save] Failed to write save: {e}")
        return False


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------

def has_in_progress_run() -> bool:
    """True if the save has an unfinished run worth resuming."""
    data = read_save()
    return bool(data and data.get('run'))


def clear_run() -> bool:
    """Wipe the in-progress run while keeping meta-unlocks intact."""
    data = read_save() or {'version': SAVE_VERSION}
    data['run'] = None
    return write_save(data)


def wipe_everything() -> bool:
    """Delete the save file entirely (run + meta unlocks)."""
    path = save_path()
    try:
        if path.exists():
            path.unlink()
        return True
    except OSError as e:
        print(f"[save] Failed to wipe save: {e}")
        return False