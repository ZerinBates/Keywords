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
# Sequential boss combat (4-hero relay)
# ---------------------------------------------------------------------------
#
# Design:
#   * The boss has a single "total score" (HP pool) and a list of keywords.
#   * Heroes fight one at a time, in order.  The LAST hero in the list is the
#     "final hero" and has no threshold.
#   * Each non-final hero must beat a threshold = THRESHOLD_FRACTION of the
#     boss's CURRENT remaining score.
#       - Pass  -> hero survives; boss score -= (hero_power - threshold);
#                  hero strips one keyword off the boss.  If the score hits 0
#                  the boss dies early and the relay ends in victory.
#       - Fail  -> that hero dies immediately (relay continues).
#   * The final hero has no threshold: they win iff their power >= the boss's
#     remaining score.  Win => boss defeated regardless of earlier deaths.
#     Lose => battle lost; the boss is left at full strength (the monster
#     object is never mutated, so returning it to the deck is a full reset).

BOSS_THRESHOLD_FRACTION = 0.30


def boss_keyword_multiplier(keywords: List[str]) -> int:
    """Stack-of-2+ multiplier for a keyword list (min 1)."""
    counts: Dict[str, int] = {}
    for k in keywords:
        counts[k] = counts.get(k, 0) + 1
    return max(1, _count_keyword_matches(counts))


def boss_total_score(base_points: int, keywords: List[str]) -> int:
    """The boss's displayed total score / HP pool.

    Hero-independent: base x keyword-multiplier x2 (the boss king bonus).
    """
    return int(base_points * boss_keyword_multiplier(keywords)) * 2


def boss_threshold(score: int, fraction: float = BOSS_THRESHOLD_FRACTION) -> int:
    """Threshold a hero must beat = `fraction` of the current boss score."""
    return int(score * fraction)


def adventurer_boss_power(adv: Adventurer, boss_keywords: List[str], bonus: dict,
                          keyword_registry: KeywordRegistry) -> dict:
    """A single hero's combat power against the boss's current keywords.

    Mirrors the adventurer side of `calculate_boss_combat` (no square / earned
    multiplier is applied — boss strength comes from base points).
    """
    adv_bonus_keywords: List[str] = []
    if bonus.get('type') == 'keyword_buff':
        adv_bonus_keywords.append(bonus['keyword'])

    immune = _normalize_immunity_list(adv.ability_effect.get('immune_weakness', []))

    adv_keywords = adv.get_all_keywords() + adv_bonus_keywords
    adv_raw_base = adv.get_base_points()

    counts: Dict[str, int] = {}
    for k in adv_keywords:
        counts[k] = counts.get(k, 0) + 1
    adv_mult = max(1, _count_keyword_matches(counts))

    adv_weakness = 0
    for k in adv_keywords:
        kw_obj = keyword_registry.get(k)
        if not kw_obj:
            continue
        for ek in boss_keywords:
            if ek in immune:
                continue
            if kw_obj.is_weak_against(ek):
                adv_weakness += 1

    power = int((adv_raw_base * adv_mult) / (1 + adv_weakness))
    return {
        'power': power,
        'base': adv_raw_base,
        'mult': adv_mult,
        'weakness': adv_weakness,
    }


def boss_item_defense(item, boss_keywords: List[str]) -> int:
    """How hard one of the boss's items is to destroy.

    The boss actively guards its gear, so an item's defense is its own points
    scaled by the boss's current keyword multiplier — smashing stacked items
    first breaks that multiplier and softens the rest.
    """
    return max(1, int(item.points * boss_keyword_multiplier(boss_keywords)))


def resolve_boss_item_attack(adv: Adventurer, item, boss_keywords: List[str],
                             bonus: dict,
                             keyword_registry: KeywordRegistry) -> dict:
    """One hero strikes at one of the boss's equipped items.

    Pure: returns a step dict. Caller applies side effects (item removal and
    total recompute on success, hero death on failure).
    """
    ap = adventurer_boss_power(adv, boss_keywords, bonus, keyword_registry)
    defense = boss_item_defense(item, boss_keywords)
    destroyed = ap['power'] >= defense
    return {
        'kind': 'item',
        'adventurer': adv,
        'item': item,
        'is_final': False,
        'power': ap['power'],
        'adv_base': ap['base'],
        'adv_mult': ap['mult'],
        'adv_weakness': ap['weakness'],
        'threshold': defense,
        'destroyed': destroyed,
        'survived': destroyed,
        'killed_boss': False,
        'damage': 0,
    }


def resolve_boss_challenge(adv: Adventurer, boss_keywords: List[str],
                           boss_score: int, bonus: dict,
                           keyword_registry: KeywordRegistry) -> dict:
    """One hero challenges the boss itself — win or lose, this ends the fight."""
    ap = adventurer_boss_power(adv, boss_keywords, bonus, keyword_registry)
    win = ap['power'] >= boss_score
    return {
        'kind': 'boss',
        'adventurer': adv,
        'is_final': True,
        'power': ap['power'],
        'adv_base': ap['base'],
        'adv_mult': ap['mult'],
        'adv_weakness': ap['weakness'],
        'threshold': boss_score,
        'destroyed': False,
        'survived': win,
        'killed_boss': win,
        'damage': boss_score if win else 0,
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