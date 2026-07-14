"""Tutorial system — Spark, the guide fairy.

Provides contextual, phase-aware tutorial messages that overlay the game UI.
Spark can be toggled on/off from the main menu, minimized to a corner per
screen, and stays quiet on phases the player has already dismissed.

Lives on `Game` (peer to GameState). The Renderer reads it; InputHandler
forwards clicks to it. GameState itself stays unaware of the tutorial.
"""

from typing import Dict, List, Optional, Set

from ..models import GamePhase


# ---------------------------------------------------------------------------
# Per-phase scripts. Keep messages SHORT — every extra line is something the
# player has to dismiss. Trim aggressively; UI affordances should carry their
# own weight where possible.
# ---------------------------------------------------------------------------

TUTORIAL_MESSAGES: Dict[GamePhase, List[str]] = {
    GamePhase.MAIN_MENU: [
        "Hey! Listen! I'm Spark — your guide to Double Edged.",
        "I'll pop up on each screen with tips. Toggle me off below any time.",
        "Click 'New Game' and pick a dungeon. I'll meet you there!",
    ],

    GamePhase.DECK_SELECT: [
        "Pick a dungeon! Each one has its own keyword theme and a final boss.",
        "Check the listed keywords — bring heroes and items that counter them.",
        "Dungeons are persistent: monsters you kill STAY dead across delves.",
        "Scroll if the list is long. Click 'Enter' on a dungeon to delve in.",
    ],

    GamePhase.DELVE_SETUP: [
        "The delve! Monsters on top, your party on the path below.",
        "First time in? The Recruit screen picks your team — up to 4 heroes.",
        "Each monster card shows a big red number: its total defense. Duplicate keywords MULTIPLY it — '2x construct' is no joke.",
        "DRAG a hero from the path onto a monster card to match them. Green number = your hero's power. Green beats red!",
        "Click a matched card to unmatch. Drop a hero on an occupied card to swap. Click a hero on the path for their full info.",
        "KING monsters hit x2, DUNCE at half. Your heroes get the same badges — earned by slaying kings.",
        "Top-right: the FINAL BOSS. Hover its icon to scout its gear and see how many rows away it is.",
        "Click 'Items' to equip gear. You only have what you DREW from your item deck (8 cards) plus loot — each cleared row draws 1 more.",
        "Hover any card for weakness details. TAB opens the keyword reference.",
        "Match every living hero, then FIGHT! Retreat bails out and keeps your loot.",
    ],

    GamePhase.DELVE_RESULTS: [
        "The row is resolved — each card tells you exactly why it went that way.",
        "'Won by N power' means your hero out-hit the defense. 'Short by N' means they fell — and dropped ALL their gear.",
        "Fallen heroes' items land in the shop's fallen stock — you can buy them back later.",
        "Clearing the row drew you a fresh card from your item deck. Check 'Items' before the next row!",
    ],

    GamePhase.BOSS_CHOICE: [
        "The BOSS! See its gear? Those items add points AND keywords to its score — stacked keywords multiply it sky-high.",
        "Pick a hero, then pick a target: SMASH an item (beat its DEF or the hero dies) or click the BOSS itself to challenge.",
        "Destroying items strips their keywords and CRASHES the boss's total. But...",
        "...every item still intact when you win becomes BONUS LOOT. Weaken it, or gamble for the full prize — that's the double edge!",
        "Challenging the boss ends the fight, win or lose. 'Skip Boss' bails out — it'll wait, at full strength.",
    ],

    GamePhase.BOSS_RESULT: [
        "Read the strike: power vs the target's number tells the whole story.",
        "Destroyed gear = the boss's score drops for the next hero. Fallen heroes drop their items.",
        "Beat the boss for coins, drops, a special reward — and bonus loot for every intact item. Lose, and it resets completely.",
    ],

    GamePhase.PREPARATION: [
        "MANAGEMENT! Three columns: your ROSTER, the middle DECK/LOADOUT panel, and your INVENTORY.",
        "The middle panel opens on your ITEM DECK — what delves draw from: 8 cards to start, +1 per cleared row. Use its tabs to keep several decks; one is active.",
        "Deck items stay in your inventory (even while equipped) — the deck is a selection. All 15 slots must be filled to delve. No duplicates, except scrap.",
        "Toggle to Loadout to gear a hero directly: click a roster card to select, click an inventory item to equip; Ctrl+click sells it.",
        "The 'Unequip' buttons strip one hero; 'Unequip All' strips everyone back to inventory.",
        "Use the '+ Team' buttons to save a squad of 4 — they auto-join your delves, skipping the recruit screen.",
        "Heroes enter and leave delves bare-handed: gear comes from your deck draws. Cleared dungeons can be REPLAYED at double strength!",
        "The right column also toggles to the SHOP: buy items and hire adventurers. Stock refreshes as you slay monsters.",
        "Use Search and the Filter button (sorted by your most-stacked keywords) to dig through gear. TAB = keyword reference.",
        "Click 'To Delve' at the bottom when you're ready.",
    ],

    GamePhase.ROUND_END: [
        "Spend your coins, then keep delving — better stock unlocks as you clear dungeons.",
    ],

    GamePhase.GAME_OVER: [
        "End of the run — every dungeon cleared, or the party wiped.",
        "Unlocks are permanent. Next run starts stronger. Back to the menu!",
    ],
}


