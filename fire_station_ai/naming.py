"""Codename helpers for saved Fire Station models."""

from __future__ import annotations

import random
from typing import Iterable, Optional, Set


ADJECTIVES = [
    "冷焰",
    "疾风",
    "静海",
    "玄月",
    "苍砂",
    "夜幕",
    "赤霄",
    "白刃",
    "霜刃",
    "流火",
    "暗潮",
    "惊雷",
    "远岚",
    "孤星",
    "沉锋",
    "微光",
]

NOUNS = [
    "筹术师",
    "夜行鲨",
    "铁筹狼",
    "影骰客",
    "风纹狐",
    "静牌鲸",
    "迷雾雀",
    "断崖豹",
    "火纹蛇",
    "黑曜鸦",
    "回声犬",
    "长夜隼",
    "碎浪鲨",
    "薄暮獾",
    "银塔鹿",
    "深巷猫",
]


def generate_codename(rng: Optional[random.Random] = None, used: Optional[Iterable[str]] = None) -> str:
    rng = rng or random.Random()
    used_set: Set[str] = set(used or [])
    pool_size = len(ADJECTIVES) * len(NOUNS)

    for _ in range(min(256, pool_size * 2)):
        name = f"{rng.choice(ADJECTIVES)}{rng.choice(NOUNS)}"
        if name not in used_set:
            return name

    suffix = 2
    while True:
        name = f"{rng.choice(ADJECTIVES)}{rng.choice(NOUNS)}{suffix}"
        if name not in used_set:
            return name
        suffix += 1
