"""CLI entrypoint for Fire Station CFR training."""

from __future__ import annotations

import argparse
from typing import Dict, List, Tuple

from .cfr import ACTION_GUIDE, CFRTrainer, CFRTrainerConfig


PRESET_DEFAULTS: Dict[str, Dict[str, object]] = {
    "quick": {
        "iterations": 24,
        "checkpoint_interval": 6,
        "hands_per_eval": 16,
        "validation_hands": 24,
        "eval_repeats": 1,
        "validation_repeats": 1,
        "bet_set": "10",
        "validation_bet_set": "10",
        "stack_set": "1000",
        "max_round_depth": 7,
    },
    "balanced": {
        "iterations": 60,
        "checkpoint_interval": 10,
        "hands_per_eval": 36,
        "validation_hands": 60,
        "eval_repeats": 2,
        "validation_repeats": 2,
        "bet_set": "10,25",
        "validation_bet_set": "10,25",
        "stack_set": "800,1000,1400",
        "max_round_depth": 8,
    },
    "robust": {
        "iterations": 140,
        "checkpoint_interval": 14,
        "hands_per_eval": 64,
        "validation_hands": 96,
        "eval_repeats": 2,
        "validation_repeats": 2,
        "bet_set": "5,10,25",
        "validation_bet_set": "5,10,25,50",
        "stack_set": "700,1000,1500",
        "max_round_depth": 9,
    },
}


def ascii_bar(value: float, low: float, high: float, width: int = 28) -> str:
    if high <= low:
        return "#" * (width // 2)
    ratio = (value - low) / (high - low)
    ratio = min(1.0, max(0.0, ratio))
    filled = int(round(ratio * width))
    return "#" * filled + "-" * (width - filled)


def parse_int_tuple(text: str) -> Tuple[int, ...]:
    values = []
    for item in str(text).split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item))
    if not values:
        raise ValueError("parameter set cannot be empty")
    return tuple(dict.fromkeys(values))


def build_parser() -> argparse.ArgumentParser:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--preset", choices=sorted(PRESET_DEFAULTS), default="balanced")
    known, _ = pre_parser.parse_known_args()
    defaults = PRESET_DEFAULTS.get(known.preset, PRESET_DEFAULTS["balanced"])

    parser = argparse.ArgumentParser(description="训练火烧洋油站 CFR / regret matching AI")
    parser.set_defaults(**defaults)
    parser.add_argument("--preset", choices=sorted(PRESET_DEFAULTS), default=known.preset)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--checkpoint-interval", type=int)
    parser.add_argument("--hands-per-eval", type=int)
    parser.add_argument("--validation-hands", type=int)
    parser.add_argument("--eval-repeats", type=int)
    parser.add_argument("--validation-repeats", type=int)
    parser.add_argument("--bet-set", type=str)
    parser.add_argument("--validation-bet-set", type=str)
    parser.add_argument("--stack-set", type=str)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-round-depth", type=int)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--output-dir", type=str, default="fire_station_ai/runs")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    return parser


def print_header(config: CFRTrainerConfig, preset: str) -> None:
    print("火烧洋油站 CFR / Regret Matching 训练器")
    print("=" * 72)
    print(f"预设模式         : {preset}")
    print(f"训练轮数         : {config.iterations}")
    print(f"检查点间隔       : {config.checkpoint_interval}")
    print(f"评估手数         : {config.hands_per_eval}")
    print(f"验证手数         : {config.validation_hands}")
    print(f"训练重复次数     : {config.eval_repeats}")
    print(f"验证重复次数     : {config.validation_repeats}")
    print(f"训练底注集合     : {list(config.bet_set)}")
    print(f"验证底注集合     : {list(config.validation_bet_set)}")
    print(f"训练筹码集合     : {list(config.stack_set)}")
    print(f"训练深度截断     : {config.max_round_depth}")
    print(f"评估并行进程     : {'自动' if config.parallel_eval_workers <= 0 else config.parallel_eval_workers}")
    print(f"随机种子         : {config.seed}")
    print()
    print("怎么读这些数字：")
    print("- `training_score` 看当前平均策略打训练池是否赚钱。")
    print("- `validation_win_rate` 更适合直观看强弱。")
    print("- `info_set_count` 表示训练过程中累计见过多少种局面。")
    print("- `strategy_table_size` 表示当前平均策略表里真正留下来的信息集数量。")
    print()


def print_history(history: List[dict]) -> None:
    print("训练曲线")
    print("-" * 72)
    if not history:
        print("没有历史记录")
        return

    score_values = [item["training_score"] for item in history]
    score_low = min(score_values)
    score_high = max(score_values)

    for item in history:
        iteration = item["iteration"]
        score = item["training_score"]
        win_rate = item["validation_win_rate"]
        score_bar = ascii_bar(score, score_low, score_high if score_high > score_low else score_low + 1e-6)
        win_bar = ascii_bar(win_rate, 0.0, 1.0)
        marker = "*" if item.get("champion_changed") else " "
        print(
            f"第 {iteration:04d} 轮{marker}  训练分 {score:>7.3f} |{score_bar}|  "
            f"验证胜率 {win_rate * 100:>5.1f}% |{win_bar}|  "
            f"信息集 {item['info_set_count']:<5} 表大小 {item['strategy_table_size']}"
        )
    print()
    print("* 代表这一轮刷新了最佳检查点")
    print()


