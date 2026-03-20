#!/usr/bin/env python3
"""Leo's Casino - 终端小赌场"""

import random
import os
import time
import sys
import json
from datetime import datetime

# ============================================================
# 存档系统
# ============================================================
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves")
MAX_SLOTS = 5

def ensure_save_dir():
    os.makedirs(SAVE_DIR, exist_ok=True)

def save_path(slot):
    return os.path.join(SAVE_DIR, f"slot_{slot}.json")

def save_game(slot, data):
    """保存游戏到指定槽位"""
    ensure_save_dir()
    data["save_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        saves[i] = data
    return saves

def auto_save(slot, chips, stats):
    """自动存档"""
    data = {
        "chips": chips,
        "stats": stats,
    }
    save_game(slot, data)

def save_menu():
    """存档管理界面，返回 (chips, stats, active_slot) 或 None"""
    while True:
        clear()
        print(colored("\n  ── 存档管理 ──\n", C.CYAN))
        saves = list_saves()

        lines = []
        for i in range(1, MAX_SLOTS + 1):
            data = saves[i]
            if data:
                chip_str = f"${data['chips']}"
                t = data.get('save_time', '???')
                wins = data.get('stats', {}).get('wins', 0)
                losses = data.get('stats', {}).get('losses', 0)
                lines.append(
                    colored(str(i), C.GREEN) +
                    f"  {colored(chip_str, C.YELLOW)}  胜{wins}/负{losses}  {colored(t, C.DIM)}"
                )
            else:
                lines.append(colored(str(i), C.GREEN) + colored("  ── 空槽位 ──", C.DIM))
        lines.append("")
        lines.append(colored("N", C.GREEN) + "  新游戏")
        lines.append(colored("D", C.RED) + "  删除存档")
        lines.append(colored("0", C.RED) + "  退出游戏")

        print(box(lines, width=52, title="存档", color=C.CYAN))
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
            stats = {"wins": 0, "losses": 0, "pushes": 0,
                     "blackjacks": 0, "total_bet": 0, "biggest_win": 0}
            auto_save(slot, 1000, stats)
            print(colored(f"  新游戏已创建在槽位 {slot}！", C.GREEN))
            pause()
            return (1000, stats, slot)
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
                stats = data.get("stats", {"wins": 0, "losses": 0, "pushes": 0,
                                            "blackjacks": 0, "total_bet": 0, "biggest_win": 0})
                return (data["chips"], stats, slot)
            else:
                # 空槽位，新建
                stats = {"wins": 0, "losses": 0, "pushes": 0,
                         "blackjacks": 0, "total_bet": 0, "biggest_win": 0}
                auto_save(slot, 1000, stats)
                print(colored(f"  新游戏已创建在槽位 {slot}！", C.GREEN))
                pause()
                return (1000, stats, slot)

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

def header(chips, slot=None, stats=None):
    """顶部状态栏"""
    chip_str = f"${chips}"
    if chips >= 1000:
        chip_color = C.GREEN
    elif chips >= 300:
        chip_color = C.YELLOW
    else:
        chip_color = C.RED
    lines = [
        bold(colored("♠ ♥ ♣ ♦  Leo's Casino  ♦ ♣ ♥ ♠", C.YELLOW)),
        "",
        f"  筹码: {colored(chip_str, chip_color)}",
    ]
    if slot is not None:
        slot_info = f"  存档: 槽位 {slot}"
        if stats:
            slot_info += f"  W{stats.get('wins',0)}/L{stats.get('losses',0)}"
        lines.append(colored(slot_info, C.DIM))
    print(box(lines, width=44, color=C.YELLOW))

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

# ============================================================
# Blackjack (21点)
# ============================================================
def blackjack(chips, slot=None, stats=None):
    while True:
        clear()
        header(chips, slot, stats)
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

        deck = Deck()
        player = [deck.deal(), deck.deal()]
        dealer = [deck.deal(), deck.deal()]
        dealer[1].hidden = True

        # 游戏循环
        doubled = False
        while True:
            clear()
            header(chips, slot, stats)
            print(colored(f"\n  ── Blackjack ── 下注: ${bet} ──\n", C.CYAN))
            render_cards(dealer, f"庄家 [{hand_value(dealer)}]")
            print()
            render_cards(player, f"你 [{hand_value(player)}]")

            pv = hand_value(player)
            if pv == 21 and len(player) == 2:
                print(colored("\n  ★ Blackjack！ ★", C.YELLOW))
                break
            if pv > 21:
                print(colored("\n  爆了！", C.RED))
                break

            options = f"  [H] 要牌  [S] 停牌"
            if len(player) == 2 and chips >= bet * 2:
                options += "  [D] 加倍"
            print(f"\n{options}")
            action = input(colored("  > ", C.YELLOW)).strip().upper()

            if action == 'H':
                player.append(deck.deal())
            elif action == 'D' and len(player) == 2 and chips >= bet * 2:
                bet *= 2
                doubled = True
                player.append(deck.deal())
                break
            elif action == 'S':
                break
            else:
                continue

        # 庄家亮牌
        dealer[1].hidden = False

        pv = hand_value(player)
        if pv <= 21:
            while hand_value(dealer) < 17:
                dealer.append(deck.deal())

        dv = hand_value(dealer)

        # 结算
        clear()
        header(chips, slot, stats)
        print(colored(f"\n  ── 结算 ── 下注: ${bet} ──\n", C.CYAN))
        render_cards(dealer, f"庄家 [{dv}]")
        print()
        render_cards(player, f"你 [{pv}]")

        if pv > 21:
            result = "LOSE"
        elif pv == 21 and len(player) == 2:
            result = "BLACKJACK"
        elif dv > 21:
            result = "WIN"
        elif pv > dv:
            result = "WIN"
        elif pv == dv:
            result = "PUSH"
        else:
            result = "LOSE"

        if result == "BLACKJACK":
            winnings = int(bet * 1.5)
            chips += winnings
            if stats:
                stats["wins"] += 1
                stats["blackjacks"] += 1
                stats["total_bet"] += bet
                stats["biggest_win"] = max(stats["biggest_win"], winnings)
            print(colored(f"\n  ★ BLACKJACK! +${winnings} ★", C.YELLOW))
        elif result == "WIN":
            chips += bet
            if stats:
                stats["wins"] += 1
                stats["total_bet"] += bet
                stats["biggest_win"] = max(stats["biggest_win"], bet)
            print(colored(f"\n  ✓ 你赢了！+${bet}", C.GREEN))
        elif result == "PUSH":
            if stats:
                stats["pushes"] += 1
            print(colored(f"\n  ─ 平局，退回筹码", C.BLUE))
        else:
            chips -= bet
            if stats:
                stats["losses"] += 1
                stats["total_bet"] += bet
            print(colored(f"\n  ✗ 你输了... -${bet}", C.RED))

        if slot is not None and stats is not None:
            auto_save(slot, chips, stats)
            print(colored("  [自动存档]", C.DIM))

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

def craps(chips, slot=None, stats=None):
    while True:
        clear()
        header(chips, slot, stats)
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

        # Come Out Roll
        print(colored("\n  ── Come Out Roll ──", C.CYAN))
        roll_animation()
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        render_dice(d1, d2)
        print(colored(f"    总点数: {total}", C.BOLD))

        if total in (7, 11):
            chips += bet
            if stats:
                stats["wins"] += 1
                stats["total_bet"] += bet
                stats["biggest_win"] = max(stats["biggest_win"], bet)
            print(colored(f"\n  ✓ 自然赢！+${bet}", C.GREEN))
            if slot is not None and stats is not None:
                auto_save(slot, chips, stats)
                print(colored("  [自动存档]", C.DIM))
            pause()
            continue
        elif total in (2, 3, 12):
            chips -= bet
            if stats:
                stats["losses"] += 1
                stats["total_bet"] += bet
            print(colored(f"\n  ✗ Craps！输了 -${bet}", C.RED))
            if slot is not None and stats is not None:
                auto_save(slot, chips, stats)
                print(colored("  [自动存档]", C.DIM))
            pause()
            continue

        point = total
        print(colored(f"\n  Point 设为 {point}，继续掷！", C.YELLOW))
        pause("按 Enter 继续掷骰...")

        # Point Phase
        while True:
            roll_animation()
            d1, d2 = random.randint(1, 6), random.randint(1, 6)
            total = d1 + d2
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
                break
            else:
                print(colored("    继续掷...", C.DIM))
                pause("按 Enter 继续掷骰...")

        if slot is not None and stats is not None:
            auto_save(slot, chips, stats)
            print(colored("  [自动存档]", C.DIM))
        pause()
    return chips
# ============================================================
SLOT_SYMBOLS = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣', '🔔']
SLOT_WEIGHTS = [30,   25,   20,   15,    5,    3,    2]   # 权重

SLOT_PAYOUTS = {
    '7️⃣':  20,
    '💎':  15,
    '🔔':  12,
    '🍇':   8,
    '🍊':   5,
    '🍋':   3,
    '🍒':   2,
}

def weighted_choice():
    return random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=1)[0]

