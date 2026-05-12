"""InputHandler - dispatches mouse, keyboard, and window events to game state.

Owns the drag-and-drop state since drag is fundamentally an input concept.
The Renderer reads drag state from here when it needs to draw the ghost card.
"""

import pygame
from typing import TYPE_CHECKING, Tuple

from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..models import GamePhase
from ..views import paper_doll

if TYPE_CHECKING:
    from .app import Game


class InputHandler:
    """Handles all pygame events: mouse clicks, drags, scrolls, keyboard."""

    def __init__(self, game: 'Game'):
        self.game = game

        # Drag-and-drop state
        self.dragging: bool = False
        self.drag_adv_index: int = -1
        self.drag_start_pos: Tuple[int, int] = (0, 0)
        self.drag_current_pos: Tuple[int, int] = (0, 0)
        self.drag_source_rect = None

        # Hover position (used for tooltips by the renderer)
        self.hover_mouse_pos: Tuple[int, int] = (0, 0)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def state(self):
        return self.game.state

    # ------------------------------------------------------------------
    # Main dispatcher
    # ------------------------------------------------------------------

    def handle_events(self):
        raw_mouse = pygame.mouse.get_pos()
        mouse_pos = self.game.screen_to_logical(raw_mouse)
        self.hover_mouse_pos = mouse_pos

        # Update button hover states
        for button in self.game.buttons:
            button.update(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.game.running = False

            elif event.type == pygame.VIDEORESIZE:
                if not self.game.is_fullscreen:
                    self.game.screen = pygame.display.set_mode(
                        (event.w, event.h), pygame.RESIZABLE,
                    )
                    self.game._update_scale()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                lpos = self.game.screen_to_logical(event.pos)
                # Try to start a drag in drag-eligible phases.
                # Guard: overlays cover the combat area, so don't start drags
                # while they're open (clicking in the overlay would otherwise
                # also pick up adventurers from the underlying tray/squares).
                if self.state.phase == GamePhase.DELVE_SETUP:
                    overlays_open = (self.state.delve_inv_open or
                                     self.state.delve_recruit_open)
                    if not overlays_open and self._try_start_drag_party(
                        lpos, party_y=345, card_w=300, card_h=160,
                        card_spacing=310, card_x_start=20,
                    ):
                        continue
                elif self.state.phase == GamePhase.BOSS_CHOICE:
                    if self._try_start_drag_party_boss(lpos):
                        continue
                # Normal click
                self._handle_click(event, lpos)

            elif event.type == pygame.MOUSEMOTION:
                if self.dragging:
                    self.drag_current_pos = self.game.screen_to_logical(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.dragging:
                    drop_pos = self.game.screen_to_logical(event.pos)
                    self._handle_drop(drop_pos)
                    self.dragging = False
                    self.drag_adv_index = -1

            elif event.type == pygame.MOUSEWHEEL:
                self._handle_scroll(event, mouse_pos)

            elif event.type == pygame.KEYDOWN:
                self._handle_keypress(event)

    # ------------------------------------------------------------------
    # Drag handling
    # ------------------------------------------------------------------

    def _try_start_drag_party(self, pos, party_y, card_w, card_h, card_spacing,
                              card_x_start) -> bool:
        """Try to start dragging an adventurer card from the party tray.
        Also allows picking up adventurers from front-row squares.
        """
        px, py = pos
        if py < party_y or py > party_y + card_h:
            # Could still pick up from front row even outside the party tray
            pass
        else:
            for i, adv in enumerate(self.state.party):
                card_x = card_x_start + i * card_spacing
                card_rect = pygame.Rect(card_x, party_y, card_w, card_h)
                if card_rect.collidepoint(pos) and not adv.is_dead:
                    self._begin_drag(i, pos, card_rect)
                    return True

        # Allow picking up from front-row squares (drag a placed adventurer back)
        square_rects = [
            pygame.Rect(20, 128, 300, 200),
            pygame.Rect(330, 128, 300, 200),
            pygame.Rect(640, 128, 300, 200),
            pygame.Rect(950, 128, 300, 200),
        ]
        for sq_idx, rect in enumerate(square_rects):
            if sq_idx < len(self.state.front_row) and rect.collidepoint(pos):
                sq = self.state.front_row[sq_idx]
                if sq['adventurer'] is not None:
                    adv = sq['adventurer']
                    party_idx = self.state.party.index(adv) if adv in self.state.party else -1
                    if party_idx >= 0:
                        self._begin_drag(party_idx, pos, rect)
                        return True
        return False

    def _try_start_drag_party_boss(self, pos) -> bool:
        """Start dragging an adventurer card during boss choice."""
        x = 30
        for i, adv in enumerate(self.state.party):
            if adv.is_dead:
                continue
            card_rect = pygame.Rect(x, 480, 280, 200)
            if card_rect.collidepoint(pos):
                self._begin_drag(i, pos, card_rect)
                return True
            x += 300
        return False

    def _begin_drag(self, party_index: int, pos, source_rect):
        self.dragging = True
        self.drag_adv_index = party_index
        self.drag_start_pos = pos
        self.drag_current_pos = pos
        self.drag_source_rect = source_rect

    def _handle_drop(self, pos):
        """Handle dropping a dragged adventurer card."""
        if self.state.phase == GamePhase.DELVE_SETUP:
            square_rects = [
                pygame.Rect(20, 128, 300, 200),
                pygame.Rect(330, 128, 300, 200),
                pygame.Rect(640, 128, 300, 200),
                pygame.Rect(950, 128, 300, 200),
            ]
            for sq_idx, rect in enumerate(square_rects):
                if sq_idx < len(self.state.front_row) and rect.collidepoint(pos):
                    sq = self.state.front_row[sq_idx]
                    adv = self.state.party[self.drag_adv_index]
                    if sq['adventurer'] is None or sq['adventurer'] is adv:
                        self.state.place_adventurer_on_front(self.drag_adv_index, sq_idx)
                        return

        elif self.state.phase == GamePhase.BOSS_CHOICE:
            boss_rect = pygame.Rect(SCREEN_WIDTH // 2 - 200, 80, 400, 250)
            if boss_rect.collidepoint(pos):
                self.state.select_boss_adventurer(self.drag_adv_index)

    # ------------------------------------------------------------------
    # Scroll handling
    # ------------------------------------------------------------------

    def _handle_scroll(self, event, mouse_pos):
        # Reference panel scroll
        if self.state.ref_panel_open:
            panel_rect = pygame.Rect(20, 100, 400, 550)
            if panel_rect.collidepoint(mouse_pos):
                self.state.ref_scroll -= event.y
                filtered = self.state.get_filtered_keywords(self.state.ref_search_text)
                max_scroll = max(0, len(filtered) - 12)
                self.state.ref_scroll = max(0, min(self.state.ref_scroll, max_scroll))
                return

        # Delve inventory panel scroll (right-column item list)
        if self.state.delve_inv_open:
            PX, PY, PW, PH = 60, 40, 1160, 710
            col_top = PY + 55
            left_x = PX + 10
            left_w = 250
            center_x = left_x + left_w + 15
            center_w = 370
            right_x = center_x + center_w + 15
            right_w = PX + PW - right_x - 10
            header_h = 26
            search_h = 26
            list_top = col_top + header_h + 4 + search_h + 6
            list_h = PY + PH - list_top - 50
            item_row_h = 38
            visible_count = list_h // item_row_h

            list_rect = pygame.Rect(right_x, list_top, right_w, list_h)
            if list_rect.collidepoint(mouse_pos):
                # Merged + search-filtered source
                merged = self.state.get_filtered_delve_items()
                self.state.delve_inv_scroll -= event.y
                max_scroll = max(0, len(merged) - visible_count)
                self.state.delve_inv_scroll = max(0, min(self.state.delve_inv_scroll, max_scroll))
                return

        if self.state.phase == GamePhase.PREPARATION:
            from ..views.screens.preparation import INV_PANEL_RECT, ROSTER_RECT
            if INV_PANEL_RECT.collidepoint(mouse_pos):
                filtered = self.state.get_filtered_inventory()
                max_vis = (INV_PANEL_RECT.h - 32) // 28
                self.state.inventory_scroll -= event.y
                max_scroll = max(0, len(filtered) - max_vis)
                self.state.inventory_scroll = max(0, min(self.state.inventory_scroll, max_scroll))

            if ROSTER_RECT.collidepoint(mouse_pos):
                self.state.roster_scroll -= event.y
                max_scroll = max(0, len(self.state.roster) - 6)
                self.state.roster_scroll = max(0, min(self.state.roster_scroll, max_scroll))

    # ------------------------------------------------------------------
    # Click handling
    # ------------------------------------------------------------------

    def _handle_click(self, event, mouse_pos):
        # Tutorial UI takes priority — its Next/Back/X are drawn rectangles,
        # not Button objects, so they need a dedicated hit-test before the
        # normal button loop.
        if self.game.tutorial.active and self._handle_tutorial_click(mouse_pos):
            return

        # Buttons first
        for button in self.game.buttons:
            if button.is_clicked(event):
                self._handle_button_click(button)
                return

        # Reference panel
        if self.state.ref_panel_open:
            if self._handle_ref_panel_click(mouse_pos):
                return

        # Phase-specific
        phase = self.state.phase
        if phase == GamePhase.PREPARATION:
            self._handle_preparation_click(mouse_pos)
        elif phase == GamePhase.DELVE_SETUP:
            self._handle_delve_click(mouse_pos)
        elif phase == GamePhase.DELVE_RESULTS:
            self._handle_delve_click(mouse_pos)  # Inventory panel works during results too
        elif phase == GamePhase.BOSS_CHOICE:
            self._handle_boss_choice_click(mouse_pos)
        elif phase == GamePhase.ROUND_END:
            self._handle_shop_click(mouse_pos)

    def _handle_button_click(self, button):
        text = button.text
        s = self.state

        if text == "New Game":
            s.new_game()
        elif text == "Quit":
            self.game.running = False
        elif text in ["Fullscreen", "Windowed"]:
            self.game.toggle_fullscreen()
        elif text in ["> Keywords", "v Keywords"]:
            s.toggle_ref_panel()
        elif text == "Select Deck":
            if len(s.party) > 0:
                s.phase = GamePhase.DECK_SELECT
            else:
                s.set_message("Add adventurers to party first!")
        elif text == "Back":
            s.phase = GamePhase.PREPARATION
        elif text == "Enter":
            if hasattr(button, 'deck_id'):
                s.start_exploration(button.deck_id)
        elif text.startswith("Enter "):
            # Legacy support
            for did in s.deck_registry.all_ids():
                if did.replace("_", " ") in text.lower() or text.lower().replace("enter ", "") in did:
                    s.start_exploration(did)
                    break
        elif text == "Continue":
            if s.phase == GamePhase.DELVE_RESULTS:
                s.proceed_after_results()
            elif s.phase == GamePhase.BOSS_RESULT:
                s.continue_after_boss()
        elif text == "FIGHT!":
            s.resolve_front_row()
        elif text == "Items":
            s.toggle_delve_inventory()
            s.delve_recruit_open = False
        elif text == "Recruit":
            s.toggle_delve_recruit()
            s.delve_inv_open = False
        elif text == "Retreat":
            s.retreat_from_delve()
        elif text == "Challenge Boss!":
            s.challenge_boss()
        elif text == "Skip Boss":
            s.skip_boss()
        elif text == "End Shopping":
            s.end_shop_phase()
        elif text in ("Tutorial: ON", "Tutorial: OFF"):
            if self.game.tutorial.active:
                self.game.tutorial.stop()
            else:
                self.game.tutorial.start()
        elif text == "Main Menu":
            s.phase = GamePhase.MAIN_MENU

    # ------------------------------------------------------------------
    # Tutorial overlay clicks
    # ------------------------------------------------------------------

    def _handle_tutorial_click(self, mouse_pos) -> bool:
        """Hit-test Spark's fairy and bubble buttons.

        Returns True if the click was consumed (so the rest of the click
        pipeline should stop). Imports the rect helpers locally to avoid
        a hard dependency at module load time — if the tutorial overlay
        module is missing, tutorial just won't function but won't crash.
        """
        from ..views.tutorial_overlay import (
            get_fairy_rect, get_bubble_rect, get_bubble_close_rect,
            get_bubble_next_rect, get_bubble_prev_rect,
        )
        tut = self.game.tutorial

        # Minimized: only the fairy is clickable, and it reopens the bubble.
        if tut.minimized:
            if get_fairy_rect().collidepoint(mouse_pos):
                tut.reopen()
                return True
            return False

        # Bubble open — check buttons in priority order.
        if not tut.has_messages_for_current_phase():
            return False
        if get_bubble_close_rect().collidepoint(mouse_pos):
            tut.toggle_minimized()
            return True
        if get_bubble_next_rect().collidepoint(mouse_pos):
            tut.advance()
            return True
        if tut.message_index > 0 and get_bubble_prev_rect().collidepoint(mouse_pos):
            tut.previous()
            return True
        if get_fairy_rect().collidepoint(mouse_pos):
            tut.toggle_minimized()
            return True
        if get_bubble_rect().collidepoint(mouse_pos):
            # Click anywhere else inside the bubble — advance.
            tut.advance()
            return True
        return False

    # ------------------------------------------------------------------
    # Reference panel clicks
    # ------------------------------------------------------------------

    def _handle_ref_panel_click(self, mouse_pos) -> bool:
        """Returns True if the click was inside the reference panel."""
        panel_rect = pygame.Rect(20, 100, 400, 550)
        if not panel_rect.collidepoint(mouse_pos):
            return False

        x, y = mouse_pos
        s = self.state

        # Keyword list area (scrollable)
        list_area = pygame.Rect(30, 180, 180, 300)
        if list_area.collidepoint(mouse_pos):
            y_offset = y - 180 + s.ref_scroll * 25
            index = y_offset // 25
            filtered = s.get_filtered_keywords(s.ref_search_text)
            if 0 <= index < len(filtered):
                clicked_kw = filtered[index]
                if s.ref_selected_keyword == clicked_kw['id']:
                    s.ref_selected_keyword = None
                else:
                    s.ref_selected_keyword = clicked_kw['id']
            return True

        # Adventurer selection
        adv_area = pygame.Rect(220, 180, 190, 200)
        if adv_area.collidepoint(mouse_pos):
            y_offset = y - 180
            adventurers = s.party if s.party else s.roster[:6]
            index = y_offset // 30
            if 0 <= index < len(adventurers):
                clicked_adv = adventurers[index]
                if s.ref_selected_adventurer == clicked_adv:
                    s.ref_selected_adventurer = None
                else:
                    s.ref_selected_adventurer = clicked_adv
            return True

        # Deck selection
        deck_area = pygame.Rect(220, 390, 190, 150)
        if deck_area.collidepoint(mouse_pos):
            y_offset = y - 390
            deck_ids = list(s.active_decks.keys())
            index = y_offset // 25
            if 0 <= index < len(deck_ids):
                clicked_deck = deck_ids[index]
                if s.ref_selected_deck_id == clicked_deck:
                    s.ref_selected_deck_id = None
                else:
                    s.ref_selected_deck_id = clicked_deck
            return True

        # Clear selections
        clear_area = pygame.Rect(30, 550, 100, 25)
        if clear_area.collidepoint(mouse_pos):
            s.ref_selected_keyword = None
            s.ref_selected_adventurer = None
            s.ref_selected_deck_id = None
            s.ref_search_text = ""
            return True

        return True  # Click was in panel but not on specific element

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def _handle_keypress(self, event):
        # F11 toggles fullscreen anytime
        if event.key == pygame.K_F11:
            self.game.toggle_fullscreen()
            return

        # Reference panel text input
        if self.state.ref_panel_open:
            if event.key == pygame.K_BACKSPACE:
                self.state.ref_search_text = self.state.ref_search_text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.state.toggle_ref_panel()
            elif event.unicode and event.unicode.isprintable():
                self.state.ref_search_text += event.unicode
            return

        # Preparation inventory search text input
        if (self.state.phase == GamePhase.PREPARATION
                and self.state.prep_inv_search_active):
            if event.key == pygame.K_BACKSPACE:
                self.state.prep_inv_search = self.state.prep_inv_search[:-1]
                self.state.inventory_scroll = 0
            elif event.key == pygame.K_ESCAPE:
                self.state.prep_inv_search = ""
                self.state.prep_inv_search_active = False
                self.state.inventory_scroll = 0
            elif event.unicode and event.unicode.isprintable():
                self.state.prep_inv_search += event.unicode
                self.state.inventory_scroll = 0
            return

        # Delve inventory panel search text input
        if (self.state.delve_inv_open
                and self.state.delve_item_search_active):
            if event.key == pygame.K_BACKSPACE:
                self.state.delve_item_search = self.state.delve_item_search[:-1]
                self.state.delve_inv_scroll = 0
            elif event.key == pygame.K_ESCAPE:
                self.state.delve_item_search = ""
                self.state.delve_item_search_active = False
                self.state.delve_inv_scroll = 0
            elif event.unicode and event.unicode.isprintable():
                self.state.delve_item_search += event.unicode
                self.state.delve_inv_scroll = 0
            return

        if event.key == pygame.K_ESCAPE:
            if self.state.phase == GamePhase.DECK_SELECT:
                self.state.phase = GamePhase.PREPARATION
        elif event.key == pygame.K_TAB:
            # Quick toggle for the reference panel
            if self.state.phase not in (GamePhase.MAIN_MENU, GamePhase.GAME_OVER):
                self.state.toggle_ref_panel()

    # ------------------------------------------------------------------
    # Phase-specific click handlers
    # ------------------------------------------------------------------

    def _handle_preparation_click(self, mouse_pos):
        s = self.state
        from ..views.screens.preparation import (
            ROSTER_RECT, PARTY_RECT, INV_SEARCH_RECT, INV_PANEL_RECT,
            STATS_RECT, CARD_RECT, SHOP_RECT, SHOP_ITEM_ROW_H,
        )

        # ---- Inventory search bar (click to activate) ----
        if INV_SEARCH_RECT.collidepoint(mouse_pos):
            s.prep_inv_search_active = True
            return

        # Deactivate search when clicking elsewhere
        s.prep_inv_search_active = False

        # ---- Roster ----
        if ROSTER_RECT.collidepoint(mouse_pos):
            y_offset = mouse_pos[1] - (ROSTER_RECT.y + 30)
            if y_offset >= 0:
                index = (y_offset // 52) + s.roster_scroll
                if 0 <= index < len(s.roster):
                    adv = s.roster[index]
                    if not adv.is_dead and adv not in s.party:
                        s.add_to_party(index)

        # ---- Party ----
        elif PARTY_RECT.collidepoint(mouse_pos):
            y_offset = mouse_pos[1] - (PARTY_RECT.y + 30)
            if y_offset >= 0:
                index = y_offset // 52
                if 0 <= index < len(s.party):
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        s.remove_from_party(index)
                    else:
                        s.selected_party_index = index

        # ---- Inventory ----
        elif INV_PANEL_RECT.collidepoint(mouse_pos):
            y_offset = mouse_pos[1] - (INV_PANEL_RECT.y + 32)
            if y_offset >= 0:
                filtered = s.get_filtered_inventory()
                idx_in_filtered = (y_offset // 28) + s.inventory_scroll
                if 0 <= idx_in_filtered < len(filtered):
                    item = filtered[idx_in_filtered]
                    if pygame.key.get_mods() & pygame.KMOD_CTRL:
                        # Ctrl+click → sell
                        s.sell_item_obj(item)
                    else:
                        # Normal click → equip to selected party member
                        if 0 <= s.selected_party_index < len(s.party):
                            adv = s.party[s.selected_party_index]
                            s.equip_item_obj(item, adv)

        # ---- Stats panel item list — click to unequip (left panel) ----
        elif STATS_RECT.collidepoint(mouse_pos) and 0 <= s.selected_party_index < len(s.party):
            adv = s.party[s.selected_party_index]
            item_start_y = STATS_RECT.y + 168
            y_offset = mouse_pos[1] - item_start_y
            if y_offset >= 0:
                idx = y_offset // 28
                if 0 <= idx < len(adv.equipped_items):
                    s.unequip_item(adv, idx)

        # ---- Equipment panel — chip-based unequip via paper doll (right card) ----
        elif CARD_RECT.collidepoint(mouse_pos) and s.selected_party_index >= 0:
            if s.selected_party_index < len(s.party):
                adv = s.party[s.selected_party_index]
                idx = paper_doll.hit_test_chip(CARD_RECT.x, CARD_RECT.y, mouse_pos, adv)
                if idx is not None:
                    s.unequip_item(adv, idx)

        # ---- Shop panel (#5): buy item ----
        elif SHOP_RECT.collidepoint(mouse_pos):
            self._handle_prep_shop_click(mouse_pos, SHOP_RECT, SHOP_ITEM_ROW_H)

    def _handle_prep_shop_click(self, mouse_pos, shop_rect, row_h):
        """Handle clicks inside the embedded preparation shop panel.

        Items section merges state.shop_items (refreshed-on-kill stock)
        with state.dead_adv_loot (items recovered from fallen heroes).
        """
        s = self.state
        sx, sy = shop_rect.x, shop_rect.y

        merged = [(it, False) for it in s.shop_items] + \
                 [(it, True)  for it in s.dead_adv_loot]

        items_y_start = sy + 34 + 20  # title row + items header
        if merged:
            for i, (item, is_fallen) in enumerate(merged):
                iy = items_y_start + i * row_h
                if iy + row_h > shop_rect.bottom - 6:
                    break
                row_rect = pygame.Rect(shop_rect.x + 4, iy,
                                       shop_rect.w - 8, row_h - 4)
                if row_rect.collidepoint(mouse_pos):
                    if is_fallen:
                        # find this item's index in dead_adv_loot
                        try:
                            dl_idx = s.dead_adv_loot.index(item)
                            s.buy_dead_adv_loot(dl_idx)
                        except ValueError:
                            pass
                    else:
                        try:
                            si_idx = s.shop_items.index(item)
                            s.buy_shop_item(si_idx)
                        except ValueError:
                            pass
                    return

        # Adventurers section (after items + their header)
        adv_y_start = items_y_start + len(merged) * row_h if merged else sy + 34
        adv_y_start += 20
        for i, adv in enumerate(s.shop_adventurers):
            iy = adv_y_start + i * row_h
            if iy + row_h > shop_rect.bottom - 6:
                break
            row_rect = pygame.Rect(shop_rect.x + 4, iy,
                                   shop_rect.w - 8, row_h - 4)
            if row_rect.collidepoint(mouse_pos):
                s.buy_shop_adventurer(i)
                return

    def _handle_delve_click(self, mouse_pos):
        """Clicks during delve phases - mainly for the inventory & recruit overlays."""
        s = self.state

        if s.delve_inv_open:
            # Layout constants must match the inventory panel renderer
            PX, PY, PW, PH = 60, 40, 1160, 710
            col_top = PY + 55
            left_x = PX + 10
            left_w = 250
            center_x = left_x + left_w + 15
            center_w = 370
            right_x = center_x + center_w + 15
            right_w = PX + PW - right_x - 10

            adv_card_h = 80
            adv_gap = 6
            adv_y_start = col_top + 32

            # Adventurer selection (left column)
            for i, adv in enumerate(s.party):
                cy = adv_y_start + i * (adv_card_h + adv_gap)
                adv_rect = pygame.Rect(left_x, cy, left_w, adv_card_h)
                if adv_rect.collidepoint(mouse_pos) and not adv.is_dead:
                    s.delve_selected_adv_idx = i
                    return

            # Equipped items (center column - click to unequip)
            if 0 <= s.delve_selected_adv_idx < len(s.party):
                adv = s.party[s.delve_selected_adv_idx]
                equip_y_start = col_top + 75 + 22
                item_h = 48
                item_gap = 5
                for j in range(len(adv.equipped_items)):
                    iy = equip_y_start + j * (item_h + item_gap)
                    item_rect = pygame.Rect(center_x, iy, center_w, item_h)
                    if item_rect.collidepoint(mouse_pos):
                        s.delve_unequip_item(j)
                        return

            # Search bar above the available-items list
            header_h = 26
            search_h = 26
            search_y = col_top + header_h + 4
            search_rect = pygame.Rect(right_x, search_y, right_w, search_h)
            if search_rect.collidepoint(mouse_pos):
                s.delve_item_search_active = True
                return
            # Click anywhere else outside the search bar deactivates it
            s.delve_item_search_active = False

            # Available items (right column — merged loot+inventory, feature #4)
            list_top = col_top + header_h + 4 + search_h + 6
            list_h = PY + PH - list_top - 50
            item_row_h = 38
            visible_count = list_h // item_row_h
            scroll = s.delve_inv_scroll

            # Build the filtered merged list (same logic as renderer)
            search_lower = s.delve_item_search.lower()
            full_merged = list(s.delve_loot) + list(s.inventory)
            if search_lower:
                def _match(it):
                    if search_lower in it.name.lower():
                        return True
                    for kw_id in it.keywords:
                        kw = s.keyword_registry.get(kw_id)
                        if kw and search_lower in kw.name.lower():
                            return True
                    return False
                filtered = [it for it in full_merged if _match(it)]
            else:
                filtered = full_merged

            for idx in range(visible_count):
                actual_idx = scroll + idx
                if actual_idx >= len(filtered):
                    break
                iy = list_top + 4 + idx * item_row_h
                row_rect = pygame.Rect(right_x + 4, iy, right_w - 8, item_row_h - 4)
                if row_rect.collidepoint(mouse_pos):
                    item = filtered[actual_idx]
                    s.delve_equip_item_obj(item)
                    return

            return  # Consumed click inside panel

        if s.delve_recruit_open:
            available = s.get_available_recruits()
            for j, adv in enumerate(available):
                recruit_rect = pygame.Rect(660, 140 + j * 65, 560, 58)
                if recruit_rect.collidepoint(mouse_pos):
                    s.delve_recruit(j)
                    if not s.party_needs_recruits():
                        s.delve_recruit_open = False
                    return

    def _handle_boss_choice_click(self, mouse_pos):
        s = self.state
        party_area = pygame.Rect(20, 500, 700, 220)
        if party_area.collidepoint(mouse_pos):
            x_offset = mouse_pos[0] - 30
            index = x_offset // 160
            if 0 <= index < len(s.party):
                s.select_boss_adventurer(index)

    def _handle_shop_click(self, mouse_pos):
        s = self.state

        # Shop items
        items_panel = pygame.Rect(20, 100, 600, 350)
        if items_panel.collidepoint(mouse_pos):
            y_offset = mouse_pos[1] - 140
            if y_offset >= 0:
                index = y_offset // 45
                if 0 <= index < len(s.shop_items):
                    s.buy_shop_item(index)

        # Shop adventurers
        adv_panel = pygame.Rect(650, 100, 600, 350)
        if adv_panel.collidepoint(mouse_pos):
            y_offset = mouse_pos[1] - 140
            if y_offset >= 0:
                index = y_offset // 80
                if 0 <= index < len(s.shop_adventurers):
                    s.buy_shop_adventurer(index)