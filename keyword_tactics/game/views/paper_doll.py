"""Character card with paper-doll equipment view.

Renders an Adventurer as a trading-card-style rectangle: name banner on top,
a sprite (or programmatic silhouette) in the middle with equipped items
overlaid at slot-specific positions, and stats at the bottom.

Item art resolution per equipped item:
    1) assets/items/{item_id}.png             - item-specific art
    2) assets/items/_default_{slot}.png       - generic fallback for a slot
    3) Programmatic placeholder chip          - obvious "art missing" marker

Item POSITION and SIZE per slot come from SLOT_LAYOUT, with optional
per-character overrides loaded from `assets/portraits/slot_overrides.json`.

Override JSON shape (each slot is optional; missing fields use defaults):

    {
      "wizard": {
        "head":  [100, 22],                              // pos only
        "chest": { "pos": [100, 95], "size": [70, 90] }, // pos + size
        "cape":  { "size": [100, 140] }                  // size only
      },
      "goblin": {
        "weapon": [148, 110]
      }
    }
"""

import hashlib
import json
import os
from typing import Optional

import pygame

from .. import theme
from ..config import COLORS


# ---------------------------------------------------------------------------
# Sprite loading (with caching)
# ---------------------------------------------------------------------------

_PORTRAIT_DIR = os.path.join("assets", "portraits")
_ITEM_DIR = os.path.join("assets", "items")

# None in a cache means "we looked, nothing's there" — don't keep retrying.
_portrait_cache: dict = {}
_item_cache: dict = {}
_slot_default_cache: dict = {}


def _try_load(path: str) -> Optional[pygame.Surface]:
    """Load a PNG with alpha if it exists, else return None."""
    if not os.path.exists(path):
        return None
    try:
        return pygame.image.load(path).convert_alpha()
    except pygame.error:
        return None


def _get_portrait(adv_id: str) -> Optional[pygame.Surface]:
    """Cached portrait Surface for `adv_id`, or None if no PNG exists."""
    if adv_id in _portrait_cache:
        return _portrait_cache[adv_id]
    surf = _try_load(os.path.join(_PORTRAIT_DIR, f"{adv_id}.png"))
    _portrait_cache[adv_id] = surf
    return surf


def _get_item_sprite(item_id: str) -> Optional[pygame.Surface]:
    """Cached item icon Surface for `item_id`, or None if missing."""
    if not item_id:
        return None
    if item_id in _item_cache:
        return _item_cache[item_id]
    surf = _try_load(os.path.join(_ITEM_DIR, f"{item_id}.png"))
    _item_cache[item_id] = surf
    return surf


def _get_slot_default_sprite(slot: str) -> Optional[pygame.Surface]:
    """Default art for a slot. Looks for assets/items/_default_{slot}.png."""
    if not slot:
        return None
    if slot in _slot_default_cache:
        return _slot_default_cache[slot]
    surf = _try_load(os.path.join(_ITEM_DIR, f"_default_{slot}.png"))
    _slot_default_cache[slot] = surf
    return surf


# ---------------------------------------------------------------------------
# Card layout
# ---------------------------------------------------------------------------

CARD_W = 280
CARD_H = 380

BANNER_H = 36

DOLL_X = 40
DOLL_Y = BANNER_H + 8
DOLL_W = CARD_W - 80     # 200
DOLL_H = 250

FOOTER_H = 70

# Per-extra-item nudge when multiple items share a slot
STACK_OFFSET = 8

# Placeholder/misc-strip chip size (only used when no art is found)
MISC_CHIP_W = 26
MISC_CHIP_H = 22


