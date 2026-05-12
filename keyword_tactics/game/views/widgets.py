"""Reusable UI widgets: Button and Panel."""

import pygame

from ..config import COLORS


class Button:
    """A clickable button with hover state and enabled/disabled flag."""

    def __init__(self, x: int, y: int, width: int, height: int, text: str,
                 color=COLORS['panel_light'],
                 hover_color=COLORS['accent'],
                 text_color=COLORS['text']):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.hovered = False
        self.enabled = True

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos) and self.enabled

    def draw(self, surface, font):
        color = self.hover_color if self.hovered else self.color
        if not self.enabled:
            color = (60, 60, 60)

        pygame.draw.rect(surface, color, self.rect, border_radius=5)
        pygame.draw.rect(surface, COLORS['text_dim'], self.rect, 2, border_radius=5)

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
        pygame.draw.rect(surface, COLORS['panel'], self.rect, border_radius=8)
        pygame.draw.rect(surface, COLORS['panel_light'], self.rect, 2, border_radius=8)

        if self.title:
            tf = title_font or font
            title_surf = tf.render(self.title, True, COLORS['accent'])
            surface.blit(title_surf, (self.rect.x + 10, self.rect.y + 8))
