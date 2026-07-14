"""InputHandler - dispatches mouse, keyboard, and window events to game state.

Owns the drag-and-drop state since drag is fundamentally an input concept.
The Renderer reads drag state from here when it needs to draw the ghost card.
"""

import pygame
from typing import TYPE_CHECKING, Tuple

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

        # Wipe-save click needs a confirmation step. Set True on the first
        # click; second click within the same main-menu visit actually wipes.
        self._wipe_armed: bool = False

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
        # Mirror onto state so screen modules can read hover without plumbing.
        self.state.hover_pos = mouse_pos

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
                if self.state.phase == GamePhase.DELVE_SETUP:
                    overlays_open = (self.state.delve_inv_open or
                                     self.state.delve_recruit_open)
                    if not overlays_open and self._try_start_drag_party(lpos):
                        continue
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

    @staticmethod
    def _front_square_rects():
        """Front-row square hit-boxes, matching delve.draw_setup geometry."""
        from ..views.screens.delve import (
            DELVE_CARD_XS, DELVE_CARD_W, FRONT_ROW_Y, FRONT_ROW_H,
        )
        return [
            pygame.Rect(cx, FRONT_ROW_Y, DELVE_CARD_W, FRONT_ROW_H)
            for cx in DELVE_CARD_XS
        ]

    def _try_start_drag_party(self, pos) -> bool:
        """Begin a drag from the party strip, or from a placed front square."""
        from ..views.screens.delve import party_slot_rects

        for i, slot in enumerate(party_slot_rects(self.state)):
            if slot.collidepoint(pos):
                adv = self.state.party[i]
                if adv.is_dead:
                    # Dead heroes can't be dragged — a click just toggles
                    # their info dropdown.
                    self.state.delve_hero_info_idx = (
                        -1 if self.state.delve_hero_info_idx == i else i)
                    return True
                self._begin_drag(i, pos, slot)
                return True

        square_rects = self._front_square_rects()
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

    def _begin_drag(self, party_index: int, pos, source_rect):
        self.dragging = True
        self.drag_adv_index = party_index
        self.drag_start_pos = pos
        self.drag_current_pos = pos
        self.drag_source_rect = source_rect

    def _handle_drop(self, pos):
        if self.state.phase != GamePhase.DELVE_SETUP:
            return
        s = self.state
        if not (0 <= self.drag_adv_index < len(s.party)):
            return

        dragged = s.party[self.drag_adv_index]
        # The hero is left on its square during the drag, so this tells us
        # where (if anywhere) the drag originated.
        source_sq = s.find_adventurer_square(dragged)

        # A click (barely moved, released where it began, inside the party
        # strip) toggles that hero's info dropdown instead of dragging.
        from ..views.screens.delve import PARTY_STRIP
        began_in_party = (self.drag_source_rect is not None
                          and PARTY_STRIP.contains(self.drag_source_rect))
        moved = (abs(pos[0] - self.drag_start_pos[0])
                 + abs(pos[1] - self.drag_start_pos[1]))
        if began_in_party and moved < 8:
            s.delve_hero_info_idx = (
                -1 if s.delve_hero_info_idx == self.drag_adv_index
                else self.drag_adv_index)
            return
        # Any real drag closes an open dropdown.
        s.delve_hero_info_idx = -1

        # Which front square, if any, did we drop onto?
        target_idx = None
        for sq_idx, rect in enumerate(self._front_square_rects()):
            if sq_idx < len(s.front_row) and rect.collidepoint(pos):
                target_idx = sq_idx
                break

        # Dropped off the board: pull a placed hero off the square (unmatch).
        if target_idx is None:
            if source_sq is not None:
                s.remove_adventurer_from_front(dragged)
            return

        target_sq = s.front_row[target_idx]

        # Released on the hero's own square (e.g. a plain click): toggle off.
        if source_sq is target_sq:
            s.remove_adventurer_from_front(dragged)
            return

        occupant = target_sq['adventurer']
        if occupant is None:
            # Empty square — move/place the dragged hero here.
            s.place_adventurer_on_front(self.drag_adv_index, target_idx)
        elif source_sq is not None:
            # Both heroes are placed — swap their squares.
            source_sq['adventurer'] = occupant
            target_sq['adventurer'] = dragged
        else:
            # Dragged from the party tray onto a matched square — bump the
            # current occupant back to the party and take the square.
            target_sq['adventurer'] = dragged

    # ------------------------------------------------------------------
    # Scroll handling
    # ------------------------------------------------------------------

    def _handle_scroll(self, event, mouse_pos):
        # Mid-delve recruit overlay (pixel-based scroll, clamped by the draw).
        if self.state.delve_recruit_open:
            panel_rect = pygame.Rect(640, 80, 620, 620)
            if panel_rect.collidepoint(mouse_pos):
                self.state.delve_recruit_scroll = max(
                    0, self.state.delve_recruit_scroll - event.y * 40)
                return

        if self.state.ref_panel_open:
            panel_rect = pygame.Rect(20, 100, 400, 550)
            if panel_rect.collidepoint(mouse_pos):
                self.state.ref_scroll -= event.y
                filtered = self.state.get_filtered_keywords(self.state.ref_search_text)
                max_scroll = max(0, len(filtered) - 12)
                self.state.ref_scroll = max(0, min(self.state.ref_scroll, max_scroll))
                return

        if self.state.delve_inv_open:
            from ..views import widgets as _w
            from ..views.screens.delve import INV_MID_RECT, INV_RIGHT_RECT

            _, _, list_rect = _w.get_item_list_geometry(INV_RIGHT_RECT)
            if list_rect.collidepoint(mouse_pos):
                merged = self.state.get_filtered_delve_items()
                visible_count = list_rect.h // _w.ITEM_LIST_ROW_H
                self.state.delve_inv_scroll -= event.y
                max_scroll = max(0, len(merged) - visible_count)
                self.state.delve_inv_scroll = max(0, min(self.state.delve_inv_scroll, max_scroll))
                return

            if (INV_MID_RECT.collidepoint(mouse_pos)
                    and 0 <= self.state.delve_selected_adv_idx < len(self.state.party)):
                adv = self.state.party[self.state.delve_selected_adv_idx]
                self.state.delve_equipped_scroll -= event.y
                max_scroll = max(0, len(adv.equipped_items) - 1)
                self.state.delve_equipped_scroll = max(
                    0, min(self.state.delve_equipped_scroll, max_scroll))
                return


        if getattr(self.state, 'delve_recruit_open', False):
            list_rect = pygame.Rect(660, 142, 580, 520)
            if list_rect.collidepoint(mouse_pos):
                available = self.state.get_available_recruits()
                total_h = len(available) * 74
                
                # Multiplier applied to event.y since this scroll is pixel-based, 
                # whereas other UI elements in the game seem to be index-based.
                scroll_speed = 30 
                current_scroll = getattr(self.state, 'delve_recruit_scroll', 0)
                current_scroll -= event.y * scroll_speed
                
                max_scroll = max(0, total_h - list_rect.height)
                self.state.delve_recruit_scroll = max(0, min(current_scroll, max_scroll))
                return
            
        if self.state.phase == GamePhase.PREPARATION:
            from ..views.screens.preparation import (
                PREP_LEFT_RECT, PREP_MID_RECT, PREP_RIGHT_RECT,
                prep_roster_visible_count,
            )
            from ..views import widgets as _w
            if PREP_RIGHT_RECT.collidepoint(mouse_pos):
                if self.state.prep_view == 'inventory':
                    _, _, list_rect = _w.get_item_list_geometry(PREP_RIGHT_RECT)
                    filtered = self.state.get_filtered_inventory()
                    max_vis = list_rect.h // _w.ITEM_LIST_ROW_H
                    self.state.inventory_scroll -= event.y
                    max_scroll = max(0, len(filtered) - max_vis)
                    self.state.inventory_scroll = max(
                        0, min(self.state.inventory_scroll, max_scroll))
                else:
                    total = (len(self.state.shop_items)
                             + len(self.state.dead_adv_loot))
                    self.state.shop_scroll = max(
                        0, min(self.state.shop_scroll - event.y, total))

            if PREP_LEFT_RECT.collidepoint(mouse_pos):
                self.state.roster_scroll -= event.y
                max_scroll = max(0, len(self.state.roster)
                                 - prep_roster_visible_count())
                self.state.roster_scroll = max(0, min(self.state.roster_scroll, max_scroll))

            if PREP_MID_RECT.collidepoint(mouse_pos):
                if self.state.prep_mid_view == 'deck':
                    max_scroll = max(0, len(self.state.item_deck) - 1)
                    self.state.deck_scroll = max(0, min(
                        self.state.deck_scroll - event.y, max_scroll))
                elif 0 <= self.state.selected_party_index < len(self.state.roster):
                    adv = self.state.roster[self.state.selected_party_index]
                    self.state.prep_equipped_scroll -= event.y
                    max_scroll = max(0, len(adv.equipped_items) - 1)
                    self.state.prep_equipped_scroll = max(
                        0, min(self.state.prep_equipped_scroll, max_scroll))

        if self.state.phase == GamePhase.DECK_SELECT:
            from ..views.screens.deck_select import (
                DECK_LIST_RECT, deck_visible_count,
            )
            if DECK_LIST_RECT.collidepoint(mouse_pos):
                total = len(self.state.deck_registry.all_ids())
                max_scroll = max(0, total - deck_visible_count())
                self.state.deck_select_scroll -= event.y
                self.state.deck_select_scroll = max(
                    0, min(self.state.deck_select_scroll, max_scroll))

    # ------------------------------------------------------------------
    # Click handling
    # ------------------------------------------------------------------

    def _handle_click(self, event, mouse_pos):
        if self.game.tutorial.active and self._handle_tutorial_click(mouse_pos):
            return

        # Any click that isn't on the Wipe Save button itself disarms the wipe
        # confirmation. We detect this here by clearing the flag if the click
        # doesn't get consumed by a Wipe Save button below.
        wipe_was_armed = self._wipe_armed

        for button in self.game.buttons:
            if button.is_clicked(event):
                self._handle_button_click(button)
                if button.text != "Wipe Save" and wipe_was_armed:
                    self._wipe_armed = False
                return

        if wipe_was_armed:
            self._wipe_armed = False

        if self.state.ref_panel_open:
            if self._handle_ref_panel_click(mouse_pos):
                return

        phase = self.state.phase
        if phase == GamePhase.PREPARATION:
            self._handle_preparation_click(mouse_pos)
        elif phase == GamePhase.DELVE_SETUP:
            self._handle_delve_click(mouse_pos)
        elif phase == GamePhase.DELVE_RESULTS:
            self._handle_delve_click(mouse_pos)
        elif phase == GamePhase.BOSS_CHOICE:
            self._handle_boss_choice_click(mouse_pos)
        elif phase == GamePhase.ROUND_END:
            self._handle_shop_click(mouse_pos)

    def _handle_button_click(self, button):
        text = button.text
        s = self.state

        if text == "New Game":
            # Starting fresh wipes any in-progress run save (meta unlocks
            # are preserved). Then new_game() rebuilds + autosaves.
            s.clear_run_save()
            s.new_game()
        elif text == "Continue":
            # The MAIN_MENU "Continue" loads the run save; the in-game
            # "Continue" buttons advance combat / boss flow.
            if s.phase == GamePhase.MAIN_MENU:
                if not s.load_run_from_disk():
                    s.set_message("No save to resume.")
            elif s.phase == GamePhase.DELVE_RESULTS:
                s.proceed_after_results()
            elif s.phase == GamePhase.BOSS_RESULT:
                s.acknowledge_boss_step()
            elif s.phase == GamePhase.UNLOCK_REVEAL:
                s.acknowledge_unlock_reveals()
        elif text == "< Prev" and s.phase == GamePhase.UNLOCK_REVEAL:
            s.unlock_reveal_page = max(0, s.unlock_reveal_page - 1)
        elif text == "Next >" and s.phase == GamePhase.UNLOCK_REVEAL:
            total = len(s.pending_unlock_reveals)
            page_count = max(1, (total + 11) // 12)
            s.unlock_reveal_page = min(page_count - 1, s.unlock_reveal_page + 1)
        elif text in ("Debug: ON", "Debug: OFF"):
            now_on = s.toggle_debug_unlock_all()
            s.set_message(
                "Debug unlocks ON — everything available." if now_on
                else "Debug unlocks OFF.",
            )
        elif text == "Wipe Save":
            if not self._wipe_armed:
                self._wipe_armed = True
                s.set_message("Click Wipe Save again to confirm.")
            else:
                from .save_manager import wipe_everything
                wipe_everything()
                s.reset_unlocks_to_starting()
                s.run_in_progress = False
                self._wipe_armed = False
                s.set_message("Save wiped. All unlocks reset.")
        elif text == "Quit":
            self.game.running = False
        elif text in ["Fullscreen", "Windowed"]:
            self.game.toggle_fullscreen()
        elif text in ["> Keywords", "v Keywords"]:
            s.toggle_ref_panel()
        elif text in ("Select Deck", "To Delve"):
            # No party-size gate: the team is recruited inside the delve.
            if any(not a.is_dead for a in s.roster):
                s.phase = GamePhase.DECK_SELECT
            else:
                s.set_message("Your roster is empty — buy adventurers first.")
        elif (text in ("Back", "Back to Party", "Back to Shop",
                       "Back to Management")
              and s.phase == GamePhase.DECK_SELECT):
            s.phase = GamePhase.PREPARATION
            s.deck_select_scroll = 0
        elif text in ("Enter", "Replay"):
            if hasattr(button, 'deck_id'):
                s.start_exploration(button.deck_id)
        elif text.startswith("Enter "):
            for did in s.deck_registry.all_ids():
                if did.replace("_", " ") in text.lower() or text.lower().replace("enter ", "") in did:
                    s.start_exploration(did)
                    break
        elif text == "FIGHT!":
            s.resolve_front_row()
        elif text == "Items" or text == "Back":
            s.toggle_delve_inventory()
            s.delve_recruit_open = False
        elif text == "Recruit":
            s.toggle_delve_recruit()
            s.delve_inv_open = False
        elif text == "Retreat":
            s.retreat_from_delve()
        elif text == "Next Hero":
            s.acknowledge_boss_step()
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
        from ..views.tutorial_overlay import (
            get_fairy_rect, get_bubble_rect, get_bubble_close_rect,
            get_bubble_next_rect, get_bubble_prev_rect,
        )
        tut = self.game.tutorial

        if tut.minimized:
            if get_fairy_rect().collidepoint(mouse_pos):
                tut.reopen()
                return True
            return False

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
            tut.advance()
            return True
        return False

    # ------------------------------------------------------------------
    # Reference panel clicks
    # ------------------------------------------------------------------

    def _handle_ref_panel_click(self, mouse_pos) -> bool:
        panel_rect = pygame.Rect(20, 100, 400, 550)
        if not panel_rect.collidepoint(mouse_pos):
            return False

        x, y = mouse_pos
        s = self.state

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

        clear_area = pygame.Rect(30, 550, 100, 25)
        if clear_area.collidepoint(mouse_pos):
            s.ref_selected_keyword = None
            s.ref_selected_adventurer = None
            s.ref_selected_deck_id = None
            s.ref_search_text = ""
            return True

        return True

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def _handle_keypress(self, event):
        if event.key == pygame.K_F11:
            self.game.toggle_fullscreen()
            return

        if self.state.ref_panel_open:
            if event.key == pygame.K_BACKSPACE:
                self.state.ref_search_text = self.state.ref_search_text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.state.toggle_ref_panel()
            elif event.unicode and event.unicode.isprintable():
                self.state.ref_search_text += event.unicode
            return

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
            if self.state.phase not in (GamePhase.MAIN_MENU, GamePhase.GAME_OVER):
                self.state.toggle_ref_panel()

    # ------------------------------------------------------------------
    # Phase-specific click handlers
    # ------------------------------------------------------------------

    def _handle_preparation_click(self, mouse_pos):
        """Shop screen clicks — hit-tests the rects stashed by the renderer."""
        s = self.state
        ui = getattr(s, '_prep_ui', {}) or {}

        # Keyword-filter dropdown claims every click while open.
        if s.prep_filter_open:
            for kw_id, r in ui.get('filter_chips', []):
                if r.collidepoint(mouse_pos):
                    if kw_id in s.prep_kw_filter:
                        s.prep_kw_filter.discard(kw_id)
                    else:
                        s.prep_kw_filter.add(kw_id)
                    s.inventory_scroll = 0
                    s.shop_scroll = 0
                    return
            cr = ui.get('filter_clear')
            if cr and cr.collidepoint(mouse_pos):
                s.prep_kw_filter.clear()
                s.inventory_scroll = 0
                s.shop_scroll = 0
                return
            for mode, r in (ui.get('sort_rects') or {}).items():
                if r.collidepoint(mouse_pos):
                    s.prep_sort_mode = mode
                    return
            pr = ui.get('filter_panel')
            if pr and pr.collidepoint(mouse_pos):
                return
            s.prep_filter_open = False
            return

        fb = ui.get('filter_btn')
        if fb and fb.collidepoint(mouse_pos):
            s.prep_filter_open = True
            return

        for lab, r in (ui.get('toggle_rects') or {}).items():
            if r.collidepoint(mouse_pos):
                s.prep_view = 'inventory' if lab == 'Inventory' else 'shop'
                return

        for lab, r in (ui.get('mid_toggle_rects') or {}).items():
            if r.collidepoint(mouse_pos):
                s.prep_mid_view = 'loadout' if lab == 'Loadout' else 'deck'
                return

        # Deck tabs / add / delete (deck-builder view)
        for i, r in ui.get('deck_tabs', []):
            if r.collidepoint(mouse_pos):
                s.set_active_deck(i)
                return
        da = ui.get('deck_add')
        if da and da.collidepoint(mouse_pos):
            s.add_deck()
            return
        dd = ui.get('deck_del')
        if dd and dd.collidepoint(mouse_pos):
            s.delete_active_deck()
            return

        sr = ui.get('search_rect')
        if sr and sr.collidepoint(mouse_pos):
            s.prep_inv_search_active = True
            return
        s.prep_inv_search_active = False

        # Roster: per-hero Unequip, Unequip All, then card selection.
        for roster_idx, r in ui.get('unequip_btns', []):
            if r.collidepoint(mouse_pos):
                if 0 <= roster_idx < len(s.roster):
                    n = s.unequip_all_from(s.roster[roster_idx])
                    if n:
                        s.set_message(f"Returned {n} item(s) to inventory.")
                return
        ua = ui.get('unequip_all')
        if ua and ua.collidepoint(mouse_pos):
            n = s.unequip_all_roster()
            s.set_message(f"Returned {n} item(s) to inventory.")
            return
        for roster_idx, r in ui.get('team_btns', []):
            if r.collidepoint(mouse_pos):
                if 0 <= roster_idx < len(s.roster):
                    s.toggle_team_member(s.roster[roster_idx])
                return
        for roster_idx, r in ui.get('roster_cards', []):
            if r.collidepoint(mouse_pos):
                if s.selected_party_index != roster_idx:
                    s.prep_equipped_scroll = 0
                s.selected_party_index = roster_idx
                return

        # Middle column: deck-builder rows return items to the inventory;
        # loadout equipped rows unequip a single item.
        for item, rr in ui.get('deck_rows', []):
            if rr.collidepoint(mouse_pos):
                s.deck_remove_item(item)
                return
        if 0 <= s.selected_party_index < len(s.roster):
            adv = s.roster[s.selected_party_index]
            for item, rr in (getattr(s, '_prep_equipped_rows', []) or []):
                if rr.collidepoint(mouse_pos) and item in adv.equipped_items:
                    s.unequip_item(adv, adv.equipped_items.index(item))
                    return

        # Right column rows: equip/sell/add-to-deck (inventory view) or
        # buy (shop view).
        for idx, item, rr in ui.get('item_rows', []):
            if rr.collidepoint(mouse_pos):
                if s.prep_view == 'inventory':
                    if pygame.key.get_mods() & pygame.KMOD_CTRL:
                        s.sell_item_obj(item)
                    elif s.prep_mid_view == 'deck':
                        # Toggle: dimmed (already-in-deck) items come back out.
                        if item in s.item_deck:
                            s.deck_remove_item(item)
                        else:
                            s.deck_add_item(item)
                    elif 0 <= s.selected_party_index < len(s.roster):
                        s.equip_item_obj(item, s.roster[s.selected_party_index])
                    else:
                        s.set_message("Select a roster member first (click a card).")
                else:
                    s.buy_shop_item_obj(item)
                return
        for i, rr in ui.get('hire_rows', []):
            if rr.collidepoint(mouse_pos):
                s.buy_shop_adventurer(i)
                return

    def _handle_delve_inventory_click(self, mouse_pos):
        """Clicks on the fullscreen loadout overlay (delve AND boss phases)."""
        s = self.state
        if True:
            from ..views.screens.delve import (
                INV_LEFT_RECT, INV_MID_RECT, INV_CARD_H, INV_CARD_GAP,
            )
            ui = getattr(s, '_delve_ui', {}) or {}

            # Keyword-filter dropdown claims every click while open.
            if s.delve_filter_open:
                for kw_id, r in ui.get('filter_chips', []):
                    if r.collidepoint(mouse_pos):
                        if kw_id in s.delve_kw_filter:
                            s.delve_kw_filter.discard(kw_id)
                        else:
                            s.delve_kw_filter.add(kw_id)
                        s.delve_inv_scroll = 0
                        return
                cr = ui.get('filter_clear')
                if cr and cr.collidepoint(mouse_pos):
                    s.delve_kw_filter.clear()
                    s.delve_inv_scroll = 0
                    return
                for mode, r in (ui.get('sort_rects') or {}).items():
                    if r.collidepoint(mouse_pos):
                        s.delve_sort_mode = mode
                        return
                pr = ui.get('filter_panel')
                if pr and pr.collidepoint(mouse_pos):
                    return
                s.delve_filter_open = False
                return

            fb = ui.get('filter_btn')
            if fb and fb.collidepoint(mouse_pos):
                s.delve_filter_open = True
                return

            # Roster: per-hero Unequip, Unequip All, then card selection.
            for i, r in ui.get('unequip_btns', []):
                if r.collidepoint(mouse_pos):
                    n = s.delve_unequip_all_from(i)
                    if n:
                        s.set_message(f"Moved {n} item(s) to delve loot.")
                    return
            ua = ui.get('unequip_all')
            if ua and ua.collidepoint(mouse_pos):
                n = s.delve_unequip_all_party()
                s.set_message(f"Moved {n} item(s) to delve loot.")
                return
            for i, adv in enumerate(s.party):
                cy = INV_LEFT_RECT.y + 10 + i * (INV_CARD_H + INV_CARD_GAP)
                card = pygame.Rect(INV_LEFT_RECT.x + 8, cy,
                                   INV_LEFT_RECT.w - 16, INV_CARD_H)
                if card.collidepoint(mouse_pos) and not adv.is_dead:
                    if s.delve_selected_adv_idx != i:
                        s.delve_equipped_scroll = 0
                    s.delve_selected_adv_idx = i
                    return

            # Middle column: click an equipped row to unequip
            if INV_MID_RECT.collidepoint(mouse_pos):
                if 0 <= s.delve_selected_adv_idx < len(s.party):
                    adv = s.party[s.delve_selected_adv_idx]
                    for item, rr in (getattr(s, '_delve_equipped_rows', []) or []):
                        if rr.collidepoint(mouse_pos) and item in adv.equipped_items:
                            s.delve_unequip_item(adv.equipped_items.index(item))
                            return
                return

            # Right column: search box focus / click an item to equip
            sr = ui.get('search_rect')
            if sr and sr.collidepoint(mouse_pos):
                s.delve_item_search_active = True
                return
            s.delve_item_search_active = False

            for idx, item, rr in ui.get('item_rows', []):
                if rr.collidepoint(mouse_pos):
                    s.delve_equip_item_obj(item)
                    return

            return

    def _handle_delve_click(self, mouse_pos):
        s = self.state

        if s.delve_inv_open:
            self._handle_delve_inventory_click(mouse_pos)
            return

        if getattr(s, 'delve_recruit_open', False):
            ui_rects = getattr(s, '_delve_recruit_ui', [])
            available = s.get_available_recruits()

            for adv, rect in ui_rects:
                if rect.collidepoint(mouse_pos):
                    if adv in available:
                        idx = available.index(adv)
                        s.delve_recruit(idx)
                        if not s.party_needs_recruits():
                            s.delve_recruit_open = False
                    return

    def _handle_boss_choice_click(self, mouse_pos):
        """Pick a hero, then a target: one of the boss's items, or the boss."""
        s = self.state
        if s.delve_inv_open:
            # Gear-up overlay is open — route clicks there instead.
            self._handle_delve_inventory_click(mouse_pos)
            return
        if not s.boss_square or s.boss_square.get('outcome'):
            return
        ui = getattr(s, '_boss_ui', {}) or {}

        # Hero cards: click selects (click again to deselect).
        for party_idx, rect in ui.get('hero_cards', []):
            if rect.collidepoint(mouse_pos):
                s.boss_selected_hero = (
                    -1 if s.boss_selected_hero == party_idx else party_idx)
                return

        if s.boss_selected_hero < 0:
            return

        # Targets: an equipped item, or the boss itself.
        for item_idx, rect in ui.get('item_cards', []):
            if rect.collidepoint(mouse_pos):
                s.boss_attack_item(s.boss_selected_hero, item_idx)
                return
        br = ui.get('boss_rect')
        if br and br.collidepoint(mouse_pos):
            s.boss_challenge(s.boss_selected_hero)
            return

    def _handle_shop_click(self, mouse_pos):
        s = self.state

        items_panel = pygame.Rect(20, 100, 600, 350)
        if items_panel.collidepoint(mouse_pos):
            y_offset = mouse_pos[1] - 140
            if y_offset >= 0:
                index = y_offset // 45
                if 0 <= index < len(s.shop_items):
                    s.buy_shop_item(index)

        adv_panel = pygame.Rect(650, 100, 600, 350)
        if adv_panel.collidepoint(mouse_pos):
            y_offset = mouse_pos[1] - 140
            if y_offset >= 0:
                index = y_offset // 80
                if 0 <= index < len(s.shop_adventurers):
                    s.buy_shop_adventurer(index)