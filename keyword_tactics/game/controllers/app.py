"""Game application - the orchestrator.

Owns:
- The pygame window and scaling system
- Fonts and the sprite manager
- The GameState (model)
- The Renderer (view)
- The InputHandler (controller)
- The button list (rebuilt each frame from state)

Run with `await game.run()`.
"""

import asyncio
from typing import Dict, List, Tuple

import pygame

from ..config import COLORS, FPS, SCREEN_WIDTH, SCREEN_HEIGHT
from ..models import GamePhase
from ..views.renderer import Renderer
from ..views.sprite_manager import SpriteManager
from ..views.widgets import Button
from .game_state import GameState
from .input_handler import InputHandler
from .tutorial import Tutorial


class Game:
    """Main game orchestrator. Owns all subsystems and drives the run loop."""

    def __init__(self):
        pygame.init()

        # --- Display / fullscreen / scaling ---
        self.logical_width = SCREEN_WIDTH
        self.logical_height = SCREEN_HEIGHT
        self.is_fullscreen = False

        display_info = pygame.display.Info()
        self.native_width = display_info.current_w
        self.native_height = display_info.current_h

        self.screen = pygame.display.set_mode(
            (self.logical_width, self.logical_height), pygame.RESIZABLE,
        )
        pygame.display.set_caption("Keyword Tactics")

        # All game rendering happens here at base resolution, then scaled
        self.logical_surface = pygame.Surface((self.logical_width, self.logical_height))

        self.render_scale: float = 1.0
        self.render_offset_x: int = 0
        self.render_offset_y: int = 0
        self._update_scale()

        self.clock = pygame.time.Clock()
        self.running = True

        # --- Fonts (bundled into a dict and shared everywhere) ---
        self.fonts: Dict[str, pygame.font.Font] = {
            'tiny':   pygame.font.Font(None, 20),
            'small':  pygame.font.Font(None, 24),
            'medium': pygame.font.Font(None, 32),
            'large':  pygame.font.Font(None, 48),
            'title':  pygame.font.Font(None, 64),
        }

        # --- Subsystems ---
        self.sprite_manager = SpriteManager()
        self.state = GameState()
        self.input_handler = InputHandler(self)
        self.renderer = Renderer(self)

        # Tutorial fairy. Active by default; toggled from the main menu.
        self.tutorial = Tutorial()
        #self.tutorial.start()

        # Buttons are rebuilt every frame from state in `update`
        self.buttons: List[Button] = []

    # ------------------------------------------------------------------
    # Display / coordinate handling
    # ------------------------------------------------------------------

    def _update_scale(self):
        """Recalculate scale + offset after a resize or fullscreen toggle."""
        real_w, real_h = self.screen.get_size()
        scale_x = real_w / self.logical_width
        scale_y = real_h / self.logical_height
        self.render_scale = min(scale_x, scale_y)
        self.render_offset_x = int(
            (real_w - self.logical_width * self.render_scale) / 2,
        )
        self.render_offset_y = int(
            (real_h - self.logical_height * self.render_scale) / 2,
        )

    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode."""
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode(
                (self.native_width, self.native_height),
                pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF,
            )
        else:
            self.screen = pygame.display.set_mode(
                (self.logical_width, self.logical_height),
                pygame.RESIZABLE,
            )
        self._update_scale()

    def screen_to_logical(self, screen_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Convert screen/window coordinates to logical (pre-scale) coordinates."""
        sx, sy = screen_pos
        if self.render_scale == 0:
            return (0, 0)
        lx = int((sx - self.render_offset_x) / self.render_scale)
        ly = int((sy - self.render_offset_y) / self.render_scale)
        return (lx, ly)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        while self.running:
            self.input_handler.handle_events()
            self.update()
            self.renderer.draw()
            self.clock.tick(FPS)
            await asyncio.sleep(0)

        pygame.quit()

    def update(self):
        """Per-frame logic update: tick message timer, rebuild buttons."""
        self.state.update_message()
        self.tutorial.tick(self.state.phase)
        self._rebuild_buttons()

    # ------------------------------------------------------------------
    # Button building (per-phase)
    # ------------------------------------------------------------------

    def _rebuild_buttons(self):
        """Rebuild the button list based on current phase and state."""
        self.buttons.clear()

        # Reference-panel toggle (everywhere except menus)
        if self.state.phase not in (GamePhase.MAIN_MENU, GamePhase.GAME_OVER):
            toggle_text = "v Keywords" if self.state.ref_panel_open else "> Keywords"
            self.buttons.append(Button(
                SCREEN_WIDTH - 130, SCREEN_HEIGHT - 45, 120, 35, toggle_text,
            ))

        phase = self.state.phase

        if phase == GamePhase.MAIN_MENU:
            # Continue: only shown when an in-progress save exists.
            x = SCREEN_WIDTH // 2 - 100
            y = 255
            if self.state.has_resumable_run():
                self.buttons.append(Button(
                    x, y, 200, 44, "Continue",
                    color=COLORS['success'], hover_color=(130, 255, 150),
                ))
                y += 50

            self.buttons.append(Button(x, y, 200, 44, "New Game"))
            y += 50

            tut_text = "Tutorial: ON" if self.tutorial.active else "Tutorial: OFF"
            self.buttons.append(Button(x, y, 200, 36, tut_text))
            y += 40

            fs_text = "Windowed" if self.is_fullscreen else "Fullscreen"
            self.buttons.append(Button(x, y, 200, 36, fs_text))
            y += 40

            debug_text = "Debug: ON" if self.state.debug_unlock_all else "Debug: OFF"
            debug_color = COLORS['warning'] if self.state.debug_unlock_all else COLORS['panel']
            self.buttons.append(Button(
                x, y, 200, 36, debug_text,
                color=debug_color, hover_color=(220, 200, 100),
            ))
            y += 40

            self.buttons.append(Button(
                x, y, 200, 36, "Wipe Save",
                color=COLORS['panel'], hover_color=(120, 60, 60),
            ))
            y += 40

            self.buttons.append(Button(x, y, 200, 36, "Quit"))

        elif phase == GamePhase.PREPARATION:
            # Team is now picked at the start of each delve (via the recruit
            # overlay) — Shop only requires a non-empty roster to enter delve.
            btn = Button(SCREEN_WIDTH - 180, 20, 160, 40, "To Delve")
            btn.enabled = any(not a.is_dead for a in self.state.roster)
            self.buttons.append(btn)

        elif phase == GamePhase.DECK_SELECT:
            # Fixed top-left Back button — always visible regardless of scroll.
            self.buttons.append(Button(20, 20, 160, 40, "Back to Shop"))

            from ..views.screens.deck_select import (
                DECK_LIST_RECT, DECK_ROW_H, deck_visible_count,
            )
            all_ids = list(self.state.deck_registry.all_ids())
            scroll = self.state.deck_select_scroll
            visible = deck_visible_count()
            base_y = DECK_LIST_RECT.y + 10
            for i, deck_id in enumerate(all_ids[scroll:scroll + visible]):
                y = base_y + i * DECK_ROW_H
                active_deck = self.state.active_decks.get(deck_id)
                is_completed = active_deck and (
                    active_deck.is_completed or active_deck.is_empty()
                )

                if is_completed:
                    btn = Button(SCREEN_WIDTH // 2 + 180, y + 25, 120, 35, "Cleared")
                    btn.enabled = False
                    btn.color = (40, 50, 40)
                else:
                    btn = Button(SCREEN_WIDTH // 2 + 180, y + 25, 120, 35, "Enter")
                    btn.deck_id = deck_id  # type: ignore[attr-defined]

                self.buttons.append(btn)
           
            #the +150 was a quick spacing fix because I plan on redoing the ui soon
        elif phase == GamePhase.DELVE_SETUP:
            from ..views.screens.delve import PARTY_TRAY_Y, PARTY_TRAY_H
            inv_open = self.state.delve_inv_open
            # Sit the action row just below the party tray so it never overlaps
            # the character cards (tracks the tray geometry automatically).
            btn_y = PARTY_TRAY_Y + PARTY_TRAY_H + 12
            items_label = "Back" if inv_open else "Items"

            fight_btn = Button(
                SCREEN_WIDTH // 2 - 80, btn_y, 160, 45, "FIGHT!",
                color=COLORS['danger'], hover_color=(255, 150, 100),
            )
            fight_btn.enabled = (
                self.state.all_alive_placed() and not inv_open
            )
            self.buttons.append(fight_btn)
            self.buttons.append(Button(SCREEN_WIDTH // 2 + 100, btn_y, 140, 45, items_label))
            if self.state.party_needs_recruits() and not inv_open:
                self.buttons.append(Button(
                    SCREEN_WIDTH // 2 + 260, btn_y, 140, 45, "Recruit",
                    color=COLORS['success'], hover_color=(130, 255, 150),
                ))
            retreat_btn = Button(SCREEN_WIDTH // 2 - 240, btn_y, 140, 45, "Retreat")
            retreat_btn.enabled = not inv_open
            self.buttons.append(retreat_btn)

        elif phase == GamePhase.DELVE_RESULTS:
            inv_open = self.state.delve_inv_open
            btn_y = SCREEN_HEIGHT - 55 if inv_open else 700
            items_label = "Back" if inv_open else "Items"

            continue_btn = Button(SCREEN_WIDTH // 2 - 80, btn_y, 160, 45, "Continue")
            continue_btn.enabled = not inv_open
            self.buttons.append(continue_btn)
            self.buttons.append(Button(SCREEN_WIDTH // 2 + 100, btn_y, 140, 45, items_label))
            if self.state.party_needs_recruits() and not inv_open:
                self.buttons.append(Button(
                    SCREEN_WIDTH // 2 + 260, btn_y, 140, 45, "Recruit",
                    color=COLORS['success'], hover_color=(130, 255, 150),
                ))

        elif phase == GamePhase.BOSS_CHOICE:
            # Heroes attack one at a time — click a hero card to send them.
            # 'Skip Boss' is only offered before the first hero commits.
            bs = self.state.boss_square
            if bs and not bs.get('fought'):
                self.buttons.append(Button(
                    SCREEN_WIDTH // 2 - 90, 730, 180, 45, "Skip Boss",
                ))

        elif phase == GamePhase.BOSS_RESULT:
            bs = self.state.boss_square
            # Mid-relay -> 'Next Hero'; relay finished -> 'Continue'.
            label = "Next Hero" if (bs and not bs.get('outcome')) else "Continue"
            self.buttons.append(Button(SCREEN_WIDTH // 2 - 90, 730, 180, 50, label))

        elif phase == GamePhase.ROUND_END:
            self.buttons.append(Button(SCREEN_WIDTH // 2 - 100, 720, 200, 50, "End Shopping"))

        elif phase == GamePhase.UNLOCK_REVEAL:
            # Pagination buttons if needed
            total = len(self.state.pending_unlock_reveals)
            page_count = max(1, (total + 11) // 12)
            if page_count > 1:
                self.buttons.append(Button(
                    SCREEN_WIDTH // 2 - 240, 720, 120, 50, "< Prev",
                ))
                self.buttons.append(Button(
                    SCREEN_WIDTH // 2 + 120, 720, 120, 50, "Next >",
                ))
            self.buttons.append(Button(
                SCREEN_WIDTH // 2 - 100, 720, 200, 50, "Continue",
            ))

        elif phase == GamePhase.GAME_OVER:
            self.buttons.append(Button(SCREEN_WIDTH // 2 - 100, 400, 200, 50, "Main Menu"))