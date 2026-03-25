#!/usr/bin/env python3
"""Leo's Casino - 终端小赌场"""

import json
import os
import random
import sys
import time
from datetime import datetime

# ============================================================
# 存档系统
# ============================================================
GAME_VERSION = "v1.2.0"
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves")
EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
FIRE_STATION_AI_RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fire_station_ai", "runs")
MAX_SLOTS = 5
INITIAL_CHIPS = 1000
MAX_GOVERNMENT_AID = 3
GOVERNMENT_AID_AMOUNT = 200
MIN_BANK_RATIO = 0.0
MAX_BANK_RATIO = 1.0
DAILY_OPERATION_COUNT = 20
MIN_LOAN_AMOUNT = 3000
BANK_DAILY_INTEREST = 0.0012
LOAN_TIERS = [
    {"name": "一档", "daily_rate": 0.0035},
    {"name": "二档", "daily_rate": 0.0055},
    {"name": "三档", "daily_rate": 0.0080},
]
LOCATIONS = {
    "home": "家里",
    "casino": "赌场",
    "bank": "银行",
    "pawnshop": "典当行",
}
ASSET_MARKETS = [
    {
        "id": "city_bonds",
        "name": "旧城债票",
        "tag": "稳健",
        "base_price": 120,
        "drift": 0.002,
        "volatility": 0.015,
        "yield_rate": 0.0015,
        "floor": 90,
        "ceiling": 165,
        "desc": "像比银行更灵活一点的慢收益票据。",
    },
    {
        "id": "vending_route",
        "name": "售货机点位",
        "tag": "经营",
        "base_price": 80,
        "drift": 0.001,
        "volatility": 0.040,
        "yield_rate": 0.0032,
        "floor": 45,
        "ceiling": 145,
        "desc": "现金流不错，但偶尔会停电、卡货、被人顺走两瓶汽水。",
    },
    {
        "id": "pawn_notes",
        "name": "典当凭单",
        "tag": "经营",
        "base_price": 140,
        "drift": 0.003,
        "volatility": 0.050,
        "yield_rate": 0.0024,
        "floor": 85,
        "ceiling": 220,
        "desc": "和街区资金周转挂钩，回报稳定但不算安静。",
    },
    {
        "id": "lamp_oil",
        "name": "洋油期货",
        "tag": "投机",
        "base_price": 100,
        "drift": 0.000,
        "volatility": 0.100,
        "yield_rate": 0.0000,
        "floor": 35,
        "ceiling": 260,
        "desc": "纯看情绪和传闻，涨得快，跌起来也快。",
    },
]


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def default_stats():
    return {
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "blackjacks": 0,
        "total_bet": 0,
        "biggest_win": 0,
        "bank_deposit_total": 0,
        "bank_withdraw_total": 0,
        "bank_interest_earned": 0,
        "loan_borrowed_total": 0,
        "loan_repaid_total": 0,
        "loan_interest_paid": 0,
        "government_aid_taken": 0,
        "bosses_defeated": 0,
        "operations_count": 0,
        "asset_trade_count": 0,
        "asset_buy_total": 0,
        "asset_sell_total": 0,
        "asset_realized_profit": 0,
        "asset_passive_income": 0,
        "games": {
            "blackjack": {"plays": 0, "wins": 0, "losses": 0, "pushes": 0, "net": 0, "biggest_win": 0, "special": 0},
            "craps": {"plays": 0, "wins": 0, "losses": 0, "pushes": 0, "net": 0, "biggest_win": 0, "special": 0},
            "slots": {"plays": 0, "wins": 0, "losses": 0, "pushes": 0, "net": 0, "biggest_win": 0, "special": 0},
            "fire_station": {"plays": 0, "wins": 0, "losses": 0, "pushes": 0, "net": 0, "biggest_win": 0, "special": 0},
            "runner": {"plays": 0, "wins": 0, "losses": 0, "pushes": 0, "net": 0, "biggest_win": 0, "special": 0},
        },
    }


def default_player_profile():
    return {
        "total_hands": 0,
        "fold_count": 0,
        "bluff_caught": 0,
        "raise_freq": [],
        "showdown_cards": [],
    }


FIRE_STATION_OPPONENTS = [
    {
        "name": "阿炳",
        "title": "街头老千",
        "personality": "tight",
        "chips": 700,
        "mood": 0.40,
        "quote": "看清楚再下注，小牌桌也能让人输得发抖。",
    },
    {
        "name": "红桃K",
        "title": "夜班赌徒",
        "personality": "loose",
        "chips": 900,
        "mood": 0.55,
        "quote": "不敢跟的人，通常已经输了半手。",
    },
    {
        "name": "鬼手七",
        "title": "偷鸡大师",
        "personality": "tricky",
        "chips": 1150,
        "mood": 0.65,
        "quote": "你的习惯，我两手牌就能记住。",
    },
    {
        "name": "白鲸",
        "title": "高压庄家",
        "personality": "tight",
        "chips": 1400,
        "mood": 0.35,
        "quote": "底池越大，犹豫的代价越高。",
    },
    {
        "name": "维克多",
        "title": "终局庄家",
        "personality": "tricky",
        "chips": 1800,
        "mood": 0.70,
        "quote": "Leo 把最后一桌留给了我。你撑得到现在，值得尊重。",
        "boss": True,
    },
]

FIRE_STATION_BET_TIERS = [5, 10, 25, 50, 100]

RUNNER_TABLES = {
    "client": ["旧码头的修理工", "夜市摊主", "巷口拳馆", "西区酒吧", "后街医务室"],
    "cargo": ["一包芯片", "几卷底片", "封好的纸袋", "一箱零件", "一只冷藏手提箱"],
    "route": ["绕开巡逻的河堤", "穿过夜班地铁口", "沿着停电的旧街区", "从市场后门", "借一条废弃高架"],
    "risk": ["有人在盯梢", "路口突然临检", "联系人临时换点", "车胎有点发软", "对面也在抢这单"],
}


def default_fire_station_state():
    opener = FIRE_STATION_OPPONENTS[0]
    return {
        "stage": 0,
        "cycle": 0,
        "ai_chips": opener["chips"],
        "mood": opener["mood"],
        "personality": opener["personality"],
        "player_profile": default_player_profile(),
        "ai_mode": "classic",
        "ai_model_path": "",
        "ai_model_name": "",
    }


def default_asset_state(asset):
    return {
        "price": asset["base_price"],
        "history": [asset["base_price"]],
        "shares": 0,
        "avg_cost": 0.0,
        "realized_profit": 0,
        "passive_income_total": 0,
        "short_shares": 0,
        "short_avg_cost": 0.0,
    }


def default_pawnshop_state():
    return {
        "assets": {asset["id"]: default_asset_state(asset) for asset in ASSET_MARKETS},
    }


def default_profile():
    return {
        "location": "home",
        "bank": 0,
        "bank_ratio": 0.5,
        "loans": [{"balance": 0} for _ in LOAN_TIERS],
        "operation_count": 0,
        "bank_days_elapsed": 0,
        "government_aid_used": 0,
        "retired": False,
        "retire_reason": "",
        "retired_at": "",
        "created_at": now_str(),
        "career_high_assets": INITIAL_CHIPS,
        "export_count": 0,
        "history": [],
        "slots": {
            "free_spins": 0,
            "free_spin_bet": 0,
            "streak": 0,
        },
        "fire_station": default_fire_station_state(),
        "runner": {
            "last_day": -1,
        },
        "pawnshop": default_pawnshop_state(),
    }


def normalize_stats(stats):
    base = default_stats()
    if isinstance(stats, dict):
        for key, value in stats.items():
            if key == "games" and isinstance(value, dict):
                for game_key, game_stats in value.items():
                    if game_key in base["games"] and isinstance(game_stats, dict):
                        base["games"][game_key].update(game_stats)
            else:
                base[key] = value
    return base


def normalize_player_profile(profile):
    base = default_player_profile()
    if isinstance(profile, dict):
        for key, value in profile.items():
            if key == "raise_freq" and isinstance(value, list):
                base[key] = value[-20:]
            elif key == "showdown_cards" and isinstance(value, list):
                base[key] = value[-20:]
            else:
                base[key] = value
    return base


def normalize_loans(loans):
    base = [{"balance": 0} for _ in LOAN_TIERS]
    if isinstance(loans, list):
        for idx, loan in enumerate(loans[:len(LOAN_TIERS)]):
            if isinstance(loan, dict):
                base[idx]["balance"] = max(0, safe_int(loan.get("balance", 0), 0))
            else:
                base[idx]["balance"] = max(0, safe_int(loan, 0))
    return base


def asset_definitions():
    return ASSET_MARKETS


def asset_definition_map():
    return {asset["id"]: asset for asset in ASSET_MARKETS}


def normalize_asset_state(asset_id, asset_state):
    asset = asset_definition_map()[asset_id]
    base = default_asset_state(asset)
    if isinstance(asset_state, dict):
        for key, value in asset_state.items():
            if key == "history" and isinstance(value, list):
                cleaned = [max(1, safe_int(item, asset["base_price"])) for item in value[-8:]]
                base["history"] = cleaned or [asset["base_price"]]
            elif key in {"avg_cost", "short_avg_cost"}:
                base[key] = max(0.0, safe_float(value, 0.0))
            else:
                base[key] = value
    base["price"] = max(asset["floor"], min(asset["ceiling"], safe_int(base.get("price", asset["base_price"]), asset["base_price"])))
    base["shares"] = max(0, safe_int(base.get("shares", 0), 0))
    base["avg_cost"] = max(0.0, safe_float(base.get("avg_cost", 0.0), 0.0))
    base["realized_profit"] = safe_int(base.get("realized_profit", 0), 0)
    base["passive_income_total"] = max(0, safe_int(base.get("passive_income_total", 0), 0))
    base["short_shares"] = max(0, safe_int(base.get("short_shares", 0), 0))
    base["short_avg_cost"] = max(0.0, safe_float(base.get("short_avg_cost", 0.0), 0.0))
    history = [max(asset["floor"], min(asset["ceiling"], safe_int(item, base["price"]))) for item in base.get("history", [])[-8:]]
    if not history:
        history = [base["price"]]
    history[-1] = base["price"]
    base["history"] = history
    return base


def normalize_pawnshop_state(state):
    base = default_pawnshop_state()
    raw_assets = state.get("assets") if isinstance(state, dict) else None
    if isinstance(raw_assets, dict):
        for asset in ASSET_MARKETS:
            asset_id = asset["id"]
            if asset_id in raw_assets:
                base["assets"][asset_id] = normalize_asset_state(asset_id, raw_assets[asset_id])
    elif isinstance(state, dict):
        # Forward-compatible fallback for older flat structures.
        for asset in ASSET_MARKETS:
            asset_id = asset["id"]
            if asset_id in state:
                base["assets"][asset_id] = normalize_asset_state(asset_id, state[asset_id])
    return base


def current_fire_opponent(fire_state):
    cycle = max(0, fire_state.get("cycle", 0))
    stage = fire_state.get("stage", 0) % len(FIRE_STATION_OPPONENTS)
    base = dict(FIRE_STATION_OPPONENTS[stage])
    bonus = cycle * 150
    if base.get("boss"):
        bonus += cycle * 100
    base["chips"] += bonus
    base["cycle"] = cycle
    return base


def normalize_fire_station_state(state):
    base = default_fire_station_state()
    if isinstance(state, dict):
        for key, value in state.items():
            if key == "player_profile":
                base[key] = normalize_player_profile(value)
            else:
                base[key] = value
    opponent = current_fire_opponent(base)
    base["personality"] = opponent["personality"]
    if base.get("ai_chips", 0) <= 0:
        base["ai_chips"] = opponent["chips"]
    ai_mode = str(base.get("ai_mode", "classic") or "classic").lower()
    if ai_mode not in {"classic", "model"}:
        ai_mode = "classic"
    ai_model_path = str(base.get("ai_model_path", "") or "")
    ai_model_name = str(base.get("ai_model_name", "") or "")
    if ai_mode == "model" and (not ai_model_path or not os.path.exists(ai_model_path)):
        ai_mode = "classic"
        ai_model_path = ""
        ai_model_name = ""
    base["ai_mode"] = ai_mode
    base["ai_model_path"] = ai_model_path
    base["ai_model_name"] = ai_model_name
    return base


def normalize_profile(profile):
    base = default_profile()
    if isinstance(profile, dict):
        for key, value in profile.items():
            if key == "slots" and isinstance(value, dict):
                base["slots"].update(value)
            elif key == "fire_station":
                base["fire_station"] = normalize_fire_station_state(value)
            elif key == "runner" and isinstance(value, dict):
                base["runner"].update(value)
            elif key == "pawnshop":
                base["pawnshop"] = normalize_pawnshop_state(value)
            elif key == "loans":
                base["loans"] = normalize_loans(value)
            elif key == "history" and isinstance(value, list):
                base["history"] = value
            else:
                base[key] = value
    location = str(base.get("location", "home") or "home").lower()
    if location not in LOCATIONS:
        location = "home"
    base["location"] = location
    base["bank_ratio"] = min(MAX_BANK_RATIO, max(MIN_BANK_RATIO, safe_float(base.get("bank_ratio", 0.5), 0.5)))
    base["bank"] = max(0, safe_int(base.get("bank", 0), 0))
    base["operation_count"] = max(0, safe_int(base.get("operation_count", 0), 0))
    base["bank_days_elapsed"] = max(0, safe_int(base.get("bank_days_elapsed", 0), 0))
    base["export_count"] = max(0, safe_int(base.get("export_count", 0), 0))
    base["government_aid_used"] = max(0, min(MAX_GOVERNMENT_AID, safe_int(base.get("government_aid_used", 0), 0)))
    base["slots"]["free_spins"] = max(0, safe_int(base["slots"].get("free_spins", 0), 0))
    base["slots"]["free_spin_bet"] = max(0, safe_int(base["slots"].get("free_spin_bet", 0), 0))
    base["slots"]["streak"] = max(0, safe_int(base["slots"].get("streak", 0), 0))
    base["runner"]["last_day"] = safe_int(base["runner"].get("last_day", -1), -1)
    base["loans"] = normalize_loans(base.get("loans"))
    base["fire_station"] = normalize_fire_station_state(base["fire_station"])
    base["pawnshop"] = normalize_pawnshop_state(base["pawnshop"])
    return base


def market_asset_state(profile, asset_id):
    assets = profile.setdefault("pawnshop", default_pawnshop_state()).setdefault("assets", {})
    if asset_id not in assets:
        assets[asset_id] = default_asset_state(asset_definition_map()[asset_id])
    return assets[asset_id]


def market_value(profile):
    total = 0
    for asset in ASSET_MARKETS:
        state = market_asset_state(profile, asset["id"])
        total += safe_int(state.get("shares", 0), 0) * safe_int(state.get("price", asset["base_price"]), asset["base_price"])
    return total


def gross_assets(chips, profile):
    return int(chips) + int(profile.get("bank", 0)) + market_value(profile)


def total_debt(profile):
    return sum(max(0, safe_int(loan.get("balance", 0), 0)) for loan in profile.get("loans", []))


def total_assets(chips, profile):
    return gross_assets(chips, profile) - total_debt(profile)


def update_career_high(chips, profile):
    profile["career_high_assets"] = max(profile.get("career_high_assets", INITIAL_CHIPS), total_assets(chips, profile))


def loan_tier_cap(chips, profile):
    assets = total_assets(chips, profile)
    if assets <= 0:
        return 0
    return max(MIN_LOAN_AMOUNT, int(assets * 2))


def next_loan_tier_index(chips, profile):
    cap = loan_tier_cap(chips, profile)
    if cap <= 0:
        return None
    loans = profile.get("loans", [])
    for idx, loan in enumerate(loans):
        balance = safe_int(loan.get("balance", 0), 0)
        if balance < cap:
            if idx == 0:
                return idx
            prev_balance = safe_int(loans[idx - 1].get("balance", 0), 0)
            if prev_balance >= cap:
                return idx
            return None
    return None


def max_loan_borrow_amount(chips, profile):
    tier_index = next_loan_tier_index(chips, profile)
    if tier_index is None:
        return 0
    cap = loan_tier_cap(chips, profile)
    return max(0, cap - safe_int(profile["loans"][tier_index].get("balance", 0), 0))


def min_loan_borrow_amount(chips, profile):
    max_amount = max_loan_borrow_amount(chips, profile)
    if max_amount <= 0:
        return 0
    return min(MIN_LOAN_AMOUNT, max_amount)


def operation_progress(profile):
    return profile.get("operation_count", 0) % DAILY_OPERATION_COUNT


def asset_price_change_pct(old_price, new_price):
    if old_price <= 0:
        return 0.0
    return (new_price - old_price) / old_price * 100


