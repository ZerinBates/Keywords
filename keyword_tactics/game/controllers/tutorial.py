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
        "Hey! Listen! I'm Spark — your guide.",
        "I'll pop up on each screen with a tip. Toggle me off any time below.",
        "Click 'New Game' when you're ready. I'll meet you there.",
    ],

    GamePhase.PREPARATION: [
        "Camp time. Build your party and gear them up here.",
        "LEFT panel: your roster. Click an adventurer to send them to the PARTY (middle). Shift-click to remove.",
        "RIGHT panel: items in your inventory. Select a party member, then click items to equip them.",
        "Combat math: matching keywords MULTIPLY your damage.",
        "Press TAB anywhere to open the keyword reference — it shows what counters what.",
        "Once your party has 4 adventurers, hit 'Select Deck' (top-right).",
    ],

    GamePhase.DECK_SELECT: [
        "Pick your dungeon. Each deck has its own keyword theme.",
        "Look at the monster keywords listed — your party should counter them.",
        "Decks persist across runs: monsters you kill stay dead.",
    ],

    GamePhase.DELVE_SETUP: [
        "The delve! Each square is one fight.",
        "There is a king badge and a dunce badge the dunce divides your total by 2 and the king doubles your total killing a king enemy makes that character a king next.",
        "Optimize your character stats by rearranging items"
        "DRAG adventurers from the bottom tray onto squares to assign matchups.",
        "Each square has a bonus — buff or resist a keyword. Read it before placing.",
        "All living adventurers must be placed before FIGHT! becomes clickable.",
        "Click 'Items' to swap gear mid-delve. 'Retreat' bails out, keeping your loot.",
    ],

    GamePhase.DELVE_RESULTS: [
        "Combat resolved. Wins earn coins and loot drops.",
        "Adventurers who LOST died and dropped all their items. Plan around that.",
        "Earned multipliers carry forward — they matter a lot for the boss fight.",
    ],

    GamePhase.BOSS_CHOICE: [
        "A BOSS! Only ONE adventurer fights it.",
        "The boss multiplier is huge. Send your strongest, best-equipped pick.",
        "Drag an adventurer onto the boss card to choose them. 'Skip Boss' to leave with what you've got.",
    ],

    GamePhase.BOSS_RESULT: [
        "Boss fight done.",
        "If you won, the boss drops a special reward: bonus slot, stolen keyword, or stat bump.",
    ],

    GamePhase.ROUND_END: [
        "Shop! Spend coins on items and new adventurers.",
        "Shop quality scales with your progress — clear more decks for better stock.",
    ],

    GamePhase.GAME_OVER: [
        "End of run.",
        "Either you cleared every dungeon or your party was wiped. Either way — back to menu.",
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