def print_takeaways(summary: dict) -> None:
    validation = summary["validation"]
    print("结果摘要")
    print("-" * 72)
    print(f"冠军代号         : {summary.get('model_name', '未命名模型')}")
    print(f"算法             : {summary['algorithm']}")
    print(f"最佳检查点       : 第 {summary['best_checkpoint_iteration']} 轮")
    print(f"最佳训练分数     : {summary['best_training_score']:.3f} 筹码/手")
    print(f"训练胜率         : {summary['best_training_win_rate'] * 100:.1f}%")
    print(f"验证分数         : {validation['score_per_scheduled_hand']:.3f} 筹码/手")
    print(f"验证胜率         : {validation['win_rate'] * 100:.1f}%")
    print(f"验证战绩         : {validation['wins']}W {validation['losses']}L {validation['ties']}T")
    print(f"最佳信息集数     : {summary['best_checkpoint_info_set_count']}")
    print(f"策略表大小       : {summary['average_strategy_table_size']}")
    print(f"最终信息集数     : {summary['final_info_set_count']}")
    if "run_dir" in summary:
        print(f"结果目录         : {summary['run_dir']}")
    print()
    print("训练机制说明：")
    print("- 每轮先抽一手牌，再用 regret matching 在整棵下注树里回传后悔值。")
    print("- 评估时会覆盖整个 `stack_set`，不再每次随机只抽一个筹码档位。")
    print("- 最佳检查点优先比较验证分，再比较验证胜率和训练分，减少误选。")
    print("- 训练分支使用轻量状态克隆，避免反复 `deepcopy` 带来的额外开销。")
    print()


def print_breakdown(breakdown: dict) -> None:
    print("当前最佳策略对训练池的表现")
    print("-" * 72)
    for name, stats in breakdown.items():
        score = stats["score_per_scheduled_hand"]
        hands = stats["hands_played"]
        wins = stats["wins"]
        losses = stats["losses"]
        ties = stats["ties"]
        bar = ascii_bar(score, -20.0, 20.0)
        print(
            f"{name:18} 分数 {score:>7.3f} |{bar}|  "
            f"战绩 {wins}W {losses}L {ties}T / {hands} 手"
        )
    print()


def print_auto_commentary(summary: dict) -> None:
    print("自动中文解读")
    print("-" * 72)
    for line in summary.get("auto_commentary_zh", []):
        print(f"- {line}")
    print()


def print_action_guide() -> None:
    print("动作词典")
    print("-" * 72)
    for action_key, text in ACTION_GUIDE.items():
        print(f"- {action_key:16} {text}")
    print()


def print_tuning_tips() -> None:
    print("怎么调参数更容易出效果")
    print("-" * 72)
    print("- 想快速确认流程能跑：用 `--preset quick`。")
    print("- 想稳一点：用 `--preset balanced`。")
    print("- 想提高稳定性：增大 `--hands-per-eval`、`--validation-hands`、`--eval-repeats`。")
    print("- 想更快跑完：调低 `--iterations` 或把 `--workers` 交给自动并行。")
    print("- 想让表格覆盖更多局面：加大 `--iterations`。")
    print("- 想减少只会打一种筹码节奏：扩展 `--stack-set`。")
    print("- 想减少只会打一种底注：扩展 `--bet-set` 和 `--validation-bet-set`。")
    print()


def parse_args() -> tuple[CFRTrainerConfig, str]:
    parser = build_parser()
    args = parser.parse_args()
    config = CFRTrainerConfig(
        iterations=args.iterations,
        checkpoint_interval=args.checkpoint_interval,
        hands_per_eval=args.hands_per_eval,
        validation_hands=args.validation_hands,
        eval_repeats=args.eval_repeats,
        validation_repeats=args.validation_repeats,
        bet_set=parse_int_tuple(args.bet_set),
        validation_bet_set=parse_int_tuple(args.validation_bet_set),
        stack_set=parse_int_tuple(args.stack_set),
        max_round_depth=args.max_round_depth,
        parallel_eval_workers=args.workers,
        seed=args.seed,
        output_dir=args.output_dir,
        save_artifacts=not args.no_save,
        show_progress=not args.no_progress,
    )
    return config, args.preset


def main() -> None:
    config, preset = parse_args()
    print_header(config, preset)
    trainer = CFRTrainer(config)
    summary = trainer.train()
    print_history(summary["history"])
    print_takeaways(summary)
    print_auto_commentary(summary)
    print_breakdown(summary["best_training_breakdown"])
    print_action_guide()
    print_tuning_tips()


if __name__ == "__main__":
    main()
