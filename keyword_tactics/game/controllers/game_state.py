"""GameState - central state container and high-level game logic.

This is the 'M' in MVC for the dynamic, mutable game state. It owns all
runtime state (player resources, party, decks-in-progress, current phase)
and exposes methods to mutate that state in well-defined ways.

It delegates pure combat math to controllers.combat and JSON loading to
controllers.data_loader.
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
from . import combat
from .data_loader import load_all_data


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
        self.delve_inv_source: str = 'loot'              # kept for compat but unused in merged view
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
        self.prep_inv_search: str = ""        # keyword/name filter for inventory panel
        self.prep_inv_search_active: bool = False

        # ---- Delve inventory search ----
        self.delve_item_search: str = ""
        self.delve_item_search_active: bool = False

        # ---- Shop kill gating (feature #6 from prior turn) ----
        # Shop only regenerates when monsters have been killed since last gen.
        self.shop_kills_snapshot: int = 0

        # ---- Items recovered from dead adventurers (persist in shop) ----
        self.dead_adv_loot: List[Item] = []

        # ---- King / Dunce system (new feature #6) ----
        # Per-row roles for monsters live on the square dicts themselves
        # (sq['is_king'], sq['is_dunce']).  These two attrs track HERO roles
        # which persist between rows.
        self.hero_king: Optional[Adventurer] = None
        self.hero_dunce: Optional[Adventurer] = None
        # Whoever killed the king monster carries the title forward.
        self.last_king_slayer: Optional[Adventurer] = None
        # First combat row of the entire game — heroes have no king/dunce.
        self.first_match_done: bool = False

    # ---------------------------------------------------------------------
    # Game lifecycle
    # ---------------------------------------------------------------------

    def _initialize_decks(self):
        """Create persistent deck instances for this game session."""
        self.active_decks = {}
        for deck_id in self.deck_registry.all_ids():
            deck = self.deck_registry.create(deck_id)
            if deck:
                # Don't shuffle - monsters stay ordered weakest to strongest
                self.active_decks[deck_id] = deck
        print(f"Initialized {len(self.active_decks)} persistent decks")

    def new_game(self):
        """Start a new game from scratch."""
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

        # Reset reference panel
        self.ref_panel_open = False
        self.ref_search_text = ""
        self.ref_selected_keyword = None
        self.ref_selected_adventurer = None
        self.ref_selected_deck_id = None
        self.ref_scroll = 0

        self._initialize_decks()

        # Starting adventurers (random + commoners)
        for _ in range(4):
            adv = self.adventurer_registry.random_adventurer()
            if adv:
                self.roster.append(adv)
        for _ in range(4):
            basic = self.adventurer_registry.create("commoner")
            if basic:
                self.roster.append(basic)

        # Starting items (mix of scrap and common)
        for _ in range(4):
            item = self.item_registry.random_item('scrap')
            if item:
                self.inventory.append(item)
        for _ in range(7):
            item = self.item_registry.random_item('common')
            if item:
                self.inventory.append(item)
        item = self.item_registry.create_copy('insect_bow')
        
        if item:
            self.inventory.append(item)
        self.phase = GamePhase.PREPARATION
        self.set_message("Welcome! Equip your adventurers and choose a deck to explore.")

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
        """Get info about all keywords for the reference panel."""
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
        """Get keywords filtered by search text."""
        all_kw = self.get_all_keywords_info()
        if not search:
            return all_kw
        s = search.lower()
        return [kw for kw in all_kw if s in kw['name'].lower() or s in kw['id'].lower()]

    def get_deck_keywords_analysis(self, deck_id: str) -> dict:
        """Analyze all keywords in a deck and what counters them."""
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
        """Analyze an adventurer's keyword loadout: what they're weak/strong against."""
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
        """Compare a single keyword against an adventurer's loadout."""
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
        """Equip an item from inventory to an adventurer."""
        if not (0 <= inventory_index < len(self.inventory)):
            return False
        if not adv.can_equip():
            self.set_message(f"{adv.name} has no free slots!")
            return False

        item = self.inventory.pop(inventory_index)
        adv.equip(item)
        return True

    def equip_item_obj(self, item: Item, adv: Adventurer) -> bool:
        """Equip a specific item object from inventory to an adventurer."""
        if item not in self.inventory:
            return False
        if not adv.can_equip():
            self.set_message(f"{adv.name} has no free slots!")
            return False
        self.inventory.remove(item)
        adv.equip(item)
        return True

    def unequip_item(self, adv: Adventurer, item_index: int) -> bool:
        """Unequip an item back to inventory."""
        if not (0 <= item_index < len(adv.equipped_items)):
            return False
        item = adv.equipped_items.pop(item_index)
        self.inventory.append(item)
        return True

    def sell_item(self, inventory_index: int) -> bool:
        """Sell an item from inventory for coins (about half buy price)."""
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
        """Sell a specific item object from inventory."""
        if item not in self.inventory:
            return False
        idx = self.inventory.index(item)
        return self.sell_item(idx)

    def get_item_sell_price(self, item: Item) -> int:
        sell_prices = {'scrap': 1, 'common': 1, 'uncommon': 3, 'rare': 5}
        return sell_prices.get(item.rarity, 1)

    def get_filtered_inventory(self) -> List[Item]:
        """Return inventory filtered by prep_inv_search (name or keyword match)."""
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
        """Return merged delve_loot + inventory filtered by delve_item_search."""
        merged = list(self.delve_loot) + list(self.inventory)
        if not self.delve_item_search:
            return merged
        return [it for it in merged if self._matches_search(it, self.delve_item_search)]

    # ---------------------------------------------------------------------
    # Shop — dead-adventurer loot (#2)
    # ---------------------------------------------------------------------

    def buy_dead_adv_loot(self, index: int) -> bool:
        """Buy an item that was lost by a dead adventurer."""
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
        """Begin a seamless delve into a deck."""
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
        self.row_mult_base = 1   # kept for compat, unused in king/dunce system
        self.boss_square = None
        self.boss_adventurer_index = -1
        self.delve_inv_open = False
        self.delve_inv_scroll = 0
        self.delve_inv_source = 'loot'
        self.delve_selected_adv_idx = -1
        self.delve_item_search = ""
        self.delve_item_search_active = False
        # earned_multipliers retained as a no-op for boss compat
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
    # King / Dunce role assignment (new feature #6)
    # ---------------------------------------------------------------------

    def _assign_hero_roles_for_row(self):
        """Set self.hero_king / self.hero_dunce for the upcoming row.

        Rules:
          - First combat match ever: no hero king, no hero dunce.
          - After that: hero_king = whoever killed the previous king monster
            (None if no king has been slain yet, or slayer is dead/gone).
            hero_dunce = a random alive party member that ISN'T the king.
        """
        if not self.first_match_done:
            # Very first combat row of the entire game — no roles yet.
            self.hero_king = None
            self.hero_dunce = None
            return

        # Hero king carries over from last king-slayer if still alive & in party
        if (self.last_king_slayer
                and self.last_king_slayer in self.party
                and not self.last_king_slayer.is_dead):
            self.hero_king = self.last_king_slayer
        else:
            self.hero_king = None

        # Hero dunce: random alive party member that isn't the king
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
                'multiplier': 1,    # multipliers removed; kept as 1 for backward compat
                'bonus': combat.generate_square_bonus(self.keyword_registry),
                'adventurer': None,
                'result': None,
                'is_king':  False,
                'is_dunce': False,
            })

        # King = strongest monster (by base_points).  Dunce = random other.
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
        """Adventurer's earned multiplier (from last square they defeated)."""
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
        """Every living adventurer is on a front-row square."""
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
        """Equip an item from the currently selected source (loot or inventory)."""
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
        """Equip from merged loot+inventory list (delve_loot first, then inventory)."""
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
        """Equip a specific item from either delve_loot or inventory."""
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
        """Unequip an item — it goes to the delve loot pile."""
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
        """Roster members not in the current party and not dead."""
        return [a for a in self.roster if a not in self.party and not a.is_dead]

    def party_needs_recruits(self) -> bool:
        """Party has fewer than 4 alive AND there are recruits available."""
        alive_in_party = sum(1 for a in self.party if not a.is_dead)
        return alive_in_party < 4 and len(self.get_available_recruits()) > 0

    def delve_recruit(self, recruit_index: int) -> bool:
        """Add a recruit from the available roster into the party mid-delve."""
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
        """Run combat for every occupied square; track king-slayer; push lost items."""
        for sq in self.front_row:
            if sq['adventurer'] is not None:
                # Pass hero king/dunce flags through to combat
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
                    # Track king-slayer for next row's hero king (#6)
                    if sq.get('is_king'):
                        self.last_king_slayer = adv
                    reward = self.current_deck.get_drop_item(self.item_registry)
                    if reward:
                        self.delve_loot.append(reward)
                        result['reward_item'] = reward
                    self.coins += 1
                    result['reward_coins'] = 1
                else:
                    adv.is_dead = True
                    lost = adv.equipped_items.copy()
                    result['lost_items'] = lost
                    # Lost items go to the shop's dead-adv loot list (#2)
                    self.dead_adv_loot.extend(lost)
                    adv.equipped_items.clear()
                    # If the dead adventurer was the previous king, clear that
                    if self.last_king_slayer is adv:
                        self.last_king_slayer = None
                    self.current_deck.return_monster(sq['monster'])
            else:
                # Skipped square — monster goes back to deck
                self.current_deck.return_monster(sq['monster'])
        self.rows_completed += 1
        # First combat row complete — hero king/dunce now applies on subsequent rows
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
        """Shift back row to front, build new back row, and possibly spawn boss."""
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
                self.current_deck.is_completed = True
                self.completed_decks.add(self.current_deck.id)
            self.end_exploration()
            return

        # If this is the final row and there's more than one square, lift the
        # last one into a boss slot.
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
        # Reassign hero roles now that the new row is built (#6)
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
                self.current_deck.is_completed = True
                self.completed_decks.add(self.current_deck.id)
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
            reward_item = self.current_deck.get_drop_item(self.item_registry)
            if reward_item:
                self.delve_loot.append(reward_item)
                result['reward_item'] = reward_item
            self.coins += 3
            result['reward_coins'] = 3
            # Bosses count as kings too (#6)
            self.last_king_slayer = adv
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
        """Roll the boss-victory reward (slot, keyword steal, or stat bump)."""
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
        """Add a small +points bonus to a random equipped or loot item."""
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
            self.current_deck.is_completed = True
            self.completed_decks.add(self.current_deck.id)
        if self.current_deck and self.current_deck.check_completion():
            self.completed_decks.add(self.current_deck.id)

        # Auto-shop at end-of-delve removed (#5): regenerate shop stock
        # (kill-gated) so it's ready in prep, but go straight to PREPARATION.
        self.generate_shop()
        # Prune dead adventurers from roster and keep surviving party
        self.roster = [a for a in self.roster if not a.is_dead]
        self.party = [a for a in self.party if not a.is_dead]
        # Drop hero-king tracking if that adv is gone
        if self.last_king_slayer and self.last_king_slayer not in self.roster:
            self.last_king_slayer = None
        self.phase = GamePhase.PREPARATION

        if self.current_deck and self.current_deck.is_completed:
            self.set_message(f" {deck_name} has been permanently cleared!", 300)
        self.current_deck = None

        # Did this clear all decks?  Or wipe out the roster?
        all_cleared = all(deck.is_completed for deck in self.active_decks.values())
        if all_cleared:
            self.phase = GamePhase.GAME_OVER
            self.set_message(" VICTORY! You\'ve cleared all dungeons!")
        elif len(self.roster) == 0:
            self.phase = GamePhase.GAME_OVER
            self.set_message("Game Over! No adventurers remain.")

    # ---------------------------------------------------------------------
    # Progress tracking
    # ---------------------------------------------------------------------

    def get_total_monsters_defeated(self) -> int:
        return sum(deck.monsters_defeated for deck in self.active_decks.values())

    def get_completed_deck_count(self) -> int:
        return len(self.completed_decks)

    def get_shop_rarity_weights(self) -> Tuple[float, float, float, float]:
        """Calculate shop rarity weights based on overall progress.

        Returns (scrap, common, uncommon, rare).

        Progression:
        - Base: 30% scrap, 45% common, 20% uncommon, 5% rare
        - Each kill adds slight improvement
        - Each completed deck adds significant bonus
        - Max (40+ kills, 6 decks): 5% scrap, 30% common, 40% uncommon, 25% rare
        """
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
        """Generate shop offerings only when new monsters have been killed.

        Feature #6: shop only refreshes if the kill count has increased since
        the last time generate_shop produced a stock.  The adventurer list
        always refreshes because it depends on roster health, not kills.
        """
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
                item = self.item_registry.random_item(rarity)
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
            adv = self.adventurer_registry.random_adventurer()
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
        """End shopping; either start the next round, win, or game-over."""
        self.roster = [a for a in self.roster if not a.is_dead]
        self.party = []

        all_cleared = all(deck.is_completed for deck in self.active_decks.values())

        if all_cleared:
            self.phase = GamePhase.GAME_OVER
            self.set_message(" VICTORY! You've cleared all dungeons!")
        elif len(self.roster) == 0:
            self.phase = GamePhase.GAME_OVER
            self.set_message("Game Over! No adventurers remain.")
        else:
            self.phase = GamePhase.PREPARATION