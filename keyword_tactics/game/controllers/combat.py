"""Combat resolution math.

Pure functions: take game entities + parameters, return result dictionaries.
No state mutation here - GameState consumes these results and applies them.

King / Dunce system (#6):
  - Each row marks one monster as KING (×2 power, ignores its biggest
    weakness keyword) and one as DUNCE (÷2 power).
  - Heroes can also be flagged is_king (×2) or is_dunce (÷2) by the caller.
  - The per-square multiplier system has been removed; sq['multiplier']
    is kept at 1 for backward compatibility but is no longer applied here.
"""

import random
from typing import Dict, List, Optional

from ..models import Adventurer, KeywordRegistry, Monster


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_immunity_list(value) -> List[str]:
    """Ability_effect immune_weakness can be a string or list. Normalize to list."""
    if isinstance(value, str):
        return [value]
    return list(value or [])


def _count_keyword_matches(counts: Dict[str, int]) -> int:
    """Sum of stack-of-2-or-more counts (the basic multiplier rule)."""
    return sum(c for c in counts.values() if c >= 2)


def _weakness_contributions(
    self_keywords: List[str],
    opponent_keywords: List[str],
    resists: List[str],
    keyword_registry: KeywordRegistry,
) -> Dict[str, int]:
    """For each `self` keyword, how many opponent keywords beat it?

    Returns {self_keyword: count}.  Sum of values = total weakness.
    Used so a king can drop its single highest-contributing keyword.
    """
    contributions: Dict[str, int] = {}
    for k in self_keywords:
        kw_obj = keyword_registry.get(k)
        if not kw_obj:
            continue
        c = 0
        for ek in opponent_keywords:
            if ek in resists:
                continue
            if kw_obj.is_weak_against(ek):
                c += 1
        if c:
            contributions[k] = contributions.get(k, 0) + c
    return contributions


# ---------------------------------------------------------------------------
# Square (front-row) combat — king / dunce aware
# ---------------------------------------------------------------------------

def calculate_square_combat(square: dict, keyword_registry: KeywordRegistry,
                            adv_is_king: bool = False,
                            adv_is_dunce: bool = False) -> dict:
    """Resolve combat for a single front-row square.

    `square` must contain: 'adventurer', 'monster', 'bonus', 'is_king',
    'is_dunce'.  Returns a result dict with both sides' power breakdown
    plus 'victory'.

    Monster role:
        is_king  → final power ×2, plus the monster's single biggest-
                   weakness keyword is dropped from its weakness count.
        is_dunce → final power ÷2.

    Hero role (passed via adv_is_king / adv_is_dunce):
        is_king  → final adv power ×2.
        is_dunce → final adv power ÷2.
    """
    adv: Adventurer = square['adventurer']
    monster: Monster = square['monster']
    bonus: dict = square['bonus']
    monster_is_king  = bool(square.get('is_king'))
    monster_is_dunce = bool(square.get('is_dunce'))

    # Square bonuses
    adv_bonus_keywords: List[str] = []
    monster_bonus_keywords: List[str] = []
    adv_resists: List[str] = []
    monster_resists: List[str] = []

    if bonus['type'] == 'keyword_buff':
        adv_bonus_keywords.append(bonus['keyword'])
        monster_bonus_keywords.append(bonus['keyword'])
    elif bonus['type'] == 'keyword_resist':
        adv_resists.append(bonus['keyword'])
        monster_resists.append(bonus['keyword'])

    # Adventurer ability immunities also act as resists
    adv_resists.extend(_normalize_immunity_list(adv.ability_effect.get('immune_weakness', [])))

    # ----- Adventurer side -----
    adv_keywords = adv.get_all_keywords() + adv_bonus_keywords
    adv_raw_base = adv.get_base_points()

    adv_kw_counts: Dict[str, int] = {}
    for k in adv_keywords:
        adv_kw_counts[k] = adv_kw_counts.get(k, 0) + 1
    adv_mult = max(1, _count_keyword_matches(adv_kw_counts))

    monster_keywords = monster.keywords + monster_bonus_keywords

    # Compute per-keyword weakness contributions so a hero king can drop the
    # single highest-contributing one (symmetric with monster king)
    adv_contribs = _weakness_contributions(
        adv_keywords, monster_keywords, adv_resists, keyword_registry)
    adv_weakness = sum(adv_contribs.values())
    adv_dropped_kw: Optional[str] = None
    if adv_is_king and adv_contribs:
        adv_dropped_kw = max(adv_contribs, key=adv_contribs.get)
        adv_weakness -= adv_contribs[adv_dropped_kw]

    adv_power = int((adv_raw_base * adv_mult) / (1 + adv_weakness))

    # Hero role modifiers
    if adv_is_king:
        adv_power *= 2
    elif adv_is_dunce:
        adv_power = adv_power // 2

    # ----- Monster side -----
    monster_base = monster.base_points
    monster_kw_counts: Dict[str, int] = {}
    for k in monster_keywords:
        monster_kw_counts[k] = monster_kw_counts.get(k, 0) + 1
    monster_mult = max(1, _count_keyword_matches(monster_kw_counts))

    # Per-keyword weakness contributions (so king can ignore its biggest one)
    contribs = _weakness_contributions(
        monster_keywords, adv_keywords, monster_resists, keyword_registry)
    total_weakness = sum(contribs.values())
    dropped_kw: Optional[str] = None
    if monster_is_king and contribs:
        # Drop the single monster keyword with the highest weakness contribution
        dropped_kw = max(contribs, key=contribs.get)
        total_weakness -= contribs[dropped_kw]

    monster_weakness = total_weakness
    monster_power = int((monster_base * monster_mult) / (1 + monster_weakness))

    # Monster role modifiers
    if monster_is_king:
        monster_power *= 2
    elif monster_is_dunce:
        monster_power = monster_power // 2

    victory = adv_power >= monster_power

    return {
        'adventurer': adv,
        'monster': monster,
        'multiplier': 1,           # legacy field — multipliers removed
        'adv_power': adv_power,
        'adv_raw_base': adv_raw_base,
        'adv_base': adv_raw_base,  # legacy
        'adv_mult': adv_mult,
        'adv_weakness': adv_weakness,
        'adv_dropped_keyword': adv_dropped_kw,
        'adv_is_king': adv_is_king,
        'adv_is_dunce': adv_is_dunce,
        'monster_power': monster_power,
        'monster_base': monster_base,
        'monster_mult': monster_mult,
        'monster_weakness': monster_weakness,
        'monster_is_king': monster_is_king,
        'monster_is_dunce': monster_is_dunce,
        'king_dropped_keyword': dropped_kw,
        'victory': victory,
        'bonus': bonus,
    }


