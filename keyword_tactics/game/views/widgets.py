"""Reusable UI widgets: Button, Panel, and shared item-list rendering.

The shared item-list helpers (`filter_items`, `draw_item_search_bar`,
`draw_item_list_panel`) are used by both the preparation screen and the
delve mid-fight inventory panel so the two operate identically and share
all per-row rendering, search filtering, and hover-hit logic.
"""

from typing import Callable, List, Optional, Tuple

import pygame

from .. import theme
from ..config import COLORS

# Standardized spacing tokens (XS=4, S=8, M=16, L=24, XL=40).
XS, S, M, L = theme.XS, theme.S, theme.M, theme.L
R_S, R_M = theme.RADIUS['S'], theme.RADIUS['M']
BW = theme.BORDER_W


def inner_rect(rect: pygame.Rect, padding: int = S) -> pygame.Rect:
    """Return `rect` inset on all sides by `padding` (a spacing token)."""
    return rect.inflate(-2 * padding, -2 * padding)


def draw_panel(surface, rect: pygame.Rect, *, fill=None, border=None,
               radius: int = R_M, border_w: int = BW) -> pygame.Rect:
    """Draw a standard panel/window surface and return its padded content rect."""
    pygame.draw.rect(surface, fill or COLORS['panel'], rect, border_radius=radius)
    pygame.draw.rect(surface, border or COLORS['border'], rect, border_w,
                     border_radius=radius)
    return inner_rect(rect, M)


def draw_text_box(surface, rect: pygame.Rect, *, active: bool = False,
                  radius: int = R_S) -> pygame.Rect:
    """Draw an inset text/search box and return its padded content rect."""
    border = COLORS['accent'] if active else COLORS['border']
    pygame.draw.rect(surface, COLORS['well'], rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, 1, border_radius=radius)
    return inner_rect(rect, S)


class Button:
    """A clickable button with hover state and enabled/disabled flag."""

    def __init__(self, x: int, y: int, width: int, height: int, text: str,
                 color=None, hover_color=None, text_color=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color or COLORS['panel_light']
        self.hover_color = hover_color or COLORS['accent']
        self.text_color = text_color or COLORS['text']
        self.hovered = False
        self.enabled = True

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos) and self.enabled

    def draw(self, surface, font):
        color = self.hover_color if self.hovered else self.color
        if not self.enabled:
            color = COLORS['panel_dark']

        pygame.draw.rect(surface, color, self.rect, border_radius=R_S)
        pygame.draw.rect(surface, COLORS['border'], self.rect, BW, border_radius=R_S)

        text_surf = font.render(
            self.text, True,
            self.text_color if self.enabled else COLORS['text_dim'],
        )
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def is_clicked(self, event) -> bool:
        return (
            event.type == pygame.MOUSEBUTTONDOWN and
            event.button == 1 and
            self.hovered and
            self.enabled
        )


class Panel:
    """A UI panel for grouping content (background + optional title)."""

    def __init__(self, x: int, y: int, width: int, height: int, title: str = ""):
        self.rect = pygame.Rect(x, y, width, height)
        self.title = title

    def draw(self, surface, font, title_font=None):
        pygame.draw.rect(surface, COLORS['panel'], self.rect, border_radius=R_M)
        pygame.draw.rect(surface, COLORS['border'], self.rect, BW, border_radius=R_M)

        if self.title:
            tf = title_font or font
            title_surf = tf.render(self.title, True, COLORS['accent'])
            surface.blit(title_surf, (self.rect.x + S, self.rect.y + S))


# ---------------------------------------------------------------------------
# Shared item-list rendering — used by both preparation and delve screens
# ---------------------------------------------------------------------------