def slots(chips, slot=None, stats=None):
    while True:
        clear()
        header(chips, slot, stats)
        print(colored("\n  ── Slots 老虎机 ──\n", C.MAGENTA))

        if chips <= 0:
            print(colored("  口袋空空！先去别的桌赢点回来。", C.RED))
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

        # 转动动画
        print()
        for i in range(8):
            s1 = random.choice(SLOT_SYMBOLS)
            s2 = random.choice(SLOT_SYMBOLS)
            s3 = random.choice(SLOT_SYMBOLS)
            sys.stdout.write(f"\r    ┃ {s1} ┃ {s2} ┃ {s3} ┃  ")
            sys.stdout.flush()
            time.sleep(0.1 + i * 0.04)

        # 最终结果
        r1, r2, r3 = weighted_choice(), weighted_choice(), weighted_choice()
        print(f"\r    ┏━━━┳━━━┳━━━┓")
        print(f"    ┃ {r1} ┃ {r2} ┃ {r3} ┃")
        print(f"    ┗━━━┻━━━┻━━━┛")

        if r1 == r2 == r3:
            mult = SLOT_PAYOUTS.get(r1, 2)
            winnings = bet * mult
            chips += winnings
            if stats:
                stats["wins"] += 1
                stats["total_bet"] += bet
                stats["biggest_win"] = max(stats["biggest_win"], winnings)
            if r1 in ('7️⃣', '💎'):
                print(colored(f"\n  ★★★ JACKPOT! {r1}x3 ★★★", C.YELLOW))
            else:
                print(colored(f"\n  ★ 三连！{r1}x3 ★", C.GREEN))
            print(colored(f"  +${winnings} ({mult}x)", C.GREEN))
        elif r1 == r2 or r2 == r3 or r1 == r3:
            winnings = bet
            chips += winnings
            if stats:
                stats["wins"] += 1
                stats["total_bet"] += bet
                stats["biggest_win"] = max(stats["biggest_win"], winnings)
            print(colored(f"\n  ✓ 两连！+${winnings}", C.GREEN))
        else:
            chips -= bet
            if stats:
                stats["losses"] += 1
                stats["total_bet"] += bet
            print(colored(f"\n  ✗ 没中... -${bet}", C.RED))

        if slot is not None and stats is not None:
            auto_save(slot, chips, stats)
            print(colored("  [自动存档]", C.DIM))

        pause()
    return chips