# ---------------------------------------------------------------------------
# Tutorial state
# ---------------------------------------------------------------------------

class Tutorial:
    """Tracks Spark's state: active flag, current message, dismissed phases."""

    def __init__(self):
        self.active: bool = False
        self.message_index: int = 0
        self.current_phase: Optional[GamePhase] = None
        self.dismissed_phases: Set[GamePhase] = set()
        self.minimized: bool = False

        # Animation timers (incremented every frame in tick())
        self.bob_timer: float = 0.0
        self.attention_pulse: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Turn Spark on (e.g. from the main menu toggle)."""
        self.active = True
        self.message_index = 0
        self.current_phase = None
        self.dismissed_phases = set()
        self.minimized = False

    def stop(self):
        """Turn Spark off entirely until next start()."""
        self.active = False
        self.minimized = False

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def tick(self, current_phase: GamePhase):
        """Called once per frame from Game.update."""
        self.bob_timer += 0.05
        self.attention_pulse += 0.08

        if not self.active:
            return

        # Phase change → reset bubble state
        if current_phase != self.current_phase:
            self.current_phase = current_phase
            self.message_index = 0
            # If we've already shown this phase's tutorial, stay minimized
            self.minimized = current_phase in self.dismissed_phases

    # ------------------------------------------------------------------
    # Content access
    # ------------------------------------------------------------------

    def messages(self) -> List[str]:
        if self.current_phase is None:
            return []
        return TUTORIAL_MESSAGES.get(self.current_phase, [])

    def current_message(self) -> Optional[str]:
        msgs = self.messages()
        if not msgs:
            return None
        if 0 <= self.message_index < len(msgs):
            return msgs[self.message_index]
        return None

    def has_messages_for_current_phase(self) -> bool:
        return bool(self.messages())

    def is_last_message(self) -> bool:
        return self.message_index >= len(self.messages()) - 1

    # ------------------------------------------------------------------
    # Player actions
    # ------------------------------------------------------------------

    def advance(self):
        """Step to next message, or minimize if we're at the end."""
        if not self.has_messages_for_current_phase():
            return
        if self.is_last_message():
            self.minimized = True
            if self.current_phase is not None:
                self.dismissed_phases.add(self.current_phase)
        else:
            self.message_index += 1

    def previous(self):
        """Step back one message (no-op at the start)."""
        if self.message_index > 0:
            self.message_index -= 1

    def reopen(self):
        """Reopen the bubble for the current phase, starting from message 0."""
        if not self.has_messages_for_current_phase():
            return
        self.minimized = False
        self.message_index = 0

    def toggle_minimized(self):
        if self.minimized:
            self.reopen()
        else:
            self.minimized = True
            if self.current_phase is not None:
                self.dismissed_phases.add(self.current_phase)