# Rarity styling tables (kept in one place so all panels look identical)
RARITY_ROW_BG = {
    'scrap':    (42, 38, 38),
    'common':   (40, 42, 50),
    'uncommon': (32, 50, 36),
    'rare':     (36, 40, 58),
}
RARITY_BORDER = {
    'scrap':    (90, 80, 80),
    'common':   (100, 100, 110),
    'uncommon': COLORS['success'],
    'rare':     COLORS['accent'],
}
RARITY_DOT = {
    'scrap':    (100, 90, 90),
    'common':   COLORS['text_dim'],
    'uncommon': COLORS['success'],
    'rare':     COLORS['accent'],
}

# Layout (in pixels)
ITEM_LIST_HEADER_H = 26
ITEM_LIST_SEARCH_H = 26
ITEM_LIST_ROW_H    = 38


def filter_items(items, search: str, keyword_registry) -> List:
    """Filter items by name OR keyword name (case insensitive)."""
    if not search:
        return list(items)
    s = search.lower()
    out = []
    for it in items:
        if s in it.name.lower():
            out.append(it); continue
        for kw_id in it.keywords:
            kw = keyword_registry.get(kw_id)
            if kw and s in kw.name.lower():
                out.append(it)
                break
    return out


def get_item_list_geometry(rect: pygame.Rect):
    """Return (header_rect, search_rect, list_rect) inside `rect`."""
    header_rect = pygame.Rect(rect.x, rect.y, rect.w, ITEM_LIST_HEADER_H)
    search_rect = pygame.Rect(rect.x, header_rect.bottom + 4,
                              rect.w, ITEM_LIST_SEARCH_H)
    list_rect = pygame.Rect(rect.x, search_rect.bottom + 6,
                            rect.w, rect.bottom - (search_rect.bottom + 6))
    return header_rect, search_rect, list_rect


def get_visible_item_rects(list_rect: pygame.Rect, n_items: int,
                            scroll: int) -> List[Tuple[int, pygame.Rect]]:
    """Return [(item_index, row_rect), ...] for visible rows."""
    visible_count = list_rect.h // ITEM_LIST_ROW_H
    out = []
    for idx in range(visible_count):
        actual = scroll + idx
        if actual >= n_items:
            break
        iy = list_rect.y + 4 + idx * ITEM_LIST_ROW_H
        row_rect = pygame.Rect(list_rect.x + 4, iy,
                               list_rect.w - 8, ITEM_LIST_ROW_H - 4)
        out.append((actual, row_rect))
    return out


def hit_test_item_list(rect: pygame.Rect, items: List, scroll: int,
                       mouse_pos: Tuple[int, int]):
    """Return the (index, item) the mouse is over, or (None, None)."""
    _, _, list_rect = get_item_list_geometry(rect)
    if not list_rect.collidepoint(mouse_pos):
        return None, None
    for idx, rr in get_visible_item_rects(list_rect, len(items), scroll):
        if rr.collidepoint(mouse_pos):
            return idx, items[idx]
    return None, None


