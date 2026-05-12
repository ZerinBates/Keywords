"""
Global configuration: screen dimensions, FPS, color palette.
Single source of truth for visual constants.
"""

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800
FPS = 60

# Color palette - referenced everywhere via COLORS['name']
COLORS = {
    'bg':           (30, 30, 40),
    'panel':        (45, 45, 60),
    'panel_light':  (60, 60, 80),
    'text':         (240, 240, 240),
    'text_dim':     (160, 160, 170),
    'accent':       (100, 200, 255),
    'success':      (100, 220, 120),
    'danger':       (255, 100, 100),
    'warning':      (255, 200, 80),
    'gold':         (255, 215, 0),
    'fire':         (255, 100, 50),
    'water':        (50, 150, 255),
    'earth':        (150, 120, 80),
    'nature':       (80, 200, 80),
    'dark':         (100, 50, 150),
    'light':        (255, 255, 200),
}
