"""Throwaway integration test for the data-defined dedicated boss (Request C).

Run from the keyword_tactics package root:  python _boss_test.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.controllers.game_state import GameState
from game.models import GamePhase
from game.controllers import combat


def make_hero(gs, item_points):
    """A hero carrying a single big-point item (slots bypassed)."""
    hero = gs.adventurer_registry.create("warrior")
    item = gs.item_registry.create_copy("flame_sword")
    item.points = item_points
    hero.equipped_items.append(item)
    return hero


def fresh_bossonly_deck(gs, deck_id="training_den"):
    """A deck whose regular monsters are all gone — only the boss remains."""
    deck = gs.deck_registry.create(deck_id)
    deck.monsters = []          # regular monsters already defeated
    deck.round_monsters = []
    gs.active_decks = {deck_id: deck}
    gs.completed_decks = set()
    return deck


def check(label, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    assert cond, label


print("== 1. Deck parses the dedicated boss ==")
gs = GameState()
deck = gs.deck_registry.create("training_den")
check("boss_monster loaded", deck.boss_monster is not None)
check("boss name", deck.boss_monster.name == "The Grand Overseer Golem")
check("boss base_points", deck.boss_monster.base_points == 500)
check("guaranteed_drop id", deck.boss_guaranteed_drop == "overseer_core")
check("boss_defeated starts False", deck.boss_defeated is False)
check("has_pending_boss True", deck.has_pending_boss() is True)
check("regular_monsters_cleared False (has monsters)",
      deck.regular_monsters_cleared() is False)
check("is_empty False (boss + monsters)", deck.is_empty() is False)

print("\n== 2. Boss-only delve: start_exploration routes straight to boss ==")
gs = GameState()
deck = fresh_bossonly_deck(gs)
hero = make_hero(gs, 5000)
gs.roster = [hero]
gs.party = [hero]
ok = gs.start_exploration("training_den")
check("start_exploration returned True", ok is True)
check("phase == BOSS_CHOICE", gs.phase == GamePhase.BOSS_CHOICE)
check("boss_square spawned", gs.boss_square is not None)
check("boss_square uses the deck's dedicated boss",
      gs.boss_square["monster"] is deck.boss_monster)
expected_total = combat.boss_total_score(deck.boss_monster.base_points,
                                          deck.boss_monster.keywords)
check(f"boss total score == {expected_total}",
      gs.boss_square["total"] == expected_total)

print("\n== 3. Boss VICTORY -> deck cleared + guaranteed-drop attempt ==")
avail = gs.boss_available_heroes()
check("one finisher available", len(avail) == 1)
gs.fight_boss_hero(gs.party.index(avail[0]))
check("outcome victory", gs.boss_square.get("outcome") == "victory")
check("deck.boss_defeated True", deck.boss_defeated is True)
# guaranteed item id 'overseer_core' is not in items.json yet -> skipped cleanly
check("guaranteed drop skipped (item not defined)",
      "guaranteed_item" not in gs.boss_square)
gs.acknowledge_boss_step()
check("deck.is_empty True after boss kill", deck.is_empty() is True)
check("deck.is_completed True", deck.is_completed is True)
check("deck in completed_decks", "training_den" in gs.completed_decks)
check("phase back to PREPARATION/UNLOCK", gs.phase in (
    GamePhase.PREPARATION, GamePhase.UNLOCK_REVEAL, GamePhase.GAME_OVER))

print("\n== 4. Boss LOSS -> boss persists, deck NOT cleared, re-enterable ==")
gs = GameState()
deck = fresh_bossonly_deck(gs)
weak = make_hero(gs, 1)          # power ~1, far below threshold/score
gs.roster = [weak]
gs.party = [weak]
gs.start_exploration("training_den")
check("phase BOSS_CHOICE", gs.phase == GamePhase.BOSS_CHOICE)
gs.fight_boss_hero(0)
check("outcome defeat", gs.boss_square.get("outcome") == "defeat")
check("finisher died", weak.is_dead is True)
check("deck.boss_defeated still False", deck.boss_defeated is False)
gs.acknowledge_boss_step()
check("deck NOT completed", deck.is_completed is False)
check("deck.is_empty False (boss still pending)", deck.is_empty() is False)
check("has_pending_boss True", deck.has_pending_boss() is True)

# Re-enter with a fresh hero: boss should respawn at full strength.
deck.monsters = []
deck.round_monsters = []
hero2 = make_hero(gs, 5000)
gs.roster = [hero2]
gs.party = [hero2]
gs.start_exploration("training_den")
check("re-entry -> BOSS_CHOICE", gs.phase == GamePhase.BOSS_CHOICE)
check("boss respawned full-strength", gs.boss_square["score"] == expected_total)

print("\n== 5. Regular monsters cleared THEN boss appears (not lifted) ==")
gs = GameState()
deck = gs.deck_registry.create("training_den")
# Keep exactly one easy regular monster, then the dedicated boss.
only = deck.monsters[0]
deck.monsters = [only]
gs.active_decks = {"training_den": deck}
gs.completed_decks = set()
hero = make_hero(gs, 5000)
gs.roster = [hero]
gs.party = [hero]
gs.start_exploration("training_den")
check("phase DELVE_SETUP (regular monster present)",
      gs.phase == GamePhase.DELVE_SETUP)
check("front_row has the regular monster", len(gs.front_row) == 1)
check("front_row is NOT the boss",
      gs.front_row[0]["monster"] is not deck.boss_monster)
# Place hero + resolve the regular row.
gs.front_row[0]["adventurer"] = hero
gs.resolve_front_row()
check("phase DELVE_RESULTS", gs.phase == GamePhase.DELVE_RESULTS)
gs.proceed_after_results()
check("boss appears after regular cleared", gs.phase == GamePhase.BOSS_CHOICE)
check("boss_square is the dedicated boss",
      gs.boss_square["monster"] is deck.boss_monster)

print("\nALL BOSS TESTS PASSED")
