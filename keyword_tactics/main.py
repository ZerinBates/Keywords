"""
Keyword-Based Tactical Deck Builder - Entry Point
==================================================
Run with:  python main.py

Architecture:
- Data-driven (data/*.json)
- Model-View-Controller separation under game/
- Async-friendly main loop for browser/pygbag compatibility
"""

import asyncio
from game.controllers.app import Game


async def main():
    game = Game()
    await game.run()


if __name__ == "__main__":
    asyncio.run(main())