# ============================================================
# 火烧洋油站 (Single Card Showdown)
# ============================================================
RANK_ORDER = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
              '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}

class FireStationAI:
    """有深度的 AI 对手"""
    def __init__(self):
        # 玩家画像追踪
        self.player_profile = {
            "total_hands": 0,
            "fold_count": 0,       # 玩家弃牌次数
            "bluff_caught": 0,     # 被抓到偷鸡
            "raise_freq": [],      # 每手加注次数记录
            "showdown_cards": [],   # 摊牌时玩家的牌力
        }
        self.personality = random.choice(["tight", "loose", "tricky"])
        self.mood = 0.5  # 0=保守 1=激进, 动态调整

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
                mult = random.uniform(2.0, 4.0)  # 大偷鸡
            else:
                mult = 1.0

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
        if player_card is not None:
            self.player_profile["showdown_cards"].append(self.card_strength(player_card))


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


def fire_station(chips, slot=None, stats=None):
    """火烧洋油站主逻辑"""
    ai = FireStationAI()
    ai_chips = 1000  # AI 初始筹码

    while True:
        clear()
        header(chips, slot, stats)
        print(colored("\n  ── 火烧洋油站 ──\n", C.RED))

        if chips <= 0:
            print(colored("  你已经破产了！回去攒点钱再来。", C.RED))
            pause()
            return chips

        if ai_chips <= 0:
            print(colored("  庄家被你打空了！换一个庄家上场...", C.GREEN))
            ai_chips = 1000
            ai.__init__()
            pause()

        # 显示双方筹码
        print(f"  你的筹码: {colored('$' + str(chips), C.GREEN)}")
        print(f"  庄家筹码: {colored('$' + str(ai_chips), C.MAGENTA)}")

        # AI 性格提示
        personality_hints = {
            "tight": "沉稳",
            "loose": "豪放",
            "tricky": "诡诈",
        }
        print(colored(f"  庄家风格: {personality_hints[ai.personality]}", C.DIM))
        print()

        # 选底注
        tiers = [5, 10, 50]
        available = [t for t in tiers if t <= chips and t <= ai_chips]
        if not available:
            print(colored("  筹码不够最低底注了！", C.RED))
            pause()
            return chips

        print("  选择底注:")
        for idx, t in enumerate(available):
            print(f"    {colored(str(idx + 1), C.GREEN)}  ${t}")
        print(f"    {colored('0', C.RED)}  返回大厅")

        try:
            tc = input(colored("  > ", C.YELLOW)).strip()
        except (EOFError, KeyboardInterrupt):
            return chips
        if tc == '0':
            return chips
        try:
            ti = int(tc) - 1
            if ti < 0 or ti >= len(available):
                continue
            base_bet = available[ti]
        except ValueError:
            continue

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
        last_raiser = None  # 记录最后加注方
        game_over = False

        # 玩家先看牌
        clear()
        header(chips, slot, stats)
        print(colored(f"\n  ── 火烧洋油站 ── 底注: ${base_bet} ──\n", C.RED))
        print(f"  底池: {colored('$' + str(pot), C.YELLOW)}")
        print()
        render_single_card(player_card, "你的牌:")
        print()
        render_single_card(ai_card, "庄家的牌:", hidden=True)
        print()

        # 玩家先行动
        turn = "player"  # player / ai
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
                    options.append("[C] 开牌" if last_raiser is None else "[C] 跟注开牌")
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
                    last_raiser = "player"
                    turn = "ai"

                    # 刷新画面
                    clear()
                    header(chips, slot, stats)
                    print(colored(f"\n  ── 火烧洋油站 ── 底注: ${base_bet} ──\n", C.RED))
                    print(f"  底池: {colored('$' + str(pot), C.YELLOW)}")
                    print()
                    render_single_card(player_card, "你的牌:")
                    print()
                    render_single_card(ai_card, "庄家的牌:", hidden=True)

                    print(colored(f"\n  你加注 ${raise_amt}！等待庄家决定...", C.CYAN))
                    pause()

                elif action == 'C' and (last_raiser == "ai" or last_raiser is None):
                    # 跟注/开牌
                    if last_raiser == "ai":
                        chips -= current_bet
                        pot += current_bet
                    game_over = True
                    winner = "showdown"

                elif action == 'F':
                    game_over = True
                    winner = "ai_fold"  # 玩家弃牌

                else:
                    round_num -= 1
                    continue

            else:
                # AI 回合
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
                    header(chips, slot, stats)
                    print(colored(f"\n  ── 火烧洋油站 ── 底注: ${base_bet} ──\n", C.RED))
                    print(f"  底池: {colored('$' + str(pot), C.YELLOW)}")
                    print()
                    render_single_card(player_card, "你的牌:")
                    print()
                    render_single_card(ai_card, "庄家的牌:", hidden=True)

                    print(colored(f"\n  庄家加注 ${raise_amt}！", C.MAGENTA))

                elif decision == "call" and (last_raiser == "player" or last_raiser is None):
                    if last_raiser == "player":
                        ai_chips -= current_bet
                        pot += current_bet
                    game_over = True
                    winner = "showdown"

                    print(colored("\n  庄家跟注！开牌！", C.MAGENTA))
                    time.sleep(0.8)

                elif decision == "fold":
                    game_over = True
                    winner = "player_fold"

                    print(colored("\n  庄家弃牌！", C.MAGENTA))
                    time.sleep(0.8)

                else:
                    # fallback: call if possible, else fold
                    if (last_raiser == "player" or last_raiser is None) and ai_chips >= current_bet:
                        if last_raiser == "player":
                            ai_chips -= current_bet
                            pot += current_bet
                        game_over = True
                        winner = "showdown"
                        print(colored("\n  庄家跟注！开牌！", C.MAGENTA))
                        time.sleep(0.8)
                    else:
                        game_over = True
                        winner = "player_fold"
                        print(colored("\n  庄家弃牌！", C.MAGENTA))
                        time.sleep(0.8)

        # === 结算 ===
        clear()
        header(chips, slot, stats)
        print(colored(f"\n  ── 结算 ── 底池: ${pot} ──\n", C.RED))

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
            # 玩家弃牌，底池归庄家
            print(colored("  你弃牌了。", C.RED))
            render_single_card(player_card, "你的牌:")
            print()
            render_single_card(ai_card, "庄家的牌:", hidden=True)
            ai_chips += pot
            print(colored(f"\n  庄家赢得底池 ${pot}", C.MAGENTA))
            ai.update_mood(True)
            ai.record_hand(True, player_raises)
            if stats:
                stats["losses"] += 1
                stats["total_bet"] += base_bet

        elif winner == "player_fold":
            chips += pot
            print(colored("  庄家弃牌！你不战而胜！", C.GREEN))
            render_single_card(player_card, "你的牌:")
            print()
            print(colored("  庄家的牌: [已弃]", C.DIM))
            print(colored(f"\n  你赢得底池 ${pot}", C.GREEN))
            ai.update_mood(False)
            ai.record_hand(False, player_raises)
            if stats:
                stats["wins"] += 1
                stats["total_bet"] += base_bet

        if slot is not None and stats is not None:
            auto_save(slot, chips, stats)
            print(colored("  [自动存档]", C.DIM))

        pause()
    return chips


