"""Game phase enumeration - the high-level state machine of the game."""

from enum import Enum


class GamePhase(Enum):
    MAIN_MENU      = "main_menu"
    PREPARATION    = "preparation"
    DECK_SELECT    = "deck_select"
    DELVE_SETUP    = "delve_setup"      # Drag onto front row, see back row, swap items
    DELVE_RESULTS  = "delve_results"    # Front row results, then shift
    BOSS_CHOICE    = "boss_choice"
    BOSS_RESULT    = "boss_result"
    ROUND_END      = "round_end"
    SHOP           = "shop"
    GAME_OVER      = "game_over"
