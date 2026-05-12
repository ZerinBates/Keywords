"""Renders Spark the tutorial fairy and her speech bubble.

Drawn on top of the main scene by Renderer.draw. Click hit-testing for the
fairy/bubble is exposed via the get_*_rect helpers, which InputHandler uses.
"""

import math
from typing import TYPE_CHECKING

import pygame

from ..config import COLORS, SCREEN_HEIGHT

if TYPE_CHECKING:
    from ..controllers.tutorial import Tutorial


# ---------------------------------------------------------------------------
# Layout — fairy in the bottom-left corner; bubble extends up-right.
# Bottom-left is the least-occupied corner across phases, but you'll still
# get some overlap with screens like DELVE_RESULTS (party status row). The X
# button minimizes to just the fairy if the player wants it out of the way.
# ---------------------------------------------------------------------------

FAIRY_X = 80
FAIRY_Y = SCREEN_HEIGHT - 90
FAIRY_RADIUS = 10
FAIRY_HIT_PAD = 24      # Generous click target
BOB_AMPLITUDE = 6

BUBBLE_W = 540
BUBBLE_H = 140
BUBBLE_OFFSET_X = 50    # Right of fairy
BUBBLE_OFFSET_Y = -170  # Above fairy

FAIRY_COLOR_CORE = (255, 250, 220)
FAIRY_COLOR_GLOW = (255, 220, 110)
FAIRY_COLOR_AURA = (255, 200, 80)


# ---------------------------------------------------------------------------
# Hit-test rectangles (used by InputHandler)
# ---------------------------------------------------------------------------

def get_fairy_rect() -> pygame.Rect:
    return pygame.Rect(
        FAIRY_X - FAIRY_HIT_PAD,
        FAIRY_Y - FAIRY_HIT_PAD,
        FAIRY_HIT_PAD * 2,
        FAIRY_HIT_PAD * 2,
    )


def get_bubble_rect() -> pygame.Rect:
    return pygame.Rect(
        FAIRY_X + BUBBLE_OFFSET_X,
        FAIRY_Y + BUBBLE_OFFSET_Y,
        BUBBLE_W,
        BUBBLE_H,
    )


def get_bubble_close_rect() -> pygame.Rect:
    """Close (X) button in the upper-right of the bubble — minimizes to fairy."""
    br = get_bubble_rect()
    return pygame.Rect(br.right - 30, br.top + 6, 24, 24)


def get_bubble_next_rect() -> pygame.Rect:
    """Next / Got it button, lower-right of bubble."""
    br = get_bubble_rect()
    return pygame.Rect(br.right - 110, br.bottom - 36, 100, 28)


def get_bubble_prev_rect() -> pygame.Rect:
    """< Back button, just left of Next."""
    br = get_bubble_rect()
    return pygame.Rect(br.right - 220, br.bottom - 36, 100, 28)


# ---------------------------------------------------------------------------
# Fairy sprite (drawn programmatically — no asset files)
# ---------------------------------------------------------------------------