# ============================================================
# 主菜单
# ============================================================
def main():
    # 存档选择
    result = save_menu()
    if result is None:
        print(colored("\n  再见！\n", C.YELLOW))
        return
    chips, stats, active_slot = result

    while True:
        clear()
        header(chips, active_slot, stats)
        print()
        menu = [
            colored("1", C.GREEN) + "  Blackjack (21点)",
            colored("2", C.GREEN) + "  Craps (骰子)",
            colored("3", C.GREEN) + "  Slots (老虎机)",
            colored("4", C.GREEN) + "  火烧洋油站",
            "",
            colored("S", C.CYAN) + "  战绩统计",
            colored("0", C.RED) + "  保存并离开",
        ]
        print(box(menu, width=36, title="游戏大厅", color=C.CYAN))

        if chips <= 0:
            print(colored("\n  你已经破产了...但这是虚拟赌场！", C.RED))
            print(colored("  输入 R 重新开始，带 $1000 回来", C.YELLOW))

        try:
            choice = input(colored("\n  选择 > ", C.YELLOW)).strip().upper()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == '1':
            chips = blackjack(chips, active_slot, stats)
        elif choice == '2':
            chips = craps(chips, active_slot, stats)
        elif choice == '3':
            chips = slots(chips, active_slot, stats)
        elif choice == '4':
            chips = fire_station(chips, active_slot, stats)
        elif choice == 'S':
            show_stats(chips, stats)
        elif choice == '0':
            auto_save(active_slot, chips, stats)
            clear()
            print(colored("\n  游戏已保存！感谢光临 Leo's Casino！", C.YELLOW))
            print(colored(f"  你带走了 ${chips} 筹码。\n", C.GREEN if chips > 1000 else C.RED))
            break
        elif choice == 'R' and chips <= 0:
            chips = 1000
            stats["wins"] = 0
            stats["losses"] = 0
            stats["pushes"] = 0
            stats["blackjacks"] = 0
            stats["total_bet"] = 0
            stats["biggest_win"] = 0
            auto_save(active_slot, chips, stats)
            print(colored("  重新发放 $1000！祝你好运！", C.GREEN))
            pause()


