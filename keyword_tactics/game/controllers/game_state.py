"""GameState - central state container and high-level game logic.

This is the 'M' in MVC for the dynamic, mutable game state. It owns all
runtime state (player resources, party, decks-in-progress, current phase)
and exposes methods to mutate that state in well-defined ways.

It delegates pure combat math to controllers.combat and JSON loading to
controllers.data_loader.

Unlock & save system
--------------------
Two parallel ideas live here:

* **Meta unlocks** (persistent across runs / deaths)
    - ``unlocked_characters``: set of character ids the shop / starter pool
      may spawn. Initially just the 4 starters.
    - ``unlocked_items``: set of item ids the shop / generic loot pool may
      spawn. Initially every non-deck-drop item, plus deck drops belonging
      to decks the player has already cleared in a previous run.
    - ``debug_unlock_all``: master override; when True, every character and
      item is treated as unlocked.

* **Run state** (one in-progress game, wiped on game-over / new game)
    - Saved on every stable transition (after a delve, after the shop,
      etc.). The Main Menu shows a Continue button when a run save exists.
"""

import random
from typing import Dict, List, Optional, Set, Tuple

from ..models import (
    Adventurer, AdventurerRegistry,
    Deck, DeckRegistry,
    GamePhase,
    Item, ItemRegistry,
    KeywordRegistry,
    Monster,
)
from . import combat, save_manager
from .data_loader import load_all_data


# ---------------------------------------------------------------------------
# Unlock configuration
# ---------------------------------------------------------------------------

# These four classes are always available — the player needs *some* roster
# choice on a fresh save.
STARTING_CHARACTERS: Set[str] = {"commoner", "warrior", "mage", "ranger"}

# Defeating a deck's BOSS (the lifted final-row monster, via challenge_boss)
# unlocks the classes mapped to that deck. One entry per deck; a deck may
# unlock multiple classes if there are more classes than decks.
DECK_BOSS_UNLOCKS_CHARACTERS: Dict[str, List[str]] = {
    "beast_den":         ["berserker"],
    "humanoid_fortress": ["knight"],
    "undead_crypt":      ["necromancer"],
    "dragon_peak":       ["dragon_rider"],
    "construct_foundry": ["engineer", "mech_pilot"],
    "demon_rift":        ["warlock"],
    "angel_spire":       ["paladin"],
    "fey_wilds":         ["fey_knight"],
    "slime_sewer":       ["rogue"],
    "insect_hive":       ["druid"],
    "plant_grove":       ["bard"],
    "aquatic_trench":    ["sea_warden"],
    "avian_peaks":       ["archer"],
    "reptile_swamp":     ["assassin"],
    "spirit_haunt":      ["time_mage"],
    "aberration_void":   ["elementalist"],
    "elemental_plane":   ["monk"],
}


