"""Renderer - dispatches drawing to the right screen module for the current phase.

Owns the window/scaling system and the per-frame compositing pipeline.
"""

from typing import TYPE_CHECKING

import pygame

from . import drag_ghost, ref_panel, tooltips, tutorial_overlay
from ..config import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT
from ..models import GamePhase
from . import drag_ghost, ref_panel, tooltips
from .screens import (
    boss as boss_screen,
    deck_select as deck_select_screen,
    delve as delve_screen,
    game_over as game_over_screen,
    main_menu as main_menu_screen,
    preparation as preparation_screen,
    shop as shop_screen,
    unlock_reveal as unlock_reveal_screen,
)

if TYPE_CHECKING:
    from ..controllers.app import Game


class Renderer:
    """Per-phase drawing dispatcher.

    Holds a reference to the Game so it can read the current screen, fonts,
    state, sprite manager, and drag state.
    """

    def __init__(self, game: 'Game'):
        self.game = game

    @property
    def state(self):
        return self.game.state

    @property
    def fonts(self):
        return self.game.fonts

    # ------------------------------------------------------------------
    # Main draw pipeline
    # ------------------------------------------------------------------

    def draw(self):
        """One full frame: render to logical surface, then scale to window."""
        # Logical surface acts as our virtual viewport
        self.game.logical_surface.fill(COLORS['bg'])

        # Make screen=logical_surface temporarily so all our draws go there
        real_screen = self.game.screen
        self.game.screen = self.game.logical_surface
        screen = self.game.logical_surface

        # ---- Phase-specific screen ----
        phase = self.state.phase
        if phase == GamePhase.MAIN_MENU:
            main_menu_screen.draw(screen, self.fonts, self.state)
        elif phase == GamePhase.PREPARATION:
            preparation_screen.draw(screen, self.fonts, self.state)
        elif phase == GamePhase.DECK_SELECT:
            deck_select_screen.draw(screen, self.fonts, self.state)
        elif phase == GamePhase.DELVE_SETUP:
            delve_screen.draw_setup(
                screen, self.fonts, self.state, self.game.sprite_manager,
                self.game.input_handler.dragging,
                self.game.input_handler.drag_adv_index,
            )
        elif phase == GamePhase.DELVE_RESULTS:
            delve_screen.draw_results(screen, self.fonts, self.state,
                                      self.game.sprite_manager)
        elif phase == GamePhase.BOSS_CHOICE:
            boss_screen.draw_choice(
                screen, self.fonts, self.state, self.game.sprite_manager,
                self.game.input_handler.dragging,
                self.game.input_handler.drag_adv_index,
            )
        elif phase == GamePhase.BOSS_RESULT:
            boss_screen.draw_result(screen, self.fonts, self.state)
        elif phase == GamePhase.ROUND_END:
            shop_screen.draw(screen, self.fonts, self.state)
        elif phase == GamePhase.UNLOCK_REVEAL:
            unlock_reveal_screen.draw(
                screen, self.fonts, self.state, self.game.sprite_manager,
            )
        elif phase == GamePhase.GAME_OVER:
            game_over_screen.draw(screen, self.fonts, self.state)

        # ---- Reference panel overlay ----
        if self.state.ref_panel_open:
            ref_panel.draw_ref_panel(screen, self.fonts, self.state)

        # ---- Buttons ----
        for button in self.game.buttons:
            button.draw(screen, self.fonts['medium'])

        # ---- Status message ----
        if self.state.message:
            msg_surf = self.fonts['medium'].render(
                self.state.message, True, COLORS['warning'],
            )
            msg_rect = msg_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 30))
            pygame.draw.rect(
                screen, COLORS['panel'], msg_rect.inflate(20, 10), border_radius=5,
            )
            screen.blit(msg_surf, msg_rect)

        # ---- Combat hover tooltips ----
        ih = self.game.input_handler
        if (
            self.state.phase in (GamePhase.DELVE_SETUP, GamePhase.DELVE_RESULTS, GamePhase.BOSS_CHOICE)
            and not ih.dragging
            and not self.state.delve_inv_open
            and not self.state.delve_recruit_open
            and not self.state.ref_panel_open
        ):
            tooltips.draw_combat_tooltip(screen, self.fonts, self.state, ih.hover_mouse_pos)

        # ---- Preparation hover tooltips (class abilities, item details) ----
        if (
            self.state.phase == GamePhase.PREPARATION
            and not self.state.ref_panel_open
        ):
            tooltips.draw_preparation_tooltip(
                screen, self.fonts, self.state, ih.hover_mouse_pos)

        # ---- Delve-inv overlay tooltips (item details + ability info) ----
        if (
            self.state.delve_inv_open
            and not ih.dragging
            and not self.state.ref_panel_open
        ):
            tooltips.draw_delve_inv_tooltip(
                screen, self.fonts, self.state, ih.hover_mouse_pos)

        # ---- Drag ghost on top ----
        if ih.dragging and ih.drag_adv_index >= 0:
            drag_ghost.draw_drag_ghost(
                screen, self.fonts, self.state,
                ih.drag_adv_index, ih.drag_current_pos,
            )
        # ---- Tutorial fairy ----
        tutorial_overlay.draw_tutorial(screen, self.fonts, self.game.tutorial)

        # ---- Fullscreen hint ----
        fs_text = "F11: Fullscreen" if not self.game.is_fullscreen else "F11: Windowed"
        fs_surf = self.fonts['small'].render(fs_text, True, COLORS['text_dim'])
        screen.blit(fs_surf, (5, SCREEN_HEIGHT - 22))

        # ---- Scale logical -> window ----
        self.game.screen = real_screen
        real_screen.fill((0, 0, 0))  # Letterbox bars

        scaled_w = int(self.game.logical_width * self.game.render_scale)
        scaled_h = int(self.game.logical_height * self.game.render_scale)
        if scaled_w > 0 and scaled_h > 0:
            # Nearest-neighbour scale keeps the pixel art crisp (no smoothing).
            scaled = pygame.transform.scale(
                self.game.logical_surface, (scaled_w, scaled_h),
            )
            real_screen.blit(scaled, (self.game.render_offset_x, self.game.render_offset_y))

        pygame.display.flip()