def apply_asset_market_day(chips, stats, profile):
    messages = []
    before = state_snapshot(chips, profile)
    passive_income = 0
    biggest_move = None

    for asset in ASSET_MARKETS:
        state = market_asset_state(profile, asset["id"])
        old_price = max(1, safe_int(state.get("price", asset["base_price"]), asset["base_price"]))
        reversion = ((asset["base_price"] - old_price) / asset["base_price"]) * 0.12
        shock = random.uniform(-asset["volatility"], asset["volatility"])
        pct_move = asset["drift"] + reversion + shock
        new_price = int(round(old_price * (1 + pct_move)))
        new_price = max(asset["floor"], min(asset["ceiling"], new_price))
        if new_price == old_price and random.random() < 0.45:
            nudge = random.choice([-1, 1])
            new_price = max(asset["floor"], min(asset["ceiling"], old_price + nudge))
        state["price"] = new_price
        history = state.setdefault("history", [])
        history.append(new_price)
        state["history"] = history[-8:]

        move_abs = abs(new_price - old_price)
        if biggest_move is None or move_abs > biggest_move["move_abs"]:
            biggest_move = {
                "name": asset["name"],
                "from": old_price,
                "to": new_price,
                "move_abs": move_abs,
                "move_pct": asset_price_change_pct(old_price, new_price),
            }

        shares = safe_int(state.get("shares", 0), 0)
        if shares > 0 and asset["yield_rate"] > 0:
            income = max(1, int(round(new_price * shares * asset["yield_rate"])))
            profile["bank"] += income
            stats["asset_passive_income"] += income
            state["passive_income_total"] = safe_int(state.get("passive_income_total", 0), 0) + income
            passive_income += income

    details = {
        "day": profile.get("bank_days_elapsed", 0),
        "passive_income": passive_income,
        "assets": {
            asset["id"]: {
                "price": market_asset_state(profile, asset["id"])["price"],
                "shares": market_asset_state(profile, asset["id"])["shares"],
            }
            for asset in ASSET_MARKETS
        },
    }
    if biggest_move:
        details["biggest_move"] = biggest_move
        direction_color = C.GREEN if biggest_move["to"] >= biggest_move["from"] else C.RED
        messages.append(
            colored(
                f"  [典当行行情] {biggest_move['name']} {biggest_move['from']} -> {biggest_move['to']} ({biggest_move['move_pct']:+.1f}%)",
                direction_color,
            )
        )
    if passive_income > 0:
        messages.append(colored(f"  [经营分红] 今日被动收入已打入银行 +${passive_income}", C.CYAN))
    append_history(
        stats,
        profile,
        "pawnshop",
        "market_day",
        details=details,
        before=before,
        after=state_snapshot(chips, profile),
        operation_delta=0,
    )
    return messages


def apply_bank_day(chips, stats, profile):
    messages = []
    before = state_snapshot(chips, profile)
    bank_interest = 0
    if profile.get("bank", 0) > 0:
        bank_interest = max(1, int(round(profile["bank"] * BANK_DAILY_INTEREST)))
        profile["bank"] += bank_interest
        stats["bank_interest_earned"] += bank_interest

    loan_interest = []
    for idx, tier in enumerate(LOAN_TIERS):
        balance = safe_int(profile["loans"][idx].get("balance", 0), 0)
        if balance <= 0:
            loan_interest.append(0)
            continue
        interest = max(1, int(round(balance * tier["daily_rate"])))
        profile["loans"][idx]["balance"] += interest
        stats["loan_interest_paid"] += interest
        loan_interest.append(interest)

    profile["bank_days_elapsed"] += 1
    summary = [f"第 {profile['bank_days_elapsed']} 天结息"]
    if bank_interest:
        summary.append(f"存款 +${bank_interest}")
    debt_interest = sum(loan_interest)
    if debt_interest:
        summary.append(f"贷款利息 -${debt_interest}")
    if len(summary) > 1:
        messages.append(colored("  [银行结息] " + " / ".join(summary), C.YELLOW))
    messages.extend(apply_asset_market_day(chips, stats, profile))
    append_history(
        stats,
        profile,
        "bank",
        "daily_interest",
        details={
            "day": profile["bank_days_elapsed"],
            "deposit_interest": bank_interest,
            "loan_interest": loan_interest,
            "loan_interest_total": debt_interest,
        },
        before=before,
        after=state_snapshot(chips, profile),
        operation_delta=0,
    )
    return messages


def record_operations(chips, stats, profile, count=1):
    messages = []
    count = max(0, safe_int(count, 0))
    if count <= 0:
        return messages
    profile["operation_count"] += count
    stats["operations_count"] += count
    while profile["operation_count"] >= DAILY_OPERATION_COUNT:
        profile["operation_count"] -= DAILY_OPERATION_COUNT
        messages.extend(apply_bank_day(chips, stats, profile))
        refresh_career_status(chips, stats, profile)
    return messages


def can_claim_government_aid(chips, profile):
    return (
        not profile.get("retired")
        and total_assets(chips, profile) <= 0
        and profile.get("government_aid_used", 0) < MAX_GOVERNMENT_AID
    )


def refresh_career_status(chips, stats, profile):
    update_career_high(chips, profile)
    if total_assets(chips, profile) <= 0 and profile.get("government_aid_used", 0) >= MAX_GOVERNMENT_AID:
        if not profile.get("retired"):
            profile["retired"] = True
            profile["retired_at"] = now_str()
            profile["retire_reason"] = "政府补贴已用尽，净资产归零，生涯终结。"
        return True
    return profile.get("retired", False)


def normalized_save_data(slot, data=None):
    data = data or {}
    chips = safe_int(data.get("chips", INITIAL_CHIPS), INITIAL_CHIPS)
    stats = normalize_stats(data.get("stats"))
    profile = normalize_profile(data.get("profile"))
    if "created_at" not in profile or not profile["created_at"]:
        profile["created_at"] = data.get("save_time", now_str())
    refresh_career_status(chips, stats, profile)
    normalized = {
        "version": data.get("version", GAME_VERSION),
        "chips": chips,
        "stats": stats,
        "profile": profile,
        "save_time": data.get("save_time", now_str()),
        "slot": slot,
    }
    return normalized


def ensure_save_dir():
    os.makedirs(SAVE_DIR, exist_ok=True)


def ensure_export_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)

def save_path(slot):
    return os.path.join(SAVE_DIR, f"slot_{slot}.json")