def _draw_fairy(screen, x: int, y: int, bob_t: float, pulse_t: float, attention: bool):
    """Glowing pixie with translucent flapping wings, bobs in place."""
    bob = int(math.sin(bob_t) * BOB_AMPLITUDE)
    cy = y + bob

    # Multi-ring aura
    for r, alpha in [(36, 22), (28, 45), (20, 80)]:
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*FAIRY_COLOR_AURA, alpha), (r, r), r)
        screen.blit(s, (x - r, cy - r))

    # Wings — translucent ovals on each side, flap with sin wave
    wing_flap = abs(math.sin(bob_t * 4)) * 0.6 + 0.4
    wing_w = max(6, int(14 * wing_flap))
    wing_h = 18
    for side in (-1, 1):
        ws = pygame.Surface((wing_w * 2, wing_h * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(ws, (220, 240, 255, 130), (0, 0, wing_w * 2, wing_h * 2))
        pygame.draw.ellipse(ws, (255, 255, 255, 200), (0, 0, wing_w * 2, wing_h * 2), 1)
        screen.blit(
            ws,
            (x + side * (FAIRY_RADIUS + wing_w // 2 - 4) - wing_w, cy - wing_h),
        )

    # Body
    pygame.draw.circle(screen, FAIRY_COLOR_GLOW, (x, cy), FAIRY_RADIUS)
    pygame.draw.circle(screen, FAIRY_COLOR_CORE, (x, cy), FAIRY_RADIUS - 3)
    pygame.draw.circle(screen, (255, 255, 255), (x - 3, cy - 3), 2)

    # "!" indicator above when minimized — pulses up and down
    if attention:
        pulse = (math.sin(pulse_t) + 1) / 2
        offset = int(pulse * 4)
        bang_y = cy - 30 - offset

        bg_r = 11
        s = pygame.Surface((bg_r * 2, bg_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 80, 80, 230), (bg_r, bg_r), bg_r)
        screen.blit(s, (x - bg_r, bang_y - bg_r))
        pygame.draw.circle(screen, (255, 255, 255), (x, bang_y), bg_r, 2)

        font = pygame.font.Font(None, 22)
        bang = font.render("!", True, (255, 255, 255))
        screen.blit(
            bang,
            (x - bang.get_width() // 2, bang_y - bang.get_height() // 2 + 1),
        )


# ---------------------------------------------------------------------------
# Speech bubble
# ---------------------------------------------------------------------------

def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list:
    words = text.split(' ')
    lines = []
    current = ""
    for word in words:
        test = current + (" " if current else "") + word
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_speech_bubble(screen, fonts, tutorial: 'Tutorial'):
    msg = tutorial.current_message()
    if msg is None:
        return

    br = get_bubble_rect()

    # Bubble body
    pygame.draw.rect(screen, (28, 30, 50), br, border_radius=12)
    pygame.draw.rect(screen, FAIRY_COLOR_GLOW, br, 2, border_radius=12)

    # Speech tail pointing toward fairy (lower-left of bubble)
    tail_pts = [
        (br.left + 18, br.bottom - 8),
        (br.left + 38, br.bottom - 8),
        (FAIRY_X + 14, FAIRY_Y - 12),
    ]
    pygame.draw.polygon(screen, (28, 30, 50), tail_pts)
    pygame.draw.line(screen, FAIRY_COLOR_GLOW, tail_pts[0], tail_pts[2], 2)
    pygame.draw.line(screen, FAIRY_COLOR_GLOW, tail_pts[1], tail_pts[2], 2)

    # Title
    title = fonts['medium'].render("Spark says:", True, FAIRY_COLOR_GLOW)
    screen.blit(title, (br.left + 14, br.top + 8))

    # Step indicator (e.g. "2 / 7")
    msgs = tutorial.messages()
    step = f"{tutorial.message_index + 1} / {len(msgs)}"
    step_surf = fonts['small'].render(step, True, COLORS['text_dim'])
    screen.blit(step_surf, (br.right - step_surf.get_width() - 40, br.top + 14))

    # Word-wrapped message body
    body_top = br.top + 40
    body_left = br.left + 14
    max_w = br.width - 28
    lines = _wrap_text(msg, fonts['small'], max_w)
    for i, line in enumerate(lines[:3]):  # Hard cap; keeps bubble height stable
        line_surf = fonts['small'].render(line, True, COLORS['text'])
        screen.blit(line_surf, (body_left, body_top + i * 22))

    # Close (X)
    close_r = get_bubble_close_rect()
    pygame.draw.rect(screen, (60, 30, 30), close_r, border_radius=4)
    pygame.draw.rect(screen, COLORS['danger'], close_r, 1, border_radius=4)
    x_label = fonts['small'].render("x", True, COLORS['text'])
    screen.blit(x_label, x_label.get_rect(center=close_r.center))

    # Back (only if not on first message)
    if tutorial.message_index > 0:
        prev_r = get_bubble_prev_rect()
        pygame.draw.rect(screen, COLORS['panel_light'], prev_r, border_radius=4)
        pygame.draw.rect(screen, COLORS['text_dim'], prev_r, 1, border_radius=4)
        prev_label = fonts['small'].render("< Back", True, COLORS['text'])
        screen.blit(prev_label, prev_label.get_rect(center=prev_r.center))

    # Next / Got it
    next_r = get_bubble_next_rect()
    next_text = "Got it!" if tutorial.is_last_message() else "Next >"
    pygame.draw.rect(screen, FAIRY_COLOR_AURA, next_r, border_radius=4)
    next_label = fonts['small'].render(next_text, True, COLORS['bg'])
    screen.blit(next_label, next_label.get_rect(center=next_r.center))


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def draw_tutorial(screen, fonts, tutorial: 'Tutorial'):
    """Draw the fairy and bubble. Call from Renderer.draw on top of the scene."""
    if not tutorial.active:
        return

    # If the current phase has no script, just float silently in the corner
    if not tutorial.has_messages_for_current_phase():
        _draw_fairy(
            screen, FAIRY_X, FAIRY_Y,
            tutorial.bob_timer, tutorial.attention_pulse, attention=False,
        )
        return

    show_attention = tutorial.minimized
    _draw_fairy(
        screen, FAIRY_X, FAIRY_Y,
        tutorial.bob_timer, tutorial.attention_pulse, attention=show_attention,
    )

    if not tutorial.minimized:
        _draw_speech_bubble(screen, fonts, tutorial)