class GameState:
    """Manages all game state and high-level logic."""

    # ---------------------------------------------------------------------
    # Construction & data loading
    # ---------------------------------------------------------------------

    def __init__(self):
        # Registries (loaded once from JSON)
        self.keyword_registry = KeywordRegistry()
        self.item_registry = ItemRegistry()
        self.adventurer_registry = AdventurerRegistry()
        self.deck_registry = DeckRegistry()

        load_all_data(
            self.keyword_registry,
            self.item_registry,
            self.adventurer_registry,
            self.deck_registry,
        )

        # ---- Player state ----
        self.coins: int = 10
        self.inventory: List[Item] = []
        self.roster: List[Adventurer] = []
        self.party: List[Adventurer] = []                # Current expedition party (up to 4)
        self.completed_decks: Set[str] = set()           # Fully cleared deck ids

        # ---- Persistent decks (monsters that die stay dead) ----
        self.active_decks: Dict[str, Deck] = {}

        # ---- Current expedition state ----
        self.current_deck: Optional[Deck] = None
        self.current_monster: Optional[Monster] = None
        self.selected_adventurer: Optional[Adventurer] = None
        self.adventures_used: int = 0

        # ---- Seamless delve state ----
        self.front_row: List[dict] = []                  # 4 squares - active, draggable
        self.back_row: List[dict] = []                   # 4 squares - preview only
        self.delve_loot: List[Item] = []
        self.row_mult_base: int = 1                      # 1, 5, 9, ...
        self.rows_completed: int = 0
        self.boss_square: Optional[dict] = None
        self.boss_adventurer_index: int = -1
        self.delve_inv_open: bool = False
        self.delve_inv_scroll: int = 0
        self.delve_inv_source: str = 'loot'
        self.delve_selected_adv_idx: int = -1
        self.earned_multipliers: Dict[Adventurer, int] = {}
        self.delve_recruit_open: bool = False

        # ---- Combat result tracking ----
        self.last_combat_result: Optional[dict] = None

        # ---- Phase ----
        self.phase: GamePhase = GamePhase.MAIN_MENU

        # ---- UI state ----
        self.selected_roster_index: int = -1
        self.selected_party_index: int = -1
        self.selected_inventory_index: int = -1
        self.shop_items: List[Item] = []
        self.shop_adventurers: List[Adventurer] = []
        self.message: str = ""
        self.message_timer: int = 0
        self.inventory_scroll: int = 0
        self.roster_scroll: int = 0

        # ---- Keyword reference panel ----
        self.ref_panel_open: bool = False
        self.ref_search_text: str = ""
        self.ref_selected_keyword: Optional[str] = None
        self.ref_selected_adventurer: Optional[Adventurer] = None
        self.ref_selected_deck_id: Optional[str] = None
        self.ref_scroll: int = 0

        # ---- Preparation inventory search ----
        self.prep_inv_search: str = ""
        self.prep_inv_search_active: bool = False

        # ---- Delve inventory search ----
        self.delve_item_search: str = ""
        self.delve_item_search_active: bool = False

        # ---- Shop kill gating ----
        self.shop_kills_snapshot: int = 0

        # ---- Items recovered from dead adventurers ----
        self.dead_adv_loot: List[Item] = []

        # ---- King / Dunce system ----
        self.hero_king: Optional[Adventurer] = None
        self.hero_dunce: Optional[Adventurer] = None
        self.last_king_slayer: Optional[Adventurer] = None
        self.first_match_done: bool = False

        # ---- Unlock system (meta-progression) ----
        self.unlocked_characters: Set[str] = set()
        self.unlocked_items: Set[str] = set()
        self.debug_unlock_all: bool = False

        # Accumulator for the post-delve "what you unlocked" reveal screen.
        # Entries: {'type': 'character'|'item', 'id': str}
        # Populated by _unlock_for_boss_kill and _unlock_for_deck_clear;
        # consumed and cleared by acknowledge_unlock_reveals().
        self.pending_unlock_reveals: List[dict] = []
        # Current page index on the reveal screen (when >12 unlocks).
        self.unlock_reveal_page: int = 0

        # ---- Run-progress tracking ----
        # True once new_game() runs; cleared on game-over. Used by the main
        # menu Continue button + auto-save guard.
        self.run_in_progress: bool = False

        # Load any persisted meta-progression on construction. This is safe
        # to call before new_game() since it only touches the unlock sets.
        self.load_meta_from_disk()

    # ---------------------------------------------------------------------
    # Game lifecycle
    # ---------------------------------------------------------------------

    def _initialize_decks(self):
        """Create persistent deck instances for this game session."""
        self.active_decks = {}
        for deck_id in self.deck_registry.all_ids():
            deck = self.deck_registry.create(deck_id)
            if deck:
                self.active_decks[deck_id] = deck
        print(f"Initialized {len(self.active_decks)} persistent decks")

    def new_game(self):
        """Start a new game from scratch (keeps meta-unlocks)."""
        self.coins = 15
        self.inventory = []
        self.roster = []
        self.party = []
        self.completed_decks = set()
        self.prep_inv_search = ""
        self.prep_inv_search_active = False
        self.delve_item_search = ""
        self.delve_item_search_active = False
        self.shop_kills_snapshot = 0
        self.dead_adv_loot = []
        self.hero_king = None
        self.hero_dunce = None
        self.last_king_slayer = None
        self.first_match_done = False
        self.pending_unlock_reveals = []
        self.unlock_reveal_page = 0

        # Reset reference panel
        self.ref_panel_open = False
        self.ref_search_text = ""
        self.ref_selected_keyword = None
        self.ref_selected_adventurer = None
        self.ref_selected_deck_id = None
        self.ref_scroll = 0

        self._initialize_decks()

        # Starting adventurers (random + commoners) — filtered by unlocks
        for _ in range(4):
            adv = self._spawn_random_adventurer()
            if adv:
                self.roster.append(adv)
        for _ in range(4):
            basic = self.adventurer_registry.create("commoner")
            if basic:
                self.roster.append(basic)

        # Starting items (mix of scrap and common) — filtered by unlocks
        for _ in range(4):
            item = self._spawn_random_item('scrap')
            if item:
                self.inventory.append(item)
        for _ in range(7):
            item = self._spawn_random_item('common')
            if item:
                self.inventory.append(item)
        item = self.item_registry.create_copy('insect_bow')
        if item:
            self.inventory.append(item)

        self.phase = GamePhase.PREPARATION
        self.run_in_progress = True
        self.set_message("Welcome! Equip your adventurers and choose a deck to explore.")
        self.autosave()

    # ---------------------------------------------------------------------
    # Status messages
    # ---------------------------------------------------------------------

    def set_message(self, msg: str, duration: int = 180):
        self.message = msg
        self.message_timer = duration

    def update_message(self):
        if self.message_timer > 0:
            self.message_timer -= 1
            if self.message_timer == 0:
                self.message = ""

    # =====================================================================
    # Unlock system
    # =====================================================================

    def is_character_unlocked(self, char_id: str) -> bool:
        if self.debug_unlock_all:
            return True
        return char_id in self.unlocked_characters

    def is_item_unlocked(self, item_id: str) -> bool:
        if self.debug_unlock_all:
            return True
        return item_id in self.unlocked_items

    def _allowed_character_ids(self) -> Optional[Set[str]]:
        """Return None when debug overrides (no filter), else the unlocked set."""
        if self.debug_unlock_all:
            return None
        return set(self.unlocked_characters)

    def _allowed_item_ids(self) -> Optional[Set[str]]:
        if self.debug_unlock_all:
            return None
        return set(self.unlocked_items)

    def _spawn_random_adventurer(self) -> Optional[Adventurer]:
        return self.adventurer_registry.random_adventurer(
            allowed_ids=self._allowed_character_ids(),
        )

    def _spawn_random_item(self, rarity: Optional[str] = None) -> Optional[Item]:
        return self.item_registry.random_item(
            rarity, allowed_ids=self._allowed_item_ids(),
        )

    def reset_unlocks_to_starting(self):
        """Reset meta-unlocks to the fresh-save baseline. Persists immediately."""
        self.unlocked_characters = set(STARTING_CHARACTERS)
        # Generic items (not in any deck-specific drop table) are unlocked
        # from the start; deck-themed loot waits on deck clears.
        deck_drop_ids: Set[str] = set()
        for deck_data in self.deck_registry.decks.values():
            deck_drop_ids.update(deck_data.get('drop_items', []))
        all_item_ids = set(self.item_registry.all_ids())
        self.unlocked_items = all_item_ids - deck_drop_ids
        self.save_meta_to_disk()

    def toggle_debug_unlock_all(self) -> bool:
        """Flip the master debug unlock. Persists. Returns new state."""
        self.debug_unlock_all = not self.debug_unlock_all
        self.save_meta_to_disk()
        return self.debug_unlock_all

    def _unlock_for_boss_kill(self, deck_id: str) -> List[str]:
        """Grant the character unlocks tied to defeating ``deck_id``'s boss.

        Returns the list of newly-unlocked character ids (may be empty if
        all were already unlocked).
        """
        granted: List[str] = []
        for char_id in DECK_BOSS_UNLOCKS_CHARACTERS.get(deck_id, []):
            if char_id not in self.unlocked_characters:
                self.unlocked_characters.add(char_id)
                granted.append(char_id)
                self.pending_unlock_reveals.append({
                    'type': 'character', 'id': char_id,
                })
        if granted:
            self.save_meta_to_disk()
        return granted

    def _unlock_for_deck_clear(self, deck_id: str) -> List[str]:
        """Grant the item unlocks tied to fully clearing a deck.

        Returns newly-unlocked item ids.
        """
        deck_data = self.deck_registry.decks.get(deck_id, {})
        granted: List[str] = []
        for item_id in deck_data.get('drop_items', []):
            if item_id in self.item_registry.items and item_id not in self.unlocked_items:
                self.unlocked_items.add(item_id)
                granted.append(item_id)
                self.pending_unlock_reveals.append({
                    'type': 'item', 'id': item_id,
                })
        if granted:
            self.save_meta_to_disk()
        return granted

    # ---------------------------------------------------------------------
    # Meta-progression persistence (separate from run save)
    # ---------------------------------------------------------------------

    def load_meta_from_disk(self):
        """Pull unlocked_characters / unlocked_items / debug flag from save."""
        data = save_manager.read_save()
        if not data:
            self.reset_unlocks_to_starting()
            return
        meta = data.get('meta') or {}
        chars = meta.get('unlocked_characters')
        items = meta.get('unlocked_items')
        if isinstance(chars, list) and chars:
            self.unlocked_characters = set(chars)
        else:
            self.unlocked_characters = set(STARTING_CHARACTERS)
        if isinstance(items, list) and items:
            self.unlocked_items = set(items)
        else:
            deck_drop_ids: Set[str] = set()
            for deck_data in self.deck_registry.decks.values():
                deck_drop_ids.update(deck_data.get('drop_items', []))
            self.unlocked_items = set(self.item_registry.all_ids()) - deck_drop_ids
        self.debug_unlock_all = bool(meta.get('debug_unlock_all', False))

        # Always ensure starters are present even if save is corrupted
        self.unlocked_characters |= STARTING_CHARACTERS

    def save_meta_to_disk(self):
        """Write just the meta block, preserving any in-progress run save."""
        existing = save_manager.read_save() or {'version': save_manager.SAVE_VERSION}
        existing.setdefault('version', save_manager.SAVE_VERSION)
        existing['meta'] = {
            'unlocked_characters': sorted(self.unlocked_characters),
            'unlocked_items':      sorted(self.unlocked_items),
            'debug_unlock_all':    self.debug_unlock_all,
        }
        save_manager.write_save(existing)

    # =====================================================================
    # Run state persistence
    # =====================================================================

    def has_resumable_run(self) -> bool:
        return save_manager.has_in_progress_run()

    def autosave(self):
        """Persist the current run if we're at a stable phase.

        Saves are only safe outside of an active combat row, because we
        don't snapshot the transient front-row / back-row state. The
        ``run_in_progress`` flag prevents saves on the main menu.
        """
        if not self.run_in_progress:
            return
        if self.phase in (GamePhase.MAIN_MENU, GamePhase.GAME_OVER):
            return
        existing = save_manager.read_save() or {'version': save_manager.SAVE_VERSION}
        existing.setdefault('version', save_manager.SAVE_VERSION)
        existing['meta'] = {
            'unlocked_characters': sorted(self.unlocked_characters),
            'unlocked_items':      sorted(self.unlocked_items),
            'debug_unlock_all':    self.debug_unlock_all,
        }
        existing['run'] = self._serialize_run()
        save_manager.write_save(existing)

    def clear_run_save(self):
        """Wipe the in-progress run file (meta-unlocks preserved)."""
        save_manager.clear_run()
        self.run_in_progress = False

    # ----- Item / Adventurer / Deck serialization helpers -----

    @staticmethod
    def _item_to_dict(item: Item) -> dict:
        return {
            'id':       item.id,
            'name':     item.name,
            'keywords': list(item.keywords),
            'points':   item.points,
            'rarity':   item.rarity,
            'slot':     item.slot,
        }

    @staticmethod
    def _item_from_dict(data: dict) -> Item:
        return Item(data.get('id', 'unknown'), {
            'name':     data['name'],
            'keywords': list(data.get('keywords', [])),
            'points':   data.get('points', 0),
            'rarity':   data.get('rarity', 'common'),
            'slot':     data.get('slot', 'misc'),
        })

    def _adv_to_dict(self, adv: Adventurer) -> dict:
        return {
            'id':       adv.id,
            'is_dead':  adv.is_dead,
            'slots':    adv.slots,          # may have been increased by boss reward
            'equipped': [self._item_to_dict(it) for it in adv.equipped_items],
        }

    def _adv_from_dict(self, data: dict) -> Optional[Adventurer]:
        adv = self.adventurer_registry.create(data['id'])
        if not adv:
            # Template went missing - skip rather than crash the save
            return None
        adv.is_dead = bool(data.get('is_dead', False))
        adv.slots = int(data.get('slots', adv.slots))
        adv.equipped_items = [self._item_from_dict(d) for d in data.get('equipped', [])]
        return adv

    @staticmethod
    def _monster_to_dict(m: Monster) -> dict:
        return {
            'name':        m.name,
            'keywords':    list(m.keywords),
            'base_points': m.base_points,
        }

    @staticmethod
    def _monster_from_dict(d: dict) -> Monster:
        return Monster(d['name'], list(d.get('keywords', [])), int(d.get('base_points', 0)))

    def _deck_to_dict(self, deck: Deck) -> dict:
        return {
            'is_completed':      deck.is_completed,
            'monsters_defeated': deck.monsters_defeated,
            # round_monsters is empty at save points (PREPARATION / ROUND_END)
            'monsters':          [self._monster_to_dict(m) for m in deck.monsters],
        }

    def _apply_deck_dict(self, deck: Deck, data: dict):
        deck.is_completed = bool(data.get('is_completed', False))
        deck.monsters_defeated = int(data.get('monsters_defeated', 0))
        saved_monsters = data.get('monsters')
        if isinstance(saved_monsters, list):
            deck.monsters = [self._monster_from_dict(m) for m in saved_monsters]
        deck.round_monsters = []

    # ----- Whole-run serialization -----

    def _serialize_run(self) -> dict:
        # Map roster identity -> index for cross-references
        ros_idx = {id(a): i for i, a in enumerate(self.roster)}

        def adv_ref(adv: Optional[Adventurer]) -> Optional[int]:
            return ros_idx.get(id(adv)) if adv is not None else None

        return {
            'phase':              self.phase.value,
            'coins':              self.coins,
            'shop_kills_snapshot': self.shop_kills_snapshot,
            'first_match_done':   self.first_match_done,
            'completed_decks':    sorted(self.completed_decks),

            'inventory':          [self._item_to_dict(i) for i in self.inventory],
            'shop_items':         [self._item_to_dict(i) for i in self.shop_items],
            'dead_adv_loot':      [self._item_to_dict(i) for i in self.dead_adv_loot],

            'roster':             [self._adv_to_dict(a) for a in self.roster],
            'party_indices':      [adv_ref(a) for a in self.party if adv_ref(a) is not None],
            'shop_adventurers':   [self._adv_to_dict(a) for a in self.shop_adventurers],

            'last_king_slayer':   adv_ref(self.last_king_slayer),

            'active_decks':       {
                did: self._deck_to_dict(d) for did, d in self.active_decks.items()
            },

            # Visual-reveal queue: empty most of the time, populated only
            # between the boss/clear that unlocked the content and the
            # player clicking Continue on the reveal screen.
            'pending_unlock_reveals': list(self.pending_unlock_reveals),
        }

    def load_run_from_disk(self) -> bool:
        """Try to restore an in-progress run. Returns True on success."""
        data = save_manager.read_save()
        if not data or not data.get('run'):
            return False
        run = data['run']

        try:
            # ---- Decks ----
            self._initialize_decks()
            for did, ddata in run.get('active_decks', {}).items():
                if did in self.active_decks:
                    self._apply_deck_dict(self.active_decks[did], ddata)
            self.completed_decks = set(run.get('completed_decks', []))

            # ---- Roster (referenced by index from party & last_king_slayer) ----
            self.roster = []
            for adv_data in run.get('roster', []):
                adv = self._adv_from_dict(adv_data)
                if adv:
                    self.roster.append(adv)

            self.party = []
            for idx in run.get('party_indices', []):
                if isinstance(idx, int) and 0 <= idx < len(self.roster):
                    self.party.append(self.roster[idx])

            slayer_idx = run.get('last_king_slayer')
            if isinstance(slayer_idx, int) and 0 <= slayer_idx < len(self.roster):
                self.last_king_slayer = self.roster[slayer_idx]
            else:
                self.last_king_slayer = None

            # ---- Items / shop ----
            self.inventory = [self._item_from_dict(d) for d in run.get('inventory', [])]
            self.shop_items = [self._item_from_dict(d) for d in run.get('shop_items', [])]
            self.dead_adv_loot = [self._item_from_dict(d) for d in run.get('dead_adv_loot', [])]
            self.shop_adventurers = []
            for adv_data in run.get('shop_adventurers', []):
                adv = self._adv_from_dict(adv_data)
                if adv:
                    self.shop_adventurers.append(adv)

            # ---- Scalars ----
            self.coins = int(run.get('coins', 10))
            self.shop_kills_snapshot = int(run.get('shop_kills_snapshot', 0))
            self.first_match_done = bool(run.get('first_match_done', False))

            # Resumed runs always land in PREPARATION (or UNLOCK_REVEAL if
            # they were mid-reveal); we never save mid-delve so any saved
            # combat-phase value would be inconsistent anyway.
            saved_phase = run.get('phase', GamePhase.PREPARATION.value)
            try:
                phase = GamePhase(saved_phase)
            except ValueError:
                phase = GamePhase.PREPARATION
            if phase in (GamePhase.DELVE_SETUP, GamePhase.DELVE_RESULTS,
                         GamePhase.BOSS_CHOICE, GamePhase.BOSS_RESULT):
                phase = GamePhase.PREPARATION
            self.phase = phase

            # ---- Restore pending unlock reveals (filtered to valid ids) ----
            self.pending_unlock_reveals = []
            self.unlock_reveal_page = 0
            for entry in run.get('pending_unlock_reveals', []):
                if not isinstance(entry, dict):
                    continue
                etype = entry.get('type')
                eid = entry.get('id')
                if etype == 'character' and eid in self.adventurer_registry.templates:
                    self.pending_unlock_reveals.append({'type': 'character', 'id': eid})
                elif etype == 'item' and eid in self.item_registry.items:
                    self.pending_unlock_reveals.append({'type': 'item', 'id': eid})

            # If we restored phase == UNLOCK_REVEAL but list is empty, fall
            # back to PREPARATION rather than show an empty reveal screen.
            if self.phase == GamePhase.UNLOCK_REVEAL and not self.pending_unlock_reveals:
                self.phase = GamePhase.PREPARATION

            # ---- Reset transient delve state ----
            self.current_deck = None
            self.current_monster = None
            self.selected_adventurer = None
            self.front_row = []
            self.back_row = []
            self.delve_loot = []
            self.boss_square = None
            self.boss_adventurer_index = -1
            self.delve_inv_open = False
            self.delve_recruit_open = False
            self.rows_completed = 0
            self.row_mult_base = 1
            self.earned_multipliers = {}
            self.hero_king = None
            self.hero_dunce = None
            self.last_combat_result = None

            self.run_in_progress = True
            self.set_message("Run resumed from save.")
            return True
        except (KeyError, TypeError, ValueError) as e:
            print(f"[save] Failed to restore run: {e}")
            return False

    # ---------------------------------------------------------------------
    # Keyword reference panel
    # ---------------------------------------------------------------------

    def toggle_ref_panel(self):
        """Toggle the keyword reference panel open/closed."""
        self.ref_panel_open = not self.ref_panel_open
        if not self.ref_panel_open:
            self.ref_search_text = ""
            self.ref_selected_keyword = None
            self.ref_selected_adventurer = None
            self.ref_selected_deck_id = None
            self.ref_scroll = 0

    def get_all_keywords_info(self) -> List[dict]:
        result = []
        for kw_id in sorted(self.keyword_registry.all_ids()):
            kw = self.keyword_registry.get(kw_id)
            if kw:
                strong_against = []
                for other_id in self.keyword_registry.all_ids():
                    other_kw = self.keyword_registry.get(other_id)
                    if other_kw and kw_id in other_kw.weak_against:
                        strong_against.append(other_id)
                result.append({
                    'id': kw_id,
                    'name': kw.name,
                    'color': kw.color,
                    'weak_against': kw.weak_against.copy(),
                    'strong_against': strong_against,
                })
        return result

    def get_filtered_keywords(self, search: str) -> List[dict]:
        all_kw = self.get_all_keywords_info()
        if not search:
            return all_kw
        s = search.lower()
        return [kw for kw in all_kw if s in kw['name'].lower() or s in kw['id'].lower()]

    def get_deck_keywords_analysis(self, deck_id: str) -> dict:
        deck = self.active_decks.get(deck_id)
        if not deck:
            return {'keywords': {}, 'effective_against': {}}

        keyword_counts: Dict[str, int] = {}
        for monster in deck.monsters + deck.round_monsters:
            for kw_id in monster.keywords:
                keyword_counts[kw_id] = keyword_counts.get(kw_id, 0) + 1

        effective_against: Dict[str, int] = {}
        for kw_id, count in keyword_counts.items():
            kw = self.keyword_registry.get(kw_id)
            if kw:
                for weak_to in kw.weak_against:
                    effective_against[weak_to] = effective_against.get(weak_to, 0) + count

        return {'keywords': keyword_counts, 'effective_against': effective_against}

    def get_adventurer_keywords_analysis(self, adv: Adventurer) -> dict:
        keywords = adv.get_all_keywords()
        keyword_counts: Dict[str, int] = {}
        for kw_id in keywords:
            keyword_counts[kw_id] = keyword_counts.get(kw_id, 0) + 1

        weak_to: Dict[str, int] = {}
        for kw_id, count in keyword_counts.items():
            kw = self.keyword_registry.get(kw_id)
            if kw:
                for weakness in kw.weak_against:
                    weak_to[weakness] = weak_to.get(weakness, 0) + count

        strong_against: Dict[str, int] = {}
        for kw_id, count in keyword_counts.items():
            for other_id in self.keyword_registry.all_ids():
                other_kw = self.keyword_registry.get(other_id)
                if other_kw and kw_id in other_kw.weak_against:
                    strong_against[other_id] = strong_against.get(other_id, 0) + count

        return {'keywords': keyword_counts, 'weak_to': weak_to, 'strong_against': strong_against}

    def compare_keyword_vs_adventurer(self, kw_id: str, adv: Adventurer) -> dict:
        adv_keywords = adv.get_all_keywords()
        kw = self.keyword_registry.get(kw_id)

        if not kw:
            return {'weakness_count': 0, 'strength_count': 0}

        weakness_count = 0
        for adv_kw_id in adv_keywords:
            adv_kw = self.keyword_registry.get(adv_kw_id)
            if adv_kw and kw_id in adv_kw.weak_against:
                weakness_count += 1

        strength_count = 0
        for adv_kw_id in adv_keywords:
            if adv_kw_id in kw.weak_against:
                strength_count += 1

        return {'weakness_count': weakness_count, 'strength_count': strength_count}

    # ---------------------------------------------------------------------
    # Preparation phase
    # ---------------------------------------------------------------------

    def add_to_party(self, roster_index: int) -> bool:
        if len(self.party) >= 4:
            self.set_message("Party is full (max 4)!")
            return False
        if not (0 <= roster_index < len(self.roster)):
            return False

        adv = self.roster[roster_index]
        if adv.is_dead:
            self.set_message("This adventurer is dead!")
            return False
        if adv in self.party:
            self.set_message("Already in party!")
            return False

        self.party.append(adv)
        return True

    def remove_from_party(self, party_index: int) -> bool:
        if not (0 <= party_index < len(self.party)):
            return False
        self.party.pop(party_index)
        return True

    def equip_item(self, inventory_index: int, adv: Adventurer) -> bool:
        if not (0 <= inventory_index < len(self.inventory)):
            return False
        if not adv.can_equip():
            self.set_message(f"{adv.name} has no free slots!")
            return False

        item = self.inventory.pop(inventory_index)
        adv.equip(item)
        return True

    def equip_item_obj(self, item: Item, adv: Adventurer) -> bool:
        if item not in self.inventory:
            return False
        if not adv.can_equip():
            self.set_message(f"{adv.name} has no free slots!")
            return False
        self.inventory.remove(item)
        adv.equip(item)
        return True

    def unequip_item(self, adv: Adventurer, item_index: int) -> bool:
        if not (0 <= item_index < len(adv.equipped_items)):
            return False
        item = adv.equipped_items.pop(item_index)
        self.inventory.append(item)
        return True

    def sell_item(self, inventory_index: int) -> bool:
        if not (0 <= inventory_index < len(self.inventory)):
            return False
        item = self.inventory[inventory_index]
        sell_prices = {'scrap': 1, 'common': 1, 'uncommon': 3, 'rare': 5}
        coins = sell_prices.get(item.rarity, 1)
        self.coins += coins
        self.inventory.pop(inventory_index)
        self.set_message(f"Sold {item.name} for {coins} coin(s).")
        return True

    def sell_item_obj(self, item: Item) -> bool:
        if item not in self.inventory:
            return False
        idx = self.inventory.index(item)
        return self.sell_item(idx)

    def get_item_sell_price(self, item: Item) -> int:
        sell_prices = {'scrap': 1, 'common': 1, 'uncommon': 3, 'rare': 5}
        return sell_prices.get(item.rarity, 1)

    def get_filtered_inventory(self) -> List[Item]:
        if not self.prep_inv_search:
            return list(self.inventory)
        s = self.prep_inv_search.lower()
        result = []
        for item in self.inventory:
            if s in item.name.lower():
                result.append(item)
                continue
            matched = False
            for kw_id in item.keywords:
                kw = self.keyword_registry.get(kw_id)
                if kw and s in kw.name.lower():
                    matched = True
                    break
            if matched:
                result.append(item)
        return result

    def _matches_search(self, item: Item, search: str) -> bool:
        if not search:
            return True
        s = search.lower()
        if s in item.name.lower():
            return True
        for kw_id in item.keywords:
            kw = self.keyword_registry.get(kw_id)
            if kw and s in kw.name.lower():
                return True
        return False

    def get_filtered_delve_items(self) -> List[Item]:
        merged = list(self.delve_loot) + list(self.inventory)
        if not self.delve_item_search:
            return merged
        return [it for it in merged if self._matches_search(it, self.delve_item_search)]

    # ---------------------------------------------------------------------
    # Shop — dead-adventurer loot
    # ---------------------------------------------------------------------

    def buy_dead_adv_loot(self, index: int) -> bool:
        if not (0 <= index < len(self.dead_adv_loot)):
            return False
        item = self.dead_adv_loot[index]
        price = self.get_item_price(item)
        if self.coins < price:
            self.set_message("Not enough coins!")
            return False
        self.coins -= price
        self.inventory.append(item)
        self.dead_adv_loot.pop(index)
        return True

    # ---------------------------------------------------------------------
    # Exploration / delve phase
    # ---------------------------------------------------------------------

    def start_exploration(self, deck_id: str) -> bool:
        if len(self.party) != 4:
            self.set_message("You need 4 adventurers in your party!")
            return False

        self.current_deck = self.active_decks.get(deck_id)
        if not self.current_deck:
            self.set_message("Deck not found!")
            return False
        if self.current_deck.is_completed or self.current_deck.is_empty():
            self.set_message("This deck has been cleared!")
            return False

        remaining = len(self.current_deck.monsters)
        self.current_deck.prepare_round(remaining)

        # Reset delve state
        self.delve_loot = []
        self.rows_completed = 0
        self.row_mult_base = 1
        self.boss_square = None
        self.boss_adventurer_index = -1
        self.delve_inv_open = False
        self.delve_inv_scroll = 0
        self.delve_inv_source = 'loot'
        self.delve_selected_adv_idx = -1
        self.delve_item_search = ""
        self.delve_item_search_active = False
        self.earned_multipliers = {adv: 1 for adv in self.party}

        # Build rows and assign monster king/dunce flags
        self.front_row = self._build_row(self.row_mult_base)
        self.back_row = self._build_row(self.row_mult_base + 4)

        # Assign hero roles for the FIRST row of this delve
        self._assign_hero_roles_for_row()

        self.phase = GamePhase.DELVE_SETUP
        self.set_message("Drag all adventurers onto the front row! Back row previews what's next.")
        return True

    # ---------------------------------------------------------------------
    # King / Dunce role assignment
    # ---------------------------------------------------------------------

    def _assign_hero_roles_for_row(self):
        if not self.first_match_done:
            self.hero_king = None
            self.hero_dunce = None
            return

        if (self.last_king_slayer
                and self.last_king_slayer in self.party
                and not self.last_king_slayer.is_dead):
            self.hero_king = self.last_king_slayer
        else:
            self.hero_king = None

        candidates = [a for a in self.party
                      if not a.is_dead and a is not self.hero_king]
        self.hero_dunce = random.choice(candidates) if candidates else None

    def _build_row(self, mult_base: int) -> List[dict]:
        row: List[dict] = []
        for i in range(4):
            if not self.current_deck.round_monsters:
                break
            monster = self.current_deck.round_monsters.pop(0)
            row.append({
                'monster': monster,
                'multiplier': 1,
                'bonus': combat.generate_square_bonus(self.keyword_registry),
                'adventurer': None,
                'result': None,
                'is_king':  False,
                'is_dunce': False,
            })

        if row:
            king_idx = max(range(len(row)),
                           key=lambda i: row[i]['monster'].base_points)
            row[king_idx]['is_king'] = True

            other_idxs = [i for i in range(len(row)) if i != king_idx]
            if other_idxs:
                dunce_idx = random.choice(other_idxs)
                row[dunce_idx]['is_dunce'] = True

        return row

    def find_adventurer_square(self, adv: Adventurer) -> Optional[dict]:
        for sq in self.front_row:
            if sq['adventurer'] is adv:
                return sq
        return None

    def get_adventurer_multiplier(self, adv: Adventurer) -> int:
        return self.earned_multipliers.get(adv, 1)

    def remove_adventurer_from_front(self, adv: Adventurer):
        for sq in self.front_row:
            if sq['adventurer'] is adv:
                sq['adventurer'] = None
                return

    def place_adventurer_on_front(self, party_index: int, sq_idx: int) -> bool:
        if not (0 <= party_index < len(self.party)):
            return False
        if not (0 <= sq_idx < len(self.front_row)):
            return False
        adv = self.party[party_index]
        if adv.is_dead:
            return False
        target = self.front_row[sq_idx]
        if target['adventurer'] is not None and target['adventurer'] is not adv:
            self.set_message("Square occupied!")
            return False
        self.remove_adventurer_from_front(adv)
        target['adventurer'] = adv
        return True

    def count_front_placed(self) -> int:
        return sum(1 for sq in self.front_row if sq['adventurer'] is not None)

    def count_alive_party(self) -> int:
        return sum(1 for a in self.party if not a.is_dead)

    def all_alive_placed(self) -> bool:
        alive = self.count_alive_party()
        placed = self.count_front_placed()
        return placed >= min(alive, len(self.front_row))

    # ---------------------------------------------------------------------
    # Mid-delve inventory swap
    # ---------------------------------------------------------------------

    def toggle_delve_inventory(self):
        self.delve_inv_open = not self.delve_inv_open
        if not self.delve_inv_open:
            self.delve_selected_adv_idx = -1
        else:
            self.delve_inv_scroll = 0

    def delve_equip_item(self, item_index: int) -> bool:
        if not (0 <= self.delve_selected_adv_idx < len(self.party)):
            self.set_message("Select an adventurer first!")
            return False
        adv = self.party[self.delve_selected_adv_idx]
        source = self.delve_loot if self.delve_inv_source == 'loot' else self.inventory
        if not (0 <= item_index < len(source)):
            return False
        if not adv.can_equip():
            self.set_message(f"{adv.name} has no free slots!")
            return False
        item = source.pop(item_index)
        adv.equip(item)
        return True

    def delve_equip_item_merged(self, merged_index: int) -> bool:
        if not (0 <= self.delve_selected_adv_idx < len(self.party)):
            self.set_message("Select an adventurer first!")
            return False
        adv = self.party[self.delve_selected_adv_idx]
        if not adv.can_equip():
            self.set_message(f"{adv.name} has no free slots!")
            return False
        loot_count = len(self.delve_loot)
        if merged_index < loot_count:
            item = self.delve_loot.pop(merged_index)
        else:
            inv_idx = merged_index - loot_count
            if not (0 <= inv_idx < len(self.inventory)):
                return False
            item = self.inventory.pop(inv_idx)
        adv.equip(item)
        return True

    def delve_equip_item_obj(self, item: Item) -> bool:
        if not (0 <= self.delve_selected_adv_idx < len(self.party)):
            self.set_message("Select an adventurer first!")
            return False
        adv = self.party[self.delve_selected_adv_idx]
        if not adv.can_equip():
            self.set_message(f"{adv.name} has no free slots!")
            return False
        if item in self.delve_loot:
            self.delve_loot.remove(item)
        elif item in self.inventory:
            self.inventory.remove(item)
        else:
            return False
        adv.equip(item)
        return True

    def delve_unequip_item(self, adv_item_index: int) -> bool:
        if not (0 <= self.delve_selected_adv_idx < len(self.party)):
            return False
        adv = self.party[self.delve_selected_adv_idx]
        if not (0 <= adv_item_index < len(adv.equipped_items)):
            return False
        item = adv.equipped_items.pop(adv_item_index)
        self.delve_loot.append(item)
        return True

    # ---------------------------------------------------------------------
    # Mid-delve recruitment
    # ---------------------------------------------------------------------

    def toggle_delve_recruit(self):
        self.delve_recruit_open = not self.delve_recruit_open

    def get_available_recruits(self) -> List[Adventurer]:
        return [a for a in self.roster if a not in self.party and not a.is_dead]

    def party_needs_recruits(self) -> bool:
        alive_in_party = sum(1 for a in self.party if not a.is_dead)
        return alive_in_party < 4 and len(self.get_available_recruits()) > 0

    def delve_recruit(self, recruit_index: int) -> bool:
        available = self.get_available_recruits()
        if not (0 <= recruit_index < len(available)):
            return False
        alive_in_party = sum(1 for a in self.party if not a.is_dead)
        if alive_in_party >= 4:
            self.set_message("Party already has 4 alive!")
            return False
        adv = available[recruit_index]
        self.party.append(adv)
        self.earned_multipliers[adv] = 1
        self.set_message(f"{adv.name} joins the delve! Equip them with  Items.")
        return True

    # ---------------------------------------------------------------------
    # Front-row resolution
    # ---------------------------------------------------------------------

    def resolve_front_row(self):
        for sq in self.front_row:
            if sq['adventurer'] is not None:
                adv = sq['adventurer']
                adv_is_king  = (adv is self.hero_king)
                adv_is_dunce = (adv is self.hero_dunce)
                result = combat.calculate_square_combat(
                    sq, self.keyword_registry,
                    adv_is_king=adv_is_king, adv_is_dunce=adv_is_dunce,
                )
                sq['result'] = result
                if result['victory']:
                    self.current_deck.record_kill()
                    if sq.get('is_king'):
                        self.last_king_slayer = adv
                    reward = self.current_deck.get_drop_item(
                        self.item_registry,
                        allowed_ids=self._allowed_item_ids(),
                    )
                    if reward:
                        self.delve_loot.append(reward)
                        result['reward_item'] = reward
                    self.coins += 1
                    result['reward_coins'] = 1
                else:
                    adv.is_dead = True
                    lost = adv.equipped_items.copy()
                    result['lost_items'] = lost
                    self.dead_adv_loot.extend(lost)
                    adv.equipped_items.clear()
                    if self.last_king_slayer is adv:
                        self.last_king_slayer = None
                    self.current_deck.return_monster(sq['monster'])
            else:
                self.current_deck.return_monster(sq['monster'])
        self.rows_completed += 1
        self.first_match_done = True
        self.phase = GamePhase.DELVE_RESULTS

    def get_front_row_summary(self) -> dict:
        occupied = [sq for sq in self.front_row if sq['adventurer'] is not None]
        wins = sum(1 for sq in occupied if sq.get('result') and sq['result']['victory'])
        return {
            'wins': wins,
            'losses': len(occupied) - wins,
            'fought': len(occupied),
            'total': len(self.front_row),
        }

    def advance_row(self):
        for sq in self.front_row:
            sq['adventurer'] = None

        self.party = [a for a in self.party if not a.is_dead]
        if not self.party:
            self.end_exploration()
            return

        self.row_mult_base += 4
        self.front_row = self.back_row
        if self.current_deck.round_monsters:
            self.back_row = self._build_row(self.row_mult_base + 4)
        else:
            self.back_row = []

        if not self.front_row:
            if self.current_deck.is_empty():
                self._mark_deck_completed(self.current_deck)
            self.end_exploration()
            return

        if not self.back_row and len(self.front_row) > 1 and not self.boss_square:
            bs = self.front_row.pop()
            self.boss_square = {
                'monster': bs['monster'],
                'multiplier': bs['multiplier'] + 1,
                'bonus': combat.generate_square_bonus(self.keyword_registry),
                'adventurer': None,
                'result': None,
                'revealed': False,
            }

        self.delve_inv_open = False
        self.delve_recruit_open = False
        self._assign_hero_roles_for_row()
        self.phase = GamePhase.DELVE_SETUP
        self.set_message(
            f"Row {self.rows_completed + 1}. King/Dunce reassigned — swap items anytime!"
        )

    def retreat_from_delve(self):
        for sq in self.front_row:
            if sq.get('result') is None:
                self.current_deck.return_monster(sq['monster'])
        for sq in self.back_row:
            self.current_deck.return_monster(sq['monster'])
        self.end_exploration()

    def proceed_after_results(self):
        if self.boss_square and any(not a.is_dead for a in self.party):
            self.phase = GamePhase.BOSS_CHOICE
            self.boss_adventurer_index = -1
        elif not self.back_row and not self.current_deck.round_monsters:
            if self.current_deck.is_empty():
                self._mark_deck_completed(self.current_deck)
            self.end_exploration()
        else:
            self.advance_row()

    # ---------------------------------------------------------------------
    # Boss combat
    # ---------------------------------------------------------------------

    def select_boss_adventurer(self, party_index: int) -> bool:
        if not (0 <= party_index < len(self.party)):
            return False
        adv = self.party[party_index]
        if adv.is_dead:
            self.set_message("This adventurer is dead!")
            return False
        self.boss_adventurer_index = party_index
        return True

    def challenge_boss(self):
        if self.boss_adventurer_index < 0 or not self.boss_square:
            return

        adv = self.party[self.boss_adventurer_index]
        adv_square_mult = self.get_adventurer_multiplier(adv)
        self.boss_square['adventurer'] = adv
        self.boss_square['revealed'] = True
        monster = self.boss_square['monster']

        result = combat.calculate_boss_combat(
            adv, monster, self.boss_square, adv_square_mult, self.keyword_registry,
        )

        if result['victory']:
            self.current_deck.record_kill()
            self._apply_boss_reward(adv, monster, result)
            reward_item = self.current_deck.get_drop_item(
                self.item_registry,
                allowed_ids=self._allowed_item_ids(),
            )
            if reward_item:
                self.delve_loot.append(reward_item)
                result['reward_item'] = reward_item
            self.coins += 3
            result['reward_coins'] = 3
            self.last_king_slayer = adv

            # Boss-kill unlock (#new): permanently unlock any classes tied to
            # this deck. Stash the names so the BOSS_RESULT screen can show
            # them via the status message.
            newly_unlocked = self._unlock_for_boss_kill(self.current_deck.id)
            if newly_unlocked:
                names = []
                for cid in newly_unlocked:
                    tmpl = self.adventurer_registry.get_template(cid)
                    names.append(tmpl['name'] if tmpl else cid)
                result['unlocked_classes'] = newly_unlocked
                result['unlocked_classes_msg'] = "Unlocked: " + ", ".join(names) + "!"
        else:
            adv.is_dead = True
            lost = adv.equipped_items.copy()
            result['lost_items'] = lost
            self.dead_adv_loot.extend(lost)
            adv.equipped_items.clear()
            if self.last_king_slayer is adv:
                self.last_king_slayer = None
            self.current_deck.return_monster(monster)

        self.boss_square['result'] = result
        self.phase = GamePhase.BOSS_RESULT

    def _apply_boss_reward(self, adv: Adventurer, monster: Monster, result: dict):
        roll = random.random()
        if roll < 1 / 8:
            adv.slots += 1
            result['boss_reward'] = {
                'type': 'bonus_slot',
                'desc': f"{adv.name} gained a bonus equipment slot!",
            }
        elif roll < 2 / 8:
            if adv.equipped_items and monster.keywords:
                target_item = random.choice(adv.equipped_items)
                stolen_kw = random.choice(monster.keywords)
                target_item.keywords.append(stolen_kw)
                result['boss_reward'] = {
                    'type': 'keyword_transfer',
                    'desc': f"{target_item.name} gained '{stolen_kw}' from {monster.name}!",
                }
            else:
                self._apply_small_bonus(result)
        else:
            self._apply_small_bonus(result)

    def _apply_small_bonus(self, result: dict):
        candidates = list(result['adventurer'].equipped_items) + list(self.delve_loot)
        if candidates:
            target = random.choice(candidates)
            amount = random.randint(3, 8)
            target.points += amount
            result['boss_reward'] = {
                'type': 'stat_bonus',
                'desc': f"{target.name} gained +{amount} points!",
            }
        else:
            result['boss_reward'] = {'type': 'none', 'desc': "No items to enhance!"}

    def skip_boss(self):
        if self.boss_square:
            self.current_deck.return_monster(self.boss_square['monster'])
        self.end_exploration()

    def continue_after_boss(self):
        self.boss_square = None
        if self.back_row or self.current_deck.round_monsters:
            self.advance_row()
        else:
            self.end_exploration()

    # ---------------------------------------------------------------------
    # Deck-clear bookkeeping (shared helper)
    # ---------------------------------------------------------------------

    def _mark_deck_completed(self, deck: Deck):
        """Mark a deck completed, grant item unlocks, persist meta. Idempotent."""
        first_time = not deck.is_completed
        deck.is_completed = True
        self.completed_decks.add(deck.id)
        if first_time:
            unlocked_items = self._unlock_for_deck_clear(deck.id)
            if unlocked_items:
                self.set_message(
                    f"{deck.name} cleared! +{len(unlocked_items)} new items unlocked.", 300,
                )

    # ---------------------------------------------------------------------
    # Unlock reveal screen
    # ---------------------------------------------------------------------

    def acknowledge_unlock_reveals(self):
        """User clicked Continue on the post-delve unlock screen.

        Clears the pending list and lands in PREPARATION. Persists so a
        crash before the next stable phase won't re-show the reveal.
        """
        self.pending_unlock_reveals = []
        self.unlock_reveal_page = 0
        self.phase = GamePhase.PREPARATION
        self.autosave()

    # ---------------------------------------------------------------------
    # End of expedition
    # ---------------------------------------------------------------------

    def end_exploration(self):
        deck_name = self.current_deck.name if self.current_deck else "Unknown"
        if self.current_deck and not self.current_deck.is_completed:
            self.current_deck.return_unused_round_monsters()

        self.inventory.extend(self.delve_loot)
        self.current_monster = None
        self.selected_adventurer = None
        self.last_combat_result = None
        self.front_row = []
        self.back_row = []
        self.delve_loot = []
        self.boss_square = None
        self.boss_adventurer_index = -1
        self.delve_inv_open = False
        self.delve_recruit_open = False
        self.row_mult_base = 1
        self.rows_completed = 0
        self.earned_multipliers = {}

        if self.current_deck and self.current_deck.is_empty() and not self.current_deck.is_completed:
            self._mark_deck_completed(self.current_deck)
        if self.current_deck and self.current_deck.check_completion():
            self._mark_deck_completed(self.current_deck)

        self.generate_shop()
        self.roster = [a for a in self.roster if not a.is_dead]
        self.party = [a for a in self.party if not a.is_dead]
        if self.last_king_slayer and self.last_king_slayer not in self.roster:
            self.last_king_slayer = None
        self.phase = GamePhase.PREPARATION

        if self.current_deck and self.current_deck.is_completed:
            self.set_message(f" {deck_name} has been permanently cleared!", 300)
        self.current_deck = None

        all_cleared = all(deck.is_completed for deck in self.active_decks.values())
        if all_cleared:
            self.phase = GamePhase.GAME_OVER
            self.set_message(" VICTORY! You\'ve cleared all dungeons!")
            self.pending_unlock_reveals = []  # game over: skip reveal screen
            self.clear_run_save()
        elif len(self.roster) == 0:
            self.phase = GamePhase.GAME_OVER
            self.set_message("Game Over! No adventurers remain.")
            self.pending_unlock_reveals = []
            self.clear_run_save()
        elif self.pending_unlock_reveals:
            # New unlocks to celebrate before going back to preparation.
            self.phase = GamePhase.UNLOCK_REVEAL
            self.autosave()
        else:
            self.autosave()

    # ---------------------------------------------------------------------
    # Progress tracking
    # ---------------------------------------------------------------------

    def get_total_monsters_defeated(self) -> int:
        return sum(deck.monsters_defeated for deck in self.active_decks.values())

    def get_completed_deck_count(self) -> int:
        return len(self.completed_decks)

    def get_shop_rarity_weights(self) -> Tuple[float, float, float, float]:
        total_kills = self.get_total_monsters_defeated()
        completed = self.get_completed_deck_count()

        scrap_w    = max(5,  30 - total_kills * 0.5 - completed * 3)
        common_w   = max(25, 45 - total_kills * 0.3 - completed * 2)
        uncommon_w = min(45, 20 + total_kills * 0.4 + completed * 3)
        rare_w     = min(30, 5  + total_kills * 0.3 + completed * 4)

        return (scrap_w, common_w, uncommon_w, rare_w)

    # ---------------------------------------------------------------------
    # Shop phase
    # ---------------------------------------------------------------------

    def generate_shop(self):
        current_kills = self.get_total_monsters_defeated()
        items_need_refresh = (not self.shop_items) or (current_kills > self.shop_kills_snapshot)

        if items_need_refresh:
            self.shop_kills_snapshot = current_kills
            self.shop_items = []

            scrap_w, common_w, uncommon_w, rare_w = self.get_shop_rarity_weights()
            for _ in range(random.randint(3, 5)):
                rarity = random.choices(
                    ['scrap', 'common', 'uncommon', 'rare'],
                    weights=[scrap_w, common_w, uncommon_w, rare_w],
                )[0]
                item = self._spawn_random_item(rarity)
                if item:
                    self.shop_items.append(item)

        # Adventurers always refresh (based on roster health, not kills)
        self.shop_adventurers = []
        alive_count = sum(1 for a in self.roster if not a.is_dead)
        if alive_count < 4:
            adv_count = 4 - alive_count + random.randint(1, 2)
        else:
            adv_count = random.randint(1, 2)
        for _ in range(adv_count):
            adv = self._spawn_random_adventurer()
            if adv:
                self.shop_adventurers.append(adv)

    def get_item_price(self, item: Item) -> int:
        prices = {'scrap': 1, 'common': 3, 'uncommon': 5, 'rare': 8}
        return prices.get(item.rarity, 3)

    def get_adventurer_price(self, adv: Adventurer) -> int:
        return 5 + (adv.slots - 3) * 2

    def buy_shop_item(self, index: int) -> bool:
        if not (0 <= index < len(self.shop_items)):
            return False
        item = self.shop_items[index]
        price = self.get_item_price(item)
        if self.coins < price:
            self.set_message("Not enough coins!")
            return False
        self.coins -= price
        self.inventory.append(item)
        self.shop_items.pop(index)
        return True

    def buy_shop_adventurer(self, index: int) -> bool:
        if not (0 <= index < len(self.shop_adventurers)):
            return False
        adv = self.shop_adventurers[index]
        price = self.get_adventurer_price(adv)
        if self.coins < price:
            self.set_message("Not enough coins!")
            return False
        self.coins -= price
        self.roster.append(adv)
        self.shop_adventurers.pop(index)
        return True

    def end_shop_phase(self):
        self.roster = [a for a in self.roster if not a.is_dead]
        self.party = []

        all_cleared = all(deck.is_completed for deck in self.active_decks.values())

        if all_cleared:
            self.phase = GamePhase.GAME_OVER
            self.set_message(" VICTORY! You've cleared all dungeons!")
            self.clear_run_save()
        elif len(self.roster) == 0:
            self.phase = GamePhase.GAME_OVER
            self.set_message("Game Over! No adventurers remain.")
            self.clear_run_save()
        else:
            self.phase = GamePhase.PREPARATION
            self.autosave()