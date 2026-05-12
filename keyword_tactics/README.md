# Keyword Tactics — Refactored Project Structure

The original `main.py` (~4250 lines) has been split into a clean MVC package.
Run with `python main.py`.

## Layout

```
project/
├── main.py                       # Entry point - just bootstraps Game
├── data/                         # JSON data (unchanged)
│   ├── keywords.json
│   ├── items.json
│   ├── characters.json
│   └── decks.json
└── game/
    ├── config.py                 # Constants: SCREEN_WIDTH, COLORS, FPS
    │
    ├── models/                   # ── MODEL ── pure domain entities
    │   ├── keyword.py            # Keyword + KeywordRegistry
    │   ├── item.py               # Item + ItemRegistry
    │   ├── adventurer.py         # Adventurer + AdventurerRegistry
    │   ├── monster.py            # Monster
    │   ├── deck.py               # Deck + DeckRegistry
    │   └── game_phase.py         # GamePhase enum
    │
    ├── controllers/              # ── CONTROLLER ── state, logic, input
    │   ├── app.py                # Game class - owns the run loop
    │   ├── game_state.py         # Central GameState (the runtime state)
    │   ├── data_loader.py        # JSON loader (game data bootstrapping)
    │   ├── combat.py             # Pure combat math (no state mutation)
    │   └── input_handler.py      # Mouse / keyboard / drag dispatcher
    │
    └── views/                    # ── VIEW ── all rendering
        ├── renderer.py           # Renderer - per-phase draw dispatcher
        ├── widgets.py            # Reusable Button + Panel
        ├── sprite_manager.py     # Sprite loading + caching
        ├── tooltips.py           # Combat hover info + tooltip drawing
        ├── ref_panel.py          # Keyword reference panel (TAB overlay)
        ├── drag_ghost.py         # Drag-and-drop ghost card
        └── screens/              # One module per game phase
            ├── main_menu.py
            ├── preparation.py
            ├── deck_select.py
            ├── delve.py          # Setup, results, inventory, recruit
            ├── boss.py           # Choice + result
            ├── shop.py
            └── game_over.py
```

## Key design decisions

**MVC separation.** Models hold data and entity behavior with no awareness of
pygame or rendering. Views never mutate state — they read `state` and draw.
Controllers own the loop and translate input into state changes.

**`Game` (controllers/app.py) is the orchestrator.** It owns one of each
subsystem: `GameState`, `Renderer`, `InputHandler`, `SpriteManager`. Cross-cutting
state like the button list and window scaling lives here because both renderer
and input handler need it.

**Combat math is a free-function module.** `controllers/combat.py` exposes
`calculate_square_combat(...)` and `calculate_boss_combat(...)` as pure
functions returning result dicts. `GameState` calls them and applies the
outcome to state. This makes combat unit-testable without instantiating
the whole game.

**Per-screen rendering modules.** Each screen module exposes a `draw(screen,
fonts, state, ...)` function. Adding a new phase = adding one file under
`views/screens/` and one branch in `Renderer.draw`.

**Fonts as a dict, not five attributes.** `game.fonts['small']`, `['medium']`,
`['large']`, `['title']`, `['tiny']`. Screens take the whole dict so signatures
stay stable as font usage changes.

**Drag state lives on `InputHandler`.** It's fundamentally an input concept.
The renderer reads `game.input_handler.dragging` and `.drag_current_pos` when
it needs to draw the ghost — no shared mutable state held by Game itself.

## Adding new content

| What you want                | Where to add it                       |
| ---------------------------- | ------------------------------------- |
| New keyword type             | `data/keywords.json`                  |
| New item                     | `data/items.json`                     |
| New character / ability      | `data/characters.json` (+ effect logic in `models/adventurer.py` if novel) |
| New dungeon                  | `data/decks.json`                     |
| New game phase / screen      | New file in `views/screens/` + branch in `Renderer.draw` + button setup in `controllers/app.py` |
| New combat rule              | `controllers/combat.py`               |
| New UI widget                | `views/widgets.py`                    |

## Running

```bash
python main.py        # Standard
```

The async `run()` loop is preserved for pygbag/browser compatibility.