# ---------------------------------------------------------------------------
# Boss combat — unchanged role-wise; multiplier system removed
# ---------------------------------------------------------------------------

def calculate_boss_combat(adv: Adventurer, monster: Monster, boss_square: dict,
                          adv_square_mult: int, keyword_registry: KeywordRegistry) -> dict:
    """Resolve a boss fight.  Boss is treated as a heavy monster.

    `adv_square_mult` is kept in the signature for compatibility but is no
    longer applied; boss strength comes from its base_points.
    """
    bonus: dict = boss_square['bonus']

    adv_bonus_keywords: List[str] = []
    monster_bonus_keywords: List[str] = []
    if bonus['type'] == 'keyword_buff':
        adv_bonus_keywords.append(bonus['keyword'])
        monster_bonus_keywords.append(bonus['keyword'])

    immune = _normalize_immunity_list(adv.ability_effect.get('immune_weakness', []))

    # ----- Adventurer side -----
    adv_keywords = adv.get_all_keywords() + adv_bonus_keywords
    adv_raw_base = adv.get_base_points()

    adv_kw_counts: Dict[str, int] = {}
    for k in adv_keywords:
        adv_kw_counts[k] = adv_kw_counts.get(k, 0) + 1
    adv_mult = max(1, _count_keyword_matches(adv_kw_counts))

    monster_keywords = monster.keywords + monster_bonus_keywords

    adv_weakness = 0
    for k in adv_keywords:
        kw_obj = keyword_registry.get(k)
        if kw_obj:
            for ek in monster_keywords:
                if ek in immune:
                    continue
                if kw_obj.is_weak_against(ek):
                    adv_weakness += 1

    adv_power = int((adv_raw_base * adv_mult) / (1 + adv_weakness))

    # ----- Monster side ----- (bosses are always treated as "king" — they
    # get the king's ×2 + ignore-biggest-weakness treatment by design.)
    monster_base = monster.base_points
    monster_kw_counts: Dict[str, int] = {}
    for k in monster_keywords:
        monster_kw_counts[k] = monster_kw_counts.get(k, 0) + 1
    monster_mult = max(1, _count_keyword_matches(monster_kw_counts))

    contribs = _weakness_contributions(
        monster_keywords, adv_keywords, [], keyword_registry)
    total_weakness = sum(contribs.values())
    dropped_kw: Optional[str] = None
    if contribs:
        dropped_kw = max(contribs, key=contribs.get)
        total_weakness -= contribs[dropped_kw]
    monster_weakness = total_weakness

    monster_power = int((monster_base * monster_mult) / (1 + monster_weakness))
    monster_power *= 2   # boss = king bonus
    victory = adv_power >= monster_power

    return {
        'adventurer': adv,
        'monster': monster,
        'multiplier': 1,
        'adv_square_mult': 1,
        'adv_power': adv_power,
        'adv_base': adv_raw_base,
        'adv_boosted_base': adv_raw_base,
        'adv_mult': adv_mult,
        'adv_weakness': adv_weakness,
        'monster_power': monster_power,
        'monster_base': monster_base,
        'monster_multiplied_base': monster_base,
        'monster_mult': monster_mult,
        'monster_weakness': monster_weakness,
        'king_dropped_keyword': dropped_kw,
        'victory': victory,
        'bonus': bonus,
        'boss_reward': None,
    }


# ---------------------------------------------------------------------------
# Square bonus generation
# ---------------------------------------------------------------------------

def generate_square_bonus(keyword_registry: KeywordRegistry) -> dict:
    """Roll a random bonus for a delve square: buff, resist, or none."""
    bonus_type = random.choice(['keyword_buff', 'keyword_resist', 'none', 'none'])
    if bonus_type == 'none':
        return {'type': 'none'}
    keywords = keyword_registry.all_ids()
    if not keywords:
        return {'type': 'none'}
    return {'type': bonus_type, 'keyword': random.choice(keywords)}