# Default slot layout. `pos` is RELATIVE to the doll viewport (DOLL_X, DOLL_Y
# origin). `size` is in pixels. Capes draw behind the body; everything else
# draws on top. Float items are positioned at the card corners (pos = None).
#'head': {'pos': ((DOLL_W // 2) - 38(x access right)), -10(y access up))), 'size': ((x)156, (y)144)},
SLOT_LAYOUT: dict = {
    'head':   {'pos': (DOLL_W // 2-3,      50),  'size': (156, 156)},
    'cape':   {'pos': (DOLL_W // 2,      115), 'size': (220, 230)},
    'chest':  {'pos': (DOLL_W // 2,      125), 'size': (130, 130)},
    'weapon': {'pos': (DOLL_W // 2 + 85, 135), 'size': (240, 240)},
    'hand':   {'pos': (DOLL_W // 2 - 48, 127), 'size': (180, 180)},
    'belt':   {'pos': (DOLL_W // 2-2,      150), 'size': (120, 120)},
    'boots':  {'pos': (DOLL_W // 2+2,      190), 'size': (110, 140)},
    'float':  {'pos': (DOLL_W // 2,      0),                    'size': (75, 75)},
}

SLOTS_BEHIND_BODY = {'cape'}

# Second weapon/hand renders mirrored on the opposite side; 3rd+ go behind+larger.
MIRRORED_SLOTS = {'weapon', 'hand'}
# Extra items in these slots render *behind* the first item, slightly larger,
# so they "peek out" without changing the primary item's position.
BEHIND_LARGER_SLOTS = {'chest', 'boots', 'head', 'belt'}
BEHIND_SCALE_FACTOR = 1.15   # 15 % bigger per extra item layer


# ---------------------------------------------------------------------------
# Per-character slot overrides (loaded from JSON sidecar at module load)
# ---------------------------------------------------------------------------

_OVERRIDES_PATH = os.path.join(_PORTRAIT_DIR, "slot_overrides.json")


def _load_slot_overrides() -> dict:
    """Read slot_overrides.json. Returns {} if missing or malformed.

    Accepted entry shapes per slot:
        [x, y]                                   -> position only
        {"pos": [x, y], "size": [w, h]}          -> pos and/or size
    """
    if not os.path.exists(_OVERRIDES_PATH):
        return {}
    try:
        with open(_OVERRIDES_PATH) as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[paper_doll] slot_overrides.json ignored: {e}")
        return {}

    out: dict = {}
    for adv_id, slots in raw.items():
        if not isinstance(slots, dict):
            continue
        per_char: dict = {}
        for slot, entry in slots.items():
            normalized: dict = {}
            if isinstance(entry, list) and len(entry) == 2:
                normalized['pos'] = (int(entry[0]), int(entry[1]))
            elif isinstance(entry, dict):
                if isinstance(entry.get('pos'), list) and len(entry['pos']) == 2:
                    normalized['pos'] = (int(entry['pos'][0]),
                                         int(entry['pos'][1]))
                if isinstance(entry.get('size'), list) and len(entry['size']) == 2:
                    normalized['size'] = (int(entry['size'][0]),
                                          int(entry['size'][1]))
            if normalized:
                per_char[slot] = normalized
        if per_char:
            out[adv_id] = per_char
    return out


SLOT_OVERRIDES: dict = _load_slot_overrides()


def _layout_for(adv_id: str) -> dict:
    """SLOT_LAYOUT merged with per-character overrides for `adv_id`.

    Partial overrides supported: an entry may set only `pos`, only `size`,
    or both; unspecified fields fall back to the default for that slot.
    """
    overrides = SLOT_OVERRIDES.get(adv_id)
    if not overrides:
        return SLOT_LAYOUT
    merged: dict = {}
    for slot, default in SLOT_LAYOUT.items():
        if slot in overrides:
            merged[slot] = {**default, **overrides[slot]}
        else:
            merged[slot] = default
    return merged


# ---------------------------------------------------------------------------
# Class color (deterministic from adventurer id — placeholder body only)
# ---------------------------------------------------------------------------

def _class_tint(adv_id: str) -> tuple:
    h = hashlib.md5(adv_id.encode()).digest()
    r = 90 + (h[0] % 130)
    g = 90 + (h[1] % 130)
    b = 90 + (h[2] % 130)
    return (r, g, b)


# ---------------------------------------------------------------------------
# Public thumbnail helpers (used by list views in preparation / delve)
# ---------------------------------------------------------------------------

def draw_portrait_thumbnail(screen, adv_id: str, x: int, y: int,
                             size: int) -> bool:
    """Blit a portrait thumbnail with top-left at (x, y). Returns True if art found."""
    portrait = _get_portrait(adv_id)
    if portrait is None:
        return False
    scaled = pygame.transform.smoothscale(portrait, (size, size))
    screen.blit(scaled, (x, y))
    return True


def draw_item_thumbnail(screen, item, x: int, y: int, size: int) -> bool:
    """Blit an item thumbnail with top-left at (x, y). Returns True if art found."""
    item_id = getattr(item, 'id', None) or getattr(item, 'name', '')
    slot = getattr(item, 'slot', 'misc')
    sprite = _get_item_sprite(item_id) or _get_slot_default_sprite(slot)
    if sprite is None:
        return False
    scaled = pygame.transform.smoothscale(sprite, (size, size))
    screen.blit(scaled, (x, y))
    return True

def draw_adventurer_thumbnail(screen, adv, x: int, y: int, size: int) -> bool:
    """Draw a mini paper-doll: portrait at (x, y) sized to `size`, with
    every equipped item rendered at scaled slot positions ON THE BODY —
    same layout as the full character card, just shrunk.

    Returns True if the portrait was found (still draws a coloured
    silhouette fallback when not).
    """
    adv_id = getattr(adv, 'id', adv.name)
    is_dead = getattr(adv, 'is_dead', False)

    # ---- Portrait (or silhouette fallback) ----
    portrait_found = draw_portrait_thumbnail(screen, adv_id, x, y, size)
    if not portrait_found:
        tint = _class_tint(adv_id)
        color = (80, 60, 60) if is_dead else tint
        pygame.draw.rect(screen, color, (x, y, size, size), border_radius=4)
        pygame.draw.rect(screen, (200, 200, 210),
                         (x, y, size, size), 1, border_radius=4)
        # Simple head + torso doodle so items have something to sit on
        cx = x + size // 2
        pygame.draw.circle(screen, (220, 200, 180) if not is_dead else (140, 120, 110),
                           (cx, y + size // 4), max(4, size // 8))

    if is_dead:
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        overlay.fill((40, 40, 40, 140))
        screen.blit(overlay, (x, y))

    # ---- Equipped items overlaid at scaled slot positions ----
    items = getattr(adv, 'equipped_items', [])
    if not items or size < 24:
        # Too small for meaningful item overlay; show a tiny count badge instead
        if items and size >= 16:
            badge = f"{len(items)}"
            screen.blit(_tiny_render(badge), (x + size - 10, y + size - 10))
        return portrait_found

    layout = _layout_for(adv_id)
    buckets = _bucket_items_by_slot(adv)

    # Scale factor: full doll viewport is DOLL_W wide; thumbnail is `size`.
    sx = size / DOLL_W
    sy = size / DOLL_H

    # Cap item render size so a single sprite never overwhelms the thumbnail.
    max_item = max(8, int(size * 0.55))

    # Cape behind body, weapon/hand/chest/etc. on top.
    for pass_behind in (True, False):
        for slot, slot_items in buckets.items():
            if slot in ('float', 'misc'):
                continue
            if slot not in layout:
                continue
            is_behind = slot in SLOTS_BEHIND_BODY
            if pass_behind != is_behind:
                continue
            entry = layout[slot]
            if entry.get('pos') is None:
                continue
            rel_x, rel_y = entry['pos']
            base_w, base_h = entry['size']

            placements = _compute_slot_placements(
                slot, slot_items, rel_x, rel_y, base_w, base_h)

            # Behind items first (reverse), then foreground
            order = list(range(len(placements)))
            order.sort(key=lambda i: (not placements[i]['behind'], -i if placements[i]['behind'] else i))

            for i in order:
                p = placements[i]
                # Skip cape on the foreground pass etc.
                if p['behind'] != pass_behind:
                    continue
                cx = x + int(p['x'] * sx)
                cy = y + int(p['y'] * sy)
                iw = min(max_item, max(6, int(p['w'] * sx)))
                ih = min(max_item, max(6, int(p['h'] * sy)))
                _draw_item(screen, _FONTS_STUB,
                           cx, cy, (iw, ih), slot_items[i], slot,
                           slot[0].upper() if slot else '?', p['flip_h'])

    # ---- King / Dunce role overlay (visible everywhere this thumbnail is used) ----
    # Caller-set attribute lets callers tag a role without modifying the
    # adventurer model: setattr(adv, '_role_badge', 'king'|'dunce'|None)
    # We also detect via global state hooks if available.
    role = getattr(adv, '_role_badge', None)
    if role == 'king':
        crown = max(10, size // 5)
        cx = x + size // 2
        cy = y - 2
        # Simple gold crown polygon
        pts = [
            (cx - crown, cy),
            (cx - crown // 2, cy - crown + 2),
            (cx, cy - crown // 4),
            (cx + crown // 2, cy - crown + 2),
            (cx + crown, cy),
        ]
        pygame.draw.polygon(screen, (250, 200, 50), pts)
        pygame.draw.polygon(screen, (120, 80, 0), pts, 1)
        pygame.draw.rect(screen, (250, 200, 50),
                         (x, y, size, 3))
    elif role == 'dunce':
        cap_w = max(8, size // 4)
        cx = x + size // 2
        cy = y - 1
        pts = [(cx - cap_w // 2, cy),
               (cx + cap_w // 2, cy),
               (cx, cy - cap_w - 2)]
        pygame.draw.polygon(screen, (160, 160, 170), pts)
        pygame.draw.polygon(screen, (90, 90, 100), pts, 1)
        pygame.draw.rect(screen, (130, 130, 140),
                         (x, y, size, 3))

    return portrait_found


# Minimal font stub used by draw_adventurer_thumbnail since _draw_item only
# needs a font to render placeholder labels when item art is missing.
class _MissingFont:
    def render(self, text, antialias, color):
        surf = pygame.Surface((1, 1), pygame.SRCALPHA)
        return surf
_FONTS_STUB = {'tiny': _MissingFont(), 'small': _MissingFont(), 'medium': _MissingFont()}


def _tiny_render(text: str) -> pygame.Surface:
    """Cheap label surface used only inside this module."""
    try:
        font = pygame.font.Font(None, 14)
        return font.render(text, True, (240, 240, 240))
    except Exception:
        return pygame.Surface((1, 1), pygame.SRCALPHA)


# ---------------------------------------------------------------------------
# Silhouette (real PNG portrait if available, else programmatic placeholder)
# ---------------------------------------------------------------------------

def _draw_silhouette(screen, ox: int, oy: int, tint: tuple, is_dead: bool,
                     adv_id: str = ""):
    portrait = _get_portrait(adv_id)
    if portrait is not None:
        scaled = pygame.transform.smoothscale(portrait, (DOLL_W, DOLL_H))
        if is_dead:
            overlay = pygame.Surface((DOLL_W, DOLL_H), pygame.SRCALPHA)
            overlay.fill((40, 40, 40, 140))
            scaled = scaled.copy()
            scaled.blit(overlay, (0, 0))
        screen.blit(scaled, (ox, oy))
        return

    # ---- Programmatic placeholder body ----
    if is_dead:
        body_color = (60, 50, 50)
        outline = (120, 80, 80)
    else:
        body_color = tint
        outline = tuple(min(255, c + 50) for c in tint)

    cx = ox + DOLL_W // 2
    pygame.draw.circle(screen, body_color, (cx, oy + 28), 22)
    pygame.draw.circle(screen, outline, (cx, oy + 28), 22, 2)
    pygame.draw.rect(screen, body_color, (cx - 5, oy + 48, 10, 8))

    torso_pts = [(cx - 35, oy + 56), (cx + 35, oy + 56),
                 (cx + 30, oy + 145), (cx - 30, oy + 145)]
    pygame.draw.polygon(screen, body_color, torso_pts)
    pygame.draw.polygon(screen, outline, torso_pts, 2)

    pygame.draw.rect(screen, body_color, (cx - 50, oy + 60, 14, 70), border_radius=6)
    pygame.draw.rect(screen, outline,    (cx - 50, oy + 60, 14, 70), 2, border_radius=6)
    pygame.draw.rect(screen, body_color, (cx + 36, oy + 60, 14, 70), border_radius=6)
    pygame.draw.rect(screen, outline,    (cx + 36, oy + 60, 14, 70), 2, border_radius=6)

    pygame.draw.rect(screen, body_color, (cx - 22, oy + 145, 16, 80), border_radius=4)
    pygame.draw.rect(screen, outline,    (cx - 22, oy + 145, 16, 80), 2, border_radius=4)
    pygame.draw.rect(screen, body_color, (cx + 6,  oy + 145, 16, 80), border_radius=4)
    pygame.draw.rect(screen, outline,    (cx + 6,  oy + 145, 16, 80), 2, border_radius=4)


# ---------------------------------------------------------------------------
# Item rendering — sprite-first, transparent overlay, placeholder fallback
# ---------------------------------------------------------------------------

_RARITY_COLORS = {
    'scrap':    (130, 110, 100),
    'common':   (180, 180, 190),
    'uncommon': (90, 200, 120),
    'rare':     (110, 160, 240),
}


def _draw_item(screen, fonts, cx: int, cy: int, size: tuple, item,
               slot: str, placeholder_label: str = "", flip_h: bool = False):
    """Draw a single item centered at (cx, cy), sized to `size`=(w,h).

    Resolution order for art:
        1) assets/items/{item.id}.png
        2) assets/items/_default_{slot}.png
        3) Programmatic placeholder chip (only path that draws a backdrop)

    When real art is found it's blitted with a transparent background — no
    box, no border — so it sits seamlessly on the body. 
    flip_h: mirror the sprite horizontally (used for 2nd weapon/hand on the
    opposite side of a symmetrical character).
    """
    w, h = size
    rarity = getattr(item, 'rarity', 'common')
    color = _RARITY_COLORS.get(rarity, _RARITY_COLORS['common'])

    item_id = getattr(item, 'id', None) or getattr(item, 'name', '')
    sprite = _get_item_sprite(item_id) or _get_slot_default_sprite(slot)

    if sprite is not None:
        rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        scaled = pygame.transform.smoothscale(sprite, (w, h))
        if flip_h:
            scaled = pygame.transform.flip(scaled, True, False)
        screen.blit(scaled, rect.topleft)
        return

    # ---- Placeholder fallback (small boxed chip, obvious "missing art") ----
    ph_rect = pygame.Rect(cx - MISC_CHIP_W // 2, cy - MISC_CHIP_H // 2,
                          MISC_CHIP_W, MISC_CHIP_H)
    pygame.draw.rect(screen, (15, 15, 20), ph_rect.inflate(2, 2), border_radius=4)
    pygame.draw.rect(screen, color, ph_rect, border_radius=4)
    pygame.draw.rect(screen, (15, 15, 20), ph_rect, 1, border_radius=4)
    if placeholder_label:
        lbl = fonts['tiny'].render(placeholder_label, True, (15, 15, 20))
        screen.blit(lbl, lbl.get_rect(center=ph_rect.center))


# ---------------------------------------------------------------------------
# Item placement helpers
# ---------------------------------------------------------------------------

def _bucket_items_by_slot(adv) -> dict:
    """Return {slot_id: [items]}. Items without a slot land in 'misc'."""
    buckets: dict = {}
    for item in adv.equipped_items:
        slot = getattr(item, 'slot', None) or 'misc'
        buckets.setdefault(slot, []).append(item)
    return buckets


def _compute_slot_placements(slot: str, items: list,
                              rel_x: int, rel_y: int,
                              w: int, h: int) -> list:
    """Return a list of placement dicts for each item in *slot*.

    Each dict:  x, y  (relative to doll viewport origin)
                w, h  (render size — may differ from default for behind items)
                flip_h  (mirror image horizontally)
                behind  (render this item BEFORE non-behind items)

    Rules
    -----
    weapon / hand
        • item[0]  →  default position, normal
        • item[1]  →  mirrored x (DOLL_W - rel_x), flipped horizontally
        • item[2+] →  same as item[0], slightly larger, drawn behind

    chest / boots / head / belt
        • item[0]  →  normal
        • item[1+] →  same position, proportionally larger, drawn behind

    All other slots
        • Stack diagonally by STACK_OFFSET (existing behaviour).
    """
    mirror_x = DOLL_W - rel_x
    placements: list = []

    if slot in MIRRORED_SLOTS:
        for i in range(len(items)):
            if i == 0:
                placements.append(dict(x=rel_x, y=rel_y, w=w, h=h,
                                       flip_h=False, behind=False))
            elif i == 1:
                placements.append(dict(x=mirror_x, y=rel_y, w=w, h=h,
                                       flip_h=True, behind=False))
            else:
                scale = BEHIND_SCALE_FACTOR + 0.05 * (i - 2)
                placements.append(dict(x=rel_x, y=rel_y,
                                       w=int(w * scale), h=int(h * scale),
                                       flip_h=False, behind=True))

    elif slot in BEHIND_LARGER_SLOTS:
        for i in range(len(items)):
            if i == 0:
                placements.append(dict(x=rel_x, y=rel_y, w=w, h=h,
                                       flip_h=False, behind=False))
            else:
                scale = BEHIND_SCALE_FACTOR + 0.05 * (i - 1)
                placements.append(dict(x=rel_x, y=rel_y,
                                       w=int(w * scale), h=int(h * scale),
                                       flip_h=False, behind=True))

    else:
        for i in range(len(items)):
            placements.append(dict(x=rel_x + i * STACK_OFFSET,
                                   y=rel_y + i * STACK_OFFSET,
                                   w=w, h=h, flip_h=False, behind=False))

    return placements


def _draw_slot_items(screen, fonts, doll_ox: int, doll_oy: int,
                     buckets: dict, layout: dict, only_behind_body: bool):
    """Draw chips for every slot in the silhouette area.

    Two body-pass design:
        Pass 1 (only_behind_body=True):  cape (drawn under the portrait)
        Pass 2 (only_behind_body=False): everything else (on top of portrait)

    Within each slot, *behind* items are drawn first in reverse index order
    (so the highest index is furthest back), then normal items in forward order.
    """
    for slot, items in buckets.items():
        if slot in ('float', 'misc'):
            continue
        if slot not in layout:
            continue
        is_behind = slot in SLOTS_BEHIND_BODY
        if only_behind_body != is_behind:
            continue

        entry = layout[slot]
        if entry.get('pos') is None:
            continue
        rel_x, rel_y = entry['pos']
        w, h = entry['size']

        placements = _compute_slot_placements(slot, items, rel_x, rel_y, w, h)

        # Draw behind items first — reversed so the highest-index is farthest back
        for i in reversed(range(len(placements))):
            p = placements[i]
            if p['behind']:
                _draw_item(screen, fonts,
                           doll_ox + p['x'], doll_oy + p['y'],
                           (p['w'], p['h']), items[i], slot,
                           slot[0].upper(), p['flip_h'])

        # Then draw normal (foreground) items
        for i in range(len(placements)):
            p = placements[i]
            if not p['behind']:
                _draw_item(screen, fonts,
                           doll_ox + p['x'], doll_oy + p['y'],
                           (p['w'], p['h']), items[i], slot,
                           slot[0].upper(), p['flip_h'])


def _draw_float_items(screen, fonts, card_x: int, card_y: int,
                      items: list, size: tuple):
    """Float items go in the top corners of the card. First item: top-right.
    Second: top-left. Beyond two: stack diagonally inward from each corner.
    """
    w, h = size
    for i, item in enumerate(items):
        if i % 2 == 0:
            base_x = card_x + CARD_W - w // 2 - 8
            ox = -(i // 2) * STACK_OFFSET
        else:
            base_x = card_x + w // 2 + 8
            ox = (i // 2) * STACK_OFFSET
        base_y = card_y + BANNER_H + h // 2 + 6
        oy = (i // 2) * STACK_OFFSET
        _draw_item(screen, fonts, base_x + ox, base_y + oy,
                   size, item, 'float', "F")


def _draw_misc_strip(screen, fonts, card_x: int, card_y: int, items: list):
    """Items with no recognized slot get a chip row above the footer."""
    if not items:
        return
    strip_y = card_y + CARD_H - FOOTER_H - MISC_CHIP_H - 6
    label = fonts['tiny'].render("misc:", True, COLORS['text_dim'])
    screen.blit(label, (card_x + 10, strip_y + 4))

    chip_x = card_x + 50
    for item in items[:6]:
        _draw_item(
            screen, fonts,
            chip_x + MISC_CHIP_W // 2, strip_y + MISC_CHIP_H // 2,
            (MISC_CHIP_W, MISC_CHIP_H), item, 'misc', "?",
        )
        chip_x += MISC_CHIP_W + 4


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def draw_character_card(screen, fonts, state, x: int, y: int, adv,
                        selected: bool = False):
    """Draw a paper-doll character card at (x, y)."""
    is_dead = getattr(adv, 'is_dead', False)

    # ---- Card background ----
    card_rect = pygame.Rect(x, y, CARD_W, CARD_H)
    bg_color = (theme.mix(COLORS['bg'], COLORS['danger'], 0.22) if is_dead
                else COLORS['panel'])
    pygame.draw.rect(screen, bg_color, card_rect, border_radius=10)

    border_color = (
        COLORS['accent'] if selected
        else (COLORS['danger'] if is_dead else COLORS['border'])
    )
    border_width = 3 if selected else 2
    pygame.draw.rect(screen, border_color, card_rect, border_width, border_radius=10)

    # ---- Banner ----
    banner_rect = pygame.Rect(x, y, CARD_W, BANNER_H)
    pygame.draw.rect(screen, COLORS['panel_dark'], banner_rect,
                     border_top_left_radius=10, border_top_right_radius=10)
    pygame.draw.line(screen, border_color,
                     (x, y + BANNER_H), (x + CARD_W, y + BANNER_H), 1)

    name = adv.name
    if len(name) > 22:
        name = name[:21] + ".."
    name_color = COLORS['danger'] if is_dead else COLORS['text']
    name_surf = fonts['medium'].render(name, True, name_color)
    screen.blit(name_surf, name_surf.get_rect(
        center=(x + CARD_W // 2, y + BANNER_H // 2),
    ))

    # ---- Doll viewport ----
    doll_rect = pygame.Rect(x + DOLL_X, y + DOLL_Y, DOLL_W, DOLL_H)
    pygame.draw.rect(screen, COLORS['well'], doll_rect, border_radius=6)
    pygame.draw.rect(screen, COLORS['border'], doll_rect, 1, border_radius=6)

    doll_ox = x + DOLL_X
    doll_oy = y + DOLL_Y

    adv_id = getattr(adv, 'id', adv.name)
    layout = _layout_for(adv_id)
    buckets = _bucket_items_by_slot(adv)

    # Draw order: behind-body items (cape) → body → on-top items → floats → misc
    _draw_slot_items(screen, fonts, doll_ox, doll_oy, buckets, layout,
                     only_behind_body=True)

    tint = _class_tint(adv_id)
    _draw_silhouette(screen, doll_ox, doll_oy, tint, is_dead, adv_id)

    _draw_slot_items(screen, fonts, doll_ox, doll_oy, buckets, layout,
                     only_behind_body=False)

    if 'float' in buckets:
        _draw_float_items(screen, fonts, x, y, buckets['float'],
                          layout['float']['size'])
    if 'misc' in buckets:
        _draw_misc_strip(screen, fonts, x, y, buckets['misc'])

    # ---- Footer ----
    footer_y = y + CARD_H - FOOTER_H
    pygame.draw.line(screen, COLORS['divider'],
                     (x + 10, footer_y), (x + CARD_W - 10, footer_y), 1)

    try:
        base = adv.get_base_points()
        mult = adv.get_multiplier()
        power = base * mult
        power_text = f"Power: {base} x {mult} = {power}"
    except AttributeError:
        power_text = f"Items: {len(adv.equipped_items)}/{adv.slots}"

    pwr_color = COLORS['success'] if not is_dead else COLORS['text_dim']
    screen.blit(fonts['small'].render(power_text, True, pwr_color),
                (x + 12, footer_y + 6))

    slot_used = len(adv.equipped_items)
    slot_max = adv.slots
    slot_color = (
        COLORS['warning'] if slot_used >= slot_max else COLORS['text_dim']
    )
    screen.blit(
        fonts['small'].render(f"Slots: {slot_used}/{slot_max}", True, slot_color),
        (x + 12, footer_y + 28),
    )

    ability = getattr(adv, 'ability_name', None)
    if ability:
        ab_text = ability
        if len(ab_text) > 28:
            ab_text = ab_text[:27] + ".."
        screen.blit(
            fonts['tiny'].render(ab_text, True, COLORS['accent']),
            (x + 12, footer_y + 50),
        )


# ---------------------------------------------------------------------------
# Hit-testing (click-to-unequip from the paper doll)
# ---------------------------------------------------------------------------

def hit_test_chip(card_x: int, card_y: int, mouse_pos: tuple, adv) -> Optional[int]:
    """Return the index of the equipped item under the cursor, or None.

    Iterates in reverse draw order so the visually-on-top item wins.
    """
    adv_id = getattr(adv, 'id', adv.name)
    layout = _layout_for(adv_id)
    buckets = _bucket_items_by_slot(adv)
    mx, my = mouse_pos
    doll_ox = card_x + DOLL_X
    doll_oy = card_y + DOLL_Y

    placements: list = []  # (item, pygame.Rect)

    # Body-slot items
    for slot, items in buckets.items():
        if slot in ('misc', 'float'):
            continue
        if slot not in layout:
            continue
        entry = layout[slot]
        if entry.get('pos') is None:
            continue
        rel_x, rel_y = entry['pos']
        w, h = entry['size']
        slot_placements = _compute_slot_placements(slot, items, rel_x, rel_y, w, h)
        for i, item in enumerate(items):
            p = slot_placements[i]
            sx = doll_ox + p['x']
            sy = doll_oy + p['y']
            pw, ph = p['w'], p['h']
            placements.append(
                (item, pygame.Rect(sx - pw // 2, sy - ph // 2, pw, ph))
            )

    # Float items
    if 'float' in buckets:
        fw, fh = layout['float']['size']
        for i, item in enumerate(buckets['float']):
            if i % 2 == 0:
                sx = card_x + CARD_W - fw // 2 - 8 - (i // 2) * STACK_OFFSET
            else:
                sx = card_x + fw // 2 + 8 + (i // 2) * STACK_OFFSET
            sy = card_y + BANNER_H + fh // 2 + 6 + (i // 2) * STACK_OFFSET
            placements.append(
                (item, pygame.Rect(sx - fw // 2, sy - fh // 2, fw, fh))
            )

    for item, rect in reversed(placements):
        if rect.collidepoint(mx, my):
            try:
                return adv.equipped_items.index(item)
            except ValueError:
                return None
    return None