def draw_item_search_bar(screen, fonts, rect: pygame.Rect,
                         search_text: str, active: bool):
    """Render a labelled search bar with caret + Esc hint."""
    border = COLORS['accent'] if active else COLORS['border']
    pygame.draw.rect(screen, COLORS['well'], rect, border_radius=R_S)
    pygame.draw.rect(screen, border, rect, 1, border_radius=R_S)

    lbl = fonts['tiny'].render("Search:", True, COLORS['text_dim'])
    screen.blit(lbl, (rect.x + 6, rect.centery - lbl.get_height() // 2))

    placeholder = "" if search_text else "type to filter keywords/names"
    show_text = search_text or placeholder
    tc = COLORS['text'] if search_text else COLORS['text_dim']
    tsurf = fonts['small'].render(show_text, True, tc)
    screen.blit(tsurf, (rect.x + 52, rect.centery - tsurf.get_height() // 2))

    if active and pygame.time.get_ticks() % 1000 < 500:
        cx = rect.x + 52 + tsurf.get_width() + 2
        pygame.draw.line(screen, COLORS['text'],
                         (cx, rect.y + 4), (cx, rect.bottom - 4), 1)

    esc = fonts['tiny'].render("[Esc] clear", True, COLORS['text_dim'])
    screen.blit(esc, (rect.right - esc.get_width() - 6,
                      rect.centery - esc.get_height() // 2))


def draw_item_row(screen, fonts, state, row_rect: pygame.Rect, item,
                  *, is_new: bool = False, is_fallen: bool = False,
                  sell_price: Optional[int] = None,
                  buy_price: Optional[int] = None,
                  hovered: bool = False,
                  paper_doll_module=None):
    """Render a single item row inside `row_rect`.

    Tags & badges:
      - is_new   → gold "NEW" badge (delve loot)
      - is_fallen → red "FALLEN" badge (dead-adv loot in shop)
      - sell_price → small "sell:N¢" hint (prep inventory)
      - buy_price  → big "N¢" price column (shop entries)
    """
    bg = RARITY_ROW_BG.get(item.rarity, (40, 42, 50))
    border = RARITY_BORDER.get(item.rarity, (100, 100, 110))
    if is_new:
        bg = tuple(min(255, c + 12) for c in bg)
    if hovered:
        bg = tuple(min(255, c + 18) for c in bg)
        border = COLORS['accent']

    pygame.draw.rect(screen, bg, row_rect, border_radius=5)
    pygame.draw.rect(screen, border, row_rect, 1, border_radius=5)

    # rarity dot
    dot_c = RARITY_DOT.get(item.rarity, COLORS['text_dim'])
    pygame.draw.circle(screen, dot_c,
                       (row_rect.x + 10, row_rect.centery), 4)

    # NEW / FALLEN badge (top-left corner)
    if is_new:
        screen.blit(fonts['tiny'].render("NEW", True, COLORS['gold']),
                    (row_rect.x + 2, row_rect.y + 1))
    elif is_fallen:
        screen.blit(fonts['tiny'].render("FALLEN", True, COLORS['danger']),
                    (row_rect.x + 2, row_rect.y + 1))

    # Item thumbnail (slot icon)
    if paper_doll_module is not None:
        paper_doll_module.draw_item_thumbnail(
            screen, item, row_rect.x + 20, row_rect.y + 5, 26)

    # Name
    iname = item.name
    if len(iname) > 20:
        iname = iname[:19] + ".."
    name_color = COLORS['text']
    screen.blit(fonts['small'].render(iname, True, name_color),
                (row_rect.x + 50, row_rect.y + 2))

    # Points (top right)
    pts_color = COLORS['gold']
    pts_surf = fonts['small'].render(f"+{item.points}", True, pts_color)
    screen.blit(pts_surf,
                (row_rect.right - pts_surf.get_width() - 10, row_rect.y + 2))

    # Keywords inline (bottom left) — show all that fit; break on overflow.
    kw_x = row_rect.x + 50
    for kw_id in item.keywords:
        kw = state.keyword_registry.get(kw_id)
        if kw:
            label = kw.name[:8]
            tw = fonts['tiny'].render(label, True, COLORS['bg']).get_width() + 6
            if kw_x + tw > row_rect.right - 60:
                break
            pygame.draw.rect(screen, kw.color,
                             (kw_x, row_rect.y + 20, tw, 12), border_radius=2)
            screen.blit(fonts['tiny'].render(label, True, COLORS['bg']),
                        (kw_x + 3, row_rect.y + 19))
            kw_x += tw + 3

    # Rarity label / sell hint / buy price (bottom right)
    if buy_price is not None:
        bp = fonts['small'].render(f"{buy_price}¢", True, COLORS['gold'])
        screen.blit(bp, (row_rect.right - bp.get_width() - 10,
                         row_rect.y + 20))
    elif sell_price is not None:
        sp = fonts['tiny'].render(f"sell:{sell_price}¢", True, COLORS['text_dim'])
        screen.blit(sp, (row_rect.right - sp.get_width() - 6,
                         row_rect.y + 21))
    else:
        rl = fonts['tiny'].render(f"[{item.rarity}]", True, dot_c)
        screen.blit(rl, (row_rect.right - rl.get_width() - 10,
                         row_rect.y + 21))


def draw_item_list_panel(screen, fonts, state, rect: pygame.Rect,
                         items: List, scroll: int,
                         search_text: str, search_active: bool,
                         header_text: str,
                         is_new_func: Optional[Callable] = None,
                         is_fallen_func: Optional[Callable] = None,
                         sell_price_func: Optional[Callable] = None,
                         buy_price_func: Optional[Callable] = None,
                         paper_doll_module=None,
                         hover_pos: Optional[Tuple[int, int]] = None) -> dict:
    """Render a complete item list panel (header + search + scrollable list).

    Returns a dict with:
      - 'header_rect', 'search_rect', 'list_rect' (pygame.Rect)
      - 'visible' [(idx, item, rect), ...]
      - 'hovered_item' (Item or None)
      - 'max_scroll' (int)
    """
    header_rect, search_rect, list_rect = get_item_list_geometry(rect)

    # Header
    pygame.draw.rect(screen, COLORS['panel_light'], header_rect, border_radius=R_M)
    pygame.draw.rect(screen, COLORS['accent'], header_rect, 1, border_radius=R_M)
    hs = fonts['small'].render(header_text, True, COLORS['accent'])
    screen.blit(hs, (header_rect.centerx - hs.get_width() // 2,
                     header_rect.centery - hs.get_height() // 2))

    # Search bar
    draw_item_search_bar(screen, fonts, search_rect, search_text, search_active)

    # List background
    pygame.draw.rect(screen, COLORS['well'], list_rect, border_radius=R_M)
    pygame.draw.rect(screen, COLORS['border'], list_rect, 1, border_radius=R_M)

    # Empty message
    if not items:
        empty = fonts['small'].render("No items", True, COLORS['text_dim'])
        screen.blit(empty,
                    (list_rect.centerx - empty.get_width() // 2,
                     list_rect.y + 30))
        return {
            'header_rect': header_rect,
            'search_rect': search_rect,
            'list_rect': list_rect,
            'visible': [],
            'hovered_item': None,
            'max_scroll': 0,
        }

    visible_count = list_rect.h // ITEM_LIST_ROW_H
    max_scroll = max(0, len(items) - visible_count)
    scroll = max(0, min(scroll, max_scroll))

    if len(items) > visible_count:
        sc = (f"Scroll: {scroll + 1}-"
              f"{min(scroll + visible_count, len(items))} of {len(items)}")
        screen.blit(fonts['tiny'].render(sc, True, COLORS['text_dim']),
                    (list_rect.right - 155, list_rect.y - 14))

    visible: List[Tuple[int, object, pygame.Rect]] = []
    hovered_item = None
    for idx, rr in get_visible_item_rects(list_rect, len(items), scroll):
        it = items[idx]
        is_new   = bool(is_new_func   and is_new_func(it))
        is_fall  = bool(is_fallen_func and is_fallen_func(it))
        sell_p   = sell_price_func(it) if sell_price_func else None
        buy_p    = buy_price_func(it)  if buy_price_func  else None
        is_hov   = hover_pos is not None and rr.collidepoint(hover_pos)
        if is_hov:
            hovered_item = it
        draw_item_row(screen, fonts, state, rr, it,
                      is_new=is_new, is_fallen=is_fall,
                      sell_price=sell_p, buy_price=buy_p,
                      hovered=is_hov, paper_doll_module=paper_doll_module)
        visible.append((idx, it, rr))

    return {
        'header_rect': header_rect,
        'search_rect': search_rect,
        'list_rect': list_rect,
        'visible': visible,
        'hovered_item': hovered_item,
        'max_scroll': max_scroll,
    }



# ---------------------------------------------------------------------------
# Shared "equipped items" side-panel
# Used by both preparation and delve item screens so both behave identically.
# ---------------------------------------------------------------------------

# Friendly display names for slot types (covers all keys from items.json's
# "_format" plus the 'misc' fallback)
SLOT_DISPLAY_NAMES = {
    'weapon':  'Weapon',
    'hand':    'Off-hand',
    'chest':   'Chest',
    'head':    'Head',
    'belt':    'Belt',
    'cape':    'Cape',
    'boots':   'Boots',
    'float':   'Floating',
    'misc':    'Misc',
}

# Colour for the slot tag (subtle but distinct from rarity/keyword chips)
SLOT_TAG_COLOR = (140, 145, 175)


def draw_equipped_items_panel(screen, fonts, state, rect: pygame.Rect,
                              adv, paper_doll_module=None,
                              scroll: int = 0) -> List[Tuple[object, pygame.Rect]]:
    """Render an "equipped items" side-panel for `adv`.

    Layout (top -> bottom):
      - Header: portrait thumbnail + name + KING/DUNCE badge
      - Stats line (power = base × multiplier)
      - Slots line
      - Ability name (clickable hover area for full description)
      - Divider
      - One row per equipped item, showing thumbnail, name, slot type tag,
        keyword chips, and points.  Clicking a row should call the caller's
        unequip handler.

    Returns a list of [(item, row_rect)] for click hit-testing.
    """
    # Panel background
    pygame.draw.rect(screen, COLORS['panel'], rect, border_radius=R_M)
    pygame.draw.rect(screen, COLORS['accent'], rect, BW, border_radius=R_M)

    pad = M
    PORT = 44
    # --- Header: portrait + name ---
    if paper_doll_module is not None:
        paper_doll_module.draw_adventurer_thumbnail(
            screen, adv, rect.x + pad, rect.y + 12, PORT)
    name_surf = fonts['medium'].render(adv.name, True, COLORS['text'])
    screen.blit(name_surf, (rect.x + pad + PORT + 8, rect.y + 14))

    # Role badge on header right
    role_badge_y = rect.y + 14
    if hasattr(state, 'hero_king') and adv is state.hero_king:
        kb = fonts['small'].render("KING", True, COLORS['gold'])
        screen.blit(kb, (rect.right - kb.get_width() - pad, role_badge_y))
    elif hasattr(state, 'hero_dunce') and adv is state.hero_dunce:
        kb = fonts['small'].render("DUNCE", True, COLORS['text_dim'])
        screen.blit(kb, (rect.right - kb.get_width() - pad, role_badge_y))

    # --- Power & slots ---
    try:
        base = adv.get_base_points()
        mult = adv.get_multiplier()
        power = base * mult
        pwr_text = f"Power: {base} × {mult} = {power}"
    except Exception:
        pwr_text = f"Items: {len(adv.equipped_items)}/{adv.slots}"
    screen.blit(fonts['small'].render(pwr_text, True, COLORS['success']),
                (rect.x + pad, rect.y + 64))

    used, total = len(adv.equipped_items), adv.slots
    slot_c = COLORS['warning'] if used >= total else COLORS['text_dim']
    screen.blit(fonts['small'].render(f"Slots: {used}/{total}", True, slot_c),
                (rect.x + pad, rect.y + 86))

    # Ability name (description comes via hover tooltip)
    if getattr(adv, 'ability_name', None):
        ab = adv.ability_name
        if len(ab) > 28:
            ab = ab[:27] + ".."
        screen.blit(fonts['small'].render(ab, True, COLORS['accent']),
                    (rect.x + pad, rect.y + 108))
        # Hint that hover shows full description
        hint = fonts['tiny'].render("(hover for details)", True, COLORS['text_dim'])
        screen.blit(hint, (rect.x + pad, rect.y + 128))

    # Divider
    div_y = rect.y + 148
    pygame.draw.line(screen, COLORS['divider'],
                     (rect.x + pad, div_y), (rect.right - pad, div_y), 1)

    # --- Equipped items header ---
    hdr_text = "Equipped (click to unequip):"
    screen.blit(fonts['small'].render(hdr_text, True, COLORS['warning']),
                (rect.x + pad, div_y + 6))

    # --- Item rows ---
    ITEM_ROW_H = 38
    list_top = div_y + 32
    list_h = rect.bottom - list_top - 22
    row_rects: List[Tuple[object, pygame.Rect]] = []

    if not adv.equipped_items:
        empty = fonts['small'].render("No items equipped", True, COLORS['text_dim'])
        screen.blit(empty, (rect.x + pad, list_top + 8))
        screen.blit(fonts['tiny'].render("× click any item to remove",
                                          True, COLORS['text_dim']),
                    (rect.x + pad, rect.bottom - 16))
        return row_rects

    max_visible = max(1, list_h // ITEM_ROW_H)
    total = len(adv.equipped_items)
    scroll = max(0, min(scroll, max(0, total - max_visible)))
    visible_slice = adv.equipped_items[scroll:scroll + max_visible]

    for j, item in enumerate(visible_slice):
        iy = list_top + j * ITEM_ROW_H
        row_rect = pygame.Rect(rect.x + 4, iy, rect.w - 8, ITEM_ROW_H - 4)

        bg = RARITY_ROW_BG.get(item.rarity, (40, 42, 50))
        border = RARITY_BORDER.get(item.rarity, (100, 100, 110))
        pygame.draw.rect(screen, bg, row_rect, border_radius=5)
        pygame.draw.rect(screen, border, row_rect, 1, border_radius=5)

        # Item thumbnail
        if paper_doll_module is not None:
            paper_doll_module.draw_item_thumbnail(
                screen, item, row_rect.x + 4, row_rect.y + 4, 26)

        # Item name (truncated)
        iname = item.name
        if len(iname) > 18:
            iname = iname[:17] + ".."
        screen.blit(fonts['small'].render(iname, True, COLORS['text']),
                    (row_rect.x + 34, row_rect.y + 2))

        # Keyword chips — show as many as fit; the break handles overflow.
        kw_x = row_rect.x + 34
        kw_y = row_rect.y + 20
        for kw_id in item.keywords:
            kw = state.keyword_registry.get(kw_id)
            if not kw:
                continue
            label = kw.name[:7]
            chip_text = fonts['tiny'].render(label, True, COLORS['bg'])
            tag_w = chip_text.get_width() + 6
            # Stop when we'd run into the points column on the right
            if kw_x + tag_w > row_rect.right - 36:
                break
            pygame.draw.rect(screen, kw.color,
                             (kw_x, kw_y, tag_w, 12), border_radius=2)
            screen.blit(chip_text, (kw_x + 3, kw_y))
            kw_x += tag_w + 3

        # Points (top-right)
        pts_surf = fonts['small'].render(f"+{item.points}", True, COLORS['gold'])
        screen.blit(pts_surf,
                    (row_rect.right - pts_surf.get_width() - 8, row_rect.y + 2))

        # Mini × icon (bottom-right) — unequip affordance
        x_surf = fonts['tiny'].render("×", True, COLORS['danger'])
        screen.blit(x_surf,
                    (row_rect.right - x_surf.get_width() - 8, row_rect.y + 20))

        row_rects.append((item, row_rect))

    # Scroll affordances
    if scroll > 0:
        screen.blit(fonts['tiny'].render("^ scroll up", True, COLORS['text_dim']),
                    (rect.right - 80, list_top - 12))
    if scroll + max_visible < total:
        screen.blit(fonts['tiny'].render("v more below", True, COLORS['text_dim']),
                    (rect.right - 80, rect.bottom - 30))

    # Footer hint
    screen.blit(fonts['tiny'].render("× click any item to remove",
                                      True, COLORS['text_dim']),
                (rect.x + pad, rect.bottom - 16))

    return row_rects


def hit_test_equipped_panel(adv, row_rects: List[Tuple[object, pygame.Rect]],
                            mouse_pos: Tuple[int, int]):
    """Given the row_rects list from draw_equipped_items_panel, return the
    (index, item) clicked, or (None, None)."""
    for item, rr in row_rects:
        if rr.collidepoint(mouse_pos):
            if item in adv.equipped_items:
                return adv.equipped_items.index(item), item
    return None, None