def save_game(slot, data):
    """保存游戏到指定槽位"""
    ensure_save_dir()
    data["version"] = GAME_VERSION
    data["save_time"] = now_str()
    data["slot"] = slot
    with open(save_path(slot), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_game(slot):
    """从指定槽位加载"""
    p = save_path(slot)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def delete_save(slot):
    """删除存档"""
    p = save_path(slot)
    if os.path.exists(p):
        os.remove(p)

def list_saves():
    """列出所有存档信息"""
    ensure_save_dir()
    saves = {}
    for i in range(1, MAX_SLOTS + 1):
        data = load_game(i)
        if data is not None:
            data = normalized_save_data(i, data)
        saves[i] = data
    return saves

def auto_save(slot, chips, stats, profile):
    """自动存档"""
    refresh_career_status(chips, stats, profile)
    data = {
        "chips": chips,
        "stats": stats,
        "profile": profile,
    }
    save_game(slot, data)


def short_save_time(text):
    if not text:
        return "???"
    if len(text) >= 16:
        return text[5:16]
    return text


def state_snapshot(chips, profile):
    return {
        "cash": int(chips),
        "bank": int(profile.get("bank", 0)),
        "market_value": int(market_value(profile)),
        "debt": int(total_debt(profile)),
        "net_assets": int(total_assets(chips, profile)),
        "bank_ratio": float(profile.get("bank_ratio", 0.5)),
        "operation_cycle_progress": int(operation_progress(profile)),
        "bank_days_elapsed": int(profile.get("bank_days_elapsed", 0)),
        "location": profile.get("location", "home"),
    }


def location_label(location):
    return LOCATIONS.get(location, "家里")


def travel_to(chips, slot, stats, profile, target):
    current = profile.get("location", "home")
    if target not in LOCATIONS:
        target = "home"
    if current == target:
        profile["location"] = target
        return
    before = state_snapshot(chips, profile)
    profile["location"] = target
    append_history(
        stats,
        profile,
        "system",
        "travel",
        details={"from": current, "to": target},
        before=before,
        after=state_snapshot(chips, profile),
        operation_delta=0,
    )
    auto_save(slot, chips, stats, profile)


def game_stats(stats, key):
    games = stats.setdefault("games", default_stats()["games"])
    if key not in games:
        games[key] = {"plays": 0, "wins": 0, "losses": 0, "pushes": 0, "net": 0, "biggest_win": 0, "special": 0}
    return games[key]


def record_game_result(stats, key, result, delta, special_inc=0):
    entry = game_stats(stats, key)
    entry["plays"] += 1
    if result == "win":
        entry["wins"] += 1
    elif result == "loss":
        entry["losses"] += 1
    else:
        entry["pushes"] += 1
    entry["net"] += delta
    if delta > 0:
        entry["biggest_win"] = max(entry["biggest_win"], delta)
    if special_inc:
        entry["special"] += special_inc


def runner_available(profile):
    return profile.get("runner", {}).get("last_day", -1) != profile.get("bank_days_elapsed", 0)


def debt_shortfall(chips):
    return max(0, -safe_int(chips, 0))


def build_runner_job():
    return {
        "client": random.choice(RUNNER_TABLES["client"]),
        "cargo": random.choice(RUNNER_TABLES["cargo"]),
        "route": random.choice(RUNNER_TABLES["route"]),
        "risk": random.choice(RUNNER_TABLES["risk"]),
    }


def runner_job_lines(job):
    return [
        f"委托人: {job['client']}",
        f"货物:   {job['cargo']}",
        f"路线:   {job['route']}",
        f"变数:   {job['risk']}",
    ]


def append_history(stats, profile, category, action, details=None, before=None, after=None, operation_delta=0):
    history = profile.setdefault("history", [])
    entry = {
        "id": len(history) + 1,
        "time": now_str(),
        "version": GAME_VERSION,
        "category": category,
        "action": action,
        "operation_delta": max(0, safe_int(operation_delta, 0)),
        "operations_total": safe_int(stats.get("operations_count", 0), 0),
        "details": details or {},
        "before": before,
        "after": after,
    }
    history.append(entry)
    return entry


def export_filename(slot, profile):
    export_index = profile.get("export_count", 0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"slot_{slot}_review_{export_index}_{timestamp}.json"


def build_export_payload(slot, chips, stats, profile):
    return {
        "metadata": {
            "game": "Leo's Casino",
            "version": GAME_VERSION,
            "slot": slot,
            "exported_at": now_str(),
            "created_at": profile.get("created_at", ""),
            "retired": bool(profile.get("retired")),
            "retired_at": profile.get("retired_at", ""),
            "history_entries": len(profile.get("history", [])),
            "export_count": profile.get("export_count", 0),
        },
        "summary": {
            "cash": chips,
            "bank": profile.get("bank", 0),
            "market_value": market_value(profile),
            "debt": total_debt(profile),
            "net_assets": total_assets(chips, profile),
            "bank_ratio": profile.get("bank_ratio", 0.5),
            "bank_days_elapsed": profile.get("bank_days_elapsed", 0),
            "operations_total": stats.get("operations_count", 0),
            "government_aid_used": profile.get("government_aid_used", 0),
            "career_high_assets": profile.get("career_high_assets", INITIAL_CHIPS),
            "bank_interest_earned": stats.get("bank_interest_earned", 0),
            "loan_interest_paid": stats.get("loan_interest_paid", 0),
            "asset_realized_profit": stats.get("asset_realized_profit", 0),
            "asset_passive_income": stats.get("asset_passive_income", 0),
            "location": profile.get("location", "home"),
        },
        "stats": stats,
        "loans": profile.get("loans", []),
        "pawnshop": profile.get("pawnshop", {}),
        "history": profile.get("history", []),
    }


def export_review_data(slot, chips, stats, profile):
    ensure_export_dir()
    before = state_snapshot(chips, profile)
    profile["export_count"] = profile.get("export_count", 0) + 1
    append_history(
        stats,
        profile,
        "system",
        "export_review",
        details={
            "slot": slot,
            "export_index": profile["export_count"],
        },
        before=before,
        after=state_snapshot(chips, profile),
        operation_delta=0,
    )
    payload = build_export_payload(slot, chips, stats, profile)
    path = os.path.join(EXPORT_DIR, export_filename(slot, profile))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def show_career_summary(chips, stats, profile, slot, wait=True):
    clear()
    assets = total_assets(chips, profile)
    debt = total_debt(profile)
    holdings = market_value(profile)
    total_games = stats.get("wins", 0) + stats.get("losses", 0) + stats.get("pushes", 0)
    win_rate = (stats.get("wins", 0) / total_games * 100) if total_games else 0
    lines = [
        f"存档:         {colored(f'槽位 {slot}', C.CYAN)}",
        f"版本:         {colored(GAME_VERSION, C.WHITE)}",
        f"创建时间:     {colored(profile.get('created_at', '???'), C.DIM)}",
        f"结束时间:     {colored(profile.get('retired_at', '进行中') or '进行中', C.DIM)}",
        "",
        f"总局数:       {colored(str(total_games), C.WHITE)}",
        f"胜/负/平:     {colored(str(stats.get('wins', 0)), C.GREEN)}/{colored(str(stats.get('losses', 0)), C.RED)}/{colored(str(stats.get('pushes', 0)), C.BLUE)}",
        f"胜率:         {colored(f'{win_rate:.1f}%', C.YELLOW)}",
        f"最大单笔赢:   {colored('$' + str(stats.get('biggest_win', 0)), C.GREEN)}",
        f"累计下注:     {colored('$' + str(stats.get('total_bet', 0)), C.CYAN)}",
        "",
        f"最终现金:     {colored('$' + str(chips), C.RED if chips <= 0 else C.GREEN)}",
        f"银行余额:     {colored('$' + str(profile.get('bank', 0)), C.YELLOW)}",
        f"持仓市值:     {colored('$' + str(holdings), C.CYAN if holdings > 0 else C.DIM)}",
        f"贷款负债:     {colored('$' + str(debt), C.RED if debt > 0 else C.DIM)}",
        f"最终净资产:   {colored('$' + str(assets), C.RED if assets <= 0 else C.GREEN)}",
        f"资产峰值:     {colored('$' + str(profile.get('career_high_assets', INITIAL_CHIPS)), C.MAGENTA)}",
        f"政府补贴:     {colored(str(profile.get('government_aid_used', 0)), C.YELLOW)}/{MAX_GOVERNMENT_AID}",
        f"Boss 击败数:  {colored(str(stats.get('bosses_defeated', 0)), C.MAGENTA)}",
        f"银行天数:     {colored(str(profile.get('bank_days_elapsed', 0)), C.CYAN)}",
        f"累计收息:     {colored('$' + str(stats.get('bank_interest_earned', 0)), C.GREEN)}",
        f"累计付息:     {colored('$' + str(stats.get('loan_interest_paid', 0)), C.RED)}",
        f"交易已实现:   {colored('$' + str(stats.get('asset_realized_profit', 0)), C.GREEN if stats.get('asset_realized_profit', 0) >= 0 else C.RED)}",
        f"经营被动收:   {colored('$' + str(stats.get('asset_passive_income', 0)), C.CYAN)}",
    ]
    if profile.get("retire_reason"):
        lines.extend(["", colored(profile["retire_reason"], C.RED)])
    print(box(lines, width=50, title="生涯总结", color=C.RED if profile.get("retired") else C.MAGENTA))
    if wait:
        pause()


def career_summary_menu(chips, stats, profile, slot):
    while True:
        show_career_summary(chips, stats, profile, slot, wait=False)
        print(colored("\n  [E] 导出复盘数据  [Enter] 返回", C.DIM))
        choice = input(colored("  > ", C.YELLOW)).strip().upper()
        if choice == 'E':
            path = export_review_data(slot, chips, stats, profile)
            auto_save(slot, chips, stats, profile)
            print(colored(f"\n  已导出到: {path}", C.GREEN))
            pause()
            continue
        break


def save_menu():
    """存档管理界面，返回 (chips, stats, profile, active_slot) 或 None"""
    while True:
        clear()
        print(colored(f"\n  ── 存档管理 ── {GAME_VERSION}\n", C.CYAN))
        saves = list_saves()

        lines = []
        for i in range(1, MAX_SLOTS + 1):
            data = saves[i]
            if data:
                chips = data["chips"]
                profile = data["profile"]
                t = short_save_time(data.get("save_time", "???"))
                wins = data["stats"].get("wins", 0)
                losses = data["stats"].get("losses", 0)
                assets = total_assets(chips, profile)
                debt = total_debt(profile)
                if profile.get("retired"):
                    slot_line = (
                        colored(str(i), C.GREEN)
                        + "  "
                        + colored("生涯结束", C.RED)
                        + f"  资产{colored('$' + str(assets), C.RED)}  {colored(t, C.DIM)}"
                    )
                else:
                    slot_line = (
                        colored(str(i), C.GREEN)
                        + f"  现金{colored('$' + str(chips), C.YELLOW)}"
                        + f"/银{colored('$' + str(profile.get('bank', 0)), C.CYAN)}"
                        + f"/债{colored('$' + str(debt), C.RED if debt else C.DIM)}"
                        + f"  胜{wins}/负{losses}  {colored(t, C.DIM)}"
                    )
                lines.append(slot_line)
            else:
                lines.append(colored(str(i), C.GREEN) + colored("  ── 空槽位 ──", C.DIM))
        lines.append("")
        lines.append(colored("N", C.GREEN) + "  新游戏")
        lines.append(colored("D", C.RED) + "  删除存档")
        lines.append(colored("0", C.RED) + "  退出游戏")

        print(box(lines, width=64, title="存档", color=C.CYAN))
        print(colored("\n  输入槽位编号加载，N 新建，D 删除，0 退出", C.DIM))

        try:
            choice = input(colored("  > ", C.YELLOW)).strip().upper()
        except (EOFError, KeyboardInterrupt):
            return None

        if choice == '0':
            return None
        elif choice == 'N':
            # 找空槽位或让用户选
            empty = [i for i in range(1, MAX_SLOTS + 1) if saves[i] is None]
            if empty:
                slot = empty[0]
            else:
                print(colored("  所有槽位已满！请先删除一个存档。", C.RED))
                pause()
                continue
            stats = default_stats()
            profile = default_profile()
            append_history(
                stats,
                profile,
                "system",
                "new_save_created",
                details={"slot": slot, "initial_cash": INITIAL_CHIPS},
                before=None,
                after=state_snapshot(INITIAL_CHIPS, profile),
                operation_delta=0,
            )
            auto_save(slot, INITIAL_CHIPS, stats, profile)
            print(colored(f"  新游戏已创建在槽位 {slot}！", C.GREEN))
            pause()
            return (INITIAL_CHIPS, stats, profile, slot)
        elif choice == 'D':
            print(f"  输入要删除的槽位 (1-{MAX_SLOTS}):")
            try:
                ds = int(input(colored("  > ", C.YELLOW)))
            except (ValueError, EOFError):
                continue
            if 1 <= ds <= MAX_SLOTS and saves[ds]:
                print(colored(f"  确定删除槽位 {ds}？(Y/N)", C.RED))
                confirm = input(colored("  > ", C.YELLOW)).strip().upper()
                if confirm == 'Y':
                    delete_save(ds)
                    print(colored("  已删除。", C.GREEN))
                    pause()
            else:
                print(colored("  无效槽位。", C.RED))
                pause()
        elif choice.isdigit() and 1 <= int(choice) <= MAX_SLOTS:
            slot = int(choice)
            data = saves[slot]
            if data:
                if data["profile"].get("retired"):
                    career_summary_menu(data["chips"], data["stats"], data["profile"], slot)
                    continue
                return (data["chips"], data["stats"], data["profile"], slot)
            else:
                # 空槽位，新建
                stats = default_stats()
                profile = default_profile()
                append_history(
                    stats,
                    profile,
                    "system",
                    "new_save_created",
                    details={"slot": slot, "initial_cash": INITIAL_CHIPS},
                    before=None,
                    after=state_snapshot(INITIAL_CHIPS, profile),
                    operation_delta=0,
                )
                auto_save(slot, INITIAL_CHIPS, stats, profile)
                print(colored(f"  新游戏已创建在槽位 {slot}！", C.GREEN))
                pause()
                return (INITIAL_CHIPS, stats, profile, slot)

# ============================================================
# 颜色系统
# ============================================================
class C:
    """ANSI 颜色码"""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_GREEN = "\033[42m"
    BG_RED   = "\033[41m"

def colored(text, color):
    return f"{color}{text}{C.RESET}"

def bold(text):
    return f"{C.BOLD}{text}{C.RESET}"

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def pause(msg="按 Enter 继续..."):
    input(colored(f"\n{msg}", C.DIM))

# ============================================================
# UI 绘制
# ============================================================
def box(lines, width=40, title="", color=C.CYAN):
    """画一个方框"""
    w = width - 2
    result = []
    if title:
        t = f" {title} "
        pad = w - len_display(t)
        left = pad // 2
        right = pad - left
        result.append(colored(f"┌{'─' * left}{t}{'─' * right}┐", color))
    else:
        result.append(colored(f"┌{'─' * w}┐", color))
    for line in lines:
        display_len = len_display(line)
        spacing = w - display_len
        if spacing < 0:
            spacing = 0
        result.append(colored("│", color) + f" {line}{' ' * (spacing - 1)}" + colored("│", color))
    result.append(colored(f"└{'─' * w}┘", color))
    return "\n".join(result)


def pad_display(text, target_width):
    spacing = target_width - len_display(text)
    if spacing < 0:
        spacing = 0
    return text + (" " * spacing)


def render_box_columns(boxes, gap=3):
    rendered = []
    widths = []
    max_lines = 0
    for content in boxes:
        lines = content.splitlines()
        rendered.append(lines)
        widths.append(max((len_display(line) for line in lines), default=0))
        max_lines = max(max_lines, len(lines))

    merged = []
    for row in range(max_lines):
        parts = []
        for idx, lines in enumerate(rendered):
            line = lines[row] if row < len(lines) else ""
            parts.append(pad_display(line, widths[idx]))
        merged.append((" " * gap).join(parts).rstrip())
    return "\n".join(merged)

def len_display(s):
    """计算字符串的显示宽度（去掉 ANSI 转义码）"""
    import re
    clean = re.sub(r'\033\[[0-9;]*m', '', s)
    # 中文字符占2格
    width = 0
    for ch in clean:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            width += 2
        else:
            width += 1
    return width

def asset_position_summary(profile, asset):
    state = market_asset_state(profile, asset["id"])
    shares = safe_int(state.get("shares", 0), 0)
    price = safe_int(state.get("price", asset["base_price"]), asset["base_price"])
    avg_cost = safe_float(state.get("avg_cost", 0.0), 0.0)
    market_val = shares * price
    unrealized = int(round((price - avg_cost) * shares))
    history = state.get("history", [price])
    prev_price = history[-2] if len(history) >= 2 else price
    return {
        "state": state,
        "shares": shares,
        "price": price,
        "avg_cost": avg_cost,
        "market_value": market_val,
        "unrealized": unrealized,
        "prev_price": prev_price,
        "move_pct": asset_price_change_pct(prev_price, price),
    }


def total_unrealized_profit(profile):
    return sum(asset_position_summary(profile, asset)["unrealized"] for asset in ASSET_MARKETS)


def asset_chart_lines(profile, asset):
    state = market_asset_state(profile, asset["id"])
    history = state.get("history", [state.get("price", asset["base_price"])])[-8:]
    if not history:
        history = [asset["base_price"]]
    low = min(history)
    high = max(history)
    span = max(1, high - low)
    lines = []
    for idx, price in enumerate(history, start=max(1, len(history) - 7)):
        bar_len = 1 + int(((price - low) / span) * 12)
        if idx == 1:
            color = C.DIM
        else:
            prev = history[idx - 2]
            color = C.GREEN if price >= prev else C.RED
        lines.append(f"D{idx:02d} {str(price).rjust(4)} {colored('█' * bar_len, color)}")
    return lines


def pawnshop_market_lines(profile):
    lines = []
    for idx, asset in enumerate(ASSET_MARKETS, start=1):
        info = asset_position_summary(profile, asset)
        direction_color = C.GREEN if info["price"] >= info["prev_price"] else C.RED
        pnl_color = C.GREEN if info["unrealized"] >= 0 else C.RED
        yield_text = f"{asset['yield_rate'] * 100:.2f}%/天" if asset["yield_rate"] > 0 else "无分红"
        lines.append(
            f"{idx}. {asset['name']} {colored('[$' + str(info['price']) + ']', direction_color)}"
            f"  持仓 {colored(str(info['shares']), C.WHITE)}"
            f"  浮盈 {colored('$' + str(info['unrealized']), pnl_color)}"
        )
        lines.append(f"   {asset['tag']} | {yield_text} | {asset['desc']}")
    return lines


def pawnshop_portfolio_lines(profile):
    holdings = market_value(profile)
    unrealized = total_unrealized_profit(profile)
    realized = safe_int(sum(market_asset_state(profile, asset["id"]).get("realized_profit", 0) for asset in ASSET_MARKETS), 0)
    passive = safe_int(sum(market_asset_state(profile, asset["id"]).get("passive_income_total", 0) for asset in ASSET_MARKETS), 0)
    return [
        f"持仓市值: {colored('$' + str(holdings), C.CYAN if holdings > 0 else C.DIM)}",
        f"浮动盈亏: {colored('$' + str(unrealized), C.GREEN if unrealized >= 0 else C.RED)}",
        f"已实现:   {colored('$' + str(realized), C.GREEN if realized >= 0 else C.RED)}",
        f"被动收入: {colored('$' + str(passive), C.CYAN)}",
        "空头位已预留，当前版本暂时只开放做多。",
    ]


def location_hint_lines(current):
    items = [
        ("H", "家里", "home"),
        ("C", "赌场", "casino"),
        ("B", "银行", "bank"),
        ("P", "典当行", "pawnshop"),
    ]
    lines = []
    for key, label, loc in items:
        text = f"{key} {label}"
        if loc == current:
            lines.append(colored(text + " (当前)", C.GREEN))
        else:
            lines.append(colored(text, C.CYAN))
    lines.extend([
        colored("S 战绩统计", C.YELLOW),
        colored("E 导出复盘", C.YELLOW),
        colored("G 领取补贴", C.YELLOW),
        colored("SKIP 跳到下一天", C.YELLOW),
        colored("0 保存并离开", C.RED),
    ])
    return lines


def header(chips, slot=None, stats=None, profile=None):
    """顶部状态栏"""
    chip_str = f"${chips}"
    if chips >= 1000:
        chip_color = C.GREEN
    elif chips >= 300:
        chip_color = C.YELLOW
    else:
        chip_color = C.RED
    lines = [
        bold(colored(f"♠ ♥ ♣ ♦  Leo's Casino {GAME_VERSION}  ♦ ♣ ♥ ♠", C.YELLOW)),
        "",
        f"  现金: {colored(chip_str, chip_color)}",
    ]
    if profile is not None:
        assets = total_assets(chips, profile)
        debt = total_debt(profile)
        lines.append(
            f"  地点: {colored(location_label(profile.get('location', 'home')), C.MAGENTA)}"
            f"  银行: {colored('$' + str(profile.get('bank', 0)), C.CYAN)}"
        )
        lines.append(
            f"  持仓: {colored('$' + str(market_value(profile)), C.WHITE)}"
            f"  负债: {colored('$' + str(debt), C.RED if debt > 0 else C.DIM)}"
        )
        lines.append(
            f"  净资产: {colored('$' + str(assets), C.GREEN if assets > 0 else C.RED)}"
            f"  结息: {colored(str(DAILY_OPERATION_COUNT - operation_progress(profile)), C.YELLOW)}步后"
        )
    if slot is not None:
        slot_info = f"  存档: 槽位 {slot}"
        if stats:
            slot_info += f"  W{stats.get('wins',0)}/L{stats.get('losses',0)}"
        lines.append(colored(slot_info, C.DIM))
    print(box(lines, width=68, color=C.YELLOW))


def global_command_result(choice, chips, slot, stats, profile):
    choice = (choice or "").strip().upper()
    travel_map = {
        "H": "home",
        "C": "casino",
        "B": "bank",
        "P": "pawnshop",
    }
    if choice in travel_map:
        travel_to(chips, slot, stats, profile, travel_map[choice])
        return chips, travel_map[choice]
    if choice == 'S':
        show_stats(chips, stats, profile)
        return chips, None
    if choice == 'E':
        path = export_review_data(slot, chips, stats, profile)
        auto_save(slot, chips, stats, profile)
        clear()
        header(chips, slot, stats, profile)
        print(colored("\n  复盘数据已导出。", C.GREEN))
        print(colored(f"  路径: {path}", C.DIM))
        pause()
        return chips, None
    if choice == 'G':
        chips = claim_government_aid(chips, slot, stats, profile)
        return chips, None
    if choice == 'SKIP':
        chips = skip_to_next_day(chips, slot, stats, profile)
        return chips, None
    if choice == '0':
        return chips, "__exit__"
    return chips, "__local__"


def max_bank_withdrawal(chips, profile):
    assets = total_assets(chips, profile)
    ratio = profile.get("bank_ratio", MIN_BANK_RATIO)
    limit = int(assets * ratio - chips)
    return max(0, min(profile.get("bank", 0), limit))


def loan_lines(chips, profile):
    cap = loan_tier_cap(chips, profile)
    lines = []
    for idx, tier in enumerate(LOAN_TIERS):
        balance = safe_int(profile["loans"][idx].get("balance", 0), 0)
        status = f"${balance}/${cap}" if cap > 0 else f"${balance}/锁定"
        lines.append(f"{tier['name']}: {colored(status, C.RED if balance > 0 else C.DIM)}  日息 {tier['daily_rate'] * 100:.2f}%")
    return lines


def bank_menu(chips, slot, stats, profile):
    while True:
        clear()
        header(chips, slot, stats, profile)
        assets = total_assets(chips, profile)
        debt = total_debt(profile)
        shortfall = debt_shortfall(chips)
        ratio = profile.get("bank_ratio", MIN_BANK_RATIO)
        max_withdraw = max_bank_withdrawal(chips, profile)
        next_borrow = max_loan_borrow_amount(chips, profile)
        min_borrow = min_loan_borrow_amount(chips, profile)
        overview_lines = [
            f"现金:       {colored('$' + str(chips), C.GREEN if chips > 0 else C.RED)}",
            f"银行余额:   {colored('$' + str(profile.get('bank', 0)), C.CYAN)}",
            f"贷款负债:   {colored('$' + str(debt), C.RED if debt > 0 else C.DIM)}",
            f"净资产:     {colored('$' + str(assets), C.YELLOW if assets > 0 else C.RED)}",
            f"安全比率:   {colored(f'{ratio:.2f}', C.MAGENTA)}",
            f"本次最多取: {colored('$' + str(max_withdraw), C.WHITE)}",
            f"当前可借:   {colored('$' + str(next_borrow), C.GREEN if next_borrow > 0 else C.DIM)}",
            f"结息倒计时: {colored(str(DAILY_OPERATION_COUNT - operation_progress(profile)), C.YELLOW)} 操作",
        ]
        action_lines = [
            colored("1", C.GREEN) + "  存钱",
            colored("2", C.GREEN) + "  取钱",
            colored("3", C.GREEN) + "  设置安全比率",
            colored("4", C.GREEN) + "  借款",
            colored("5", C.GREEN) + "  还款",
            (colored("6", C.GREEN) + "  一键补缺") if shortfall > 0 and profile.get("bank", 0) > 0 else (colored("6", C.DIM) + "  一键补缺"),
        ]
        print(colored("\n  ── 银行 ──\n", C.CYAN))
        left_panel = box(overview_lines, width=34, title="资产总览", color=C.CYAN)
        right_panel = box(loan_lines(chips, profile), width=42, title="贷款分档", color=C.MAGENTA)
        print(render_box_columns([left_panel, right_panel]))
        print()
        print(render_box_columns([
            box(action_lines, width=34, title="银行操作", color=C.GREEN),
            box([
                "取钱后，现金不能超过 净资产 x 安全比率",
                "借款按一档→二档→三档开放。",
                f"每 {DAILY_OPERATION_COUNT} 次操作自动结算一天利息。",
                "现金为负时，可用一键补缺自动回填。",
                "",
                colored("提示", C.YELLOW) + "  利率越高越危险，优先还高档贷款。",
            ], width=42, title="规则说明", color=C.YELLOW)
        ]))
        print()
        print(box(location_hint_lines("bank"), width=68, title="全局快捷", color=C.BLUE))
        if shortfall > 0:
            print(colored(f"  当前现金欠款 ${shortfall}，在补齐前不能参加任何赌桌。", C.RED))

        choice = input(colored("\n  选择 > ", C.YELLOW)).strip().upper()
        chips, global_result = global_command_result(choice, chips, slot, stats, profile)
        if global_result == "__exit__":
            return chips, "__exit__"
        if global_result in LOCATIONS and global_result != "bank":
            return chips, global_result
        if global_result != "__local__":
            continue
        if choice == '1':
            if chips <= 0:
                print(colored("  你手上没有可存入的现金。", C.RED))
                pause()
                continue
            print(f"  输入存入金额 (1-{chips})，或输入 0 取消:")
            try:
                amount = int(input(colored("  > ", C.YELLOW)))
            except (ValueError, EOFError):
                continue
            if amount == 0:
                continue
            if amount < 1 or amount > chips:
                print(colored("  金额无效。", C.RED))
                pause()
                continue
            before = state_snapshot(chips, profile)
            chips -= amount
            profile["bank"] += amount
            stats["bank_deposit_total"] += amount
            notices = record_operations(chips, stats, profile, 1)
            append_history(
                stats,
                profile,
                "bank",
                "deposit",
                details={"amount": amount},
                before=before,
                after=state_snapshot(chips, profile),
                operation_delta=1,
            )
            auto_save(slot, chips, stats, profile)
            print(colored(f"  已存入 ${amount}。", C.GREEN))
            for notice in notices:
                print(notice)
            pause()
        elif choice == '2':
            if profile.get("bank", 0) <= 0:
                print(colored("  银行里没有钱。", C.RED))
                pause()
                continue
            if max_withdraw <= 0:
                print(colored("  当前安全比率限制下，暂时不能再取钱。", C.RED))
                pause()
                continue
            print(f"  输入取出金额 (1-{max_withdraw})，或输入 0 取消:")
            try:
                amount = int(input(colored("  > ", C.YELLOW)))
            except (ValueError, EOFError):
                continue
            if amount == 0:
                continue
            if amount < 1 or amount > max_withdraw:
                print(colored("  超出可取范围。", C.RED))
                pause()
                continue
            before = state_snapshot(chips, profile)
            chips += amount
            profile["bank"] -= amount
            stats["bank_withdraw_total"] += amount
            notices = record_operations(chips, stats, profile, 1)
            append_history(
                stats,
                profile,
                "bank",
                "withdraw",
                details={"amount": amount, "limit": max_withdraw},
                before=before,
                after=state_snapshot(chips, profile),
                operation_delta=1,
            )
            auto_save(slot, chips, stats, profile)
            print(colored(f"  已取出 ${amount}。", C.GREEN))
            for notice in notices:
                print(notice)
            pause()
        elif choice == '3':
            print(f"  输入新的安全比率 ({MIN_BANK_RATIO:.1f}-{MAX_BANK_RATIO:.1f})，如 0.6:")
            try:
                ratio_input = float(input(colored("  > ", C.YELLOW)))
            except (ValueError, EOFError):
                continue
            if ratio_input < MIN_BANK_RATIO or ratio_input > MAX_BANK_RATIO:
                print(colored("  超出允许范围。", C.RED))
                pause()
                continue
            before = state_snapshot(chips, profile)
            old_ratio = profile.get("bank_ratio", 0.5)
            profile["bank_ratio"] = round(ratio_input, 2)
            notices = record_operations(chips, stats, profile, 1)
            append_history(
                stats,
                profile,
                "bank",
                "set_ratio",
                details={"from": old_ratio, "to": profile["bank_ratio"]},
                before=before,
                after=state_snapshot(chips, profile),
                operation_delta=1,
            )
            auto_save(slot, chips, stats, profile)
            print(colored(f"  安全比率已设置为 {profile['bank_ratio']:.2f}。", C.GREEN))
            for notice in notices:
                print(notice)
            pause()
        elif choice == '4':
            tier_index = next_loan_tier_index(chips, profile)
            if tier_index is None or next_borrow <= 0:
                print(colored("  当前没有可借额度。", C.RED))
                pause()
                continue
            print(colored(f"  当前档位最少借款 ${min_borrow}。", C.DIM))
            print(colored(f"  将进入{LOAN_TIERS[tier_index]['name']}，日息 {LOAN_TIERS[tier_index]['daily_rate'] * 100:.2f}%。", C.DIM))
            print(f"  输入借款金额 ({min_borrow}-{next_borrow})，或输入 0 取消:")
            try:
                amount = int(input(colored("  > ", C.YELLOW)))
            except (ValueError, EOFError):
                continue
            if amount == 0:
                continue
            if amount < min_borrow or amount > next_borrow:
                print(colored("  超出当前档位可借范围。", C.RED))
                pause()
                continue
            before = state_snapshot(chips, profile)
            profile["loans"][tier_index]["balance"] += amount
            chips += amount
            stats["loan_borrowed_total"] += amount
            notices = record_operations(chips, stats, profile, 1)
            append_history(
                stats,
                profile,
                "bank",
                "borrow",
                details={
                    "amount": amount,
                    "tier_index": tier_index,
                    "tier_name": LOAN_TIERS[tier_index]["name"],
                    "daily_rate": LOAN_TIERS[tier_index]["daily_rate"],
                },
                before=before,
                after=state_snapshot(chips, profile),
                operation_delta=1,
            )
            auto_save(slot, chips, stats, profile)
            print(colored(f"  已从{LOAN_TIERS[tier_index]['name']}借入 ${amount}。", C.GREEN))
            for notice in notices:
                print(notice)
            pause()
        elif choice == '5':
            if debt <= 0:
                print(colored("  当前没有贷款需要偿还。", C.RED))
                pause()
                continue
            if chips <= 0:
                print(colored("  手上没有现金可还款。", C.RED))
                pause()
                continue
            max_repay = min(chips, debt)
            print(f"  输入还款金额 (1-{max_repay})，或输入 0 取消:")
            try:
                amount = int(input(colored("  > ", C.YELLOW)))
            except (ValueError, EOFError):
                continue
            if amount == 0:
                continue
            if amount < 1 or amount > max_repay:
                print(colored("  金额无效。", C.RED))
                pause()
                continue
            before = state_snapshot(chips, profile)
            chips -= amount
            remaining = amount
            for idx in range(len(LOAN_TIERS) - 1, -1, -1):
                balance = safe_int(profile["loans"][idx].get("balance", 0), 0)
                if balance <= 0:
                    continue
                paid = min(balance, remaining)
                profile["loans"][idx]["balance"] -= paid
                remaining -= paid
                if remaining <= 0:
                    break
            stats["loan_repaid_total"] += amount
            notices = record_operations(chips, stats, profile, 1)
            append_history(
                stats,
                profile,
                "bank",
                "repay",
                details={"amount": amount},
                before=before,
                after=state_snapshot(chips, profile),
                operation_delta=1,
            )
            auto_save(slot, chips, stats, profile)
            print(colored(f"  已还款 ${amount}。", C.GREEN))
            for notice in notices:
                print(notice)
            pause()
        elif choice == '6':
            if shortfall <= 0:
                print(colored("  当前没有现金欠款需要补。", C.RED))
                pause()
                continue
            if profile.get("bank", 0) <= 0:
                print(colored("  银行里没有钱可用于补缺。", C.RED))
                pause()
                continue
            before = state_snapshot(chips, profile)
            amount = min(profile.get("bank", 0), shortfall)
            chips += amount
            profile["bank"] -= amount
            stats["bank_withdraw_total"] += amount
            notices = record_operations(chips, stats, profile, 1)
            append_history(
                stats,
                profile,
                "bank",
                "cover_cash_shortfall",
                details={
                    "amount": amount,
                    "shortfall_before": shortfall,
                    "shortfall_after": debt_shortfall(chips),
                },
                before=before,
                after=state_snapshot(chips, profile),
                operation_delta=1,
            )
            auto_save(slot, chips, stats, profile)
            if debt_shortfall(chips) == 0:
                print(colored(f"  已用银行资金补齐 ${amount}，现金恢复为 ${chips}。", C.GREEN))
            else:
                print(colored(f"  已补上 ${amount}，但现金仍欠 ${debt_shortfall(chips)}。", C.YELLOW))
            for notice in notices:
                print(notice)
            pause()
        else:
            print(colored("  无效输入。", C.RED))
            pause()


def choose_asset_from_market(chips, slot, stats, profile, title="选择资产"):
    while True:
        clear()
        header(chips, slot, stats, profile)
        print(colored(f"\n  ── {title} ──\n", C.MAGENTA))
        print(box(pawnshop_market_lines(profile), width=68, title="典当行行情", color=C.MAGENTA))
        print(colored("\n  输入资产编号，或直接回车取消。", C.DIM))
        choice = input(colored("  > ", C.YELLOW)).strip()
        if not choice:
            return None
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(ASSET_MARKETS):
                return ASSET_MARKETS[idx - 1]
        print(colored("  无效编号。", C.RED))
        pause()


def pawnshop_buy_asset(chips, slot, stats, profile):
    asset = choose_asset_from_market(chips, slot, stats, profile, title="买入资产")
    if asset is None:
        return chips
    info = asset_position_summary(profile, asset)
    price = info["price"]
    max_shares = chips // price
    if max_shares <= 0:
        print(colored("  现金不够，至少也得先攒一手。", C.RED))
        pause()
        return chips
    print(colored(f"\n  {asset['name']} 当前价格 ${price}，最多可买 {max_shares} 份。", C.CYAN))
    print(colored("  输入买入份数，或输入 0 取消。", C.DIM))
    try:
        shares = int(input(colored("  > ", C.YELLOW)))
    except (ValueError, EOFError):
        return chips
    if shares <= 0:
        return chips
    if shares > max_shares:
        print(colored("  超出可买范围。", C.RED))
        pause()
        return chips
    before = state_snapshot(chips, profile)
    state = market_asset_state(profile, asset["id"])
    cost = shares * price
    total_basis = safe_float(state.get("avg_cost", 0.0), 0.0) * safe_int(state.get("shares", 0), 0) + cost
    state["shares"] = safe_int(state.get("shares", 0), 0) + shares
    state["avg_cost"] = total_basis / state["shares"]
    chips -= cost
    stats["asset_trade_count"] += 1
    stats["asset_buy_total"] += cost
    notices = record_operations(chips, stats, profile, 1)
    append_history(
        stats,
        profile,
        "pawnshop",
        "buy_asset",
        details={
            "asset_id": asset["id"],
            "asset_name": asset["name"],
            "shares": shares,
            "price": price,
            "cost": cost,
        },
        before=before,
        after=state_snapshot(chips, profile),
        operation_delta=1,
    )
    auto_save(slot, chips, stats, profile)
    print(colored(f"  已买入 {asset['name']} x{shares}，花费 ${cost}。", C.GREEN))
    for notice in notices:
        print(notice)
    pause()
    return chips


def pawnshop_sell_asset(chips, slot, stats, profile):
    owned_assets = [asset for asset in ASSET_MARKETS if asset_position_summary(profile, asset)["shares"] > 0]
    if not owned_assets:
        print(colored("  你手上还没有可卖出的持仓。", C.RED))
        pause()
        return chips
    asset = choose_asset_from_market(chips, slot, stats, profile, title="卖出资产")
    if asset is None:
        return chips
    info = asset_position_summary(profile, asset)
    if info["shares"] <= 0:
        print(colored("  这项资产你还没持有。", C.RED))
        pause()
        return chips
    print(colored(f"\n  {asset['name']} 当前价格 ${info['price']}，可卖 {info['shares']} 份。", C.CYAN))
    print(colored("  输入卖出份数，或输入 0 取消。", C.DIM))
    try:
        shares = int(input(colored("  > ", C.YELLOW)))
    except (ValueError, EOFError):
        return chips
    if shares <= 0:
        return chips
    if shares > info["shares"]:
        print(colored("  超出可卖范围。", C.RED))
        pause()
        return chips
    before = state_snapshot(chips, profile)
    state = market_asset_state(profile, asset["id"])
    revenue = shares * info["price"]
    realized = int(round((info["price"] - safe_float(state.get("avg_cost", 0.0), 0.0)) * shares))
    chips += revenue
    state["shares"] = safe_int(state.get("shares", 0), 0) - shares
    if state["shares"] <= 0:
        state["shares"] = 0
        state["avg_cost"] = 0.0
    state["realized_profit"] = safe_int(state.get("realized_profit", 0), 0) + realized
    stats["asset_trade_count"] += 1
    stats["asset_sell_total"] += revenue
    stats["asset_realized_profit"] += realized
    notices = record_operations(chips, stats, profile, 1)
    append_history(
        stats,
        profile,
        "pawnshop",
        "sell_asset",
        details={
            "asset_id": asset["id"],
            "asset_name": asset["name"],
            "shares": shares,
            "price": info["price"],
            "revenue": revenue,
            "realized_profit": realized,
        },
        before=before,
        after=state_snapshot(chips, profile),
        operation_delta=1,
    )
    auto_save(slot, chips, stats, profile)
    color = C.GREEN if realized >= 0 else C.RED
    print(colored(f"  已卖出 {asset['name']} x{shares}，回笼 ${revenue}。", C.GREEN))
    print(colored(f"  本次已实现盈亏 ${realized}。", color))
    for notice in notices:
        print(notice)
    pause()
    return chips


def pawnshop_show_asset_chart(chips, slot, stats, profile):
    asset = choose_asset_from_market(chips, slot, stats, profile, title="查看走势")
    if asset is None:
        return
    info = asset_position_summary(profile, asset)
    clear()
    header(chips, slot, stats, profile)
    details = [
        f"资产:     {colored(asset['name'], C.MAGENTA)}",
        f"分类:     {colored(asset['tag'], C.CYAN)}",
        f"当前价格: {colored('$' + str(info['price']), C.GREEN if info['price'] >= info['prev_price'] else C.RED)}",
        f"持仓份数: {colored(str(info['shares']), C.WHITE)}",
        f"持仓成本: {colored('$' + format(info['avg_cost'], '.1f'), C.YELLOW)}",
        f"浮动盈亏: {colored('$' + str(info['unrealized']), C.GREEN if info['unrealized'] >= 0 else C.RED)}",
        f"日收益率: {colored(format(asset['yield_rate'] * 100, '.2f') + '%', C.CYAN if asset['yield_rate'] > 0 else C.DIM)}",
        "",
        asset["desc"],
    ]
    print(colored(f"\n  ── {asset['name']} ──\n", C.MAGENTA))
    print(render_box_columns([
        box(details, width=34, title="资产详情", color=C.CYAN),
        box(asset_chart_lines(profile, asset), width=31, title="近 8 天 ASCII 走势", color=C.MAGENTA),
    ], gap=3))
    pause()


def pawnshop_menu(chips, slot, stats, profile):
    while True:
        clear()
        header(chips, slot, stats, profile)
        print(colored("\n  ── 典当行 ──\n", C.MAGENTA))
        print(box(pawnshop_market_lines(profile), width=68, title="当日行情", color=C.MAGENTA))
        print()
        print(render_box_columns([
            box(pawnshop_portfolio_lines(profile), width=34, title="投资组合", color=C.CYAN),
            box([
                colored("1", C.GREEN) + "  买入资产",
                colored("2", C.GREEN) + "  卖出资产",
                colored("3", C.GREEN) + "  查看走势",
            ], width=24, title="典当行操作", color=C.GREEN),
            box([
                "这里处理长期资产和街区生意。",
                "每逢银行结息日，资产价格会统一更新。",
                "带收益的资产会把日收入自动打进银行。",
                "没现金但有持仓时，不算破产，可来这里卖仓救急。",
            ], width=34, title="说明", color=C.YELLOW),
        ], gap=2))
        print()
        print(box(location_hint_lines("pawnshop"), width=68, title="全局快捷", color=C.BLUE))
        choice = input(colored("\n  选择 > ", C.YELLOW)).strip().upper()
        chips, global_result = global_command_result(choice, chips, slot, stats, profile)
        if global_result == "__exit__":
            return chips, "__exit__"
        if global_result in LOCATIONS and global_result != "pawnshop":
            return chips, global_result
        if global_result != "__local__":
            continue
        if choice == '1':
            chips = pawnshop_buy_asset(chips, slot, stats, profile)
        elif choice == '2':
            chips = pawnshop_sell_asset(chips, slot, stats, profile)
        elif choice == '3':
            pawnshop_show_asset_chart(chips, slot, stats, profile)
        else:
            print(colored("  无效输入。", C.RED))
            pause()


def claim_government_aid(chips, slot, stats, profile):
    if not can_claim_government_aid(chips, profile):
        print(colored("  当前不符合领取补贴的条件。", C.RED))
        pause()
        return chips
    before = state_snapshot(chips, profile)
    chips += GOVERNMENT_AID_AMOUNT
    profile["government_aid_used"] += 1
    stats["government_aid_taken"] += 1
    notices = record_operations(chips, stats, profile, 1)
    append_history(
        stats,
        profile,
        "bank",
        "government_aid",
        details={
            "amount": GOVERNMENT_AID_AMOUNT,
            "used": profile["government_aid_used"],
            "remaining": MAX_GOVERNMENT_AID - profile["government_aid_used"],
        },
        before=before,
        after=state_snapshot(chips, profile),
        operation_delta=1,
    )
    auto_save(slot, chips, stats, profile)
    print(colored(f"  政府补贴到账 ${GOVERNMENT_AID_AMOUNT}。第 {profile['government_aid_used']}/{MAX_GOVERNMENT_AID} 次。", C.GREEN))
    for notice in notices:
        print(notice)
    pause()
    return chips

# ============================================================
# 扑克牌系统
# ============================================================
SUITS = {'♠': C.WHITE, '♣': C.WHITE, '♥': C.RED, '♦': C.RED}
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.color = SUITS[suit]
        self.hidden = False

    def value(self):
        if self.rank in ('J', 'Q', 'K'):
            return 10
        if self.rank == 'A':
            return 11
        return int(self.rank)

    def art(self):
        """返回卡牌的 ASCII art 行列表"""
        if self.hidden:
            return [
                "┌─────┐",
                "│░░░░░│",
                "│░░░░░│",
                "│░░░░░│",
                "└─────┘",
            ]
        r = self.rank.ljust(2)
        r2 = self.rank.rjust(2)
        s = self.suit
        c = self.color
        return [
            "┌─────┐",
            f"│{colored(r, c)}   │",
            f"│  {colored(s, c)}  │",
            f"│   {colored(r2, c)}│",
            "└─────┘",
        ]


def card_text(card):
    return f"{card.rank}{card.suit}"

def render_cards(cards, label=""):
    """横向排列渲染多张牌"""
    if label:
        print(colored(f"  {label}", C.DIM))
    arts = [c.art() for c in cards]
    for row in range(5):
        print("  " + " ".join(a[row] for a in arts))

class Deck:
    def __init__(self, num_decks=2):
        self.cards = []
        for _ in range(num_decks):
            for suit in SUITS:
                for rank in RANKS:
                    self.cards.append(Card(rank, suit))
        random.shuffle(self.cards)

    def deal(self):
        if len(self.cards) < 20:
            self.__init__()
        return self.cards.pop()

def hand_value(cards):
    """计算手牌点数（A 自动调整）"""
    total = sum(c.value() for c in cards if not c.hidden)
    aces = sum(1 for c in cards if c.rank == 'A' and not c.hidden)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def is_blackjack_hand(cards):
    return len(cards) == 2 and hand_value(cards) == 21


def can_split_cards(cards):
    return len(cards) == 2 and cards[0].rank == cards[1].rank


def blackjack_reserved_amount(hands, insurance_bet=0):
    return sum(hand["bet"] for hand in hands) + insurance_bet


def render_blackjack_hands(hands, active_index):
    for idx, hand in enumerate(hands, start=1):
        markers = []
        if idx - 1 == active_index:
            markers.append("行动中")
        if hand.get("split"):
            markers.append("分牌")
        if hand.get("doubled"):
            markers.append("加倍")
        if hand.get("surrendered"):
            markers.append("投降")
        if hand.get("done") and not hand.get("surrendered"):
            markers.append("完成")
        marker_text = f" ({'/'.join(markers)})" if markers else ""
        label = f"手牌{idx} [{hand_value(hand['cards'])}] 下注:${hand['bet']}{marker_text}"
        render_cards(hand["cards"], label)
        print()

# ============================================================
# Blackjack (21点)
# ============================================================
def blackjack(chips, slot=None, stats=None, profile=None):
    while True:
        clear()
        header(chips, slot, stats, profile)
        print(colored("\n  ── Blackjack 21点 ──\n", C.CYAN))

        if chips <= 0:
            print(colored("  你已经破产了！回去攒点钱再来吧。", C.RED))
            pause()
            return chips

        # 下注
        print(f"  当前筹码: {colored(f'${chips}', C.GREEN)}")
        print(f"  输入下注金额 (1-{chips})，输入 0 返回大厅")
        try:
            bet = int(input(colored("  > ", C.YELLOW)))
        except (ValueError, EOFError):
            continue
        if bet == 0:
            return chips
        if bet < 1 or bet > chips:
            print(colored("  无效金额！", C.RED))
            pause()
            continue
        round_before = state_snapshot(chips, profile)

        deck = Deck()
        player_hand = {
            "cards": [deck.deal(), deck.deal()],
            "bet": bet,
            "done": False,
            "split": False,
            "doubled": False,
            "surrendered": False,
            "acted": False,
        }
        dealer = [deck.deal(), deck.deal()]
        dealer[1].hidden = True
        hands = [player_hand]
        insurance_bet = 0
        insurance_delta = 0
        insurance_text = None

        available_bankroll = chips - blackjack_reserved_amount(hands)
        if dealer[0].rank == 'A' and available_bankroll >= max(1, bet // 2):
            insurance_offer = max(1, bet // 2)
            clear()
            header(chips, slot, stats, profile)
            print(colored(f"\n  ── Blackjack ── 下注: ${bet} ──\n", C.CYAN))
            render_cards(dealer, f"庄家 [{hand_value(dealer)}]")
            print()
            render_cards(player_hand["cards"], f"你 [{hand_value(player_hand['cards'])}]")
            print(colored(f"\n  庄家明牌是 A，可买保险 ${insurance_offer}。", C.YELLOW))
            print("  [Y] 购买保险  [N] 不买")
            choice = input(colored("  > ", C.YELLOW)).strip().upper()
            if choice == 'Y':
                insurance_bet = insurance_offer

        dealer[1].hidden = False
        dealer_blackjack = is_blackjack_hand(dealer)
        dealer[1].hidden = True

        if dealer_blackjack:
            dealer[1].hidden = False
            clear()
            header(chips, slot, stats, profile)
            print(colored(f"\n  ── 结算 ── 下注: ${bet} ──\n", C.CYAN))
            render_cards(dealer, f"庄家 [{hand_value(dealer)}]")
            print()
            render_cards(player_hand["cards"], f"你 [{hand_value(player_hand['cards'])}]")

            total_delta = insurance_bet * 2 if insurance_bet else 0
            total_bet = bet + insurance_bet
            player_blackjack = is_blackjack_hand(player_hand["cards"])

            if player_blackjack:
                stats["pushes"] += 1
                print(colored("\n  庄家 Blackjack，但你也有 Blackjack。主注平局。", C.BLUE))
            else:
                total_delta -= bet
                stats["losses"] += 1
                print(colored("\n  庄家 Blackjack！主注输掉。", C.RED))

            if insurance_bet:
                print(colored(f"  保险命中！+${insurance_bet * 2}", C.GREEN))

            chips += total_delta
            if total_delta > 0:
                stats["biggest_win"] = max(stats["biggest_win"], total_delta)
            stats["total_bet"] += total_bet
            record_game_result(stats, "blackjack", "push" if player_blackjack else "loss", total_delta, special_inc=1 if player_blackjack else 0)
            notices = record_operations(chips, stats, profile, 1)
            append_history(
                stats,
                profile,
                "blackjack",
                "round_resolved",
                details={
                    "base_bet": bet,
                    "insurance_bet": insurance_bet,
                    "dealer_cards": [card_text(card) for card in dealer],
                    "dealer_blackjack": True,
                    "player_cards": [card_text(card) for card in player_hand["cards"]],
                    "player_blackjack": player_blackjack,
                    "result": "push" if player_blackjack else "lose",
                    "delta": total_delta,
                },
                before=round_before,
                after=state_snapshot(chips, profile),
                operation_delta=1,
            )

            if slot is not None and stats is not None and profile is not None:
                auto_save(slot, chips, stats, profile)
                print(colored("  [自动存档]", C.DIM))
            for notice in notices:
                print(notice)
            pause()
            continue

        if insurance_bet:
            insurance_delta = -insurance_bet
            insurance_text = colored(f"  保险未中，结算时 -${insurance_bet}", C.DIM)

        if is_blackjack_hand(player_hand["cards"]):
            player_hand["done"] = True

        active = 0
        while active < len(hands):
            hand = hands[active]
            if hand["done"]:
                active += 1
                continue

            while not hand["done"]:
                clear()
                header(chips, slot, stats, profile)
                print(colored(f"\n  ── Blackjack ── 基础下注: ${bet} ──\n", C.CYAN))
                render_cards(dealer, f"庄家 [{hand_value(dealer)}]")
                print()
                render_blackjack_hands(hands, active)
                if insurance_text:
                    print(insurance_text)

                value = hand_value(hand["cards"])
                if value >= 21:
                    hand["done"] = True
                    break

                reserved = blackjack_reserved_amount(hands, insurance_bet)
                extra_bankroll = chips - reserved
                options = ["[H] 要牌", "[S] 停牌"]
                if len(hand["cards"]) == 2 and extra_bankroll >= hand["bet"]:
                    options.append("[D] 加倍")
                if len(hands) == 1 and not hand["acted"] and can_split_cards(hand["cards"]) and extra_bankroll >= hand["bet"]:
                    options.append("[P] 分牌")
                if len(hands) == 1 and not hand["acted"]:
                    options.append("[U] 投降")
                print("\n  " + "  ".join(options))
                action = input(colored("  > ", C.YELLOW)).strip().upper()

                if action == 'H':
                    hand["cards"].append(deck.deal())
                    hand["acted"] = True
                    if hand_value(hand["cards"]) >= 21:
                        hand["done"] = True
                elif action == 'S':
                    hand["done"] = True
                elif action == 'D' and len(hand["cards"]) == 2 and extra_bankroll >= hand["bet"]:
                    hand["bet"] *= 2
                    hand["doubled"] = True
                    hand["acted"] = True
                    hand["cards"].append(deck.deal())
                    hand["done"] = True
                elif action == 'P' and len(hands) == 1 and not hand["acted"] and can_split_cards(hand["cards"]) and extra_bankroll >= hand["bet"]:
                    second_card = hand["cards"].pop()
                    new_hand = {
                        "cards": [second_card, deck.deal()],
                        "bet": hand["bet"],
                        "done": False,
                        "split": True,
                        "doubled": False,
                        "surrendered": False,
                        "acted": False,
                    }
                    hand["cards"].append(deck.deal())
                    hand["split"] = True
                    hands.append(new_hand)
                    if hand_value(hand["cards"]) == 21:
                        hand["done"] = True
                    if hand_value(new_hand["cards"]) == 21:
                        new_hand["done"] = True
                elif action == 'U' and len(hands) == 1 and not hand["acted"]:
                    hand["surrendered"] = True
                    hand["done"] = True
                else:
                    continue

            active += 1

        dealer[1].hidden = False
        live_hands = [
            hand for hand in hands
            if not hand.get("surrendered") and hand_value(hand["cards"]) <= 21
        ]
        if live_hands:
            while hand_value(dealer) < 17:
                dealer.append(deck.deal())

        dv = hand_value(dealer)

        clear()
        header(chips, slot, stats, profile)
        print(colored(f"\n  ── 结算 ── 基础下注: ${bet} ──\n", C.CYAN))
        render_cards(dealer, f"庄家 [{dv}]")
        print()
        render_blackjack_hands(hands, -1)

        total_delta = insurance_delta
        if insurance_text:
            print(insurance_text)

        for idx, hand in enumerate(hands, start=1):
            pv = hand_value(hand["cards"])
            if hand.get("surrendered"):
                loss = hand["bet"] // 2
                total_delta -= loss
                stats["losses"] += 1
                print(colored(f"  手牌{idx}: 投降，-${loss}", C.RED))
            elif pv > 21:
                total_delta -= hand["bet"]
                stats["losses"] += 1
                print(colored(f"  手牌{idx}: 爆牌，-${hand['bet']}", C.RED))
            elif not hand.get("split") and is_blackjack_hand(hand["cards"]):
                winnings = int(hand["bet"] * 1.5)
                total_delta += winnings
                stats["wins"] += 1
                stats["blackjacks"] += 1
                print(colored(f"  手牌{idx}: Blackjack！+${winnings}", C.YELLOW))
            elif dv > 21 or pv > dv:
                total_delta += hand["bet"]
                stats["wins"] += 1
                print(colored(f"  手牌{idx}: 赢了！+${hand['bet']}", C.GREEN))
            elif pv == dv:
                stats["pushes"] += 1
                print(colored(f"  手牌{idx}: 平局，退回筹码", C.BLUE))
            else:
                total_delta -= hand["bet"]
                stats["losses"] += 1
                print(colored(f"  手牌{idx}: 输了，-${hand['bet']}", C.RED))

        chips += total_delta
        stats["total_bet"] += blackjack_reserved_amount(hands, insurance_bet)
        if total_delta > 0:
            stats["biggest_win"] = max(stats["biggest_win"], total_delta)
        round_result = "push" if total_delta == 0 else ("win" if total_delta > 0 else "loss")
        round_blackjacks = sum(1 for hand in hands if not hand.get("split") and is_blackjack_hand(hand["cards"]))
        record_game_result(stats, "blackjack", round_result, total_delta, special_inc=round_blackjacks)
        notices = record_operations(chips, stats, profile, 1)
        append_history(
            stats,
            profile,
            "blackjack",
            "round_resolved",
            details={
                "base_bet": bet,
                "insurance_bet": insurance_bet,
                "dealer_cards": [card_text(card) for card in dealer],
                "dealer_value": dv,
                "delta": total_delta,
                "hands": [
                    {
                        "cards": [card_text(card) for card in hand["cards"]],
                        "value": hand_value(hand["cards"]),
                        "bet": hand["bet"],
                        "split": hand.get("split", False),
                        "doubled": hand.get("doubled", False),
                        "surrendered": hand.get("surrendered", False),
                    }
                    for hand in hands
                ],
            },
            before=round_before,
            after=state_snapshot(chips, profile),
            operation_delta=1,
        )

        if slot is not None and stats is not None and profile is not None:
            auto_save(slot, chips, stats, profile)
            print(colored("  [自动存档]", C.DIM))
        for notice in notices:
            print(notice)

        pause()
    return chips

# ============================================================
# Craps (骰子)
# ============================================================
DICE_ART = {
    1: ["┌───┐", "│   │", "│ ● │", "│   │", "└───┘"],
    2: ["┌───┐", "│ ● │", "│   │", "│ ● │", "└───┘"],
    3: ["┌───┐", "│ ● │", "│ ● │", "│ ● │", "└───┘"],
    4: ["┌───┐", "│● ●│", "│   │", "│● ●│", "└───┘"],
    5: ["┌───┐", "│● ●│", "│ ● │", "│● ●│", "└───┘"],
    6: ["┌───┐", "│● ●│", "│● ●│", "│● ●│", "└───┘"],
}

def render_dice(d1, d2):
    art1 = DICE_ART[d1]
    art2 = DICE_ART[d2]
    for i in range(5):
        print(f"    {art1[i]}  {art2[i]}")

def roll_animation():
    """简单的掷骰动画"""
    for _ in range(6):
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        sys.stdout.write("\r" + f"    🎲 掷骰中... [{d1}] [{d2}]  ")
        sys.stdout.flush()
        time.sleep(0.12)
    print()

def craps(chips, slot=None, stats=None, profile=None):
    while True:
        clear()
        header(chips, slot, stats, profile)
        print(colored("\n  ── Craps 骰子 ──\n", C.MAGENTA))
        print(colored("  规则简介:", C.DIM))
        print(colored("  Come Out Roll: 7或11直接赢，2/3/12直接输", C.DIM))
        print(colored("  其他数字成为 Point，继续掷到 Point 赢，掷到 7 输\n", C.DIM))

        if chips <= 0:
            print(colored("  破产了！先回去看看别的。", C.RED))
            pause()
            return chips

        print(f"  当前筹码: {colored(f'${chips}', C.GREEN)}")
        print(f"  输入下注金额 (1-{chips})，输入 0 返回大厅")
        try:
            bet = int(input(colored("  > ", C.YELLOW)))
        except (ValueError, EOFError):
            continue
        if bet == 0:
            return chips
        if bet < 1 or bet > chips:
            print(colored("  无效金额！", C.RED))
            pause()
            continue
        round_before = state_snapshot(chips, profile)
        roll_history = []

        # Come Out Roll
        print(colored("\n  ── Come Out Roll ──", C.CYAN))
        roll_animation()
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        roll_history.append({"phase": "come_out", "dice": [d1, d2], "total": total})
        render_dice(d1, d2)
        print(colored(f"    总点数: {total}", C.BOLD))

        if total in (7, 11):
            chips += bet
            if stats:
                stats["wins"] += 1
                stats["total_bet"] += bet
                stats["biggest_win"] = max(stats["biggest_win"], bet)
            print(colored(f"\n  ✓ 自然赢！+${bet}", C.GREEN))
            record_game_result(stats, "craps", "win", bet)
            notices = record_operations(chips, stats, profile, 1)
            append_history(
                stats,
                profile,
                "craps",
                "round_resolved",
                details={
                    "bet": bet,
                    "result": "natural_win",
                    "delta": bet,
                    "rolls": roll_history,
                },
                before=round_before,
                after=state_snapshot(chips, profile),
                operation_delta=1,
            )
            if slot is not None and stats is not None and profile is not None:
                auto_save(slot, chips, stats, profile)
                print(colored("  [自动存档]", C.DIM))
            for notice in notices:
                print(notice)
            pause()
            continue
        elif total in (2, 3, 12):
            chips -= bet
            if stats:
                stats["losses"] += 1
                stats["total_bet"] += bet
            print(colored(f"\n  ✗ Craps！输了 -${bet}", C.RED))
            record_game_result(stats, "craps", "loss", -bet)
            notices = record_operations(chips, stats, profile, 1)
            append_history(
                stats,
                profile,
                "craps",
                "round_resolved",
                details={
                    "bet": bet,
                    "result": "craps_lose",
                    "delta": -bet,
                    "rolls": roll_history,
                },
                before=round_before,
                after=state_snapshot(chips, profile),
                operation_delta=1,
            )
            if slot is not None and stats is not None and profile is not None:
                auto_save(slot, chips, stats, profile)
                print(colored("  [自动存档]", C.DIM))
            for notice in notices:
                print(notice)
            pause()
            continue

        point = total
        result_label = "point_made"
        round_delta = bet
        print(colored(f"\n  Point 设为 {point}，继续掷！", C.YELLOW))
        pause("按 Enter 继续掷骰...")

        # Point Phase
        while True:
            roll_animation()
            d1, d2 = random.randint(1, 6), random.randint(1, 6)
            total = d1 + d2
            roll_history.append({"phase": "point", "dice": [d1, d2], "total": total})
            render_dice(d1, d2)
            print(colored(f"    总点数: {total}  (Point: {point})", C.BOLD))

            if total == point:
                chips += bet
                if stats:
                    stats["wins"] += 1
                    stats["total_bet"] += bet
                    stats["biggest_win"] = max(stats["biggest_win"], bet)
                print(colored(f"\n  ✓ 命中 Point！+${bet}", C.GREEN))
                break
            elif total == 7:
                chips -= bet
                if stats:
                    stats["losses"] += 1
                    stats["total_bet"] += bet
                print(colored(f"\n  ✗ Seven Out！-${bet}", C.RED))
                result_label = "seven_out"
                round_delta = -bet
                break
            else:
                print(colored("    继续掷...", C.DIM))
                pause("按 Enter 继续掷骰...")

        notices = record_operations(chips, stats, profile, 1)
        record_game_result(stats, "craps", "win" if round_delta > 0 else "loss", round_delta, special_inc=1)
        append_history(
            stats,
            profile,
            "craps",
            "round_resolved",
            details={
                "bet": bet,
                "point": point,
                "result": result_label,
                "delta": round_delta,
                "rolls": roll_history,
            },
            before=round_before,
            after=state_snapshot(chips, profile),
            operation_delta=1,
        )
        if slot is not None and stats is not None and profile is not None:
            auto_save(slot, chips, stats, profile)
            print(colored("  [自动存档]", C.DIM))
        for notice in notices:
            print(notice)
        pause()
    return chips
# ============================================================
SLOT_WILD = '🃏'
SLOT_SCATTER = '⭐'
SLOT_REGULAR_SYMBOLS = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣', '🔔']
SLOT_SYMBOLS = SLOT_REGULAR_SYMBOLS + [SLOT_WILD, SLOT_SCATTER]
SLOT_WEIGHTS = [28, 24, 20, 14, 5, 3, 2, 4, 3]

SLOT_PAYOUTS = {
    '7️⃣': 20,
    '💎': 15,
    '🔔': 12,
    '🍇': 8,
    '🍊': 5,
    '🍋': 3,
    '🍒': 2,
    SLOT_WILD: 25,
}


def weighted_choice():
    return random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=1)[0]


def render_slot_machine(result):
    print("\r    ┏━━━┳━━━┳━━━┓")
    print(f"    ┃ {result[0]} ┃ {result[1]} ┃ {result[2]} ┃")
    print("    ┗━━━┻━━━┻━━━┛")


def slot_line_result(result):
    if all(symbol == SLOT_WILD for symbol in result):
        return SLOT_PAYOUTS[SLOT_WILD], "超级 Wild x3"

    for symbol in SLOT_REGULAR_SYMBOLS[::-1]:
        if all(item in (symbol, SLOT_WILD) for item in result):
            return SLOT_PAYOUTS[symbol], f"{symbol} 三连"

    if SLOT_SCATTER not in result:
        for symbol in SLOT_REGULAR_SYMBOLS[::-1]:
            matches = sum(1 for item in result if item in (symbol, SLOT_WILD))
            if matches >= 2:
                return 1, f"{symbol} 两连"

        if result.count(SLOT_WILD) >= 2:
            return 2, "Wild 两连"

    return 0, ""


def slots(chips, slot=None, stats=None, profile=None):
    slot_state = profile["slots"]
    while True:
        clear()
        header(chips, slot, stats, profile)
        print(colored("\n  ── Slots 老虎机 ──\n", C.MAGENTA))

        free_spins = slot_state.get("free_spins", 0)
        if chips <= 0 and free_spins <= 0:
            print(colored("  口袋空空，连免费旋转也没有了。先去银行或别的桌想办法。", C.RED))
            pause()
            return chips

        if free_spins > 0 and slot_state.get("free_spin_bet", 0) > 0:
            bet = slot_state["free_spin_bet"]
            free_mode = True
            multiplier = 2 + min(slot_state.get("streak", 0), 3)
            print(colored(f"  免费旋转剩余: {free_spins}", C.YELLOW))
            print(colored(f"  本次免费旋转基准下注: ${bet}  当前奖励倍率: x{multiplier}", C.CYAN))
            print(colored("  按 Enter 开始免费旋转，输入 0 返回大厅保留次数", C.DIM))
            command = input(colored("  > ", C.YELLOW)).strip()
            if command == '0':
                return chips
        else:
            free_mode = False
            multiplier = 1
            print(colored(f"  当前筹码: ${chips}", C.GREEN))
            print(colored(f"  免费旋转: {free_spins}", C.YELLOW))
            print(colored(f"  输入下注金额 (1-{chips})，输入 0 返回大厅", C.DIM))
            try:
                bet = int(input(colored("  > ", C.YELLOW)))
            except (ValueError, EOFError):
                continue
            if bet == 0:
                return chips
            if bet < 1 or bet > chips:
                print(colored("  无效金额！", C.RED))
                pause()
                continue
        spin_before = state_snapshot(chips, profile)

        if free_mode:
            slot_state["free_spins"] -= 1

        print()
        for i in range(8):
            s1 = weighted_choice()
            s2 = weighted_choice()
            s3 = weighted_choice()
            sys.stdout.write(f"\r    ┃ {s1} ┃ {s2} ┃ {s3} ┃  ")
            sys.stdout.flush()
            time.sleep(0.08 + i * 0.03)

        result = [weighted_choice(), weighted_choice(), weighted_choice()]
        print()
        render_slot_machine(result)

        line_mult, label = slot_line_result(result)
        scatter_count = result.count(SLOT_SCATTER)
        free_spins_awarded = 0
        scatter_bonus = 0

        if scatter_count == 2:
            free_spins_awarded = 2
        elif scatter_count == 3:
            free_spins_awarded = 5
            scatter_bonus = 2

        winnings = bet * (line_mult + scatter_bonus) * multiplier
        paid_spin = not free_mode

        if paid_spin:
            stats["total_bet"] += bet

        if winnings > 0:
            chips += winnings
            stats["wins"] += 1
            stats["biggest_win"] = max(stats["biggest_win"], winnings)
            print(colored(f"\n  ★ {label or '奖励命中'} ★", C.GREEN if line_mult < 15 else C.YELLOW))
            print(colored(f"  +${winnings}  (倍率 x{multiplier})", C.GREEN))
            record_game_result(stats, "slots", "win", winnings, special_inc=free_spins_awarded)
        elif paid_spin:
            chips -= bet
            stats["losses"] += 1
            print(colored(f"\n  ✗ 没中... -${bet}", C.RED))
            record_game_result(stats, "slots", "loss", -bet)
        else:
            print(colored("\n  这次免费旋转没有打中。", C.DIM))
            record_game_result(stats, "slots", "push", 0)

        if free_spins_awarded:
            slot_state["free_spins"] += free_spins_awarded
            slot_state["free_spin_bet"] = bet
            print(colored(f"  Scatter 触发！额外获得 {free_spins_awarded} 次免费旋转。", C.YELLOW))
            if scatter_bonus:
                print(colored(f"  三个 Scatter 追加现金奖励 {scatter_bonus}x！", C.YELLOW))

        if free_mode:
            if winnings > 0 or free_spins_awarded:
                slot_state["streak"] += 1
            else:
                slot_state["streak"] = 0
        else:
            slot_state["streak"] = 0
            if free_spins_awarded == 0:
                slot_state["free_spin_bet"] = slot_state.get("free_spin_bet", 0)

        if slot_state["free_spins"] <= 0:
            slot_state["free_spins"] = 0
            slot_state["free_spin_bet"] = 0
            slot_state["streak"] = 0

        notices = record_operations(chips, stats, profile, 1)
        append_history(
            stats,
            profile,
            "slots",
            "spin_resolved",
            details={
                "bet": bet,
                "free_mode": free_mode,
                "multiplier": multiplier,
                "symbols": result,
                "line_multiplier": line_mult,
                "label": label,
                "scatter_count": scatter_count,
                "free_spins_awarded": free_spins_awarded,
                "free_spins_remaining": slot_state["free_spins"],
                "delta": winnings if winnings > 0 else (-bet if paid_spin else 0),
            },
            before=spin_before,
            after=state_snapshot(chips, profile),
            operation_delta=1,
        )
        if slot is not None and stats is not None and profile is not None:
            auto_save(slot, chips, stats, profile)
            print(colored("  [自动存档]", C.DIM))
        for notice in notices:
            print(notice)

        pause()
    return chips

# ============================================================
# 火烧洋油站 (Single Card Showdown)
# ============================================================
RANK_ORDER = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
              '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}

class FireStationAI:
    """有深度的 AI 对手"""
    def __init__(self, personality="tight", mood=0.5, player_profile=None, opponent_name="庄家", boss=False, cycle=0):
        self.player_profile = normalize_player_profile(player_profile)
        self.personality = personality
        self.mood = mood
        self.opponent_name = opponent_name
        self.boss = boss
        self.cycle = cycle

    def card_strength(self, card):
        """牌力归一化 0~1"""
        return (RANK_ORDER[card.rank] - 2) / 12

    def player_aggression(self):
        """评估玩家激进度"""
        p = self.player_profile
        if p["total_hands"] < 3:
            return 0.5  # 数据不够，假设中等
        fold_rate = p["fold_count"] / max(p["total_hands"], 1)
        avg_raises = sum(p["raise_freq"][-10:]) / max(len(p["raise_freq"][-10:]), 1)
        # 弃牌多=保守, 加注多=激进
        aggression = (1 - fold_rate) * 0.4 + min(avg_raises / 4, 1) * 0.6
        return aggression

    def decide(self, my_card, current_bet, pot, my_chips, round_num, player_raised_this_hand):
        """
        AI 决策：返回 'raise', 'call', 'fold'
        round_num: 当前手内第几轮加注
        player_raised_this_hand: 这手牌玩家已加注次数
        """
        strength = self.card_strength(my_card)
        aggression = self.player_aggression()

        # 基础概率
        if strength >= 0.75:      # 强牌 (J, Q, K, A)
            base_raise = 0.80
            base_call = 0.18
            base_fold = 0.02
        elif strength >= 0.5:     # 中等牌 (8, 9, 10)
            base_raise = 0.35
            base_call = 0.45
            base_fold = 0.20
        elif strength >= 0.25:    # 弱牌 (5, 6, 7)
            base_raise = 0.15
            base_call = 0.30
            base_fold = 0.55
        else:                     # 垃圾牌 (2, 3, 4)
            base_raise = 0.08
            base_call = 0.15
            base_fold = 0.77

        # === 动态调整 ===

        # 1. 如果玩家这手很激进（加了很多注），AI 弱牌更倾向弃牌
        if player_raised_this_hand >= 2 and strength < 0.5:
            base_fold += 0.20
            base_raise -= 0.10
        # 但如果玩家平时很爱 bluff，反而要勇敢 call
        if aggression > 0.7 and strength >= 0.3:
            base_call += 0.15
            base_fold -= 0.15

        # 2. 偷鸡：弱牌偶尔大胆加注
        bluff_chance = 0
        if self.personality == "tricky":
            bluff_chance = 0.18
        elif self.personality == "loose":
            bluff_chance = 0.12
        else:
            bluff_chance = 0.06

        # 对保守玩家加大偷鸡力度
        if aggression < 0.35:
            bluff_chance *= 1.8

        if strength < 0.4 and random.random() < bluff_chance:
            base_raise += 0.40
            base_fold -= 0.30

        # 3. 性格影响
        if self.personality == "tight":
            base_fold += 0.08
            base_raise -= 0.05
        elif self.personality == "loose":
            base_raise += 0.10
            base_fold -= 0.08

        # 4. 情绪波动 (连输会更激进，连赢更保守)
        base_raise += (self.mood - 0.5) * 0.15
        base_fold -= (self.mood - 0.5) * 0.10

        # 5. 筹码深度：筹码少了更保守
        if my_chips < current_bet * 3:
            if strength < 0.6:
                base_fold += 0.25
                base_raise -= 0.20

        # 6. 沉没成本：已经投入很多就不轻易弃
        if pot > my_chips * 0.3 and round_num >= 2:
            base_fold *= 0.5
            base_call += 0.15

        # 7. 后期轮次压力递增
        if round_num >= 3:
            base_call += 0.15
            base_raise -= 0.10

        # 8. Boss 与周目强度
        if self.boss:
            base_raise += 0.08
            base_fold -= 0.06
        if self.cycle > 0:
            base_raise += min(0.04 * self.cycle, 0.16)
            base_fold -= min(0.03 * self.cycle, 0.12)

        # 正规化
        base_raise = max(base_raise, 0.01)
        base_call = max(base_call, 0.01)
        base_fold = max(base_fold, 0.01)
        total = base_raise + base_call + base_fold
        base_raise /= total
        base_call /= total
        base_fold /= total

        # 筹码不够加注就只能 call 或 fold
        if my_chips < current_bet * 2:
            base_call += base_raise
            base_raise = 0

        roll = random.random()
        if roll < base_raise:
            return "raise"
        elif roll < base_raise + base_call:
            return "call"
        else:
            return "fold"

    def choose_raise_amount(self, my_card, current_bet, my_chips):
        """决定加注金额"""
        strength = self.card_strength(my_card)
        min_raise = current_bet  # 最少加当前数额（翻倍）
        max_raise = my_chips

        if max_raise < min_raise:
            return max_raise  # all-in

        # 根据牌力选倍数
        if strength >= 0.8:
            # 强牌：有时大加，有时小加（隐藏牌力）
            if random.random() < 0.4:
                mult = random.uniform(1.0, 1.5)  # 最小加注，扮猪吃虎
            else:
                mult = random.uniform(1.5, 3.0)
        elif strength >= 0.5:
            mult = random.uniform(1.0, 2.0)
        else:
            # 弱牌偷鸡要下重注才有威慑
            if random.random() < 0.3:
                mult = random.uniform(2.0, 4.0 + self.cycle * 0.2)  # 大偷鸡
            else:
                mult = 1.0

        if self.boss:
            mult += 0.3

        amount = int(current_bet * mult)
        amount = max(amount, min_raise)
        amount = min(amount, max_raise)
        return amount

    def update_mood(self, won):
        """更新情绪"""
        if won:
            self.mood = max(0, self.mood - 0.1)  # 赢了反而冷静
        else:
            self.mood = min(1, self.mood + 0.15)  # 输了更激进

    def record_hand(self, player_folded, player_raises, player_card=None):
        """记录这手牌的玩家数据"""
        self.player_profile["total_hands"] += 1
        if player_folded:
            self.player_profile["fold_count"] += 1
        self.player_profile["raise_freq"].append(player_raises)
        self.player_profile["raise_freq"] = self.player_profile["raise_freq"][-20:]
        if player_card is not None:
            self.player_profile["showdown_cards"].append(self.card_strength(player_card))
            self.player_profile["showdown_cards"] = self.player_profile["showdown_cards"][-20:]


def render_single_card(card, label="", hidden=False):
    """渲染单张牌"""
    if label:
        print(colored(f"  {label}", C.DIM))
    if hidden:
        tmp = Card('A', '♠')
        tmp.hidden = True
        arts = tmp.art()
    else:
        arts = card.art()
    for row in arts:
        print(f"    {row}")


def personality_name(personality):
    return {
        "tight": "沉稳",
        "loose": "豪放",
        "tricky": "诡诈",
        "model": "模型",
    }.get(personality, personality)


_FIRE_STATION_MODEL_CACHE = {}


def discover_fire_station_models():
    try:
        from fire_station_ai.runtime import discover_saved_policies
    except Exception:
        return []
    return discover_saved_policies(FIRE_STATION_AI_RUNS_DIR)


def load_fire_station_model(path):
    normalized_path = os.path.normpath(path)
    cached = _FIRE_STATION_MODEL_CACHE.get(normalized_path)
    if cached is not None:
        return cached
    try:
        from fire_station_ai.runtime import load_saved_policy
        loaded = load_saved_policy(normalized_path)
    except Exception:
        loaded = None
    _FIRE_STATION_MODEL_CACHE[normalized_path] = loaded
    return loaded


def current_fire_ai_display(fire_state):
    fire_state = normalize_fire_station_state(fire_state)
    if fire_state.get("ai_mode") == "model" and fire_state.get("ai_model_name"):
        return f"训练模型 · {fire_state['ai_model_name']}"
    return "规则庄家"


def choose_fire_station_ai_mode(chips, slot=None, stats=None, profile=None):
    fire_state = profile["fire_station"]
    models = discover_fire_station_models()

    while True:
        clear()
        header(chips, slot, stats, profile)
        print(colored("\n  ── 火烧洋油站：决策核心 ──\n", C.RED))
        print(colored(f"  当前核心: {current_fire_ai_display(fire_state)}", C.CYAN))
        print()
        print(f"    {colored('1', C.GREEN)}  规则庄家")

        if models:
            for idx, model in enumerate(models, start=2):
                current_tag = colored(" [当前]", C.YELLOW) if fire_state.get("ai_mode") == "model" and os.path.normpath(fire_state.get("ai_model_path", "")) == os.path.normpath(model["path"]) else ""
                training_score = f"{model['best_training_score']:.3f}"
                validation_win = f"{model['validation_win_rate'] * 100:.1f}%"
                run_name = os.path.basename(model["run_dir"])
                print(f"    {colored(str(idx), C.GREEN)}  {model['codename']}  训练 {training_score}  验证 {validation_win}  {colored(run_name, C.DIM)}{current_tag}")
        else:
            print(colored("  还没有可用的训练模型。先运行 `python -m fire_station_ai.train` 或 `python -m fire_station_ai.cfr_train`。", C.DIM))

        print(f"\n    {colored('0', C.RED)}  返回")

        try:
            choice = input(colored("  > ", C.YELLOW)).strip()
        except (EOFError, KeyboardInterrupt):
            return

        if choice == "0":
            return
        if choice == "1":
            fire_state["ai_mode"] = "classic"
            fire_state["ai_model_path"] = ""
            fire_state["ai_model_name"] = ""
            profile["fire_station"] = fire_state
            if slot is not None and stats is not None and profile is not None:
                auto_save(slot, chips, stats, profile)
            return
        try:
            index = int(choice) - 2
        except ValueError:
            continue
        if 0 <= index < len(models):
            selected = models[index]
            fire_state["ai_mode"] = "model"
            fire_state["ai_model_path"] = selected["path"]
            fire_state["ai_model_name"] = selected["codename"]
            profile["fire_station"] = fire_state
            if slot is not None and stats is not None and profile is not None:
                auto_save(slot, chips, stats, profile)
            return


class FireStationModelAI(FireStationAI):
    """Bridge a saved training policy into the terminal game."""

    def __init__(self, loaded_model, personality="tight", mood=0.5, player_profile=None, opponent_name="庄家", boss=False, cycle=0):
        super().__init__(
            personality=personality,
            mood=mood,
            player_profile=player_profile,
            opponent_name=opponent_name,
            boss=boss,
            cycle=cycle,
        )
        self.loaded_model = loaded_model
        self.model_name = loaded_model.get("codename", "未命名模型")
        self._pending_raise_amount = None

    def decide_model_action(self, my_card, current_bet, pot, my_chips, round_num, player_raised_this_hand, opponent_chips, my_raises=0):
        from fire_station_ai.runtime import choose_model_action

        action = choose_model_action(
            self.loaded_model,
            card_rank=RANK_ORDER[my_card.rank],
            my_chips=my_chips,
            opponent_chips=opponent_chips,
            pot=pot,
            current_bet=current_bet,
            round_num=round_num,
            my_raises=my_raises,
            opponent_raises=player_raised_this_hand,
            opponent_profile_dict=self.player_profile,
            rng_module=random,
        )
        self._pending_raise_amount = action.amount
        return action

    def choose_raise_amount(self, my_card, current_bet, my_chips):
        if self._pending_raise_amount is not None:
            amount = int(self._pending_raise_amount)
            self._pending_raise_amount = None
            return max(current_bet, min(my_chips, amount))
        return super().choose_raise_amount(my_card, current_bet, my_chips)


def sync_fire_station_state(profile, ai, ai_chips):
    profile["fire_station"]["ai_chips"] = ai_chips
    profile["fire_station"]["mood"] = ai.mood
    profile["fire_station"]["personality"] = ai.personality
    profile["fire_station"]["player_profile"] = ai.player_profile


def advance_fire_station(profile, stats):
    fire_state = profile["fire_station"]
    current = current_fire_opponent(fire_state)
    stage = fire_state.get("stage", 0) + 1
    cycle = fire_state.get("cycle", 0)

    if current.get("boss") or stage >= len(FIRE_STATION_OPPONENTS):
        if current.get("boss"):
            stats["bosses_defeated"] += 1
        stage = 0
        cycle += 1

    fire_state["stage"] = stage
    fire_state["cycle"] = cycle
    next_opponent = current_fire_opponent(fire_state)
    fire_state["ai_chips"] = next_opponent["chips"]
    fire_state["mood"] = next_opponent["mood"]
    fire_state["personality"] = next_opponent["personality"]
    fire_state["player_profile"] = default_player_profile()
    return current, next_opponent


def fire_station(chips, slot=None, stats=None, profile=None):
    """火烧洋油站主逻辑"""
    fire_state = profile["fire_station"]

    while True:
        fire_state = normalize_fire_station_state(fire_state)
        profile["fire_station"] = fire_state
        opponent = current_fire_opponent(fire_state)
        loaded_model = None
        if fire_state.get("ai_mode") == "model" and fire_state.get("ai_model_path"):
            loaded_model = load_fire_station_model(fire_state["ai_model_path"])
            if loaded_model is None:
                fire_state["ai_mode"] = "classic"
                fire_state["ai_model_path"] = ""
                fire_state["ai_model_name"] = ""
                profile["fire_station"] = fire_state

        if loaded_model is not None:
            ai = FireStationModelAI(
                loaded_model=loaded_model,
                personality=opponent["personality"],
                mood=fire_state.get("mood", opponent["mood"]),
                player_profile=fire_state.get("player_profile"),
                opponent_name=opponent["name"],
                boss=opponent.get("boss", False),
                cycle=fire_state.get("cycle", 0),
            )
        else:
            ai = FireStationAI(
                personality=opponent["personality"],
                mood=fire_state.get("mood", opponent["mood"]),
                player_profile=fire_state.get("player_profile"),
                opponent_name=opponent["name"],
                boss=opponent.get("boss", False),
                cycle=fire_state.get("cycle", 0),
            )
        ai_chips = fire_state.get("ai_chips", opponent["chips"])
        min_fire_bet = min(FIRE_STATION_BET_TIERS)

        if ai_chips < min_fire_bet:
            sync_fire_station_state(profile, ai, ai_chips)
            defeated, next_opponent = advance_fire_station(profile, stats)
            clear()
            header(chips, slot, stats, profile)
            print(colored("\n  ── 火烧洋油站 ──\n", C.RED))
            print(colored(f"  {defeated['name']} 的剩余筹码不足最低底注 ${min_fire_bet}，视为破产。", C.GREEN))
            if defeated.get("boss"):
                print(colored(f"  ★ 你击败了 Boss {defeated['name']}！周目提升！", C.YELLOW))
            else:
                print(colored(f"  ✓ 你击败了 {defeated['name']}！下一位对手是 {next_opponent['name']}。", C.GREEN))
            pause()
            fire_state = profile["fire_station"]
            continue

        clear()
        header(chips, slot, stats, profile)
        print(colored("\n  ── 火烧洋油站 ──\n", C.RED))

        if chips <= 0:
            print(colored("  你已经破产了！回去攒点钱再来。", C.RED))
            pause()
            return chips

        stage_text = f"第 {fire_state.get('cycle', 0) + 1} 周目"
        boss_text = colored("Boss", C.YELLOW) if opponent.get("boss") else colored("常规桌", C.DIM)
        print(f"  对手: {colored(opponent['name'], C.MAGENTA)}  {colored(opponent['title'], C.WHITE)}  {boss_text}")
        print(f"  难度: {colored(stage_text, C.CYAN)}")
        print(colored(f"  “{opponent['quote']}”", C.DIM))
        print()

        print(f"  你的筹码: {colored('$' + str(chips), C.GREEN)}")
        print(f"  庄家筹码: {colored('$' + str(ai_chips), C.MAGENTA)}")
        print(colored(f"  桌面对手风格: {personality_name(opponent['personality'])}", C.DIM))
        if loaded_model is not None:
            print(colored(f"  决策核心: 训练模型 · {loaded_model['codename']}", C.CYAN))
        else:
            print(colored(f"  决策核心: 规则庄家 · {personality_name(ai.personality)}", C.DIM))
        print()

        tiers = FIRE_STATION_BET_TIERS
        available = [t for t in tiers if t <= chips and t <= ai_chips]
        if not available:
            print(colored("  筹码不够最低底注了！", C.RED))
            pause()
            return chips

        print("  选择底注:")
        for idx, t in enumerate(available):
            print(f"    {colored(str(idx + 1), C.GREEN)}  ${t}")
        print(f"    {colored('M', C.CYAN)}  切换决策核心")
        print(f"    {colored('0', C.RED)}  返回大厅")

        try:
            tc = input(colored("  > ", C.YELLOW)).strip()
        except (EOFError, KeyboardInterrupt):
            return chips
        if tc.upper() == 'M':
            choose_fire_station_ai_mode(chips, slot, stats, profile)
            fire_state = profile["fire_station"]
            continue
        if tc == '0':
            return chips
        try:
            ti = int(tc) - 1
            if ti < 0 or ti >= len(available):
                continue
            base_bet = available[ti]
        except ValueError:
            continue
        hand_before = state_snapshot(chips, profile)
        hand_action_log = []

        # === 开始一手 ===
        deck = Deck(num_decks=1)
        player_card = deck.deal()
        ai_card = deck.deal()

        pot = base_bet * 2  # 双方各投底注
        chips -= base_bet
        ai_chips -= base_bet
        current_bet = base_bet  # 当前要跟的注
        round_num = 0
        player_raises = 0
        ai_raises = 0
        hand_operations = 0
        last_raiser = None  # 记录最后加注方
        game_over = False

        clear()
        header(chips, slot, stats, profile)
        print(colored(f"\n  ── 火烧洋油站 ── 底注: ${base_bet} ──\n", C.RED))
        print(colored(f"  对手: {opponent['name']} / {opponent['title']}", C.MAGENTA))
        print(f"  底池: {colored('$' + str(pot), C.YELLOW)}")
        print()
        render_single_card(player_card, "你的牌:")
        print()
        render_single_card(ai_card, "庄家的牌:", hidden=True)
        print()

        turn = "player"
        while not game_over:
            round_num += 1

            if turn == "player":
                print(f"\n  底池: {colored('$' + str(pot), C.YELLOW)}  "
                      f"当前注: {colored('$' + str(current_bet), C.CYAN)}")
                print()
                options = []
                can_raise = chips >= current_bet
                if can_raise:
                    options.append(f"[R] 加注 (最少 +${current_bet}，即总注 ${current_bet * 2})")
                if last_raiser == "ai" or last_raiser is None:
                    if last_raiser is None:
                        options.append("[C] 开牌")
                    elif chips >= current_bet:
                        options.append("[C] 跟注开牌")
                    else:
                        options.append(f"[C] 欠款开牌 (将欠 ${current_bet - chips})")
                options.append("[F] 弃牌")

                for o in options:
                    print(f"    {o}")
                action = input(colored("  > ", C.YELLOW)).strip().upper()

                if action == 'R' and can_raise:
                    # 输入加注金额
                    max_raise = chips
                    print(f"  加注金额 (最少 ${current_bet}，最多 ${max_raise}):")
                    try:
                        raise_amt = int(input(colored("  > ", C.YELLOW)))
                    except (ValueError, EOFError):
                        continue
                    if raise_amt < current_bet:
                        print(colored(f"  最少加 ${current_bet}！", C.RED))
                        pause()
                        round_num -= 1
                        continue
                    if raise_amt > max_raise:
                        raise_amt = max_raise
                        print(colored(f"  All-in! ${raise_amt}", C.YELLOW))

                    chips -= raise_amt
                    pot += raise_amt
                    current_bet = raise_amt
                    player_raises += 1
                    hand_operations += 1
                    hand_action_log.append({"turn": round_num, "action": "raise", "amount": raise_amt, "pot_after": pot})
                    last_raiser = "player"
                    turn = "ai"

                    clear()
                    header(chips, slot, stats, profile)
                    print(colored(f"\n  ── 火烧洋油站 ── 底注: ${base_bet} ──\n", C.RED))
                    print(colored(f"  对手: {opponent['name']} / {opponent['title']}", C.MAGENTA))
                    print(f"  底池: {colored('$' + str(pot), C.YELLOW)}")
                    print()
                    render_single_card(player_card, "你的牌:")
                    print()
                    render_single_card(ai_card, "庄家的牌:", hidden=True)

                    print(colored(f"\n  你加注 ${raise_amt}！等待 {opponent['name']} 决定...", C.CYAN))
                    pause()

                elif action == 'C' and (last_raiser == "ai" or last_raiser is None):
                    if last_raiser == "ai":
                        chips -= current_bet
                        pot += current_bet
                    hand_operations += 1
                    hand_action_log.append({"turn": round_num, "action": "call" if last_raiser == "ai" else "showdown", "amount": current_bet if last_raiser == "ai" else 0, "pot_after": pot})
                    game_over = True
                    winner = "showdown"

                elif action == 'F':
                    hand_operations += 1
                    hand_action_log.append({"turn": round_num, "action": "fold", "amount": 0, "pot_after": pot})
                    game_over = True
                    winner = "ai_fold"  # 玩家弃牌

                else:
                    round_num -= 1
                    continue

            else:
                if isinstance(ai, FireStationModelAI):
                    model_action = ai.decide_model_action(
                        ai_card,
                        current_bet,
                        pot,
                        ai_chips,
                        round_num,
                        player_raises,
                        opponent_chips=chips,
                        my_raises=ai_raises,
                    )
                    if model_action.kind.value == "fold":
                        decision = "fold"
                    elif model_action.kind.value == "call":
                        decision = "call"
                    else:
                        decision = "raise"
                else:
                    decision = ai.decide(ai_card, current_bet, pot, ai_chips,
                                         round_num, player_raises)

                if decision == "raise" and ai_chips >= current_bet:
                    raise_amt = ai.choose_raise_amount(ai_card, current_bet, ai_chips)
                    ai_chips -= raise_amt
                    pot += raise_amt
                    current_bet = raise_amt
                    ai_raises += 1
                    last_raiser = "ai"
                    turn = "player"

                    clear()
                    header(chips, slot, stats, profile)
                    print(colored(f"\n  ── 火烧洋油站 ── 底注: ${base_bet} ──\n", C.RED))
                    print(colored(f"  对手: {opponent['name']} / {opponent['title']}", C.MAGENTA))
                    print(f"  底池: {colored('$' + str(pot), C.YELLOW)}")
                    print()
                    render_single_card(player_card, "你的牌:")
                    print()
                    render_single_card(ai_card, "庄家的牌:", hidden=True)

                    print(colored(f"\n  {opponent['name']} 加注 ${raise_amt}！", C.MAGENTA))

                elif decision == "call" and (last_raiser == "player" or last_raiser is None):
                    if last_raiser == "player":
                        ai_chips -= current_bet
                        pot += current_bet
                    game_over = True
                    winner = "showdown"

                    print(colored(f"\n  {opponent['name']} 跟注！开牌！", C.MAGENTA))
                    time.sleep(0.8)

                elif decision == "fold":
                    game_over = True
                    winner = "player_fold"

                    print(colored(f"\n  {opponent['name']} 弃牌！", C.MAGENTA))
                    time.sleep(0.8)

                else:
                    if (last_raiser == "player" or last_raiser is None) and ai_chips >= current_bet:
                        if last_raiser == "player":
                            ai_chips -= current_bet
                            pot += current_bet
                        game_over = True
                        winner = "showdown"
                        print(colored(f"\n  {opponent['name']} 跟注！开牌！", C.MAGENTA))
                        time.sleep(0.8)
                    else:
                        game_over = True
                        winner = "player_fold"
                        print(colored(f"\n  {opponent['name']} 弃牌！", C.MAGENTA))
                        time.sleep(0.8)

        clear()
        header(chips, slot, stats, profile)
        print(colored(f"\n  ── 结算 ── 底池: ${pot} ──\n", C.RED))
        print(colored(f"  对手: {opponent['name']} / {opponent['title']}", C.MAGENTA))

        if winner == "showdown":
            render_single_card(player_card, "你的牌:")
            print()
            render_single_card(ai_card, "庄家的牌:")
            print()

            pv = RANK_ORDER[player_card.rank]
            av = RANK_ORDER[ai_card.rank]

            if pv > av:
                chips += pot
                print(colored(f"  ✓ 你赢了！{player_card.rank}{player_card.suit} > "
                              f"{ai_card.rank}{ai_card.suit}  +${pot}", C.GREEN))
                ai.update_mood(False)
                if stats:
                    stats["wins"] += 1
                    stats["total_bet"] += pot // 2
                    stats["biggest_win"] = max(stats["biggest_win"], pot)
            elif pv < av:
                ai_chips += pot
                print(colored(f"  ✗ 你输了！{player_card.rank}{player_card.suit} < "
                              f"{ai_card.rank}{ai_card.suit}  -${pot // 2}", C.RED))
                ai.update_mood(True)
                if stats:
                    stats["losses"] += 1
                    stats["total_bet"] += pot // 2
            else:
                # 平局，各退一半
                half = pot // 2
                chips += half
                ai_chips += pot - half
                print(colored(f"  ─ 平局！{player_card.rank} = {ai_card.rank}，退回筹码", C.BLUE))
                if stats:
                    stats["pushes"] += 1

            ai.record_hand(False, player_raises, player_card)

        elif winner == "ai_fold":
            print(colored("  你弃牌了。", C.RED))
            render_single_card(player_card, "你的牌:")
            print()
            render_single_card(ai_card, "庄家的牌:", hidden=True)
            ai_chips += pot
            print(colored(f"\n  {opponent['name']} 赢得底池 ${pot}", C.MAGENTA))
            ai.update_mood(True)
            ai.record_hand(True, player_raises)
            if stats:
                stats["losses"] += 1
                stats["total_bet"] += base_bet

        elif winner == "player_fold":
            chips += pot
            print(colored(f"  {opponent['name']} 弃牌！你不战而胜！", C.GREEN))
            render_single_card(player_card, "你的牌:")
            print()
            print(colored(f"  {opponent['name']} 的牌: [已弃]", C.DIM))
            print(colored(f"\n  你赢得底池 ${pot}", C.GREEN))
            ai.update_mood(False)
            ai.record_hand(False, player_raises)
            if stats:
                stats["wins"] += 1
                stats["total_bet"] += base_bet

        sync_fire_station_state(profile, ai, ai_chips)

        if ai_chips < min_fire_bet:
            defeated, next_opponent = advance_fire_station(profile, stats)
            print()
            if defeated.get("boss"):
                print(colored(f"  ★ 你击败了 Boss {defeated['name']}！周目提升！", C.YELLOW))
            else:
                print(colored(f"  ✓ 你击败了 {defeated['name']}！下一位对手是 {next_opponent['name']}。", C.GREEN))

        notices = record_operations(chips, stats, profile, max(1, hand_operations))
        fire_delta = chips - hand_before["cash"]
        if winner == "showdown":
            if pv > av:
                record_game_result(stats, "fire_station", "win", fire_delta, special_inc=1 if ai_chips < min_fire_bet and opponent.get("boss") else 0)
            elif pv < av:
                record_game_result(stats, "fire_station", "loss", fire_delta)
            else:
                record_game_result(stats, "fire_station", "push", 0)
        elif winner == "ai_fold":
            record_game_result(stats, "fire_station", "loss", fire_delta)
        else:
            record_game_result(stats, "fire_station", "win", fire_delta, special_inc=1 if ai_chips < min_fire_bet and opponent.get("boss") else 0)
        append_history(
            stats,
            profile,
            "fire_station",
            "hand_resolved",
            details={
                "opponent": {
                    "name": opponent["name"],
                    "title": opponent["title"],
                    "personality": opponent["personality"],
                    "boss": opponent.get("boss", False),
                    "cycle": opponent.get("cycle", 0),
                },
                "ai_engine": {
                    "mode": fire_state.get("ai_mode", "classic"),
                    "model_name": fire_state.get("ai_model_name", ""),
                    "model_path": fire_state.get("ai_model_path", ""),
                },
                "base_bet": base_bet,
                "player_card": card_text(player_card),
                "ai_card": card_text(ai_card),
                "winner": winner,
                "pot": pot,
                "player_actions": hand_action_log,
                "player_raises": player_raises,
                "ai_raises": ai_raises,
                "operation_count_for_hand": max(1, hand_operations),
            },
            before=hand_before,
            after=state_snapshot(chips, profile),
            operation_delta=max(1, hand_operations),
        )
        if slot is not None and stats is not None and profile is not None:
            auto_save(slot, chips, stats, profile)
            print(colored("  [自动存档]", C.DIM))
        for notice in notices:
            print(notice)

        pause()
    return chips


# ============================================================
# 地下跑单
# ============================================================
def underground_runner(chips, slot=None, stats=None, profile=None):
    while True:
        clear()
        header(chips, slot, stats, profile)
        current_day = profile.get("bank_days_elapsed", 0)
        available = runner_available(profile)
        print(colored("\n  ── 地下跑单 ──\n", C.YELLOW))

        if not available:
            next_day = current_day + 1
            print(colored(f"  今天的单已经接过了。等到第 {next_day + 1} 天再来吧。", C.RED))
            pause()
            return chips

        job = build_runner_job()
        print(box(runner_job_lines(job), width=48, title="任务简报", color=C.YELLOW))
        print(colored("\n  说明:", C.DIM))
        print(colored("  成功概率很高，但仍有小概率翻车。", C.DIM))
        print(colored("  投入 0-100 美元；投入越高，成功和大成功收益越大。", C.DIM))
        print(colored("  翻车时，投入部分会血本无归。每 20 次操作只能接 1 单。", C.DIM))

        if chips <= 0:
            print(colored("\n  手上没现金，先去银行或者别的桌想办法。", C.RED))
            pause()
            return chips

        max_invest = min(100, chips)
        print(colored(f"\n  输入投入金额 (0-{max_invest})，输入 0 代表空手跑腿。", C.CYAN))
        print(colored("  输入 -1 返回大厅。", C.DIM))
        try:
            invest = int(input(colored("  > ", C.YELLOW)))
        except (ValueError, EOFError):
            continue
        if invest == -1:
            return chips
        if invest < 0 or invest > max_invest:
            print(colored("  金额无效。", C.RED))
            pause()
            continue

        before = state_snapshot(chips, profile)
        profile["runner"]["last_day"] = current_day
        if invest > 0:
            chips -= invest

        roll = random.random()
        if roll < 0.72:
            result = "win"
            reward = random.randint(10, 20) if invest == 0 else random.randint(15, 30) + int(invest * random.uniform(0.8, 1.6))
            chips += invest + reward
            delta = reward
            result_text = colored(f"  ✓ 跑单成功，赚到 ${reward}。", C.GREEN)
        elif roll < 0.90:
            result = "big_win"
            reward = random.randint(35, 50) if invest == 0 else random.randint(45, 70) + int(invest * random.uniform(1.8, 2.8))
            chips += invest + reward
            delta = reward
            result_text = colored(f"  ★ 大成功！这单直接带回 ${reward}。", C.YELLOW)
        else:
            result = "loss"
            reward = 0
            delta = -invest
            if invest > 0:
                result_text = colored(f"  ✗ 翻车了，投入的 ${invest} 全没了。", C.RED)
            else:
                result_text = colored("  ✗ 人到了，货没接上，白跑一趟。", C.RED)

        notices = record_operations(chips, stats, profile, 1)

        if result == "loss":
            stats["losses"] += 1
            record_game_result(stats, "runner", "loss", delta)
        else:
            stats["wins"] += 1
            stats["biggest_win"] = max(stats["biggest_win"], reward)
            record_game_result(stats, "runner", "win", delta, special_inc=1 if result == "big_win" else 0)

        append_history(
            stats,
            profile,
            "runner",
            "job_resolved",
            details={
                "job": job,
                "invest": invest,
                "result": result,
                "reward": reward,
                "delta": delta,
            },
            before=before,
            after=state_snapshot(chips, profile),
            operation_delta=1,
        )

        auto_save(slot, chips, stats, profile)
        clear()
        header(chips, slot, stats, profile)
        print(colored("\n  ── 地下跑单结算 ──\n", C.YELLOW))
        print(box(runner_job_lines(job), width=48, title="任务回放", color=C.YELLOW))
        print()
        print(result_text)
        for notice in notices:
            print(notice)
        print(colored(f"  今天的跑单资格已用掉。", C.DIM))
        pause()
        return chips


# ============================================================
# 跳天作弊
# ============================================================
def skip_to_next_day(chips, slot, stats, profile):
    before = state_snapshot(chips, profile)
    day_before = profile.get("bank_days_elapsed", 0)
    steps = DAILY_OPERATION_COUNT - operation_progress(profile)
    if steps <= 0:
        steps = DAILY_OPERATION_COUNT
    notices = record_operations(chips, stats, profile, steps)
    append_history(
        stats,
        profile,
        "system",
        "skip_to_next_day",
        details={
            "steps_added": steps,
            "day_before": day_before,
            "day_after": profile.get("bank_days_elapsed", 0),
        },
        before=before,
        after=state_snapshot(chips, profile),
        operation_delta=steps,
    )
    auto_save(slot, chips, stats, profile)
    clear()
    header(chips, slot, stats, profile)
    print(colored("\n  已快速跳到下一天。", C.YELLOW))
    print(colored(f"  第 {day_before + 1} 天 -> 第 {profile.get('bank_days_elapsed', 0) + 1} 天", C.DIM))
    for notice in notices:
        print(notice)
    pause()
    return chips


# ============================================================
# 主菜单
# ============================================================
def save_and_exit(chips, slot, stats, profile):
    append_history(
        stats,
        profile,
        "system",
        "session_saved_and_exit",
        details={"slot": slot, "location": profile.get("location", "home")},
        before=state_snapshot(chips, profile),
        after=state_snapshot(chips, profile),
        operation_delta=0,
    )
    auto_save(slot, chips, stats, profile)
    clear()
    print(colored("\n  游戏已保存！感谢光临 Leo's Casino！", C.YELLOW))
    print(
        colored(
            f"  你带走了 ${chips} 现金，银行 ${profile.get('bank', 0)}，持仓 ${market_value(profile)}，负债 ${total_debt(profile)}。\n",
            C.GREEN if total_assets(chips, profile) >= INITIAL_CHIPS else C.RED,
        )
    )


def home_menu(chips, slot, stats, profile):
    while True:
        clear()
        header(chips, slot, stats, profile)
        cash_shortfall = debt_shortfall(chips)
        left = box([
            f"现金:       {colored('$' + str(chips), C.GREEN if chips > 0 else C.RED)}",
            f"银行存款:   {colored('$' + str(profile.get('bank', 0)), C.CYAN)}",
            f"持仓市值:   {colored('$' + str(market_value(profile)), C.WHITE)}",
            f"贷款负债:   {colored('$' + str(total_debt(profile)), C.RED if total_debt(profile) > 0 else C.DIM)}",
            f"净资产:     {colored('$' + str(total_assets(chips, profile)), C.GREEN if total_assets(chips, profile) > 0 else C.RED)}",
            f"现金缺口:   {colored('$' + str(cash_shortfall), C.RED if cash_shortfall > 0 else C.DIM)}",
            f"今日地点:   {colored(location_label('home'), C.MAGENTA)}",
        ], width=34, title="家里", color=C.CYAN)
        right = box([
            colored("1", C.GREEN) + "  去赌场",
            colored("2", C.GREEN) + "  去银行",
            colored("3", C.GREEN) + "  去典当行",
            "",
            "你从家里出发，决定今天先去哪里。",
            "赌场适合搏一把，银行适合整理现金流，",
            "典当行适合做长期仓位和卖仓救急。",
        ], width=46, title="出门计划", color=C.GREEN)
        print()
        print(render_box_columns([left, right], gap=3))
        print()
        print(box(location_hint_lines("home"), width=68, title="全局快捷", color=C.BLUE))
        if cash_shortfall > 0:
            print(colored(f"  现金当前为负 ${cash_shortfall}。你不能上赌桌，但还能去银行或典当行处理仓位。", C.RED))
        elif can_claim_government_aid(chips, profile):
            print(colored(f"  你符合补贴条件，可领取 ${GOVERNMENT_AID_AMOUNT}。", C.GREEN))
        choice = input(colored("\n  选择 > ", C.YELLOW)).strip().upper()
        chips, global_result = global_command_result(choice, chips, slot, stats, profile)
        if global_result == "__exit__":
            return chips, "__exit__"
        if global_result in LOCATIONS and global_result != "home":
            return chips, global_result
        if global_result != "__local__":
            continue
        if choice == '1':
            travel_to(chips, slot, stats, profile, "casino")
            return chips, "casino"
        if choice == '2':
            travel_to(chips, slot, stats, profile, "bank")
            return chips, "bank"
        if choice == '3':
            travel_to(chips, slot, stats, profile, "pawnshop")
            return chips, "pawnshop"
        print(colored("  无效输入。", C.RED))
        pause()


def casino_menu(chips, slot, stats, profile):
    while True:
        clear()
        header(chips, slot, stats, profile)
        menu = [
            colored("1", C.GREEN) + "  Blackjack (21点)",
            colored("2", C.GREEN) + "  Craps (骰子)",
            colored("3", C.GREEN) + "  Slots (老虎机)",
            colored("4", C.GREEN) + "  火烧洋油站",
            colored("5", C.GREEN) + "  地下跑单",
        ]
        print(colored("\n  ── 赌场 ──\n", C.CYAN))
        print(render_box_columns([
            box(menu, width=34, title="赌桌列表", color=C.CYAN),
            box([
                "这里还是那个最危险也最刺激的地方。",
                "短线现金流靠赌桌，长期资金线可以去典当行。",
                "地下跑单每天只能做一次，火烧洋油站仍然是长线 Boss 桌。",
            ], width=42, title="街区情报", color=C.YELLOW),
        ], gap=2))
        print()
        print(box(location_hint_lines("casino"), width=68, title="全局快捷", color=C.BLUE))

        cash_shortfall = debt_shortfall(chips)
        if chips <= 0 and profile.get("bank", 0) > 0:
            print(colored("\n  手上没现金了，可以去银行取钱，或去典当行卖一点仓位。", C.YELLOW))
        if cash_shortfall > 0:
            print(colored(f"  当前现金欠款 ${cash_shortfall}，赌场桌面已锁定。先去银行补缺，或去典当行卖仓。", C.RED))
        if total_debt(profile) > 0:
            print(colored(f"  当前贷款负债 ${total_debt(profile)}，距离下一次结息还差 {DAILY_OPERATION_COUNT - operation_progress(profile)} 步。", C.RED))
        if runner_available(profile):
            print(colored("  今日地下跑单资格可用。", C.CYAN))
        else:
            print(colored("  今日地下跑单资格已用掉。", C.DIM))

        choice = input(colored("\n  选择 > ", C.YELLOW)).strip().upper()
        chips, global_result = global_command_result(choice, chips, slot, stats, profile)
        if global_result == "__exit__":
            return chips, "__exit__"
        if global_result in LOCATIONS and global_result != "casino":
            return chips, global_result
        if global_result != "__local__":
            continue
        if cash_shortfall > 0 and choice in {'1', '2', '3', '4', '5'}:
            clear()
            header(chips, slot, stats, profile)
            print(colored("\n  现金为负时不能参加任何赌桌。", C.RED))
            print(colored("  去银行用一键补缺，或者去典当行卖一点持仓。", C.YELLOW))
            pause()
            continue
        if choice == '1':
            chips = blackjack(chips, slot, stats, profile)
        elif choice == '2':
            chips = craps(chips, slot, stats, profile)
        elif choice == '3':
            chips = slots(chips, slot, stats, profile)
        elif choice == '4':
            chips = fire_station(chips, slot, stats, profile)
        elif choice == '5':
            chips = underground_runner(chips, slot, stats, profile)
        else:
            print(colored("  无效输入。", C.RED))
            pause()


def main():
    result = save_menu()
    if result is None:
        print(colored("\n  再见！\n", C.YELLOW))
        return
    chips, stats, profile, active_slot = result
    append_history(
        stats,
        profile,
        "system",
        "session_opened",
        details={"slot": active_slot, "location": profile.get("location", "home")},
        before=state_snapshot(chips, profile),
        after=state_snapshot(chips, profile),
        operation_delta=0,
    )

    while True:
        refresh_career_status(chips, stats, profile)
        if profile.get("retired"):
            auto_save(active_slot, chips, stats, profile)
            career_summary_menu(chips, stats, profile, active_slot)
            break

        current_location = profile.get("location", "home")
        if current_location == "casino":
            chips, next_action = casino_menu(chips, active_slot, stats, profile)
        elif current_location == "bank":
            chips, next_action = bank_menu(chips, active_slot, stats, profile)
        elif current_location == "pawnshop":
            chips, next_action = pawnshop_menu(chips, active_slot, stats, profile)
        else:
            chips, next_action = home_menu(chips, active_slot, stats, profile)

        if next_action == "__exit__":
            save_and_exit(chips, active_slot, stats, profile)
            break
        if next_action in LOCATIONS:
            profile["location"] = next_action
            continue


def game_panel_lines(stats, key, title, special_label):
    entry = game_stats(stats, key)
    plays = entry.get("plays", 0)
    win_rate = (entry.get("wins", 0) / plays * 100) if plays else 0
    return [
        f"局数:   {colored(str(plays), C.WHITE)}",
        f"胜负平: {colored(str(entry.get('wins', 0)), C.GREEN)}/{colored(str(entry.get('losses', 0)), C.RED)}/{colored(str(entry.get('pushes', 0)), C.BLUE)}",
        f"胜率:   {colored(f'{win_rate:.1f}%', C.YELLOW)}",
        f"净收益: {colored('$' + str(entry.get('net', 0)), C.GREEN if entry.get('net', 0) >= 0 else C.RED)}",
        f"大赢:   {colored('$' + str(entry.get('biggest_win', 0)), C.CYAN)}",
        f"{special_label}: {colored(str(entry.get('special', 0)), C.MAGENTA)}",
    ]


def show_stats(chips, stats, profile):
    """显示战绩统计"""
    clear()
    total_games = stats.get("wins", 0) + stats.get("losses", 0) + stats.get("pushes", 0)
    win_rate = (stats["wins"] / total_games * 100) if total_games > 0 else 0
    assets = total_assets(chips, profile)
    debt = total_debt(profile)
    holdings = market_value(profile)
    overview_box = box([
        f"总局数:   {colored(str(total_games), C.WHITE)}",
        f"胜负平:   {colored(str(stats.get('wins', 0)), C.GREEN)}/{colored(str(stats.get('losses', 0)), C.RED)}/{colored(str(stats.get('pushes', 0)), C.BLUE)}",
        f"总胜率:   {colored(f'{win_rate:.1f}%', C.YELLOW)}",
        f"总下注:   {colored('$' + str(stats.get('total_bet', 0)), C.CYAN)}",
        f"最大单赢: {colored('$' + str(stats.get('biggest_win', 0)), C.GREEN)}",
        f"历史条目: {colored(str(len(profile.get('history', []))), C.WHITE)}",
    ], width=34, title="总览", color=C.CYAN)
    fire_box = box(game_panel_lines(stats, "fire_station", "火烧洋油站", "Boss"), width=34, title="火烧洋油站", color=C.RED)
    bank_box = box([
        f"现金:     {colored(f'${chips}', C.GREEN if chips > 0 else C.RED)}",
        f"存款:     {colored('$' + str(profile.get('bank', 0)), C.CYAN)}",
        f"持仓:     {colored('$' + str(holdings), C.WHITE)}",
        f"负债:     {colored('$' + str(debt), C.RED if debt > 0 else C.DIM)}",
        f"净资产:   {colored('$' + str(assets), C.GREEN if assets > 0 else C.RED)}",
        f"资产峰值: {colored('$' + str(profile.get('career_high_assets', INITIAL_CHIPS)), C.MAGENTA)}",
        f"盈亏:     {colored(f'${assets - INITIAL_CHIPS}', C.GREEN if assets >= INITIAL_CHIPS else C.RED)}",
        "",
        f"存入/取出: {colored('$' + str(stats.get('bank_deposit_total', 0)), C.WHITE)}/{colored('$' + str(stats.get('bank_withdraw_total', 0)), C.WHITE)}",
        f"累计收息:  {colored('$' + str(stats.get('bank_interest_earned', 0)), C.GREEN)}",
        f"累计付息:  {colored('$' + str(stats.get('loan_interest_paid', 0)), C.RED)}",
        f"借还款:    {colored('$' + str(stats.get('loan_borrowed_total', 0)), C.YELLOW)}/{colored('$' + str(stats.get('loan_repaid_total', 0)), C.CYAN)}",
        f"补贴/天数: {colored(str(profile.get('government_aid_used', 0)), C.YELLOW)}/{colored(str(profile.get('bank_days_elapsed', 0)), C.WHITE)}",
        f"操作/导出: {colored(str(stats.get('operations_count', 0)), C.WHITE)}/{colored(str(profile.get('export_count', 0)), C.WHITE)}",
    ], width=38, title="银行与资产", color=C.YELLOW)
    asset_box_lines = [
        f"交易次数: {colored(str(stats.get('asset_trade_count', 0)), C.WHITE)}",
        f"买入/卖出: {colored('$' + str(stats.get('asset_buy_total', 0)), C.YELLOW)}/{colored('$' + str(stats.get('asset_sell_total', 0)), C.CYAN)}",
        f"已实现:   {colored('$' + str(stats.get('asset_realized_profit', 0)), C.GREEN if stats.get('asset_realized_profit', 0) >= 0 else C.RED)}",
        f"被动收入: {colored('$' + str(stats.get('asset_passive_income', 0)), C.CYAN)}",
        f"浮动盈亏: {colored('$' + str(total_unrealized_profit(profile)), C.GREEN if total_unrealized_profit(profile) >= 0 else C.RED)}",
        "",
    ]
    for asset in ASSET_MARKETS:
        info = asset_position_summary(profile, asset)
        asset_box_lines.append(f"{asset['name']}: {colored(str(info['shares']) + '份', C.WHITE)} / {colored('$' + str(info['market_value']), C.MAGENTA if info['market_value'] > 0 else C.DIM)}")
    asset_box = box(asset_box_lines, width=38, title="典当行与持仓", color=C.MAGENTA)
    system_box = box([
        f"Blackjack: {colored(str(stats.get('blackjacks', 0)), C.YELLOW)}",
        f"Boss 击败: {colored(str(stats.get('bosses_defeated', 0)), C.MAGENTA)}",
        f"历史条目: {colored(str(len(profile.get('history', []))), C.WHITE)}",
        f"导出次数: {colored(str(profile.get('export_count', 0)), C.WHITE)}",
        f"今日跑单: {colored('可接' if runner_available(profile) else '已用', C.CYAN if runner_available(profile) else C.DIM)}",
        f"结息进度: {colored(str(DAILY_OPERATION_COUNT - operation_progress(profile)), C.YELLOW)} 步",
        f"当前地点: {colored(location_label(profile.get('location', 'home')), C.MAGENTA)}",
    ], width=34, title="系统与进度", color=C.GREEN)
    print(render_box_columns([overview_box, fire_box], gap=2))
    print()
    print(render_box_columns([bank_box, system_box], gap=2))
    print()
    print(asset_box)
    print()
    print(render_box_columns([
        box(game_panel_lines(stats, "blackjack", "Blackjack", "BJ"), width=34, title="Blackjack", color=C.CYAN),
        box(game_panel_lines(stats, "craps", "Craps", "Point"), width=34, title="Craps", color=C.BLUE),
    ], gap=2))
    print()
    print(render_box_columns([
        box(game_panel_lines(stats, "slots", "Slots", "免旋"), width=34, title="Slots", color=C.MAGENTA),
        box(game_panel_lines(stats, "runner", "跑单", "大成"), width=34, title="地下跑单", color=C.YELLOW),
    ], gap=2))
    pause()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(colored("\n\n  下次再来！👋\n", C.YELLOW))
