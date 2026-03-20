"""Codename helpers for saved Fire Station models."""

from __future__ import annotations

import random
from typing import Iterable, Optional, Set


import random

# 前缀 —— 2~3字，状态/形容类
ADJECTIVES = [
    "皇家",    # Royal
    "诈唬",    # Bluffing
    "全押",    # All-In
    "暗牌",    # Pocket
    "失控",    # Tilted
    "同花",    # Suited
    "爆牌",    # Busted
    "满筹",    # Stacked
    "出千",    # Rigged
    "弃牌",    # Folded
    "加注",    # Raised
    "翻牌",    # Flopped
    "河牌",    # Rivered
    "幸运",    # Lucky
    "百搭",    # Wild
    "过牌",    # Checked
    "底注",    # Ante
    "杂色",    # Offsuit
    "压制",    # Dominated
    "烧牌",    # Burned
]

# 后缀 —— 2~3字，名词类，大量牌名
NOUNS = [
    # 标准牌名
    "老A",      # Ace
    "老K",      # King
    "老Q",      # Queen
    "老J",      # Jack
    "鬼牌",     # Joker
    "小二",     # Deuce（2的别称）
    # 花色
    "黑桃",     # Spade
    "梅花",     # Club
    "方块",     # Diamond
    "红心",     # Heart
    # 牌型
    "同花",     # Flush
    "顺子",     # Straight
    "摊牌",     # Showdown
    # 牌的江湖别称
    "子弹",     # Bullet（A的别称）
    "牛仔",     # Cowboy（K的别称）
    "女王",     # Lady（Q的别称）
    "铁钩",     # Hook（J的别称）
    "双鸭",     # Ducks（2-2的别称）
    "雪人",     # Snowmen（8-8的别称）
    "帆船",     # Sailboats（4-4的别称）
    # 扑克人物
    "鲨鱼",     # Shark
    "鱼腩",     # Fish
    "大鲸",     # Whale
    "老千",     # Hustler
    "赌徒",     # Gambler
    "独行侠",   # Maverick
    "枪手",     # Gunslinger
    "庄家",     # Dealer
    # 术语
    "筹码",     # Chip
    "底池",     # Pot
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