def show_stats(chips, stats):
    """显示战绩统计"""
    clear()
    total_games = stats.get("wins", 0) + stats.get("losses", 0) + stats.get("pushes", 0)
    win_rate = (stats["wins"] / total_games * 100) if total_games > 0 else 0

    lines = [
        f"总局数:     {colored(str(total_games), C.WHITE)}",
        f"胜:         {colored(str(stats.get('wins', 0)), C.GREEN)}",
        f"负:         {colored(str(stats.get('losses', 0)), C.RED)}",
        f"平:         {colored(str(stats.get('pushes', 0)), C.BLUE)}",
        f"胜率:       {colored(f'{win_rate:.1f}%', C.YELLOW)}",
        "",
        f"Blackjack:  {colored(str(stats.get('blackjacks', 0)), C.YELLOW)}",
        f"总下注:     {colored('$' + str(stats.get('total_bet', 0)), C.CYAN)}",
        f"最大单笔赢: {colored('$' + str(stats.get('biggest_win', 0)), C.GREEN)}",
        "",
        f"当前筹码:   {colored(f'${chips}', C.GREEN if chips >= 1000 else C.RED)}",
        f"盈亏:       {colored(f'${chips - 1000}', C.GREEN if chips >= 1000 else C.RED)}",
    ]
    print(box(lines, width=42, title="战绩统计", color=C.MAGENTA))
    pause()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(colored("\n\n  下次再来！👋\n", C.YELLOW))
